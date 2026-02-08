"""Unit tests for terminal attachment orchestration."""

import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

from mc.terminal.attach import (
    attach_terminal,
    build_exec_command,
    build_window_title,
    should_launch_terminal,
)
from mc.utils.validation import validate_case_number


class TestShouldLaunchTerminal:
    """Tests for TTY detection."""

    def test_should_launch_terminal_tty(self, mocker: Mock) -> None:
        """Test should_launch_terminal returns True when stdout is TTY."""
        mocker.patch.object(sys.stdout, "isatty", return_value=True)

        result = should_launch_terminal()

        assert result is True

    def test_should_launch_terminal_pipe(self, mocker: Mock) -> None:
        """Test should_launch_terminal returns False when stdout is piped."""
        mocker.patch.object(sys.stdout, "isatty", return_value=False)

        result = should_launch_terminal()

        assert result is False


class TestBuildExecCommand:
    """Tests for podman exec command builder."""

    def test_build_exec_command_format(self) -> None:
        """Test exec command includes all required flags and arguments."""
        container_id = "mc-12345678"
        bashrc_path = "/tmp/bashrc"
        case_number = "12345678"

        result = build_exec_command(container_id, bashrc_path, case_number)

        # Verify command structure
        assert result.startswith("podman exec -it")
        assert f"--env 'BASH_ENV={bashrc_path}'" in result
        assert f"--env 'PS1=[MC-{case_number}" in result
        assert result.endswith(f"{container_id} /bin/bash; exit")

    def test_build_exec_command_special_chars(self) -> None:
        """Test exec command handles special characters in paths."""
        container_id = "mc-12345678"
        bashrc_path = "/tmp/path with spaces/bashrc"
        case_number = "12345678"

        result = build_exec_command(container_id, bashrc_path, case_number)

        # Path should be included as-is (shell escaping happens at launch)
        assert bashrc_path in result


class TestBuildWindowTitle:
    """Tests for window title formatting."""

    def test_build_window_title_format(self) -> None:
        """Test window title format matches spec."""
        case_number = "12345678"
        customer_name = "ACME Corp"
        description = "Server down"

        result = build_window_title(case_number, customer_name, description)

        assert result == "12345678:ACME Corp:Server down://case"

    def test_build_window_title_truncation(self) -> None:
        """Test window title truncates long descriptions."""
        case_number = "12345678"
        customer_name = "ACME"
        # Long description that would exceed 100 chars
        description = "x" * 200

        result = build_window_title(case_number, customer_name, description)

        # Total length should be under 100 chars
        assert len(result) <= 100
        # Should end with vm_path suffix after ellipsis in description
        assert result.endswith("://case")
        # Description should be truncated with ellipsis
        assert "..." in result

    def test_build_window_title_no_truncation_needed(self) -> None:
        """Test window title doesn't truncate short descriptions."""
        case_number = "12345678"
        customer_name = "ACME Corp"
        description = "Quick fix"

        result = build_window_title(case_number, customer_name, description)

        # Should not have ellipsis
        assert not result.endswith("...")
        assert description in result


