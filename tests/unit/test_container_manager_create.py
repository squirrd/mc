"""Unit tests for ContainerManager.create() method."""

import os
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from mc.container.manager import ContainerManager
from mc.container.models import ContainerMetadata
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


class TestContainerManagerInit:
    """Tests for ContainerManager initialization."""

    def test_init_with_clients(self):
        """Test initialization with PodmanClient and StateDatabase."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        manager = ContainerManager(podman_client, state_db)

        assert manager.podman is podman_client
        assert manager.state is state_db


class TestCreateNewContainer:
    """Tests for creating new containers."""

    @patch('mc.container.manager.os.makedirs')
    def test_create_new_container(self, mock_makedirs):
        """Test creating new container when none exists."""
        # Setup mocks
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Mock reconciliation (no existing containers)
        mock_containers_list = Mock(return_value=[])
        podman_client.client.containers.list = mock_containers_list

        # State returns None (no existing container)
        state_db.get_container.return_value = None

        # Mock image verification (mc-rhel10:latest exists)
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        # Mock container creation
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        podman_client.client.containers.create.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Create container
        result = manager.create("12345678", "/path/to/workspace", "TestCustomer")

        # Verify reconciliation called
        mock_containers_list.assert_called_once_with(
            all=True,
            filters={"label": "mc.managed=true"}
        )
        state_db.reconcile.assert_called_once()

        # Verify state query
        state_db.get_container.assert_called_once_with("12345678")

        # Verify workspace directory created
        mock_makedirs.assert_called_once_with("/path/to/workspace", exist_ok=True)

        # Verify image exists check
        podman_client.client.images.get.assert_called_once_with("mc-rhel10:latest")

        # Verify container created with correct parameters
        podman_client.client.containers.create.assert_called_once()
        create_call = podman_client.client.containers.create.call_args
        assert create_call.kwargs["image"] == "mc-rhel10:latest"
        assert create_call.kwargs["name"] == "mc-12345678"
        assert create_call.kwargs["command"] == ["/bin/bash", "-c", "tail -f /dev/null"]
        assert create_call.kwargs["detach"] is True
        assert create_call.kwargs["tty"] is True
        assert create_call.kwargs["stdin_open"] is True
        assert create_call.kwargs["userns_mode"] == "keep-id"
        assert create_call.kwargs["labels"]["mc.managed"] == "true"
        assert create_call.kwargs["labels"]["mc.case_number"] == "12345678"
        assert create_call.kwargs["labels"]["mc.customer"] == "TestCustomer"
        assert create_call.kwargs["environment"]["CASE_NUMBER"] == "12345678"
        assert create_call.kwargs["environment"]["CUSTOMER_NAME"] == "TestCustomer"
        assert create_call.kwargs["environment"]["WORKSPACE_PATH"] == "/case"
        assert create_call.kwargs["environment"]["MC_RUNTIME_MODE"] == "agent"
        assert create_call.kwargs["volumes"] == {
            "/path/to/workspace": {"bind": "/case", "mode": "rw"}
        }

        # Verify container started
        mock_container.start.assert_called_once()

        # Verify state recorded
        state_db.add_container.assert_called_once_with(
            "12345678", "abc123", "/path/to/workspace"
        )

        # Verify return value
        assert result is mock_container

    @patch('mc.container.manager.os.makedirs')
    def test_create_with_default_customer_name(self, mock_makedirs):
        """Test creating container with default customer name."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None

        # Mock image verification
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        mock_container = MagicMock()
        mock_container.id = "abc123"
        podman_client.client.containers.create.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)
        manager.create("12345678", "/path/to/workspace")

        # Verify default customer name used in label and environment
        create_call = podman_client.client.containers.create.call_args
        assert create_call.kwargs["labels"]["mc.customer"] == "Unknown"
        assert create_call.kwargs["environment"]["CUSTOMER_NAME"] == "Unknown"


