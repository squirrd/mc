"""Unit tests for terminal launcher module."""

import subprocess
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from mc.terminal.detector import detect_terminal, find_available_terminal
from mc.terminal.launcher import LaunchOptions, get_launcher
from mc.terminal.linux import LinuxLauncher
from mc.terminal.macos import MacOSLauncher


class TestGetLauncher:
    """Tests for get_launcher factory function."""

    def test_get_launcher_macos(self, mocker: Mock) -> None:
        """Test get_launcher returns MacOSLauncher on Darwin."""
        mocker.patch("mc.terminal.launcher.platform.system", return_value="Darwin")

        launcher = get_launcher()

        assert isinstance(launcher, MacOSLauncher)

    def test_get_launcher_linux(self, mocker: Mock) -> None:
        """Test get_launcher returns LinuxLauncher on Linux."""
        mocker.patch("mc.terminal.launcher.platform.system", return_value="Linux")
        mocker.patch("shutil.which", return_value="/usr/bin/gnome-terminal")

        launcher = get_launcher()

        assert isinstance(launcher, LinuxLauncher)

    def test_get_launcher_unsupported(self, mocker: Mock) -> None:
        """Test get_launcher raises NotImplementedError on Windows."""
        mocker.patch("mc.terminal.launcher.platform.system", return_value="Windows")

        with pytest.raises(NotImplementedError, match="not supported on Windows"):
            get_launcher()

    def test_get_launcher_platform_override(self, mocker: Mock) -> None:
        """Test get_launcher respects platform_override parameter."""
        mocker.patch("shutil.which", return_value="/usr/bin/gnome-terminal")

        # Override to Linux regardless of actual platform
        launcher = get_launcher(platform_override="Linux")

        assert isinstance(launcher, LinuxLauncher)


class TestDetectTerminal:
    """Tests for terminal detection."""

    def test_detect_terminal_iterm2_primary(self, mocker: Mock) -> None:
        """Test iTerm2 detection via TERM_PROGRAM."""
        mocker.patch.dict("os.environ", {"TERM_PROGRAM": "iTerm.app"})

        result = detect_terminal()

        assert result == "iTerm2"

    def test_detect_terminal_iterm2_fallback(self, mocker: Mock) -> None:
        """Test iTerm2 detection via ITERM_SESSION_ID."""
        mocker.patch.dict(
            "os.environ", {"ITERM_SESSION_ID": "w0t0p0:12345678-1234-1234-1234"}
        )

        result = detect_terminal()

        assert result == "iTerm2"

    def test_detect_terminal_terminal_app(self, mocker: Mock) -> None:
        """Test Terminal.app detection."""
        mocker.patch.dict("os.environ", {"TERM_PROGRAM": "Apple_Terminal"}, clear=True)

        result = detect_terminal()

        assert result == "Terminal.app"

    def test_detect_terminal_konsole(self, mocker: Mock) -> None:
        """Test Konsole detection via KONSOLE_DBUS_SERVICE."""
        mocker.patch.dict(
            "os.environ", {"KONSOLE_DBUS_SERVICE": "org.kde.konsole-12345"}, clear=True
        )

        result = detect_terminal()

        assert result == "konsole"

    def test_detect_terminal_gnome(self, mocker: Mock) -> None:
        """Test GNOME Terminal detection."""
        mocker.patch.dict("os.environ", {"COLORTERM": "gnome-terminal"}, clear=True)

        result = detect_terminal()

        assert result == "gnome-terminal"

    def test_detect_terminal_unknown(self, mocker: Mock) -> None:
        """Test detection returns None for unknown terminal."""
        mocker.patch.dict("os.environ", {}, clear=True)

        result = detect_terminal()

        assert result is None


