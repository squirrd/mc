"""Other utility commands."""

import subprocess
from mc.integrations.ldap import ldap_search


def go(case_number, launch=False):
    """
    Print or launch Salesforce case URL.

    Args:
        case_number: Case number
        launch: If True, launch URL in Chrome
    """
    url = f"https://gss--c.vf.force.com/apex/Case_View?sbstr={case_number}"

    if launch:
        print(f"Launching URL in Chrome: {url}")
        subprocess.run([
            "open",
            "-a", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            f"{url}"
        ])
    else:
        print(url)


def ls(uid, show_all=False):
    """
    Search for a user in LDAP.

    Args:
        uid: User ID to search for
        show_all: If True, show raw LDAP output
    """
    ldap_search(uid, show_all=show_all)