class TestAutoRestartStopped:
    """Tests for auto-restarting stopped containers."""

    @patch('mc.container.manager.os.makedirs')
    def test_auto_restart_stopped_container(self, mock_makedirs, capsys):
        """Test auto-restart of stopped container."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Mock reconciliation
        podman_client.client.containers.list.return_value = []

        # State returns existing container
        existing_metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = existing_metadata

        # Mock container with stopped status
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "stopped"
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)
        result = manager.create("12345678", "/path/to/workspace")

        # Verify container fetched from Podman
        podman_client.client.containers.get.assert_called_once_with("abc123")

        # Verify container restarted
        mock_container.start.assert_called_once()

        # Verify notification printed
        captured = capsys.readouterr()
        assert "Restarting container for case 12345678" in captured.out

        # Verify no new container created
        podman_client.client.containers.create.assert_not_called()

        # Verify no workspace directory creation
        mock_makedirs.assert_not_called()

        # Verify return value
        assert result is mock_container

    @patch('mc.container.manager.os.makedirs')
    def test_auto_restart_exited_container(self, mock_makedirs):
        """Test auto-restart of exited container."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []

        existing_metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = existing_metadata

        # Mock container with exited status
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "exited"
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)
        result = manager.create("12345678", "/path/to/workspace")

        # Verify container restarted
        mock_container.start.assert_called_once()

        # Verify no new container created
        podman_client.client.containers.create.assert_not_called()
        mock_makedirs.assert_not_called()


