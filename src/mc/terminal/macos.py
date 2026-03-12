"""macOS terminal launchers (iTerm2, Terminal.app)."""

from __future__ import annotations

import asyncio
import datetime
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Literal

from mc.terminal.launcher import LaunchOptions

logger = logging.getLogger(__name__)

try:
    import iterm2 as _iterm2_module  # noqa: F401

    _ITERM2_LIB_AVAILABLE = True
except ImportError:
    _ITERM2_LIB_AVAILABLE = False

_ITERM2_FALLBACK_SENTINEL = Path.home() / ".cache" / "mc" / "iterm2_fallback_notice_date"


def _should_show_iterm2_fallback_notice() -> bool:
    today = datetime.date.today().isoformat()
    try:
        return _ITERM2_FALLBACK_SENTINEL.read_text().strip() != today
    except (OSError, FileNotFoundError):
        return True


def _record_iterm2_fallback_notice() -> None:
    today = datetime.date.today().isoformat()
    _ITERM2_FALLBACK_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    _ITERM2_FALLBACK_SENTINEL.write_text(today)


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
        self._last_api_window_id: str | None = None

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

    def find_window_by_title(self, title: str) -> bool:
        """Check if a window with matching title exists.

        Args:
            title: Window title to search for (format: "CASE:Customer:Description:/path")

        Returns:
            True if window found, False otherwise
        """
        if not shutil.which("osascript"):
            return False

        escaped_title = self._escape_applescript(title)

        # Extract case number from title for more reliable searching
        # Title format: "CASE:Customer:Description:/path" -> extract "CASE"
        case_number = title.split(":")[0] if ":" in title else title
        escaped_case = self._escape_applescript(case_number)

        if self.terminal == "iTerm2":
            # Search using the full title first (works when window is idle)
            # If not found, search for case number (works when command is running)
            script = f'''
tell application "iTerm"
    repeat with theWindow in windows
        repeat with theTab in tabs of theWindow
            tell current session of theTab
                set sessionName to name
                -- Try exact match first (when window is idle)
                if sessionName is "{escaped_title}" then
                    return true
                end if
                -- Then try substring match (catches partial matches)
                if sessionName contains "{escaped_title}" then
                    return true
                end if
                -- Finally check if the case number appears (when command is running)
                if sessionName contains "{escaped_case}" then
                    return true
                end if
            end tell
        end repeat
    end repeat
    return false
end tell
'''
        else:  # Terminal.app
            script = f'''
tell application "Terminal"
    repeat with theWindow in windows
        if custom title of theWindow contains "{escaped_title}" then
            return true
        end if
    end repeat
    return false
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def focus_window_by_title(self, title: str) -> bool:
        """Focus window with matching title.

        Args:
            title: Window title to search for (format: "CASE:Customer:Description:/path")

        Returns:
            True if window found and focused, False otherwise
        """
        if not shutil.which("osascript"):
            return False

        escaped_title = self._escape_applescript(title)

        # Extract case number for fallback search
        case_number = title.split(":")[0] if ":" in title else title
        escaped_case = self._escape_applescript(case_number)

        if self.terminal == "iTerm2":
            script = f'''
tell application "iTerm"
    activate
    repeat with theWindow in windows
        repeat with theTab in tabs of theWindow
            tell current session of theTab
                set sessionName to name
                set shouldFocus to false
                -- Try exact match, substring match, or case number match
                if sessionName is "{escaped_title}" then
                    set shouldFocus to true
                else if sessionName contains "{escaped_title}" then
                    set shouldFocus to true
                else if sessionName contains "{escaped_case}" then
                    set shouldFocus to true
                end if

                if shouldFocus then
                    select theWindow
                    select theTab
                    return true
                end if
            end tell
        end repeat
    end repeat
    return false
end tell
'''
        else:  # Terminal.app
            script = f'''
