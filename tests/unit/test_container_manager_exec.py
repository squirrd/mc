"""Unit tests for ContainerManager.exec() method."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from mc.container.manager import ContainerManager
from mc.container.models import ContainerMetadata
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient


class TestExecCommand:
    """Tests for executing commands in running containers."""

    def test_exec_command_success(self):
        """Test executing command in running container."""
        # Setup mocks
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # Mock state returns container metadata
        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123def456",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        # Mock container
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = (0, b"Hello from container\n")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command
        exit_code, output = manager.exec("12345678", ["echo", "test"])

        # Verify container retrieved
        podman_client.client.containers.get.assert_called_once_with("abc123def456")

        # Verify exec_run called with correct parameters
        mock_container.exec_run.assert_called_once()
        call_kwargs = mock_container.exec_run.call_args.kwargs
        assert call_kwargs["cmd"] == ["echo", "test"]
        assert call_kwargs["workdir"] == "/case"
        assert call_kwargs["stdout"] is True
        assert call_kwargs["stderr"] is True
        assert call_kwargs["stdin"] is False
        assert call_kwargs["tty"] is False

        # Verify output decoded
        assert exit_code == 0
        assert output == "Hello from container\n"

    def test_exec_command_with_custom_workdir(self):
        """Test executing command with custom working directory."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = (0, b"output")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute with custom workdir
        manager.exec("12345678", ["ls", "-la"], workdir="/tmp")

        # Verify workdir parameter passed
        call_kwargs = mock_container.exec_run.call_args.kwargs
        assert call_kwargs["workdir"] == "/tmp"

    def test_exec_command_string_command(self):
        """Test executing command passed as string."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = (0, b"output")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute with string command
        manager.exec("12345678", "ls -la")

        # Verify command passed as-is
        call_kwargs = mock_container.exec_run.call_args.kwargs
        assert call_kwargs["cmd"] == "ls -la"

    def test_exec_command_non_zero_exit_code(self):
        """Test executing command that returns non-zero exit code."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = (127, b"command not found\n")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command that fails
        exit_code, output = manager.exec("12345678", ["nonexistent_command"])

        # Verify exit code returned accurately
        assert exit_code == 127
        assert output == "command not found\n"


class TestExecAutoRestart:
    """Tests for auto-restart behavior on exec."""

    def test_exec_auto_restarts_stopped_container(self, capsys):
        """Test stopped container auto-restarts before exec."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        # Mock container that's stopped
        mock_container = MagicMock()
        mock_container.status = "stopped"
        mock_container.exec_run.return_value = (0, b"output")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command
        manager.exec("12345678", ["echo", "test"])

        # Verify container.start() called
        mock_container.start.assert_called_once()

        # Verify notification printed
        captured = capsys.readouterr()
        assert "Restarting container for case 12345678" in captured.out

        # Verify exec_run still called after restart
        mock_container.exec_run.assert_called_once()

    def test_exec_auto_restarts_exited_container(self):
        """Test exited container auto-restarts before exec."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        # Mock container that's exited
        mock_container = MagicMock()
        mock_container.status = "exited"
        mock_container.exec_run.return_value = (0, b"output")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command
        manager.exec("12345678", ["echo", "test"])

        # Verify container.start() called
        mock_container.start.assert_called_once()

    def test_exec_does_not_restart_running_container(self):
        """Test running container is not restarted."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        # Mock container that's already running
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.return_value = (0, b"output")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command
        manager.exec("12345678", ["echo", "test"])

        # Verify container.start() NOT called
        mock_container.start.assert_not_called()


class TestExecErrors:
    """Tests for error handling in exec."""

    def test_exec_container_not_found_in_state(self):
        """Test exec raises error if container not in state."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        # State returns None (no container)
        state_db.get_container.return_value = None

        manager = ContainerManager(podman_client, state_db)

        # Execute command should raise
        with pytest.raises(RuntimeError, match="No container found for case 99999999"):
            manager.exec("99999999", ["echo", "test"])

    def test_exec_container_not_found_in_podman(self):
        """Test exec raises error if container not in Podman."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        # Mock Podman raises NotFound
        class NotFound(Exception):
            """Mock NotFound exception."""
            pass

        podman_client.client.containers.get.side_effect = NotFound("404: No such container")

        manager = ContainerManager(podman_client, state_db)

        # Execute command should raise
        with pytest.raises(RuntimeError, match="Container not found for case 12345678"):
            manager.exec("12345678", ["echo", "test"])

    def test_exec_run_fails(self):
        """Test exec raises error if exec_run fails."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.exec_run.side_effect = Exception("Exec failed")
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Execute command should raise
        with pytest.raises(RuntimeError, match="Failed to execute command"):
            manager.exec("12345678", ["echo", "test"])


class TestGetOrRestart:
    """Tests for _get_or_restart helper method."""

    def test_get_or_restart_running_container(self):
        """Test _get_or_restart returns running container as-is."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "running"
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Get container
        result = manager._get_or_restart("12345678")

        # Verify container returned
        assert result is mock_container

        # Verify start not called
        mock_container.start.assert_not_called()

    def test_get_or_restart_stopped_container(self):
        """Test _get_or_restart restarts stopped container."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        metadata = ContainerMetadata(
            case_number="12345678",
            container_id="abc123",
            workspace_path="/path/to/workspace",
            created_at=1234567890,
            updated_at=1234567890,
        )
        state_db.get_container.return_value = metadata

        mock_container = MagicMock()
        mock_container.status = "stopped"
        podman_client.client.containers.get.return_value = mock_container

        manager = ContainerManager(podman_client, state_db)

        # Get container
        result = manager._get_or_restart("12345678")

        # Verify container returned
        assert result is mock_container

        # Verify start called
        mock_container.start.assert_called_once()

    def test_get_or_restart_no_metadata(self):
        """Test _get_or_restart raises error if no metadata."""
        podman_client = Mock(spec=PodmanClient)
        state_db = Mock(spec=StateDatabase)

        state_db.get_container.return_value = None

        manager = ContainerManager(podman_client, state_db)

        # Get container should raise
        with pytest.raises(RuntimeError, match="No container found for case 99999999"):
            manager._get_or_restart("99999999")
