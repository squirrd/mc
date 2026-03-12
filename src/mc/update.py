"""mc-update entry point module.

This module provides the `mc-update` command as a standalone console_scripts entry point.
It is intentionally kept independent from `mc.cli.main` so that mc-update survives a
partial package upgrade — even if mc's CLI machinery is temporarily broken during the
package replacement, mc-update can still run and complete the upgrade.

Usage:
    mc-update upgrade    # Upgrade MC CLI via uv tool upgrade mc
"""

import argparse
import logging
import re
import subprocess
import sys
from typing import Literal

import requests

logger = logging.getLogger(__name__)

ExitCode = Literal[0, 1]


def _run_upgrade() -> int:
    """Run 'uv tool upgrade mc' and return the exit code.

    Uses capture_output=False so uv's live progress output streams directly
    to the terminal, giving the user real-time feedback during the upgrade.

    Returns:
        Exit code from uv tool upgrade (0 on success, non-zero on failure,
        or 1 if uv is not found on PATH).
    """
    try:
        result = subprocess.run(
            ["uv", "tool", "upgrade", "mc"],
            capture_output=False,
            text=True,
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        print("Error: uv not found. Install from https://docs.astral.sh/uv/", file=sys.stderr)
        return 1


def _verify_mc_version() -> bool:
    """Run 'mc --version' to confirm the upgrade succeeded.

    Uses capture_output=True to inspect and print the version output.

    Returns:
        True if mc --version exits 0 (upgrade verified), False otherwise.
    """
    try:
        result = subprocess.run(
            ["mc", "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print(result.stdout.strip())
            return True
        return False
    except FileNotFoundError:
        print("Error: mc not found on PATH after upgrade. Check: uv tool list", file=sys.stderr)
        return False


def _print_recovery_instructions() -> None:
    """Print actionable recovery instructions to stderr when upgrade fails."""
    print("", file=sys.stderr)
    print("Upgrade failed. To recover, run:", file=sys.stderr)
    print("  uv tool install --force mc", file=sys.stderr)


_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_GITHUB_RELEASES_BASE = "https://api.github.com/repos/squirrd/mc/releases"

_AGENT_MODE_PIN_MSG = (
    "mc-update pin/unpin/check is not available in agent mode. "
    "To control the mc version inside a case container, pin the container image instead."
)


def _fetch_latest_version() -> str | None:
    """Fetch the latest release version from GitHub.

    Returns:
        Version string (e.g. "2.0.5") on success, or None on any network/API error.
    """
    try:
        response = requests.get(
            f"{_GITHUB_RELEASES_BASE}/latest",
            headers=_GITHUB_HEADERS,
            timeout=10,
        )
        if response.status_code == 200:
            return str(response.json()["tag_name"]).lstrip("v")
        return None
    except Exception:
        return None


def _validate_version_exists(version: str) -> bool:
    """Check if a specific version tag exists in GitHub releases.

    Args:
        version: Version string without leading 'v' (e.g. "2.0.3").

    Returns:
        True if the release exists (HTTP 200), False if not found (HTTP 404).

    Raises:
        requests.RequestException: On any non-200/404 response or network failure.
    """
    response = requests.get(
        f"{_GITHUB_RELEASES_BASE}/tags/v{version}",
        headers=_GITHUB_HEADERS,
        timeout=10,
    )
    if response.status_code == 200:
        return True
    if response.status_code == 404:
        return False
    raise requests.RequestException(
        f"Unexpected status {response.status_code} from GitHub API"
    )


def pin(version: str) -> ExitCode:
    """Pin MC CLI to a specific version.

    Validates format, checks GitHub for release existence, and writes the pin
    to config.toml via ConfigManager.

    Args:
        version: Version string to pin to (e.g. "2.0.3" or "v2.0.3").

    Returns:
        0 on success, 1 on any validation or network failure.
    """
    from mc.runtime import is_agent_mode

    if is_agent_mode():
        print(_AGENT_MODE_PIN_MSG, file=sys.stderr)
        return 1

    version = version.lstrip("v")

    if not re.match(r"^\d+\.\d+\.\d+$", version):
        print(
            f"Invalid version format '{version}'. Expected format: 2.0.3 or v2.0.3",
            file=sys.stderr,
        )
        return 1

    try:
        exists = _validate_version_exists(version)
    except requests.RequestException:
        print(
            "Cannot validate version: network unreachable. Try again when online.",
            file=sys.stderr,
        )
        return 1

    if not exists:
        print(f"Version {version} not found on GitHub releases.", file=sys.stderr)
        return 1

    from mc.config.manager import ConfigManager

    ConfigManager().update_version_config(pinned_mc=version)
    print(f"Pinned to {version}. Run mc-update unpin to remove.")
    return 0


def unpin() -> ExitCode:
    """Remove any active version pin, restoring 'latest' tracking.

    Returns:
        0 always (no pin or pin removed successfully).
    """
    from mc.runtime import is_agent_mode

    if is_agent_mode():
        print(_AGENT_MODE_PIN_MSG, file=sys.stderr)
        return 1

    from mc.config.manager import ConfigManager

    version_config = ConfigManager().get_version_config()
    if version_config["pinned_mc"] == "latest":
        print("No pin active.")
        return 0

    ConfigManager().update_version_config(pinned_mc="latest")
    print("Pin removed.")
    return 0


def check() -> ExitCode:
    """Display current version, latest version, and pin status.

    Returns:
        0 always.
    """
    from mc.runtime import is_agent_mode

    if is_agent_mode():
        print(_AGENT_MODE_PIN_MSG, file=sys.stderr)
        return 1

    from mc.version import get_version

    installed = get_version()

    from mc.config.manager import ConfigManager

    version_config = ConfigManager().get_version_config()
    pin_value = version_config["pinned_mc"]

    latest = _fetch_latest_version()

    lines = [
        "Version status:",
        f"  Installed : {installed}",
    ]

    if latest is not None:
        lines.append(f"  Latest    : {latest}")
    else:
        lines.append("  Latest    : unavailable (network error)")

    if pin_value == "latest":
        lines.append("  Pin       : none")
    else:
        lines.append(f"  Pin       : {pin_value}")

    if latest is not None:
        from packaging.version import InvalidVersion, Version

        try:
            if pin_value != "latest":
                lines.append("  Update    : pinned (run mc-update unpin to upgrade)")
            elif Version(latest) > Version(installed):
                lines.append("  Update    : available")
            else:
                lines.append("  Update    : up to date")
        except InvalidVersion:
            pass  # Omit Update line on unparseable version strings

    for line in lines:
        print(line)
    return 0


def upgrade() -> ExitCode:
    """Execute the mc-update upgrade command.

    Guards against agent mode (running inside a container), runs the uv upgrade,
    and verifies the result. Prints recovery instructions on failure.

    Returns:
        0 on success, 1 on failure.
    """
    from mc.runtime import is_agent_mode

    if is_agent_mode():
        print(
            "mc-update is not available in agent mode. Run mc-update on the host.",
            file=sys.stderr,
        )
        return 1

    print("Upgrading MC CLI...")
    rc = _run_upgrade()

    if rc != 0:
        _print_recovery_instructions()
        return 1

    print("Verifying upgrade...")
    if not _verify_mc_version():
        _print_recovery_instructions()
        return 1

    print("Upgrade complete.")
    return 0


def main() -> None:
    """mc-update CLI entry point.

    Parses arguments and dispatches to the appropriate subcommand.
    Registered as the 'mc-update' console_scripts entry point in pyproject.toml.
    """
    parser = argparse.ArgumentParser(prog="mc-update", description="MC CLI updater")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("upgrade", help="Upgrade MC CLI via uv tool upgrade")

    args = parser.parse_args()

    if args.command == "upgrade":
        sys.exit(upgrade())
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