tell application "Terminal"
    activate
    repeat with theWindow in windows
        if custom title of theWindow contains "{escaped_title}" then
            set frontmost of theWindow to true
            set index of theWindow to 1
            return true
        end if
    end repeat
    return false
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def _capture_window_id(self) -> str | None:
        """Capture window ID after terminal creation.

        Returns:
            Window ID as string, or None if capture fails

        When the last launch used the Python API, returns the window_id
        captured directly from the API. Otherwise, falls back to AppleScript
        to capture the current/front window ID.
        """
        # If last launch used the Python API, return its window_id directly
        api_id = self._last_api_window_id
        if api_id is not None:
            self._last_api_window_id = None  # consume it
            return api_id

        if not shutil.which("osascript"):
            return None

        if self.terminal == "iTerm2":
            script = '''
tell application "iTerm"
    return id of current window as text
end tell
'''
        else:  # Terminal.app
            script = '''
tell application "Terminal"
    return id of front window as text
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
            return None
        except Exception:
            return None

    def _window_exists_by_id_api(self, window_id: str) -> bool | None:
        """Check window existence via Python API. Returns None if API unavailable."""
        if not _ITERM2_LIB_AVAILABLE:
            return None
        import iterm2

        result: list[bool | None] = [None]

        async def _main(connection: iterm2.Connection) -> None:
            try:
                async with asyncio.timeout(5):
                    app = await iterm2.async_get_app(connection)
                    window = app.get_window_by_id(window_id)
                    result[0] = window is not None
            except asyncio.TimeoutError:
                pass

        try:
            iterm2.run_until_complete(_main)
        except Exception:
            pass
        return result[0]

    def _window_exists_by_id(self, window_id: str) -> bool:
        """Validate if window with specific ID still exists.

        Args:
            window_id: Window ID to check (as string)

        Returns:
            True if window exists, False otherwise

        Used as validator callback for WindowRegistry.lookup() operations.
        For iTerm2, tries the Python API first; falls back to AppleScript
        if the API is unavailable. For Terminal.app, uses AppleScript only.
        """
        if self.terminal == "iTerm2":
            api_result = self._window_exists_by_id_api(window_id)
            if api_result is not None:
                return api_result
            # API unavailable — fall through to AppleScript

        if not shutil.which("osascript"):
            return False

        escaped_id = self._escape_applescript(window_id)

        if self.terminal == "iTerm2":
            script = f'''
tell application "iTerm"
    try
        repeat with theWindow in windows
            if (id of theWindow as text) is "{escaped_id}" then
                return true
            end if
        end repeat
        return false
    on error
        return false
    end try
end tell
'''
        else:  # Terminal.app
            script = f'''
