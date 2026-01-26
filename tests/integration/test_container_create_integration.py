"""Integration test for container creation with real Podman."""

import os
import tempfile

import pytest

from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


def _podman_available() -> bool:
    """Check if Podman is available and accessible.

    Returns:
        bool: True if Podman can be reached, False otherwise
    """
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_create_container_e2e():
    """End-to-end test: create container, verify it exists, cleanup.

    Tests the entire stack:
    - PodmanClient connection
    - ContainerManager.create() with real Podman
    - StateDatabase persistence
    - Container configuration (userns_mode, volumes, labels)
    """
    # Setup temporary workspace and database
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        # Initialize clients
        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            # Create container
            container = manager.create("99999999", workspace_path, "TestCustomer")

            # Verify container exists and is running
            assert container.status == "running", f"Expected running, got {container.status}"
            assert "mc.managed" in container.labels, "Missing mc.managed label"
            assert container.labels["mc.case_number"] == "99999999", "Case number mismatch"
            assert container.labels["mc.customer"] == "TestCustomer", "Customer name mismatch"

            # Verify container configuration
            # userns_mode verification
            assert container.attrs["HostConfig"]["UsernsMode"] == "keep-id", (
                f"Expected userns_mode=keep-id, got {container.attrs['HostConfig']['UsernsMode']}"
            )

            # Volume mount verification
            mounts = container.attrs["Mounts"]
            assert any(m["Destination"] == "/case" for m in mounts), "Missing /case mount"

            case_mount = next(m for m in mounts if m["Destination"] == "/case")
            assert case_mount["Source"] == workspace_path, (
                f"Mount source mismatch: expected {workspace_path}, got {case_mount['Source']}"
            )
            assert case_mount["Mode"] == "rw", f"Expected rw mode, got {case_mount['Mode']}"

            # Verify state database updated
            metadata = state_db.get_container("99999999")
            assert metadata is not None, "Container not found in state database"
            assert metadata.container_id == container.id, "Container ID mismatch in state"
            assert metadata.workspace_path == workspace_path, "Workspace path mismatch in state"

            # Test auto-restart: stop container and verify it restarts on next access
            container.stop(timeout=2)  # type: ignore[no-untyped-call]

            # Wait for container to stop
            import time
            time.sleep(1)

            # Re-create (should auto-restart)
            restarted_container = manager.create("99999999", workspace_path, "TestCustomer")
            assert restarted_container.id == container.id, "Different container created instead of restart"
            assert restarted_container.status == "running", "Container not running after restart"

        finally:
            # Cleanup: stop and remove container
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass  # Ignore cleanup errors

            # Clean up state
            try:
                state_db.delete_container("99999999")
            except Exception:
                pass


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_reconciliation_with_real_podman():
    """Test reconciliation detects externally deleted containers.

    Verifies that state reconciliation correctly detects when a container
    is deleted outside the ContainerManager (e.g., via 'podman rm').
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        client = PodmanClient()
        state_db = StateDatabase(db_path)
        manager = ContainerManager(client, state_db)

        container = None
        try:
            # Create container
            container = manager.create("88888888", workspace_path, "ReconcileTest")

            # Verify state has the container
            metadata = state_db.get_container("88888888")
            assert metadata is not None

            # Delete container externally (bypass ContainerManager)
            container.stop(timeout=2)  # type: ignore[no-untyped-call]
            container.remove()  # type: ignore[no-untyped-call]
            container = None

            # Trigger reconciliation by creating a new container
            new_container = manager.create("77777777", workspace_path, "NewContainer")

            # Verify old container removed from state (reconciliation worked)
            metadata = state_db.get_container("88888888")
            assert metadata is None, "Reconciliation failed to remove externally deleted container"

            # Verify new container was created successfully
            assert new_container.status == "running"

            # Cleanup new container
            new_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            new_container.remove()  # type: ignore[no-untyped-call]
            state_db.delete_container("77777777")

        finally:
            # Cleanup if container still exists
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass
