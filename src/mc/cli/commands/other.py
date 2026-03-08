"""Other utility commands."""

import logging
import subprocess
import sys
from mc.integrations.ldap import ldap_search

logger = logging.getLogger(__name__)


def go(case_number: str, launch: bool = True) -> None:
    """
    Print or launch Salesforce case URL.

    Args:
        case_number: Case number
        launch: If True (default), launch URL in Chrome; if False, print URL
    """
    url = f"https://gss--c.vf.force.com/apex/Case_View?sbstr={case_number}"

    if launch:
        logger.info("Launching URL in Chrome: %s", url)
        subprocess.run([
            "open",
            "-a", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"{url}"
        ])
    else:
        # Intentional user output - print URL for copy/paste
        print(url)  # print OK


def ls(uid: str, show_all: bool = False) -> None:
    """
    Search for a user in LDAP.

    Args:
        uid: User ID to search for
        show_all: If True, show raw LDAP output
    """
    ldap_search(uid, show_all=show_all)


def version(update: bool = False) -> None:
    """Display MC CLI version and optionally check for updates.

    Args:
        update: If True, force immediate version check (bypasses throttle)
    """
    from mc.version import get_version
    from mc.version_check import VersionChecker

    # Always display current version
    current = get_version()
    print(f"mc version {current}")

    if update:
        # Manual override: force immediate check (synchronous, not background)
        print("Checking for updates...", file=sys.stderr)

        try:
            checker = VersionChecker()
            # Bypass throttle by calling worker directly (not start_background_check)
            checker._perform_version_check()
            print("Version check complete.", file=sys.stderr)
        except Exception as e:
            # Show error for manual command (different from silent auto-check)
            print(f"Error checking for updates: {e}", file=sys.stderr)
            sys.exit(1)
