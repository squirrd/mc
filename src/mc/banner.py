"""Update notification banner for MC CLI startup."""
from __future__ import annotations

import sys
import threading
from datetime import date, datetime
from typing import Optional

_TIMEOUT_SECONDS = 1.5
_BANNER_TITLE = "MC Update Available"
_BORDER_STYLE = "yellow"


def _is_version_invocation() -> bool:
    """Return True if this invocation is 'mc --version'."""
    return len(sys.argv) > 1 and sys.argv[1] == "--version"


def _already_shown_today() -> bool:
    """Check whether the banner was already shown today (calendar day).

    Returns:
        True if last_banner_shown date matches today's date, False otherwise.
    """
    from mc.config.manager import ConfigManager

    version_config = ConfigManager().get_version_config()
    last_banner_shown: Optional[str] = version_config.get("last_banner_shown")
    if last_banner_shown is None:
        return False
    try:
        parsed_date = datetime.fromisoformat(last_banner_shown).date()
        return parsed_date == date.today()
    except (ValueError, TypeError):
        return False


def _fetch_with_timeout() -> Optional[str]:
    """Fetch latest version from GitHub with a hard timeout.

    Uses a daemon thread so we never block the CLI beyond _TIMEOUT_SECONDS.

    Returns:
        Version string on success, None on timeout or network failure.
    """
    from mc.update import _fetch_latest_version

    result: list[Optional[str]] = [None]
    done = threading.Event()

    def _worker() -> None:
        result[0] = _fetch_latest_version()
        done.set()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()

    if not done.wait(timeout=_TIMEOUT_SECONDS):
        print("Update check timed out.", file=sys.stderr)
        return None

    return result[0]


def _write_suppression_timestamp() -> None:
    """Write the current datetime as last_banner_shown in config.

    Only writes when running interactively (stdout is a TTY).
    """
    if not sys.stdout.isatty():
        return
    from mc.config.manager import ConfigManager

    ConfigManager().update_version_config(
        last_banner_shown=datetime.now().isoformat(timespec="seconds")
    )


def _render_banner(current: str, latest: str, pinned: Optional[str]) -> None:
    """Render the update notification banner to stderr using Rich.

    Args:
        current: Installed version string (without leading 'v').
        latest: Latest available version string (without leading 'v').
        pinned: Active pin version string if pinned, else None.
    """
    from rich.console import Console
    from rich.panel import Panel

    console = Console(stderr=True)

    if pinned is None:
        content = f"v{current} \u2192 v{latest}\nRun: mc-update upgrade"
    else:
        content = f"v{latest} available (pinned at v{current})\nRun: mc-update unpin to upgrade"

    panel = Panel(content, title=_BANNER_TITLE, border_style=_BORDER_STYLE)

    console.print("")
    console.print(panel)
    console.print("")


def show_update_banner() -> None:
    """Show update banner on stderr if a newer version is available.

    - Skips entirely if not a TTY (piped run)
    - Skips if today's date matches last_banner_shown date in config
    - Fetches latest version from GitHub with a 1.5s timeout
    - On timeout: prints brief note to stderr, does NOT write suppression timestamp
    - On network failure: returns None from _fetch_with_timeout (treated as timeout)
    - Skips if mc --version invocation
    """
    if _is_version_invocation():
        return

    if not sys.stdout.isatty():
        return

    if _already_shown_today():
        return

    from mc.version import get_version

    current = get_version()

    from mc.config.manager import ConfigManager

    version_config = ConfigManager().get_version_config()
    pinned_mc: str = version_config["pinned_mc"]

    latest = _fetch_with_timeout()
    if latest is None:
        return

    from packaging.version import InvalidVersion, Version

    try:
        is_newer = Version(latest) > Version(current)
    except InvalidVersion:
        return

    if not is_newer:
        return

    pinned_arg: Optional[str] = pinned_mc if pinned_mc != "latest" else None
    _render_banner(current, latest, pinned_arg)
    _write_suppression_timestamp()
