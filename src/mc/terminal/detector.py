"""Terminal emulator detection via environment variables."""

import os
import shutil
from typing import Sequence


def detect_terminal() -> str | None:
    """Detect current terminal emulator via environment variables.

    Returns:
        Terminal name if detected, None otherwise

    Checks environment variables in order:
        - $TERM_PROGRAM (macOS terminals)
        - $ITERM_SESSION_ID (iTerm2 fallback)
        - $KONSOLE_DBUS_SERVICE (Konsole)
        - $COLORTERM (XFCE Terminal)
    """
    # iTerm2 detection (primary)
    if os.getenv("TERM_PROGRAM") == "iTerm.app":
        return "iTerm2"

    # iTerm2 detection (fallback)
    if os.getenv("ITERM_SESSION_ID"):
        return "iTerm2"

    # Terminal.app detection
    if os.getenv("TERM_PROGRAM") == "Apple_Terminal":
        return "Terminal.app"

    # Konsole detection
    if os.getenv("KONSOLE_DBUS_SERVICE") or os.getenv("KONSOLE_DBUS_SESSION"):
        return "konsole"

    # GNOME Terminal detection (via COLORTERM)
    if os.getenv("COLORTERM") == "gnome-terminal":
        return "gnome-terminal"

    return None


def find_available_terminal(platform_name: str) -> str | None:
    """Find first available terminal binary for platform.

    Args:
        platform_name: Platform name ("Darwin" or "Linux")

    Returns:
        Terminal binary name if found, None otherwise

    Priority order:
        macOS: iTerm, Terminal.app
        Linux: gnome-terminal, konsole, xterm
    """
    if platform_name == "Darwin":
        # macOS terminals (check if applications exist)
        macos_terminals: Sequence[str] = ["iTerm", "Terminal"]
        for term in macos_terminals:
            # On macOS, check if application exists
            app_path = f"/Applications/{term}.app"
            if os.path.exists(app_path):
                return term + ("2" if term == "iTerm" else ".app")
        return None

    elif platform_name == "Linux":
        # Linux terminals (check if binaries exist)
        linux_terminals: Sequence[str] = [
            "gnome-terminal",
            "konsole",
            "xterm",
        ]
        for term in linux_terminals:
            if shutil.which(term):
                return term
        return None

    return None
