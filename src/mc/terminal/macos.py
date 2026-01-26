"""macOS terminal launchers (iTerm2, Terminal.app)."""

import shutil
import subprocess
from typing import Literal

from mc.terminal.launcher import LaunchOptions


class MacOSLauncher:
    """macOS terminal launcher supporting iTerm2 and Terminal.app."""

    def __init__(
        self, terminal: Literal["iTerm2", "Terminal.app"] | None = None
    ) -> None:
        """Initialize macOS launcher.

        Args:
            terminal: Specific terminal to use, or None for auto-detection
        """
        self.terminal = terminal or self._detect_terminal()

    def _detect_terminal(self) -> Literal["iTerm2", "Terminal.app"]:
        """Detect available terminal application.

        Returns:
            Available terminal name

        Priority: iTerm2 > Terminal.app
        """
        # Check for iTerm2
        if self._is_iterm_installed():
            return "iTerm2"

        # Fall back to Terminal.app (always available on macOS)
        return "Terminal.app"

    def _is_iterm_installed(self) -> bool:
        """Check if iTerm2 is installed.

        Returns:
            True if iTerm2.app exists
        """
        return shutil.which("osascript") is not None and (
            subprocess.run(
                ["osascript", "-e", 'exists application "iTerm"'],
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
            == "true"
        )

    def _escape_applescript(self, text: str) -> str:
        """Escape special characters for AppleScript string literals.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for AppleScript

        Escapes backslashes and quotes to prevent injection.
        """
        text = text.replace("\\", "\\\\")  # Escape backslashes first
        text = text.replace('"', '\\"')  # Escape quotes
        return text

    def _build_iterm_script(self, options: LaunchOptions) -> str:
        """Build AppleScript for launching iTerm2.

        Args:
            options: Launch configuration

        Returns:
            AppleScript code
        """
        escaped_command = self._escape_applescript(options.command)
        escaped_title = self._escape_applescript(options.title)

        script = f'''
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        set name to "{escaped_title}"
        write text "{escaped_command}"
    end tell
end tell
'''
        return script

    def _build_terminal_app_script(self, options: LaunchOptions) -> str:
        """Build AppleScript for launching Terminal.app.

        Args:
            options: Launch configuration

        Returns:
            AppleScript code
        """
        escaped_command = self._escape_applescript(options.command)
        escaped_title = self._escape_applescript(options.title)

        script = f'''
tell application "Terminal"
    activate
    do script "{escaped_command}"
    set custom title of front window to "{escaped_title}"
end tell
'''
        return script

    def launch(self, options: LaunchOptions) -> None:
        """Launch a new terminal window.

        Args:
            options: Launch configuration

        Raises:
            FileNotFoundError: If osascript not found
            RuntimeError: If terminal launch fails
        """
        # Check osascript availability
        if not shutil.which("osascript"):
            raise FileNotFoundError(
                "osascript not found. AppleScript required for macOS terminal launching."
            )

        # Build appropriate AppleScript
        if self.terminal == "iTerm2":
            script = self._build_iterm_script(options)
        else:
            script = self._build_terminal_app_script(options)

        # Launch terminal (non-blocking)
        try:
            process = subprocess.Popen(
                ["osascript", "-e", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Don't wait for completion - return to prompt immediately
            # Background cleanup to prevent zombie processes
            def cleanup() -> None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

            import threading

            threading.Thread(target=cleanup, daemon=True).start()

        except Exception as e:
            raise RuntimeError(f"Failed to launch {self.terminal}: {e}") from e