class TestReuseRunning:
    """Tests for reusing running containers."""

    @patch('mc.container.manager.os.makedirs')
    def test_reuse_running_container(self, mock_makedirs):
        """Test reusing already running container."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []

        existing_metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = existing_metadata

        # Mock container with running status
        mock_container = MagicMock()
        mock_container.id = "abc123"
        mock_container.status = "running"
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)
        result = manager.create("12345678", "/path/to/workspace")

        # Verify container fetched
        podman_client.client.containers.get.assert_called_once_with("abc123")

        # Verify no restart (already running)
        mock_container.start.assert_not_called()

        # Verify no new container created
        podman_client.client.containers.create.assert_not_called()
        mock_makedirs.assert_not_called()

        # Verify return value
        assert result is mock_container


class TestReconciliation:
    """Tests for state reconciliation."""

    @patch('mc.container.manager.os.makedirs')
    def test_reconciliation_before_create(self, mock_makedirs):
        """Test reconciliation called before create operation."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Mock Podman containers (for reconciliation)
        mock_container_1 = MagicMock()
        mock_container_1.id = "container1"
        mock_container_2 = MagicMock()
        mock_container_2.id = "container2"
        podman_client.client.containers.list.return_value = [
            mock_container_1,
            mock_container_2,
        ]

        state_db.get_container.return_value = None

        mock_new_container = MagicMock()
        mock_new_container.id = "abc123"
        podman_client.client.containers.create.return_value = mock_new_container

        manager = ContainerManager(podman_client, state_db)
        manager.create("12345678", "/path/to/workspace")

        # Verify reconciliation called before any other operations
        assert state_db.reconcile.call_count == 1
        state_db.reconcile.assert_called_once_with({"container1", "container2"})

        # Verify reconciliation happened before state query
        assert state_db.method_calls[0][0] == 'reconcile'
        assert state_db.method_calls[1][0] == 'get_container'

    @patch('mc.container.manager.os.makedirs')
    def test_reconciliation_detects_external_deletion(self, mock_makedirs, capsys):
        """Test creating new container when existing was externally deleted."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Reconciliation shows no mc-managed containers
        podman_client.client.containers.list.return_value = []

        # State has old container (externally deleted)
        existing_metadata = ContainerMetadata(
            case_number="12345678",
            container_id="deleted123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = existing_metadata

        # Podman raises exception when trying to get deleted container
        podman_client.client.containers.get.side_effect = Exception(
            "No such container: deleted123"
        )

        # Mock image verification
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        # Mock new container creation
        mock_new_container = MagicMock()
        mock_new_container.id = "new456"
        podman_client.client.containers.create.return_value = mock_new_container

        manager = ContainerManager(podman_client, state_db)
        result = manager.create("12345678", "/path/to/workspace")

        # Verify warning printed
        captured = capsys.readouterr()
        assert "Warning: Container deleted123 in state but not found in Podman" in captured.out

        # Verify old state deleted
        state_db.delete_container.assert_called_once_with("12345678")

        # Verify new container created
        podman_client.client.containers.create.assert_called_once()

        # Verify new state recorded
        state_db.add_container.assert_called_once_with(
            "12345678", "new456", "/path/to/workspace"
        )

        assert result is mock_new_container


class TestErrorHandling:
    """Tests for error handling."""

    @patch('mc.container.manager.os.makedirs')
    def test_image_not_found_raises_runtime_error(self, mock_makedirs):
        """Test RuntimeError raised when mc-rhel10:latest image not found."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None

        # Mock image not found
        podman_client.client.images.get.side_effect = Exception(
            "No such image: mc-rhel10:latest"
        )

        manager = ContainerManager(podman_client, state_db)

        with pytest.raises(RuntimeError) as exc_info:
            manager.create("12345678", "/path/to/workspace")

        assert "Image mc-rhel10:latest not found" in str(exc_info.value)
        assert "podman build -t mc-rhel10:latest -f container/Containerfile ." in str(exc_info.value)

    @patch('mc.container.manager.os.makedirs')
    def test_create_failure_raises_runtime_error(self, mock_makedirs):
        """Test RuntimeError raised when container creation fails."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None

        # Mock image exists
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        # Mock creation failure
        podman_client.client.containers.create.side_effect = Exception(
            "Insufficient memory"
        )

        manager = ContainerManager(podman_client, state_db)

        with pytest.raises(RuntimeError) as exc_info:
            manager.create("12345678", "/path/to/workspace")

        assert "Failed to create container for case 12345678" in str(exc_info.value)
        assert "Insufficient memory" in str(exc_info.value)

    @patch('mc.container.manager.os.makedirs')
    def test_start_failure_raises_runtime_error(self, mock_makedirs):
        """Test RuntimeError raised when container start fails."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None

        # Mock image exists
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        mock_container = MagicMock()
        mock_container.id = "abc123"
        podman_client.client.containers.create.return_value = mock_container

        # Mock start failure
        mock_container.start.side_effect = Exception("Failed to start")

        manager = ContainerManager(podman_client, state_db)

        with pytest.raises(RuntimeError) as exc_info:
            manager.create("12345678", "/path/to/workspace")

        assert "Failed to start container for case 12345678" in str(exc_info.value)

    @patch('mc.container.manager.os.makedirs')
    def test_state_failure_cleanup_container(self, mock_makedirs):
        """Test container cleanup when state persistence fails."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        podman_client.client.containers.list.return_value = []
        state_db.get_container.return_value = None

        # Mock image exists
        mock_image = MagicMock()
        podman_client.client.images.get.return_value = mock_image

        mock_container = MagicMock()
        mock_container.id = "abc123"
        podman_client.client.containers.create.return_value = mock_container

        # Mock state persistence failure
        state_db.add_container.side_effect = Exception("Database error")

        manager = ContainerManager(podman_client, state_db)

        with pytest.raises(RuntimeError) as exc_info:
            manager.create("12345678", "/path/to/workspace")

        assert "Failed to record container state for case 12345678" in str(exc_info.value)

        # Verify cleanup attempted
        mock_container.stop.assert_called_once_with(timeout=2)
        mock_container.remove.assert_called_once()

    def test_reconciliation_failure_non_fatal(self, capsys):
        """Test reconciliation failure is non-fatal."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Mock reconciliation failure
        podman_client.client.containers.list.side_effect = Exception(
            "Podman connection error"
        )

        manager = ContainerManager(podman_client, state_db)
        manager._reconcile()

        # Verify warning printed
        captured = capsys.readouterr()
        assert "Warning: Failed to reconcile container state" in captured.out
        assert "Podman connection error" in captured.out

        # Verify reconcile not called on state (due to early failure)
        state_db.reconcile.assert_not_called()
