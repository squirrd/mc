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
        assert "DESCRIPTION" in captured.out  # Changed from WORKSPACE PATH
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
        args = argparse.Namespace(case_numbers=["123"])

        with pytest.raises(SystemExit) as exc_info:
            container.stop(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_success(self, mock_get_manager, capsys):
        """Test mc container stop <case> calls manager.stop()."""
        mock_manager = Mock()
        mock_manager.stop.return_value = True
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678"])
        container.stop(args)

        mock_manager.stop.assert_called_once_with("12345678")
        captured = capsys.readouterr()
        assert "Stopped container for case 12345678" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_already_stopped(self, mock_get_manager, capsys):
        """Test mc container stop handles already stopped container."""
        mock_manager = Mock()
        mock_manager.stop.return_value = False
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678"])
        container.stop(args)

        captured = capsys.readouterr()
        assert "already stopped" in captured.out

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_failure(self, mock_get_manager):
        """Test mc container stop handles errors."""
        mock_manager = Mock()
        mock_manager.stop.side_effect = RuntimeError("Stop failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678"])

        with pytest.raises(SystemExit) as exc_info:
            container.stop(args)

        assert exc_info.value.code == 1

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_multiple_cases(self, mock_get_manager, capsys):
        """Test mc container stop processes all case numbers."""
        mock_manager = Mock()
        mock_manager.stop.return_value = True
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678", "87654321"])
        container.stop(args)

        assert mock_manager.stop.call_count == 2
        mock_manager.stop.assert_any_call("12345678")
        mock_manager.stop.assert_any_call("87654321")

    @patch("mc.cli.commands.container._get_manager")
    def test_stop_multiple_continues_on_error(self, mock_get_manager, capsys):
        """Test mc container stop continues past one failure and exits non-zero."""
        mock_manager = Mock()
        mock_manager.stop.side_effect = [RuntimeError("Stop failed"), True]
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678", "87654321"])

        with pytest.raises(SystemExit) as exc_info:
            container.stop(args)

        assert exc_info.value.code == 1
        # Second case was still attempted
        assert mock_manager.stop.call_count == 2
        captured = capsys.readouterr()
        assert "Stopped container for case 87654321" in captured.out