class TestAttachTerminal:
    """Tests for terminal attachment workflow."""

    @pytest.fixture
    def mock_dependencies(self, mocker: Mock):
        """Create mocked dependencies for attach_terminal."""
        # Mock managers
        config_manager = MagicMock()
        config_manager.load.return_value = {"base_directory": "/tmp/mc"}

        # Mock get_case_metadata to return (case_details, account_details, was_cached)
        mock_get_case_metadata = mocker.patch("mc.terminal.attach.get_case_metadata")
        mock_get_case_metadata.return_value = (
            {
                "summary": "Test case",
                "status": "Open",
                "severity": "High",
            },
            {
                "name": "Test Customer",
            },
            False  # was_cached
        )

        api_client = MagicMock()

        container_manager = MagicMock()
        container_manager.status.return_value = {
            "status": "running",
            "workspace_path": "/tmp/mc/12345678",
        }

        # Mock TTY check
        mocker.patch.object(sys.stdout, "isatty", return_value=True)

        # Mock terminal launcher
        mock_launcher = MagicMock()
        mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

        # Mock bashrc writer
        mocker.patch("mc.terminal.attach.write_bashrc", return_value="/tmp/bashrc")

        # Mock validate_case_number to return the case number unchanged
        mocker.patch("mc.terminal.attach.validate_case_number", side_effect=lambda x: x)

        # Mock shorten_and_format to return simple formatted strings
        mocker.patch("mc.terminal.attach.shorten_and_format", side_effect=lambda x: x.replace(" ", "_"))

        return {
            "config_manager": config_manager,
            "api_client": api_client,
            "container_manager": container_manager,
            "launcher": mock_launcher,
            "get_case_metadata": mock_get_case_metadata,
        }

    def test_attach_terminal_creates_container(self, mock_dependencies, mocker: Mock) -> None:
        """Test attach_terminal creates container when missing."""
        deps = mock_dependencies

        # Mock container missing
        deps["container_manager"].status.return_value = {"status": "missing"}

        # Mock print to verify output
        mock_print = mocker.patch("builtins.print")

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify container.create was called
        deps["container_manager"].create.assert_called_once()
        # Verify "Creating container..." message
        mock_print.assert_called_with("Creating container...")

    def test_attach_terminal_starts_stopped_container(self, mock_dependencies) -> None:
        """Test attach_terminal handles stopped containers."""
        deps = mock_dependencies

        # Mock container stopped
        deps["container_manager"].status.return_value = {
            "status": "stopped",
            "workspace_path": "/tmp/mc/12345678",
        }

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Launcher should still be called (container auto-starts on exec)
        deps["launcher"].launch.assert_called_once()

    def test_attach_terminal_launches_terminal(self, mock_dependencies) -> None:
        """Test attach_terminal launches terminal with correct command."""
        deps = mock_dependencies

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify launcher.launch was called
        deps["launcher"].launch.assert_called_once()

        # Verify launch options
        call_args = deps["launcher"].launch.call_args
        launch_options = call_args[0][0]

        assert "12345678" in launch_options.title
        assert "Test Customer" in launch_options.title
        assert "podman exec" in launch_options.command
        assert "mc-12345678" in launch_options.command
        assert launch_options.auto_focus is True

    def test_attach_terminal_custom_bashrc(self, mock_dependencies, mocker: Mock) -> None:
        """Test attach_terminal generates custom bashrc with case metadata."""
        deps = mock_dependencies

        mock_write_bashrc = mocker.patch("mc.terminal.attach.write_bashrc", return_value="/tmp/bashrc")

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify write_bashrc was called
        mock_write_bashrc.assert_called_once()

        # Verify metadata passed to write_bashrc
        call_args = mock_write_bashrc.call_args
        case_number_arg = call_args[0][0]
        metadata_arg = call_args[0][1]

        assert case_number_arg == "12345678"
        assert metadata_arg["case_number"] == "12345678"
        assert metadata_arg["customer_name"] == "Test Customer"
        assert metadata_arg["description"] == "Test case"

    def test_attach_terminal_window_title(self, mock_dependencies) -> None:
        """Test attach_terminal formats window title correctly."""
        deps = mock_dependencies

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify launcher called with formatted title
        call_args = deps["launcher"].launch.call_args
        launch_options = call_args[0][0]

        # Title format: "{case}:{customer}:{description}://case"
        assert launch_options.title == "12345678:Test Customer:Test case://case"

    def test_attach_terminal_podman_exec_command(self, mock_dependencies) -> None:
        """Test attach_terminal builds correct podman exec command."""
        deps = mock_dependencies

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify command structure
        call_args = deps["launcher"].launch.call_args
        launch_options = call_args[0][0]

        command = launch_options.command
        assert command.startswith("podman exec -it")
        assert "--env 'BASH_ENV=/tmp/bashrc'" in command
        assert "--env 'PS1=[MC-12345678]" in command
        assert "mc-12345678 /bin/bash; exit" in command

    def test_attach_terminal_not_tty(self, mock_dependencies, mocker: Mock) -> None:
        """Test attach_terminal raises error when not in TTY."""
        deps = mock_dependencies

        # Mock not a TTY
        mocker.patch.object(sys.stdout, "isatty", return_value=False)

        with pytest.raises(RuntimeError, match="requires interactive terminal"):
            attach_terminal(
                case_number="12345678",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

    def test_attach_terminal_invalid_case_number(self, mock_dependencies, mocker: Mock) -> None:
        """Test attach_terminal rejects invalid case numbers."""
        deps = mock_dependencies

        # Don't mock validate_case_number for this test - let it actually validate
        mocker.patch("mc.terminal.attach.validate_case_number", side_effect=lambda x: validate_case_number(x))

        # Test 7 digits
        with pytest.raises(RuntimeError, match="Invalid case number.*must be exactly 8 digits"):
            attach_terminal(
                case_number="1234567",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

        # Test non-digits
        with pytest.raises(RuntimeError, match="Invalid case number.*must be exactly 8 digits"):
            attach_terminal(
                case_number="abcd1234",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

    def test_attach_terminal_salesforce_failure(self, mock_dependencies) -> None:
        """Test attach_terminal handles Red Hat API failures."""
        deps = mock_dependencies

        # Mock Red Hat API failure
        deps["get_case_metadata"].side_effect = Exception("Network error")

        with pytest.raises(RuntimeError, match="Failed to fetch case metadata.*Check network and credentials"):
            attach_terminal(
                case_number="12345678",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

    def test_attach_terminal_container_create_failure(self, mock_dependencies) -> None:
        """Test attach_terminal handles container creation failures."""
        deps = mock_dependencies

        # Mock container missing
        deps["container_manager"].status.return_value = {"status": "missing"}

        # Mock create failure
        deps["container_manager"].create.side_effect = Exception("Podman error: permission denied")

        with pytest.raises(RuntimeError, match="Failed to create container.*Podman error"):
            attach_terminal(
                case_number="12345678",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

    def test_attach_terminal_launcher_failure(self, mock_dependencies) -> None:
        """Test attach_terminal handles terminal launch failures."""
        deps = mock_dependencies

        # Mock launcher failure
        deps["launcher"].launch.side_effect = Exception("Terminal not found")

        with pytest.raises(RuntimeError, match="Terminal launch failed.*Run: mc --check-terminal"):
            attach_terminal(
                case_number="12345678",
                config_manager=deps["config_manager"],
                api_client=deps["api_client"],
                container_manager=deps["container_manager"],
            )

    def test_attach_terminal_metadata_fallbacks(self, mock_dependencies) -> None:
        """Test attach_terminal uses metadata fallbacks correctly."""
        deps = mock_dependencies

        # Return minimal metadata (no summary, empty account name)
        deps["get_case_metadata"].return_value = (
            {},  # Empty case_details
            {},  # Empty account_details
            False
        )

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Verify fallback used
        call_args = deps["launcher"].launch.call_args
        launch_options = call_args[0][0]

        # account name falls back to "Unknown"
        assert "Unknown" in launch_options.title
        # description defaults to empty string
        assert "12345678:Unknown:://case" == launch_options.title

    def test_attach_terminal_workspace_path_fallback(self, mock_dependencies) -> None:
        """Test attach_terminal constructs workspace path when not in status."""
        deps = mock_dependencies

        # Status returns no workspace_path
        deps["container_manager"].status.return_value = {
            "status": "running",
        }

        attach_terminal(
            case_number="12345678",
            config_manager=deps["config_manager"],
            api_client=deps["api_client"],
            container_manager=deps["container_manager"],
        )

        # Should still work (constructs workspace path from config)
        deps["launcher"].launch.assert_called_once()
