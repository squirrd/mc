"""Unit tests for container lifecycle operations (stop, delete, status, logs)."""

import pytest
from unittest.mock import MagicMock, Mock, patch

from mc.container.manager import ContainerManager
from mc.container.models import ContainerMetadata
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


@pytest.fixture
def mock_podman():
    """Create mock Podman client."""
    client = MagicMock(spec=PodmanClient)
    return client


@pytest.fixture
def mock_state():
    """Create mock state database."""
    db = MagicMock(spec=StateDatabase)
    return db


@pytest.fixture
def manager(mock_podman, mock_state):
    """Create container manager with mocked dependencies."""
    return ContainerManager(mock_podman, mock_state)


@pytest.fixture
def container_metadata():
    """Create sample container metadata."""
    return ContainerMetadata(
        case_number="12345678",
        container_id="abc123def456",
        workspace_path="/Users/user/Cases/12345678",
        created_at=1700000000,
        updated_at=1700000000,
    )


class TestStopContainer:
    """Test ContainerManager.stop() method."""

    def test_stop_running_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping a running container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "running"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.stop("12345678")

        # Verify
        assert result is True
        mock_state.get_container.assert_called_once_with("12345678")
        mock_podman.client.containers.get.assert_called_once_with("abc123def456")
        mock_container.stop.assert_called_once_with(timeout=10)

    def test_stop_with_custom_timeout(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping container with custom timeout."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "running"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.stop("12345678", timeout=30)

        # Verify
        assert result is True
        mock_container.stop.assert_called_once_with(timeout=30)

    def test_stop_already_stopped_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping an already stopped container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.stop("12345678")

        # Verify
        assert result is False
        mock_container.stop.assert_not_called()

    def test_stop_exited_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping an exited container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "exited"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.stop("12345678")

        # Verify
        assert result is False
        mock_container.stop.assert_not_called()

    def test_stop_nonexistent_container_in_state(self, manager, mock_state):
        """Test stopping container that doesn't exist in state."""
        # Setup
        mock_state.get_container.return_value = None

        # Execute and verify
        with pytest.raises(RuntimeError, match="No container found for case 12345678"):
            manager.stop("12345678")

    def test_stop_container_podman_error(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping container when Podman API fails."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("Connection error")

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to get container for case 12345678"):
            manager.stop("12345678")

    def test_stop_container_stop_fails(self, manager, mock_podman, mock_state, container_metadata):
        """Test stopping container when stop operation fails."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "running"
        mock_container.stop.side_effect = Exception("Stop failed")
        mock_podman.client.containers.get.return_value = mock_container

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to stop container for case 12345678"):
            manager.stop("12345678")


class TestDeleteContainer:
    """Test ContainerManager.delete() method."""

    def test_delete_stopped_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting a stopped container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        manager.delete("12345678")

        # Verify
        mock_state.get_container.assert_called_once_with("12345678")
        mock_podman.client.containers.get.assert_called_once_with("abc123def456")
        mock_container.stop.assert_not_called()  # Already stopped
        mock_container.remove.assert_called_once()
        mock_state.delete_container.assert_called_once_with("12345678")

    def test_delete_running_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting a running container (auto-stops first)."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "running"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        manager.delete("12345678")

        # Verify
        mock_container.stop.assert_called_once_with(timeout=10)
        mock_container.remove.assert_called_once()
        mock_state.delete_container.assert_called_once_with("12345678")

    def test_delete_preserves_workspace_by_default(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container preserves workspace by default."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        with patch("os.path.exists") as mock_exists, \
             patch("shutil.rmtree") as mock_rmtree:
            manager.delete("12345678")

            # Verify workspace NOT deleted
            mock_rmtree.assert_not_called()

    def test_delete_with_workspace_removal(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container with workspace removal."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        with patch("os.path.exists", return_value=True) as mock_exists, \
             patch("shutil.rmtree") as mock_rmtree:
            manager.delete("12345678", remove_workspace=True)

            # Verify workspace deleted
            mock_exists.assert_called_once_with("/Users/user/Cases/12345678")
            mock_rmtree.assert_called_once_with("/Users/user/Cases/12345678")

    def test_delete_workspace_removal_nonexistent_path(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container with workspace removal when path doesn't exist."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        with patch("os.path.exists", return_value=False) as mock_exists, \
             patch("shutil.rmtree") as mock_rmtree:
            manager.delete("12345678", remove_workspace=True)

            # Verify no deletion attempted
            mock_rmtree.assert_not_called()

    def test_delete_workspace_removal_fails_nonfatal(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container continues if workspace deletion fails."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        with patch("os.path.exists", return_value=True), \
             patch("shutil.rmtree", side_effect=OSError("Permission denied")):
            # Should not raise exception
            manager.delete("12345678", remove_workspace=True)

            # State still cleaned up
            mock_state.delete_container.assert_called_once_with("12345678")

    def test_delete_nonexistent_container_in_state(self, manager, mock_state):
        """Test deleting container that doesn't exist in state."""
        # Setup
        mock_state.get_container.return_value = None

        # Execute and verify
        with pytest.raises(RuntimeError, match="No container found for case 12345678"):
            manager.delete("12345678")

    def test_delete_container_already_removed_externally(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container that was already removed externally."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("no such container")

        # Execute (should succeed - cleans up state)
        manager.delete("12345678")

        # Verify state cleaned up
        mock_state.delete_container.assert_called_once_with("12345678")

    def test_delete_container_podman_api_error(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container when Podman API fails with non-NotFound error."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("Connection timeout")

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to delete container for case 12345678"):
            manager.delete("12345678")

    def test_delete_state_cleanup_fails(self, manager, mock_podman, mock_state, container_metadata):
        """Test deleting container when state cleanup fails."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_podman.client.containers.get.return_value = mock_container
        mock_state.delete_container.side_effect = Exception("Database locked")

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to delete container state for case 12345678"):
            manager.delete("12345678")


class TestStatusContainer:
    """Test ContainerManager.status() method."""

    def test_status_running_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting status for running container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "running"
        mock_container.short_id = "abc123"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.status("12345678")

        # Verify
        assert result == {
            "status": "running",
            "container_id": "abc123",
            "workspace_path": "/Users/user/Cases/12345678",
            "created_at": 1700000000,
        }

    def test_status_stopped_container(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting status for stopped container."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.status = "stopped"
        mock_container.short_id = "abc123"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.status("12345678")

        # Verify
        assert result["status"] == "stopped"
        assert result["container_id"] == "abc123"

    def test_status_missing_from_state(self, manager, mock_state):
        """Test getting status for container not in state."""
        # Setup
        mock_state.get_container.return_value = None

        # Execute
        result = manager.status("12345678")

        # Verify
        assert result == {
            "status": "missing",
            "container_id": None,
            "workspace_path": None,
            "created_at": None,
        }

    def test_status_container_deleted_externally(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting status for container deleted externally."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("no such container")

        # Execute
        result = manager.status("12345678")

        # Verify reconciliation happened
        mock_state.delete_container.assert_called_once_with("12345678")
        assert result == {
            "status": "missing",
            "container_id": None,
            "workspace_path": None,
            "created_at": None,
        }

    def test_status_podman_api_error(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting status when Podman API fails with non-NotFound error."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("Connection timeout")

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to query container status for case 12345678"):
            manager.status("12345678")


class TestLogsContainer:
    """Test ContainerManager.logs() method."""

    def test_logs_with_default_tail(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting logs with default tail."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.return_value = b"2026-01-26T12:00:00Z Log line 1\n2026-01-26T12:00:01Z Log line 2\n"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.logs("12345678")

        # Verify
        assert result == "2026-01-26T12:00:00Z Log line 1\n2026-01-26T12:00:01Z Log line 2\n"
        mock_container.logs.assert_called_once_with(
            stdout=True,
            stderr=True,
            timestamps=True,
            tail=50,
            follow=False,
        )

    def test_logs_with_custom_tail(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting logs with custom tail."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.return_value = b"Log line\n"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.logs("12345678", tail=100)

        # Verify
        mock_container.logs.assert_called_once_with(
            stdout=True,
            stderr=True,
            timestamps=True,
            tail=100,
            follow=False,
        )

    def test_logs_with_follow(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting logs with follow enabled."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.return_value = b"Streaming logs\n"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.logs("12345678", follow=True)

        # Verify
        mock_container.logs.assert_called_once_with(
            stdout=True,
            stderr=True,
            timestamps=True,
            tail=50,
            follow=True,
        )

    def test_logs_returns_string_when_bytes(self, manager, mock_podman, mock_state, container_metadata):
        """Test logs decodes bytes to string."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.return_value = b"Byte logs\n"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.logs("12345678")

        # Verify
        assert isinstance(result, str)
        assert result == "Byte logs\n"

    def test_logs_returns_string_when_string(self, manager, mock_podman, mock_state, container_metadata):
        """Test logs returns string as-is."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.return_value = "String logs\n"
        mock_podman.client.containers.get.return_value = mock_container

        # Execute
        result = manager.logs("12345678")

        # Verify
        assert result == "String logs\n"

    def test_logs_nonexistent_container_in_state(self, manager, mock_state):
        """Test getting logs for container not in state."""
        # Setup
        mock_state.get_container.return_value = None

        # Execute and verify
        with pytest.raises(RuntimeError, match="No container found for case 12345678"):
            manager.logs("12345678")

    def test_logs_container_not_found(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting logs when container not found in Podman."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_podman.client.containers.get.side_effect = Exception("no such container")

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to get container for case 12345678"):
            manager.logs("12345678")

    def test_logs_retrieval_fails(self, manager, mock_podman, mock_state, container_metadata):
        """Test getting logs when logs retrieval fails."""
        # Setup
        mock_state.get_container.return_value = container_metadata
        mock_container = Mock()
        mock_container.logs.side_effect = Exception("Logs unavailable")
        mock_podman.client.containers.get.return_value = mock_container

        # Execute and verify
        with pytest.raises(RuntimeError, match="Failed to retrieve logs for case 12345678"):
            manager.logs("12345678")
