"""Container lifecycle management and orchestration."""

from __future__ import annotations

import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


def get_ocm_config_path() -> Path:
    """Return the platform-specific host OCM config path.

    Returns:
        Path to ocm.json on this host (may or may not exist).
    """
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ocm" / "ocm.json"
    return Path.home() / ".config" / "ocm" / "ocm.json"


def get_mc_config_path() -> Path:
    """Return the host mc config directory path.

    Returns:
        Path to ~/mc/config on this host (may or may not exist).
    """
    return Path.home() / "mc" / "config"


def get_claude_config_path() -> Path:
    """Return the host Claude Code config directory path.

    Returns:
        Path to ~/.claude on this host (may or may not exist).
    """
    return Path.home() / ".claude"


def get_claude_global_config_path() -> Path:
    """Return the host Claude Code global config file path.

    This file (~/.claude.json) contains global runtime state including
    hasCompletedOnboarding and per-project hasTrustDialogAccepted flags.
    Without it mounted, each new container forces Claude Code to re-run
    the onboarding wizard and trust dialog.

    Returns:
        Path to ~/.claude.json on this host (may or may not exist).
    """
    return Path.home() / ".claude.json"


def get_gcloud_adc_path() -> Path:
    """Return the host GCP Application Default Credentials file path.

    Returns:
        Path to application_default_credentials.json on this host (may or may not exist).
    """
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


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

        # 3. Pre-flight: verify required host paths before any side effects
        mc_config = get_mc_config_path()
        if not mc_config.exists():
            raise RuntimeError(
                f"MC config directory not found: {mc_config}\n"
                f"Run mc on the host first to complete initial setup, "
                f"then retry."
            )

        claude_dir = get_claude_config_path()
        if not claude_dir.exists():
            print(
                f"Warning: Claude config directory not found: {claude_dir}\n"
                f"claude will not be authenticated inside the container."
            )

        # 4. Create workspace directory if missing (prevents mount failures)
        os.makedirs(workspace_path, exist_ok=True)

        # 5. Ensure image exists (pull from registry or use local)
        try:
            self._ensure_image(
                image_name="mc-rhel10:latest",
                registry_image="quay.io/rhn_support_dsquirre/mc-container:latest"
            )
        except RuntimeError:
            # Re-raise with context preserved
            raise

        # 6. Build volumes dict — workspace, mc config (ro), mc state (rw), OCM config, and claude dir (rw)
        volumes: dict[str, dict[str, str]] = {
            workspace_path: {"bind": "/case", "mode": "rw"},
            str(mc_config): {"bind": "/home/mcuser/mc/config", "mode": "ro"},
        }
        mc_state = Path.home() / "mc" / "state"
        mc_state.mkdir(parents=True, exist_ok=True)
        volumes[str(mc_state)] = {"bind": "/home/mcuser/mc/state", "mode": "rw"}
        mc_auth = Path.home() / "mc" / "auth"
        mc_auth.mkdir(parents=True, exist_ok=True)
        volumes[str(mc_auth)] = {"bind": "/home/mcuser/mc/auth", "mode": "rw"}
        ocm_config = get_ocm_config_path()
        if ocm_config.exists():
            volumes[str(ocm_config)] = {"bind": "/home/mcuser/.config/ocm/ocm.json", "mode": "ro"}
        if claude_dir.exists():
            volumes[str(claude_dir)] = {"bind": "/home/mcuser/.claude", "mode": "rw"}

        # Mount Claude global config file (~/.claude.json) if present (ro)
        # Contains hasCompletedOnboarding + hasTrustDialogAccepted — prevents
        # re-onboarding and re-trust on every new container launch.
        claude_json = get_claude_global_config_path()
        if claude_json.exists():
            volumes[str(claude_json)] = {"bind": "/home/mcuser/.claude.json", "mode": "ro"}

        # Mount GCP ADC credentials file if present (enables claude Vertex auth inside container)
        adc_path = get_gcloud_adc_path()
        if adc_path.exists():
            volumes[str(adc_path)] = {"bind": "/gcp/creds.json", "mode": "ro"}

        # 6b. Build environment dict — base vars plus optional host env var forwarding
        environment: dict[str, str] = {
            "CASE_NUMBER": str(case_number),
            "CUSTOMER_NAME": customer_name,
            "WORKSPACE_PATH": "/case",
            "MC_RUNTIME_MODE": "agent",
        }

        # Forward GCP Vertex / Claude auth env vars from host when set
        for env_var in (
            "CLAUDE_CODE_USE_VERTEX",
            "CLOUD_ML_REGION",
            "ANTHROPIC_VERTEX_PROJECT_ID",
            "ANTHROPIC_API_KEY",
            "CLAUDE_CODE_OAUTH_TOKEN",
        ):
            value = os.environ.get(env_var)
            if value is not None:
                environment[env_var] = value

        # Set GOOGLE_APPLICATION_CREDENTIALS inside container when ADC file is mounted
        if adc_path.exists():
            environment["GOOGLE_APPLICATION_CREDENTIALS"] = "/gcp/creds.json"

        # 7. Create new container via Podman API
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
                environment=environment,
                volumes=volumes,
                userns_mode="keep-id",  # Critical for rootless volume permissions
                tty=True,
                stdin_open=True,
            )
        except Exception as e:
            raise RuntimeError(
                f"Failed to create container for case {case_number}: {e}"
            ) from e

        # 8. Start container
        try:
            container.start()  # type: ignore[no-untyped-call]
        except Exception as e:
            raise RuntimeError(
                f"Failed to start container for case {case_number}: {e}"
            ) from e

        # 8b. Reload container to update status attribute
        try:
            container.reload()  # type: ignore[no-untyped-call]
        except Exception:
            # Reload is best-effort - if it fails, continue
            pass

        # 9. Record in state database
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

    def _ensure_image(self, image_name: str, registry_image: str) -> None:
        """Ensure container image is available and current (pull from registry when stale).

        Compares the local image digest against the registry manifest. If the local
        image predates the registry image (stale), pulls the fresh registry image and
        re-tags it. This prevents containers being created from locally-built images
        that are missing tools added in later registry builds (e.g. claude binary).

        Args:
            image_name: Local image name (e.g., "mc-rhel10:latest")
            registry_image: Full registry path (e.g., "quay.io/rhn_support_dsquirre/mc-container:latest")

        Raises:
            RuntimeError: If image cannot be found locally or pulled from registry
        """
        import logging
        logger = logging.getLogger(__name__)

        # 1. Check if image exists locally first
        local_image = None
        try:
            local_image = self.podman.client.images.get(image_name)
        except Exception as e:
            # Check if this is a connection error
            error_str = str(e).lower()
            if "connection" in error_str or "socket" in error_str or "scheme" in error_str:
                raise RuntimeError(
                    f"Failed to connect to Podman: {e}\n"
                    f"Unable to verify image {image_name} exists. "
                    f"Check that Podman is running and accessible."
                ) from e
            # Image not found locally - will pull from registry below
            logger.debug(f"Image {image_name} not found locally, will pull from {registry_image}")

        # 2. If local image exists, check if it matches the registry (staleness check)
        if local_image is not None:
            try:
                reg_data = self.podman.client.images.get_registry_data(registry_image)
                if local_image.id == reg_data.id:  # type: ignore[attr-defined]
                    logger.debug(f"Local image {image_name} is current (digest matches registry)")
                    return
                logger.info(
                    f"Local image {image_name} is stale "
                    f"(local={local_image.id[:12]}, registry={reg_data.id[:12]}), "  # type: ignore[attr-defined]
                    f"pulling fresh image from {registry_image}"
                )
                print(f"Container image is outdated — pulling latest from registry...")
            except Exception as check_error:
                # Registry check failed (offline, auth issue, etc.) — use local image
                logger.debug(
                    f"Could not check registry for {image_name} staleness: {check_error}. "
                    f"Using existing local image."
                )
                return

        # 3. Pull from registry (either local missing or local is stale)
        try:
            print(f"Pulling container image from {registry_image}...")
            self.podman.client.images.pull(registry_image)

            # Tag the pulled image with local name for consistency
            pulled_image = self.podman.client.images.get(registry_image)
            # Split image_name into repository and tag components
            repo, tag = image_name.split(':', 1) if ':' in image_name else (image_name, 'latest')
            pulled_image.tag(repo, tag)  # type: ignore[no-untyped-call]

            logger.info(f"Successfully pulled and tagged {registry_image} as {image_name}")
            print(f"Successfully pulled image from registry")
            return
        except Exception as pull_error:
            # Pull failed - if we have a local image (stale), fall back to it
            if local_image is not None:
                logger.warning(
                    f"Failed to pull fresh image from {registry_image}: {pull_error}. "
                    f"Falling back to existing local image {image_name}."
                )
                return

            # No local image and pull failed - raise with helpful instructions
            logger.debug(f"Failed to pull from registry: {pull_error}")
            raise RuntimeError(
                f"Container image {image_name} not available.\n"
                f"Attempted to pull from {registry_image} but failed: {pull_error}\n\n"
                f"To build locally:\n"
                f"  podman build -t {image_name} -f container/Containerfile .\n\n"
                f"Or wait for the image to be published to the registry."
            ) from pull_error

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
            # Clean up window registry — terminal window disconnects on stop, avoid stale focus
            try:
                from mc.terminal.registry import WindowRegistry
                WindowRegistry().remove(case_number)
            except Exception:
                pass  # non-fatal
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

        # Clean up window registry entry so next mc case opens a fresh terminal
        try:
            from mc.terminal.registry import WindowRegistry
            WindowRegistry().remove(case_number)
        except Exception:
            pass  # non-fatal

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
