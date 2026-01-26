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

    # XFCE Terminal detection
    if os.getenv("COLORTERM") == "xfce4-terminal":
        return "xfce4-terminal"

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
        Linux: gnome-terminal, konsole, xfce4-terminal, xterm
    """
    if platform_name == "Darwin":
        # macOS terminals (check if applications exist)
        terminals = ["iTerm", "Terminal"]
        for term in terminals:
            # On macOS, check if application exists
            app_path = f"/Applications/{term}.app"
            if os.path.exists(app_path):
                return term + ("2" if term == "iTerm" else ".app")
        return None

    elif platform_name == "Linux":
        # Linux terminals (check if binaries exist)
        terminals: Sequence[str] = [
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "xterm",
        ]
        for term in terminals:
            if shutil.which(term):
                return term
        return None

    return None