class TestFindAvailableTerminal:
    """Tests for finding available terminal binaries."""

    def test_find_available_terminal_macos_iterm(self, mocker: Mock) -> None:
        """Test finding iTerm2 on macOS."""
        mocker.patch("os.path.exists", side_effect=lambda p: p == "/Applications/iTerm.app")

        result = find_available_terminal("Darwin")

        assert result == "iTerm2"

    def test_find_available_terminal_macos_terminal_app(self, mocker: Mock) -> None:
        """Test finding Terminal.app on macOS when iTerm not available."""
        mocker.patch(
            "os.path.exists",
            side_effect=lambda p: p == "/Applications/Terminal.app",
        )

        result = find_available_terminal("Darwin")

        assert result == "Terminal.app"

    def test_find_available_terminal_macos_none(self, mocker: Mock) -> None:
        """Test returns None when no macOS terminal found."""
        mocker.patch("os.path.exists", return_value=False)

        result = find_available_terminal("Darwin")

        assert result is None

    def test_find_available_terminal_linux_gnome(self, mocker: Mock) -> None:
        """Test finding gnome-terminal on Linux."""
        mocker.patch("shutil.which", side_effect=lambda t: t == "gnome-terminal")

        result = find_available_terminal("Linux")

        assert result == "gnome-terminal"

    def test_find_available_terminal_linux_konsole(self, mocker: Mock) -> None:
        """Test finding konsole on Linux when gnome-terminal not available."""
        mocker.patch("shutil.which", side_effect=lambda t: t == "konsole")

        result = find_available_terminal("Linux")

        assert result == "konsole"

    def test_find_available_terminal_linux_xterm(self, mocker: Mock) -> None:
        """Test finding xterm on Linux as last resort."""
        mocker.patch("shutil.which", side_effect=lambda t: t == "xterm")

        result = find_available_terminal("Linux")

        assert result == "xterm"

    def test_find_available_terminal_linux_none(self, mocker: Mock) -> None:
        """Test returns None when no Linux terminal found."""
        mocker.patch("shutil.which", return_value=None)

        result = find_available_terminal("Linux")

        assert result is None

    def test_find_available_terminal_unsupported_platform(self) -> None:
        """Test returns None for unsupported platform."""
        result = find_available_terminal("Windows")

        assert result is None