tell application "Terminal"
    try
        repeat with theWindow in windows
            if (id of theWindow as text) is "{escaped_id}" then
                return true
            end if
        end repeat
        return false
    on error
        return false
    end try
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() == "true"
        except Exception:
            return False

    def _focus_window_by_id_api(self, window_id: str) -> bool | None:
        """Focus window via Python API. Returns None if API unavailable."""
        if not _ITERM2_LIB_AVAILABLE:
            return None
        import iterm2

        result: list[bool | None] = [None]

        async def _main(connection: iterm2.Connection) -> None:
            try:
                async with asyncio.timeout(5):
                    app = await iterm2.async_get_app(connection)
                    window = app.get_window_by_id(window_id)
                    if window is None:
                        result[0] = False
                        return
                    await app.async_activate()
                    await window.async_activate()
                    result[0] = True
            except asyncio.TimeoutError:
                pass

        try:
            iterm2.run_until_complete(_main)
        except Exception:
            pass
        return result[0]

    def focus_window_by_id(self, window_id: str) -> bool:
        """Focus window by ID, handling minimized windows and cross-Space switching.

        Args:
            window_id: Window ID to focus (as string)

        Returns:
            True if window found and focused, False otherwise

        For iTerm2, tries the Python API first; falls back to AppleScript if
        the API is unavailable. Un-minimizes Dock-minimized windows and
        switches macOS Spaces if needed.
        """
        if self.terminal == "iTerm2":
            api_result = self._focus_window_by_id_api(window_id)
            if api_result is not None:
                return api_result
            # API unavailable — fall through to AppleScript

        if not shutil.which("osascript"):
            return False

        escaped_id = self._escape_applescript(window_id)

        if self.terminal == "iTerm2":
            script = f'''
tell application "iTerm"
    activate
    repeat with theWindow in windows
        if (id of theWindow as text) is "{escaped_id}" then
            -- Un-minimize if needed
            if miniaturized of theWindow then
                set miniaturized of theWindow to false
            end if
            -- Bring to front
            set index of theWindow to 1
            return true
        end if
    end repeat
    return false
end tell
'''
        else:  # Terminal.app
            script = f'''
tell application "Terminal"
    activate
    repeat with theWindow in windows
        if (id of theWindow as text) is "{escaped_id}" then
            -- Un-minimize if needed
            if miniaturized of theWindow then
                set miniaturized of theWindow to false
            end if
            -- Bring to front
            set index of theWindow to 1
            return true
        end if
    end repeat
    return false
end tell
'''

        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout.strip() == "true"
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    def _build_iterm_script(self, options: LaunchOptions) -> str:
        """Build AppleScript for launching iTerm2.

        Args:
            options: Launch configuration

        Returns:
            AppleScript code

        Note: This method is kept for backwards compatibility and test coverage.
        It is no longer the primary code path for iTerm2 window creation —
        the Python API (_launch_via_iterm2_api) is used instead when available.
        """
        escaped_command = self._escape_applescript(options.command)
        escaped_title = self._escape_applescript(options.title)

        script = f'''
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        set name to "{escaped_title}"
        delay 0.1
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

    def _launch_via_iterm2_api(self, options: LaunchOptions) -> str | None:
        """Launch iTerm2 window via Python API. Returns window_id or None.

        Args:
            options: Launch configuration

        Returns:
            Window ID string on success, None on timeout or exception.

        Bridges the synchronous launch() to the async iterm2 API.
        """
        import iterm2  # imported here — guarded by _ITERM2_LIB_AVAILABLE check upstream

        result: list[str | None] = [None]

        async def _main(connection: iterm2.Connection) -> None:
            try:
                async with asyncio.timeout(5):
                    window = await iterm2.Window.async_create(
                        connection,
                        profile="MCC-Term",
                        command=options.command,
                    )
                    if window is not None:
                        result[0] = window.window_id
            except asyncio.TimeoutError:
                pass  # result stays None → caller falls back

        iterm2.run_until_complete(_main)
        return result[0]

    def _try_iterm2_api(self, options: LaunchOptions) -> str | None:
        """Attempt iTerm2 Python API launch. Returns window_id or None if unavailable.

        Args:
            options: Launch configuration

        Returns:
            Window ID string on success, None if API unavailable or failed.

        Safe wrapper around _launch_via_iterm2_api — catches all exceptions
        from run_until_complete (connection refused, API disabled, etc.).
        """
        if not _ITERM2_LIB_AVAILABLE:
            return None
        try:
            return self._launch_via_iterm2_api(options)
        except Exception:
            logger.debug("iTerm2 Python API unavailable", exc_info=True)
            return None

    def launch(self, options: LaunchOptions) -> None:
        """Launch a new terminal window.

        Args:
            options: Launch configuration

        Raises:
            FileNotFoundError: If osascript not found and iTerm2 API is unavailable
            RuntimeError: If terminal launch fails
        """
        if self.terminal == "iTerm2":
            window_id = self._try_iterm2_api(options)
            if window_id is not None:
                # API success — store window_id for _capture_window_id() to return
                self._last_api_window_id = window_id
                return
            # API unavailable — show fallback notice (once per day) then use Terminal.app path
            if _should_show_iterm2_fallback_notice():
                print(
                    "iTerm2 API unavailable, using Terminal.app. "
                    "Enable via iTerm2 > Settings > General > Magic > Enable Python API",
                    file=sys.stderr,
                )
                _record_iterm2_fallback_notice()
            # Fall through to Terminal.app AppleScript path
            script = self._build_terminal_app_script(options)
        else:
            script = self._build_terminal_app_script(options)

        # Check osascript availability (needed for Terminal.app fallback path)
        if not shutil.which("osascript"):
            raise FileNotFoundError(
                "osascript not found. AppleScript required for macOS terminal launching."
            )

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
