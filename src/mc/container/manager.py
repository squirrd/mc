"""Container lifecycle management and orchestration."""

from __future__ import annotations

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

                # Reload container to ensure attrs is properly populated
                try:
                    container.reload()  # type: ignore[no-untyped-call]
                except Exception:
                    pass

                # Get status with defensive handling
                try:
                    status = container.status
                except (TypeError, KeyError, AttributeError):
                    if isinstance(container.attrs, dict):
                        status = container.attrs.get("State", {}).get("Status", "unknown")
                    else:
                        status = "unknown"

                # Auto-restart if stopped/exited
                if status in ("stopped", "exited"):
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

        # 4. Verify mc-rhel10:latest image exists
        try:
            self.podman.client.images.get("mc-rhel10:latest")
        except Exception as e:
            # Distinguish between connection failures and missing images
            error_str = str(e).lower()
            if "connection" in error_str or "socket" in error_str or "scheme" in error_str:
                # Connection failure - can't reach Podman
                raise RuntimeError(
                    f"Failed to connect to Podman: {e}\n"
                    f"Unable to verify image mc-rhel10:latest exists. "
                    f"Check that Podman is running and accessible."
                ) from e
            else:
                # Image genuinely not found
                raise RuntimeError(
                    f"Image mc-rhel10:latest not found. "
                    f"Run 'podman build -t mc-rhel10:latest -f container/Containerfile .' first. "
                    f"Error: {e}"
                ) from e

        # 5. Create new container via Podman API
        try:
            container = self.podman.client.containers.create(
                image="mc-rhel10:latest",
                name=f"mc-{case_number}",
                command=["/bin/bash", "-c", "tail -f /dev/null"],
                detach=True,
                labels={
                    "mc.managed": "true",
                    "mc.case_number": case_number,
                    "mc.customer": customer_name,
                },
                environment={
                    "CASE_NUMBER": str(case_number),
                    "CUSTOMER_NAME": customer_name,
                    "WORKSPACE_PATH": "/case",
                    "MC_RUNTIME_MODE": "agent",
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

        # 6. Start container
        try:
            container.start()  # type: ignore[no-untyped-call]
        except Exception as e:
            raise RuntimeError(
                f"Failed to start container for case {case_number}: {e}"
            ) from e

        # 7. Record in state database
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

            # Reload container to ensure attrs is properly populated
            # (workaround for podman-py versions where attrs may be incomplete)
            try:
                container.reload()  # type: ignore[no-untyped-call]
            except Exception:
                # If reload fails, continue with existing data
                pass

            # Get status and customer from container
            # Defensive: handle case where container.status might fail due to attrs issues
            try:
                status = container.status
            except (TypeError, KeyError, AttributeError):
                # Fallback: try to get status from attrs directly, or use "unknown"
                if isinstance(container.attrs, dict):
                    status = container.attrs.get("State", {}).get("Status", "unknown")
                else:
                    status = "unknown"

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

    def stop(self, case_number: str, timeout: int = 10) -> bool:
        """Stop running container gracefully.

        Args:
            case_number: Case number
            timeout: Seconds to wait for graceful shutdown before SIGKILL (default: 10)

        Returns:
            True if container stopped, False if already stopped

        Raises:
            RuntimeError: If container not found or stop fails
        """
        # Get container metadata from state
        metadata = self.state.get_container(case_number)
        if not metadata:
            raise RuntimeError(f"No container found for case {case_number}")

        # Get container from Podman
        try:
            container = self.podman.client.containers.get(metadata.container_id)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get container for case {case_number}: {e}"
            ) from e

        # Reload container to ensure attrs is properly populated
        try:
            container.reload()  # type: ignore[no-untyped-call]
        except Exception:
            pass

        # Check if already stopped
        try:
            status = container.status
        except (TypeError, KeyError, AttributeError):
            if isinstance(container.attrs, dict):
                status = container.attrs.get("State", {}).get("Status", "unknown")
            else:
                status = "unknown"

        if status in ("stopped", "exited"):
            return False

        # Stop container gracefully
        try:
            container.stop(timeout=timeout)  # type: ignore[no-untyped-call]
            return True
        except Exception as e:
            raise RuntimeError(
                f"Failed to stop container for case {case_number}: {e}"
            ) from e

    def delete(self, case_number: str, remove_workspace: bool = False) -> None:
        """Delete container and clean up state.

        Workspace is PRESERVED by default (safety measure).

        Args:
            case_number: Case number
            remove_workspace: If True, also delete workspace directory (DANGEROUS, default: False)

        Raises:
            RuntimeError: If container not found or deletion fails
        """
        import shutil

        # Get container metadata from state
        metadata = self.state.get_container(case_number)
        if not metadata:
            raise RuntimeError(f"No container found for case {case_number}")

        # Get container from Podman (may be already deleted externally)
        try:
            container = self.podman.client.containers.get(metadata.container_id)

            # Reload container to ensure attrs is properly populated
            try:
                container.reload()  # type: ignore[no-untyped-call]
            except Exception:
                pass

            # Get status with defensive handling
            try:
                status = container.status
            except (TypeError, KeyError, AttributeError):
                if isinstance(container.attrs, dict):
                    status = container.attrs.get("State", {}).get("Status", "unknown")
                else:
                    status = "running"  # Assume running if unknown, will try to stop

            # Stop container if running
            if status not in ("stopped", "exited"):
                container.stop(timeout=10)  # type: ignore[no-untyped-call]

            # Remove container
            container.remove()  # type: ignore[no-untyped-call]

        except Exception as e:
            # Container might have been deleted externally - check if it's NotFound
            error_str = str(e).lower()
            if "not found" not in error_str and "no such container" not in error_str:
                raise RuntimeError(
                    f"Failed to delete container for case {case_number}: {e}"
                ) from e
            # If container not found, continue to clean up state

        # Delete from state database
        try:
            self.state.delete_container(case_number)
        except Exception as e:
            raise RuntimeError(
                f"Failed to delete container state for case {case_number}: {e}"
            ) from e

        # Delete workspace if requested
        if remove_workspace:
            try:
                if os.path.exists(metadata.workspace_path):
                    shutil.rmtree(metadata.workspace_path)
                    print(f"WARNING: Deleted workspace at {metadata.workspace_path}")
            except OSError as e:
                # Non-fatal - log warning but don't fail delete operation
                print(
                    f"Warning: Failed to delete workspace at {metadata.workspace_path}: {e}"
                )

        print(f"Deleted container for case {case_number}")

    def status(self, case_number: str) -> dict[str, Any]:
        """Get container status and metadata.

        Args:
            case_number: Case number

        Returns:
            Dictionary with keys:
            - status: str (running, stopped, exited, missing)
            - container_id: str | None
            - workspace_path: str | None
            - created_at: int | None (Unix timestamp)

        Raises:
            RuntimeError: If Podman query fails
        """
        # Get container metadata from state
        metadata = self.state.get_container(case_number)
        if not metadata:
            return {
                "status": "missing",
                "container_id": None,
                "workspace_path": None,
                "created_at": None,
            }

        # Try to get container from Podman
        try:
            container = self.podman.client.containers.get(metadata.container_id)

            # Reload container to ensure attrs is properly populated
            try:
                container.reload()  # type: ignore[no-untyped-call]
            except Exception:
                pass

            # Get status with defensive handling
            try:
                status = container.status
            except (TypeError, KeyError, AttributeError):
                if isinstance(container.attrs, dict):
                    status = container.attrs.get("State", {}).get("Status", "unknown")
                else:
                    status = "unknown"

            return {
                "status": status,
                "container_id": container.short_id,
                "workspace_path": metadata.workspace_path,
                "created_at": metadata.created_at,
            }
        except Exception as e:
            # Container in state but not in Podman - reconcile
            error_str = str(e).lower()
            if "not found" in error_str or "no such container" in error_str:
                self.state.delete_container(case_number)
                return {
                    "status": "missing",
                    "container_id": None,
                    "workspace_path": None,
                    "created_at": None,
                }
            raise RuntimeError(
                f"Failed to query container status for case {case_number}: {e}"
            ) from e

    def logs(self, case_number: str, tail: int = 50, follow: bool = False) -> str:
        """Get container logs.

        Args:
            case_number: Case number
            tail: Number of lines to show (default: 50)
            follow: If True, stream logs continuously (default: False)

        Returns:
            Log output as string

        Raises:
            RuntimeError: If container not found or logs retrieval fails
        """
        # Get container metadata from state
        metadata = self.state.get_container(case_number)
        if not metadata:
            raise RuntimeError(f"No container found for case {case_number}")

        # Get container from Podman
        try:
            container = self.podman.client.containers.get(metadata.container_id)
        except Exception as e:
            raise RuntimeError(
                f"Failed to get container for case {case_number}: {e}"
            ) from e

        # Get logs
        try:
            logs = container.logs(
                stdout=True,
                stderr=True,
                timestamps=True,
                tail=tail,
                follow=follow,
            )  # type: ignore[no-untyped-call]

            # Decode bytes to string if necessary
            if isinstance(logs, bytes):
                return logs.decode("utf-8")
            return logs

        except Exception as e:
            raise RuntimeError(
                f"Failed to retrieve logs for case {case_number}: {e}"
            ) from e

    def _get_or_restart(self, case_number: str) -> Any:
        """Get container, restarting if stopped.

        Args:
            case_number: Case number

        Returns:
            Running container instance

        Raises:
            RuntimeError: If container not found or restart fails
        """
        # Get metadata from state
        metadata = self.state.get_container(case_number)
        if not metadata:
            raise RuntimeError(f"No container found for case {case_number}")

        try:
            # Get container from Podman
            container = self.podman.client.containers.get(metadata.container_id)

            # Reload container to ensure attrs is properly populated
            try:
                container.reload()  # type: ignore[no-untyped-call]
            except Exception:
                pass

            # Get status with defensive handling
            try:
                status = container.status
            except (TypeError, KeyError, AttributeError):
                if isinstance(container.attrs, dict):
                    status = container.attrs.get("State", {}).get("Status", "unknown")
                else:
                    status = "unknown"

            # Auto-restart if stopped
            if status in ("stopped", "exited"):
                print(f"Restarting container for case {case_number}...")
                container.start()  # type: ignore[no-untyped-call]

            return container

        except Exception as e:
            # Wrap Podman exceptions in RuntimeError
            if "NotFound" in str(type(e).__name__):
                raise RuntimeError(f"Container not found for case {case_number}") from e
            raise RuntimeError(
                f"Failed to access container for case {case_number}: {e}"
            ) from e

    def exec(
        self, case_number: str, command: str | list[str], workdir: str = "/case"
    ) -> tuple[int, str]:
        """Execute command inside container, auto-restarting if stopped.

        Args:
            case_number: Case number
            command: Command to execute (string or list of args)
            workdir: Working directory for command (default: /case)

        Returns:
            Tuple of (exit_code, output)
            - exit_code: int (0 for success, non-zero for error)
            - output: str (combined stdout/stderr)

        Raises:
            RuntimeError: If container not found or exec fails
        """
        # Get container, auto-restarting if stopped
        container = self._get_or_restart(case_number)

        try:
            # Execute command inside container
            exit_code, output = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False,
                workdir=workdir,
            )

            # Decode output from bytes to string
            output_str = output.decode("utf-8") if isinstance(output, bytes) else output

            return (exit_code, output_str)

        except Exception as e:
            raise RuntimeError(
                f"Failed to execute command in container for case {case_number}: {e}"
            ) from e