class TestCLIDelete:
    """Tests for mc container delete command."""

    def test_delete_invalid_case_number(self, capsys):
        """Test mc container delete rejects invalid case number."""
        args = argparse.Namespace(case_numbers=["123"])

        with pytest.raises(SystemExit) as exc_info:
            container.delete(args)

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Invalid case number: '123'" in captured.err
        assert "must be exactly 8 digits" in captured.err

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_success(self, mock_get_manager, capsys):
        """Test mc container delete <case> calls manager.delete()."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678"])
        container.delete(args)

        captured = capsys.readouterr()
        assert "preserve the workspace" in captured.out
        mock_manager.delete.assert_called_once_with("12345678")

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_failure(self, mock_get_manager):
        """Test mc container delete handles errors."""
        mock_manager = Mock()
        mock_manager.delete.side_effect = RuntimeError("Delete failed")
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678"])

        with pytest.raises(SystemExit) as exc_info:
            container.delete(args)

        assert exc_info.value.code == 1

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_multiple_cases(self, mock_get_manager, capsys):
        """Test mc container delete processes all case numbers."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678", "87654321"])
        container.delete(args)

        assert mock_manager.delete.call_count == 2
        mock_manager.delete.assert_any_call("12345678")
        mock_manager.delete.assert_any_call("87654321")

    @patch("mc.cli.commands.container._get_manager")
    def test_delete_multiple_continues_on_error(self, mock_get_manager, capsys):
        """Test mc container delete continues past one failure and exits non-zero."""
        mock_manager = Mock()
        mock_manager.delete.side_effect = [RuntimeError("Delete failed"), None]
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_numbers=["12345678", "87654321"])

        with pytest.raises(SystemExit) as exc_info:
            container.delete(args)

        assert exc_info.value.code == 1
        # Second case was still attempted
        assert mock_manager.delete.call_count == 2


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

    @patch("mc.cli.commands.container.attach_terminal")
    @patch("mc.cli.commands.container.RedHatAPIClient")
    @patch("mc.cli.commands.container.get_access_token")
    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    def test_quick_access_creates_missing_container(
        self, mock_config_mgr, mock_get_manager, mock_get_token, mock_api_client, mock_attach
    ):
        """Test mc <case_number> creates container if missing."""
        # Mock ConfigManager to return proper config structure
        mock_config_instance = Mock()
        mock_config_instance.load.return_value = {
            "api": {"rh_api_offline_token": "test_token"},
            "workspace": {"base_path": "/Users/user/mc"}
        }
        mock_config_mgr.return_value = mock_config_instance

        # Mock authentication
        mock_get_token.return_value = "test_access_token"
        mock_api_instance = Mock()
        mock_api_client.return_value = mock_api_instance

        # Mock container manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.quick_access(args)

        # Verify authentication flow
        mock_config_instance.load.assert_called_once()
        mock_get_token.assert_called_once_with("test_token")
        mock_api_client.assert_called_once_with("test_access_token")

        # Verify attach_terminal was called with correct parameters
        mock_attach.assert_called_once()
        call_kwargs = mock_attach.call_args.kwargs
        assert call_kwargs["case_number"] == "12345678"
        assert call_kwargs["config_manager"] == mock_config_instance
        assert call_kwargs["api_client"] == mock_api_instance
        assert call_kwargs["container_manager"] == mock_manager

    @patch("mc.cli.commands.container.attach_terminal")
    @patch("mc.cli.commands.container.RedHatAPIClient")
    @patch("mc.cli.commands.container.get_access_token")
    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    def test_quick_access_existing_container(
        self, mock_config_mgr, mock_get_manager, mock_get_token, mock_api_client, mock_attach
    ):
        """Test mc <case_number> uses existing container."""
        # Mock ConfigManager to return proper config structure
        mock_config_instance = Mock()
        mock_config_instance.load.return_value = {
            "api": {"rh_api_offline_token": "test_token"},
            "workspace": {"base_path": "/Users/user/mc"}
        }
        mock_config_mgr.return_value = mock_config_instance

        # Mock authentication
        mock_get_token.return_value = "test_access_token"
        mock_api_instance = Mock()
        mock_api_client.return_value = mock_api_instance

        # Mock container manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        args = argparse.Namespace(case_number="12345678")

        # Run command
        container.quick_access(args)

        # Verify authentication flow
        mock_config_instance.load.assert_called_once()
        mock_get_token.assert_called_once_with("test_token")
        mock_api_client.assert_called_once_with("test_access_token")

        # Verify attach_terminal was called
        mock_attach.assert_called_once()
        call_kwargs = mock_attach.call_args.kwargs
        assert call_kwargs["case_number"] == "12345678"

    @patch("mc.cli.commands.container.attach_terminal")
    @patch("mc.cli.commands.container.RedHatAPIClient")
    @patch("mc.cli.commands.container.get_access_token")
    @patch("mc.cli.commands.container._get_manager")
    @patch("mc.cli.commands.container.ConfigManager")
    def test_quick_access_failure(
        self, mock_config_mgr, mock_get_manager, mock_get_token, mock_api_client, mock_attach
    ):
        """Test mc <case_number> handles errors."""
        # Mock ConfigManager to return proper config structure
        mock_config_instance = Mock()
        mock_config_instance.load.return_value = {
            "api": {"rh_api_offline_token": "test_token"},
            "workspace": {"base_path": "/Users/user/mc"}
        }
        mock_config_mgr.return_value = mock_config_instance

        # Mock authentication
        mock_get_token.return_value = "test_access_token"
        mock_api_instance = Mock()
        mock_api_client.return_value = mock_api_instance

        # Mock container manager
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager

        # Mock attach_terminal to raise an error
        mock_attach.side_effect = RuntimeError("Attach failed")

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
    @patch("mc.cli.commands.container.os.path.expanduser")
    def test_get_manager_creates_manager(
        self, mock_expanduser, mock_makedirs, mock_podman, mock_state_db
    ):
        """Test _get_manager creates ContainerManager instance."""
        mock_expanduser.return_value = "/Users/user"

        # Call helper
        manager = container._get_manager()

        # Verify data directory created with consolidated path
        mock_makedirs.assert_called_once_with(
            "/Users/user/mc/state",
            exist_ok=True
        )

        # Verify PodmanClient created
        mock_podman.assert_called_once()

        # Verify StateDatabase created with correct path
        mock_state_db.assert_called_once_with(
            "/Users/user/mc/state/containers.db"
        )

        # Verify ContainerManager created
        assert manager is not None
