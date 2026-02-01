"""Unit tests for container CLI commands."""

import argparse
import os
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from mc.cli.commands import container


class TestCLICreate:
    """Tests for mc container create command."""

    def test_create_invalid_case_number_too_short(self, capsys):
        """Test mc container create rejects case number that's too short."""
        args = argparse.Namespace(case_number="123")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.create(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    def test_create_invalid_case_number_too_long(self, capsys):
        """Test mc container create rejects case number that's too long."""
        args = argparse.Namespace(case_number="123456789")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.create(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: '123456789'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    def test_create_invalid_case_number_non_digits(self, capsys):
        """Test mc container create rejects case number with non-digits."""
        args = argparse.Namespace(case_number="abcd1234")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.create(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: 'abcd1234'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    @patch("mc.cli.commands.container.os.makedirs")
    def test_create_success(self, mock_makedirs, mock_config_mgr, mock_get_manager, capsys):
        """Test mc container create <case> calls manager.create()."""
        # Setup mocks
        mock_config = Mock()
        mock_config.get.return_value = "/Users/user/mc"
        mock_config_mgr.return_value = mock_config

        mock_manager = Mock()
        mock_container = Mock()
        mock_container.short_id = "abc123"
        mock_manager.create.return_value = mock_container
        mock_get_manager.return_value = mock_manager

        # Create args
        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.create(args)

        # Verify workspace directory created
        mock_makedirs.assert_called_once_with("/Users/user/mc/12345678", exist_ok=True)

        # Verify manager.create called
        mock_manager.create.assert_called_once_with("12345678", "/Users/user/mc/12345678")

        # Verify success message printed
        captured = capsys.readouterr()
        assert "Created container for case 12345678" in captured.out
        assert "Container ID: abc123" in captured.out
        assert "Workspace: /Users/user/mc/12345678" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    @patch("mc.cli.commands.container.os.makedirs")
    def test_create_failure(self, mock_makedirs, mock_config_mgr, mock_get_manager, capsys):
        """Test mc container create handles errors."""
        mock_config = Mock()
        mock_config.get.return_value = "/Users/user/mc"
        mock_config_mgr.return_value = mock_config

        mock_manager = Mock()
        mock_manager.create.side_effect = RuntimeError("Creation failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.create(args)

        assert exc_info.value.code == 1

        # Verify error message printed
        captured = capsys.readouterr()
        assert "Error: Creation failed" in captured.err


class TestCLIList:
    """Tests for mc container list command."""

    @patch("mc.cli.commands.container._get_manager")
    def test_list_containers_success(self, mock_get_manager, capsys):
        """Test mc container list formats table."""
        mock_manager = Mock()
        mock_manager.list.return_value = [
            {
                "case_number": "12345678",
                "status": "running",
                "customer": "Acme Corp",
                "workspace_path": "/Users/user/mc/12345678",
                "created_at": "2026-01-26 12:34:56",
            },
            {
                "case_number": "87654321",
                "status": "stopped",
                "customer": "XYZ Inc",
                "workspace_path": "/Users/user/mc/87654321",
                "created_at": "2026-01-25 10:15:00",
            },
        ]
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace()

        # Run command
        container.list_containers(args)

        # Verify table printed
        captured = capsys.readouterr()
        assert "CASE" in captured.out
        assert "STATUS" in captured.out
        assert "CUSTOMER" in captured.out
        assert "WORKSPACE PATH" in captured.out
        assert "CREATED" in captured.out
        assert "12345678" in captured.out
        assert "running" in captured.out
        assert "Acme Corp" in captured.out
        assert "87654321" in captured.out
        assert "stopped" in captured.out
        assert "XYZ Inc" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_list_containers_empty(self, mock_get_manager, capsys):
        """Test mc container list handles empty list."""
        mock_manager = Mock()
        mock_manager.list.return_value = []
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace()

        # Run command
        container.list_containers(args)

        # Verify empty message printed
        captured = capsys.readouterr()
        assert "No containers found" in captured.out
        assert "mc container create" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_list_containers_truncates_long_names(self, mock_get_manager, capsys):
        """Test mc container list truncates long customer names and paths."""
        mock_manager = Mock()
        mock_manager.list.return_value = [
            {
                "case_number": "12345678",
                "status": "running",
                "customer": "Very Long Customer Name That Exceeds Twenty Characters",
                "workspace_path": "/Users/user/very/long/path/to/workspace/that/exceeds/forty/characters/12345678",
                "created_at": "2026-01-26 12:34:56",
            },
        ]
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace()

        # Run command
        container.list_containers(args)

        # Verify truncation
        captured = capsys.readouterr()
        # Customer should be truncated (17 chars + "...")
        assert "Very Long Custome..." in captured.out
        # Workspace path should be truncated
        assert "..." in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_list_containers_failure(self, mock_get_manager):
        """Test mc container list handles errors."""
        mock_manager = Mock()
        mock_manager.list.side_effect = RuntimeError("List failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace()

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.list_containers(args)

        assert exc_info.value.code == 1


class TestCLIStop:
    """Tests for mc container stop command."""

    def test_stop_invalid_case_number(self, capsys):
        """Test mc container stop rejects invalid case number."""
        args = argparse.Namespace(case_number="123")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.stop(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_success(self, mock_get_manager, capsys):
        """Test mc container stop <case> calls manager.stop()."""
        mock_manager = Mock()
        mock_manager.stop.return_value = True  # Was stopped
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.stop(args)

        # Verify manager.stop called
        mock_manager.stop.assert_called_once_with("12345678")

        # Verify success message
        captured = capsys.readouterr()
        assert "Stopped container for case 12345678" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_already_stopped(self, mock_get_manager, capsys):
        """Test mc container stop handles already stopped container."""
        mock_manager = Mock()
        mock_manager.stop.return_value = False  # Already stopped
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.stop(args)

        # Verify message
        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_failure(self, mock_get_manager):
        """Test mc container stop handles errors."""
        mock_manager = Mock()
        mock_manager.stop.side_effect = RuntimeError("Stop failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.stop(args)

        assert exc_info.value.code == 1


class TestCLIDelete:
    """Tests for mc container delete command."""

    def test_delete_invalid_case_number(self, capsys):
        """Test mc container delete rejects invalid case number."""
        args = argparse.Namespace(case_number="123")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.delete(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_success(self, mock_get_manager, capsys):
        """Test mc container delete <case> calls manager.delete()."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.delete(args)

        # Verify warning printed
        captured = capsys.readouterr()
        assert "preserve the workspace" in captured.out

        # Verify manager.delete called
        mock_manager.delete.assert_called_once_with("12345678")

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_failure(self, mock_get_manager):
        """Test mc container delete handles errors."""
        mock_manager = Mock()
        mock_manager.delete.side_effect = RuntimeError("Delete failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.delete(args)

        assert exc_info.value.code == 1


class TestCLIExec:
    """Tests for mc container exec command."""

    def test_exec_invalid_case_number(self, capsys):
        """Test mc container exec rejects invalid case number."""
        args = argparse.Namespace(case_number="123", command=["echo", "test"])

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.exec_command(args)

        assert exc_info.value.code == 1

        # Verify error message
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    def test_exec_success(self, mock_get_manager, capsys):
        """Test mc container exec <case> <cmd> calls manager.exec()."""
        mock_manager = Mock()
        mock_manager.exec.return_value = (0, "Hello from container\n")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(
            case_number="12345678",
            command=["echo", "hello"]
        )

        # Run command should exit with 0
        with pytest.raises(SystemExit) as exc_info:
            container.exec_command(args)

        assert exc_info.value.code == 0

        # Verify manager.exec called
        mock_manager.exec.assert_called_once_with("12345678", ["echo", "hello"])

        # Verify output printed
        captured = capsys.readouterr()
        assert "Hello from container\n" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_exec_non_zero_exit_code(self, mock_get_manager, capsys):
        """Test mc container exec exits with command's exit code."""
        mock_manager = Mock()
        mock_manager.exec.return_value = (127, "command not found\n")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(
            case_number="12345678",
            command=["nonexistent"]
        )

        # Run command should exit with 127
        with pytest.raises(SystemExit) as exc_info:
            container.exec_command(args)

        assert exc_info.value.code == 127

        # Verify output printed
        captured = capsys.readouterr()
        assert "command not found\n" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_exec_failure(self, mock_get_manager):
        """Test mc container exec handles errors."""
        mock_manager = Mock()
        mock_manager.exec.side_effect = RuntimeError("Exec failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(
            case_number="12345678",
            command=["echo", "test"]
        )

        # Run command should exit with 1
        with pytest.raises(SystemExit) as exc_info:
            container.exec_command(args)

        assert exc_info.value.code == 1


class TestQuickAccess:
    """Tests for mc <case_number> quick access."""

    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    @patch("mc.cli.commands.container.os.makedirs")
    def test_quick_access_creates_missing_container(
        self, mock_makedirs, mock_config_mgr, mock_get_manager, capsys
    ):
        """Test mc <case_number> creates container if missing."""
        mock_config = Mock()
        mock_config.get.return_value = "/Users/user/mc"
        mock_config_mgr.return_value = mock_config

        mock_manager = Mock()
        mock_manager.status.return_value = {"status": "missing"}
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.quick_access(args)

        # Verify workspace created
        mock_makedirs.assert_called_once_with("/Users/user/mc/12345678", exist_ok=True)

        # Verify container created
        mock_manager.create.assert_called_once_with("12345678", "/Users/user/mc/12345678")

        # Verify success message
        captured = capsys.readouterr()
        assert "Container ready for case 12345678" in captured.out
        assert "mc attach 12345678" in captured.out
        assert "Phase 12" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    @patch("mc.cli.commands.container.os.makedirs")
    def test_quick_access_existing_container(
        self, mock_makedirs, mock_config_mgr, mock_get_manager, capsys
    ):
        """Test mc <case_number> uses existing container."""
        mock_config = Mock()
        mock_config.get.return_value = "/Users/user/mc"
        mock_config_mgr.return_value = mock_config

        mock_manager = Mock()
        mock_manager.status.return_value = {
            "status": "running",
            "container_id": "abc123",
        }
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.quick_access(args)

        # Verify container NOT created
        mock_manager.create.assert_not_called()

        # Verify success message
        captured = capsys.readouterr()
        assert "Container ready for case 12345678" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    def test_quick_access_failure(self, mock_config_mgr, mock_get_manager):
        """Test mc <case_number> handles errors."""
        mock_config = Mock()
        mock_config.get.return_value = "/Users/user/mc"
        mock_config_mgr.return_value = mock_config

        mock_manager = Mock()
        mock_manager.status.side_effect = RuntimeError("Status check failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command should exit
        with pytest.raises(SystemExit) as exc_info:
            container.quick_access(args)

        assert exc_info.value.code == 1


class TestGetManager:
    """Tests for _get_manager helper."""

    @patch("mc.cli.commands.container.StateDatabase")
    @patch("mc.cli.commands.container.PodmanClient")
    @patch("mc.cli.commands.container.os.makedirs")
    @patch("mc.cli.commands.container.user_data_dir")
    def test_get_manager_creates_manager(
        self, mock_user_data_dir, mock_makedirs, mock_podman, mock_state_db
    ):
        """Test _get_manager creates ContainerManager instance."""
        mock_user_data_dir.return_value = "/Users/user/Library/Application Support/mc"

        # Call helper
        manager = container._get_manager()

        # Verify data directory created
        mock_makedirs.assert_called_once_with(
            "/Users/user/Library/Application Support/mc",
            exist_ok=True
        )

        # Verify PodmanClient created
        mock_podman.assert_called_once()

        # Verify StateDatabase created with correct path
        mock_state_db.assert_called_once_with(
            "/Users/user/Library/Application Support/mc/containers.db"
        )

        # Verify ContainerManager created
        assert manager is not None