class TestMacOSLauncher:
    """Tests for macOS terminal launcher."""

    def test_macos_launcher_iterm2_detection(self, mocker: Mock) -> None:
        """Test MacOSLauncher detects iTerm2 when available."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mocker.patch(
            "subprocess.run",
            return_value=Mock(stdout="true\n"),
        )

        launcher = MacOSLauncher()

        assert launcher.terminal == "iTerm2"

    def test_macos_launcher_terminal_app_fallback(self, mocker: Mock) -> None:
        """Test MacOSLauncher falls back to Terminal.app when iTerm not available."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mocker.patch(
            "subprocess.run",
            return_value=Mock(stdout="false\n"),
        )

        launcher = MacOSLauncher()

        assert launcher.terminal == "Terminal.app"

    def test_macos_launcher_manual_terminal(self) -> None:
        """Test MacOSLauncher respects manually specified terminal."""
        launcher = MacOSLauncher(terminal="Terminal.app")

        assert launcher.terminal == "Terminal.app"

    def test_macos_launcher_escaping(self) -> None:
        """Test AppleScript string escaping."""
        launcher = MacOSLauncher(terminal="iTerm2")

        # Test backslash escaping
        assert launcher._escape_applescript("path\\to\\file") == "path\\\\to\\\\file"

        # Test quote escaping
        assert launcher._escape_applescript('say "hello"') == 'say \\"hello\\"'

        # Test combined escaping
        assert (
            launcher._escape_applescript('C:\\Program Files\\test "app"')
            == 'C:\\\\Program Files\\\\test \\"app\\"'
        )

    def test_macos_launcher_iterm2_script(self) -> None:
        """Test iTerm2 AppleScript generation."""
        launcher = MacOSLauncher(terminal="iTerm2")
        options = LaunchOptions(
            title="Test Window",
            command="echo 'hello world'",
            auto_focus=True,
        )

        script = launcher._build_iterm_script(options)

        assert 'tell application "iTerm"' in script
        assert "activate" in script
        assert "create window with default profile" in script
        assert 'set name to "Test Window"' in script
        assert "write text" in script
        assert "echo 'hello world'" in script

    def test_macos_launcher_terminal_app_script(self) -> None:
        """Test Terminal.app AppleScript generation."""
        launcher = MacOSLauncher(terminal="Terminal.app")
        options = LaunchOptions(
            title="Test Window",
            command="echo 'hello world'",
            auto_focus=True,
        )

        script = launcher._build_terminal_app_script(options)

        assert 'tell application "Terminal"' in script
        assert "activate" in script
        assert "do script" in script
        assert "echo 'hello world'" in script
        assert 'set custom title of front window to "Test Window"' in script

    def test_macos_launcher_launch_iterm2(self, mocker: Mock) -> None:
        """Test launching iTerm2."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        launcher = MacOSLauncher(terminal="iTerm2")
        options = LaunchOptions(
            title="12345678 - Customer - Description",
            command="podman exec -it mc-12345678 bash",
            auto_focus=True,
        )

        launcher.launch(options)

        # Verify osascript called with AppleScript
        assert mock_popen.call_count == 1
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "osascript"
        assert call_args[0][0][1] == "-e"
        assert "iTerm" in call_args[0][0][2]

    def test_macos_launcher_launch_terminal_app(self, mocker: Mock) -> None:
        """Test launching Terminal.app."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        launcher = MacOSLauncher(terminal="Terminal.app")
        options = LaunchOptions(
            title="12345678 - Customer - Description",
            command="podman exec -it mc-12345678 bash",
            auto_focus=True,
        )

        launcher.launch(options)

        # Verify osascript called with AppleScript
        assert mock_popen.call_count == 1
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "osascript"
        assert call_args[0][0][1] == "-e"
        assert "Terminal" in call_args[0][0][2]

    def test_macos_launcher_non_blocking(self, mocker: Mock) -> None:
        """Test terminal launch is non-blocking."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        # Mock threading to prevent actual background thread
        mocker.patch("threading.Thread")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        launcher.launch(options)

        # Popen used (non-blocking), not run()
        assert mock_popen.called
        # Verify it's called with correct args
        assert mock_popen.call_args[0][0][0] == "osascript"

    def test_macos_launcher_missing_osascript(self, mocker: Mock) -> None:
        """Test error when osascript not found."""
        mocker.patch("shutil.which", return_value=None)

        launcher = MacOSLauncher(terminal="iTerm2")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        with pytest.raises(FileNotFoundError, match="osascript not found"):
            launcher.launch(options)

    def test_macos_launcher_launch_failure(self, mocker: Mock) -> None:
        """Test error handling when launch fails."""
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mocker.patch(
            "subprocess.Popen",
            side_effect=subprocess.SubprocessError("Command failed"),
        )

        launcher = MacOSLauncher(terminal="iTerm2")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        with pytest.raises(RuntimeError, match="Failed to launch iTerm2"):
            launcher.launch(options)


class TestLinuxLauncher:
    """Tests for Linux terminal launcher."""

    def test_linux_launcher_gnome_detection(self, mocker: Mock) -> None:
        """Test LinuxLauncher detects gnome-terminal."""
        mocker.patch("shutil.which", side_effect=lambda t: t == "gnome-terminal")

        launcher = LinuxLauncher()

        assert launcher.terminal == "gnome-terminal"

    def test_linux_launcher_konsole_detection(self, mocker: Mock) -> None:
        """Test LinuxLauncher detects konsole when gnome-terminal not available."""
        mocker.patch("shutil.which", side_effect=lambda t: t == "konsole")

        launcher = LinuxLauncher()

        assert launcher.terminal == "konsole"

    def test_linux_launcher_no_terminal_found(self, mocker: Mock) -> None:
        """Test error when no supported terminal found."""
        mocker.patch("shutil.which", return_value=None)

        with pytest.raises(RuntimeError, match="No supported terminal emulator found"):
            LinuxLauncher()

    def test_linux_launcher_manual_terminal(self, mocker: Mock) -> None:
        """Test LinuxLauncher respects manually specified terminal."""
        # Skip auto-detection by providing explicit terminal
        launcher = LinuxLauncher(terminal="konsole")

        assert launcher.terminal == "konsole"

    def test_linux_launcher_gnome_terminal_args(self, mocker: Mock) -> None:
        """Test gnome-terminal command-line arguments."""
        launcher = LinuxLauncher(terminal="gnome-terminal")
        options = LaunchOptions(
            title="Test Window",
            command="echo 'hello world'",
            auto_focus=True,
        )

        args = launcher._build_gnome_terminal_args(options)

        assert args[0] == "gnome-terminal"
        assert "--title=Test Window" in args
        assert "--" in args
        assert "bash" in args
        assert "-c" in args
        assert "echo 'hello world'" in args

    def test_linux_launcher_konsole_args(self, mocker: Mock) -> None:
        """Test konsole command-line arguments."""
        launcher = LinuxLauncher(terminal="konsole")
        options = LaunchOptions(
            title="Test Window",
            command="echo 'hello world'",
            auto_focus=True,
        )

        args = launcher._build_konsole_args(options)

        assert args[0] == "konsole"
        assert "--noclose" in args
        assert "-e" in args
        assert "bash" in args
        assert "-c" in args
        # Title set via escape sequence
        assert any("\\033]0;" in arg and "Test Window" in arg for arg in args)

    def test_linux_launcher_launch_gnome_terminal(self, mocker: Mock) -> None:
        """Test launching gnome-terminal."""
        mocker.patch("shutil.which", return_value="/usr/bin/gnome-terminal")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        launcher = LinuxLauncher(terminal="gnome-terminal")
        options = LaunchOptions(
            title="12345678 - Customer - Description",
            command="podman exec -it mc-12345678 bash",
            auto_focus=True,
        )

        launcher.launch(options)

        # Verify gnome-terminal called
        assert mock_popen.call_count == 1
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "gnome-terminal"

    def test_linux_launcher_launch_konsole(self, mocker: Mock) -> None:
        """Test launching konsole."""
        mocker.patch("shutil.which", return_value="/usr/bin/konsole")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process

        launcher = LinuxLauncher(terminal="konsole")
        options = LaunchOptions(
            title="12345678 - Customer - Description",
            command="podman exec -it mc-12345678 bash",
            auto_focus=True,
        )

        launcher.launch(options)

        # Verify konsole called
        assert mock_popen.call_count == 1
        call_args = mock_popen.call_args
        assert call_args[0][0][0] == "konsole"

    def test_linux_launcher_missing_binary(self, mocker: Mock) -> None:
        """Test error when terminal binary not found."""
        mocker.patch("shutil.which", return_value=None)

        launcher = LinuxLauncher(terminal="gnome-terminal")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        with pytest.raises(FileNotFoundError, match="gnome-terminal not found"):
            launcher.launch(options)

    def test_linux_launcher_non_blocking(self, mocker: Mock) -> None:
        """Test terminal launch is non-blocking."""
        mocker.patch("shutil.which", return_value="/usr/bin/gnome-terminal")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        # Mock threading to prevent actual background thread
        mocker.patch("threading.Thread")

        launcher = LinuxLauncher(terminal="gnome-terminal")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        launcher.launch(options)

        # Popen used (non-blocking), not run()
        assert mock_popen.called
        # Verify it's called with correct args
        assert mock_popen.call_args[0][0][0] == "gnome-terminal"

    def test_linux_launcher_launch_failure(self, mocker: Mock) -> None:
        """Test error handling when launch fails."""
        mocker.patch("shutil.which", return_value="/usr/bin/gnome-terminal")
        mocker.patch(
            "subprocess.Popen",
            side_effect=subprocess.SubprocessError("Command failed"),
        )

        launcher = LinuxLauncher(terminal="gnome-terminal")
        options = LaunchOptions(title="Test", command="echo test", auto_focus=True)

        with pytest.raises(RuntimeError, match="Failed to launch gnome-terminal"):
            launcher.launch(options)
