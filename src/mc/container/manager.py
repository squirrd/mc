"""Container lifecycle management and orchestration."""

import os
from datetime import datetime, timezone
from typing import Any

from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


class ContainerManager:
    """Orchestrate container lifecycle operations with state tracking.

    Manages creation, listing, stopping, and deletion of mc-managed containers,
    integrating Podman operations with SQLite state management and reconciliation.
    """

    def __init__(self, podman_client: PodmanClient, state_db: StateDatabase):
        """Initialize container manager.

        Args:
            podman_client: Podman client wrapper for container operations
            state_db: State database for container metadata persistence
        """
        self.podman = podman_client
        self.state = state_db

    def create(
        self, case_number: str, workspace_path: str, customer_name: str = "Unknown"
    ) -> Any:
        """Create container for case with workspace mounted at /case.

        Implements auto-restart pattern: if container exists but stopped, restarts
        instead of creating duplicate. Workspace directory created if missing.

        Args:
            case_number: Case number (e.g., "12345678")
            workspace_path: Host path to mount as /case (e.g., "/Users/user/Cases/12345678")
            customer_name: Customer name for container label (optional, defaults to "Unknown")

        Returns:
            podman.Container instance (running container)

        Raises:
            RuntimeError: If container creation or startup fails
        """
        # 1. Reconcile state to detect external deletions
        self._reconcile()

        # 2. Check if container already exists in state
        existing = self.state.get_container(case_number)
        if existing:
            try:
                # Get container from Podman
                container = self.podman.client.containers.get(existing.container_id)

                # Auto-restart if stopped/exited
                if container.status in ("stopped", "exited"):
                    print(f"Restarting container for case {case_number}...")
                    container.start()  # type: ignore[no-untyped-call]

                return container

            except Exception as e:
                # Container in state but not in Podman (reconciliation race condition)
                # Fall through to create new container
                print(
                    f"Warning: Container {existing.container_id} in state but not found in Podman, "
                    f"creating new container. Error: {e}"
                )
                self.state.delete_container(case_number)

        # 3. Create workspace directory if missing (prevents mount failures)
        os.makedirs(workspace_path, exist_ok=True)

        # 4. Create new container via Podman API
        try:
            container = self.podman.client.containers.create(
                image="registry.access.redhat.com/ubi9/ubi:latest",
                name=f"mc-{case_number}",
                command=["/bin/bash", "-l"],
                detach=True,
                labels={
                    "mc.managed": "true",
                    "mc.case_number": case_number,
                    "mc.customer": customer_name,
                },
                volumes={
                    workspace_path: {"bind": "/case", "mode": "rw"}
                },
                userns_mode="keep-id",  # Critical for rootless volume permissions
                tty=True,
                stdin_open=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create container for case {case_number}: {e}"
            ) from e

        # 5. Start container
        try:
            container.start()  # type: ignore[no-untyped-call]
        except Exception as e:
            raise RuntimeError(
                f"Failed to start container for case {case_number}: {e}"
            ) from e

        # 6. Record in state database
        try:
            self.state.add_container(case_number, container.id, workspace_path)  # type: ignore[attr-defined]
        except Exception as e:
            # Clean up container if state persistence fails
            try:
                container.stop(timeout=2)  # type: ignore[no-untyped-call]
                container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass
            raise RuntimeError(
                f"Failed to record container state for case {case_number}: {e}"
            ) from e

        return container

    def _reconcile(self) -> None:
        """Reconcile state with Podman reality.

        Detects containers that were externally deleted (e.g., via 'podman rm')
        and removes their orphaned state entries. Called before operations to
        ensure state database reflects current Podman state.
        """
        try:
            # Get all mc-managed containers from Podman
            containers = self.podman.client.containers.list(
                all=True,  # Include stopped
                filters={"label": "mc.managed=true"}
            )
            podman_ids = {c.id for c in containers}

            # Reconcile state database
            self.state.reconcile(podman_ids)
        except Exception as e:
            # Reconciliation failures are non-fatal - log and continue
            print(f"Warning: Failed to reconcile container state: {e}")

    def _calculate_uptime(self, started_at: str) -> str:
        """Calculate human-readable uptime from ISO timestamp.

        Args:
            started_at: ISO 8601 timestamp (e.g., "2026-01-26T12:34:56.789Z")

        Returns:
            Human-readable duration (e.g., "2h 34m", "5d 3h", "45s")
        """
        started = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        delta = now - started

        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"

    def list(self) -> list[dict[str, Any]]:
        """List all mc-managed containers with status and metadata.

        Reconciles state before listing to ensure accuracy. Queries Podman for
        all mc-managed containers, enriches with metadata from state database,
        and calculates uptime for running containers.

        Returns:
            List of container info dictionaries with keys:
            - case_number: str - Salesforce case number
            - status: str - Container status (running, stopped, exited, etc.)
            - customer: str - Customer name from label or "Unknown"
            - container_id: str - Short container ID
            - workspace_path: str - Host workspace path from state database
            - created_at: str - Formatted timestamp
            - uptime: str - Human-readable uptime (if running)

        Raises:
            RuntimeError: If Podman connection fails
        """
        # Reconcile state before listing
        self._reconcile()

        # Query Podman for all mc-managed containers
        containers = self.podman.client.containers.list(
            all=True,  # Include stopped
            filters={"label": "mc.managed=true"}
        )

        # Build container info list
        container_list: list[dict[str, Any]] = []

        for container in containers:
            # Extract case number from label
            case_number = container.labels.get("mc.case_number", "")
            if not case_number:
                # Skip containers without case number (shouldn't happen)
                continue

            # Get status and customer from container
            status = container.status
            customer = container.labels.get("mc.customer", "Unknown")

            # Get metadata from state database
            metadata = self.state.get_container(case_number)

            # Extract workspace path from metadata
            workspace_path = metadata.workspace_path if metadata else "N/A"

            # Format created_at timestamp
            if metadata:
                created_timestamp = datetime.fromtimestamp(
                    metadata.created_at,
                    tz=timezone.utc
                )
                created_at = created_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_at = "Unknown"

            # Calculate uptime if running
            uptime = ""
            if status == "running":
                started_at = container.attrs.get("State", {}).get("StartedAt", "")
                if started_at:
                    uptime = self._calculate_uptime(started_at)

            # Build container info dict
            container_info = {
                "case_number": case_number,
                "status": status,
                "customer": customer,
                "container_id": container.short_id,
                "workspace_path": workspace_path,
                "created_at": created_at,
                "uptime": uptime,
            }

            container_list.append(container_info)

        # Sort by created_at (newest first)
        # Use metadata.created_at for sorting if available
        def sort_key(info: dict[str, Any]) -> int:
            case_num = info["case_number"]
            metadata = self.state.get_container(case_num)
            return metadata.created_at if metadata else 0

        container_list.sort(key=sort_key, reverse=True)

        return container_list
