"""Other utility commands."""

import logging
import subprocess
from mc.integrations.ldap import ldap_search

logger = logging.getLogger(__name__)


def go(case_number: str, launch: bool = False) -> None:
    """
    Print or launch Salesforce case URL.

    Args:
        case_number: Case number
        launch: If True, launch URL in Chrome
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
