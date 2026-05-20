"""mc-update entry point module.

This module provides the `mc-update` command as a standalone console_scripts entry point.
It is intentionally kept independent from `mc.cli.main` so that mc-update survives a
partial package upgrade — even if mc's CLI machinery is temporarily broken during the
package replacement, mc-update can still run and complete the upgrade.

Usage:
    mc-update            # Show version status (default: check)
    mc-update upgrade    # Upgrade MC CLI via uv tool upgrade mc
"""

import argparse
import logging
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

import requests

logger = logging.getLogger(__name__)

ExitCode = Literal[0, 1]


_MC_GIT_URL = "git+https://github.com/squirrd/mc"


def _get_uv_env() -> dict[str, str]:
    """Returns subprocess env with UV_TOOL_DIR/UV_TOOL_BIN_DIR for env isolation.

    When MC_ENV is set, uv operations are directed to ~/mc-{env}/tools and ~/mc-{env}/bin
    so that non-prod installs never overwrite the prod binary at ~/.local/bin/mc.
    When MC_ENV is unset (prod), uv uses its default paths unchanged.
    """
    env = dict(os.environ)
    mc_env = os.environ.get("MC_ENV")
    if mc_env:
        env_base = Path.home() / f"mc-{mc_env}"
        env["UV_TOOL_DIR"] = str(env_base / "tools")
        env["UV_TOOL_BIN_DIR"] = str(env_base / "bin")
    return env


def _current_env_label() -> str:
    """Returns the current MC_ENV value, or 'prod' when unset."""
    return os.environ.get("MC_ENV", "prod")


def _run_upgrade() -> int:
    """Run 'uv tool install --reinstall git+https://github.com/squirrd/mc@latest' and return exit code.

    Uses the git URL with @latest tag so that uv installs the latest tagged release
    rather than silently doing nothing (as 'uv tool upgrade mc' does for git-pinned installs).
    Uses capture_output=False so uv's live progress output streams directly
    to the terminal, giving the user real-time feedback during the upgrade.

    Returns:
        Exit code from uv tool install (0 on success, non-zero on failure,
        or 1 if uv is not found on PATH).
    """
    try:
        result = subprocess.run(
            ["uv", "tool", "install", "--reinstall", f"{_MC_GIT_URL}@latest"],
            capture_output=False,
            text=True,
            check=False,
            env=_get_uv_env(),
        )
        return result.returncode
    except FileNotFoundError:
        print(
            "Error: mc-update not found on PATH. Re-install MC CLI and try again.",
            file=sys.stderr,
        )
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
        print(
            "Error: mc not found on PATH after upgrade. Run: mc-update check",
            file=sys.stderr,
        )
        return False


def _print_recovery_instructions() -> None:
    """Print actionable recovery instructions to stderr when upgrade fails."""
    print("", file=sys.stderr)
    print("Upgrade failed. To recover, run:", file=sys.stderr)
    print("  mc-update upgrade", file=sys.stderr)


_GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
_GITHUB_RELEASES_BASE = "https://api.github.com/repos/squirrd/mc/releases"

_AGENT_MODE_PIN_MSG = (
    "mc-update pin/unpin/check is not available in agent mode. "
    "To control the mc version inside a case container, pin the container image instead."
)


def _fetch_releases(count: int) -> list[tuple[str, str]]:
    """Fetch the most recent releases from GitHub.

    Args:
        count: Number of releases to return.

    Returns:
        List of (tag_name, release_name) tuples in descending order (newest first).

    Raises:
        requests.RequestException: On network or API errors.
    """
    response = requests.get(
        _GITHUB_RELEASES_BASE,
        headers=_GITHUB_HEADERS,
        params={"per_page": count},
        timeout=10,
    )
    response.raise_for_status()
    releases = response.json()
    return [(r["tag_name"], r["name"]) for r in releases[:count]]


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

    try:
        result = subprocess.run(
            ["uv", "tool", "install", "--reinstall", f"{_MC_GIT_URL}@v{version}"],
            capture_output=False,
            text=True,
            check=False,
            env=_get_uv_env(),
        )
        if result.returncode != 0:
            print(
                f"Warning: config pinned to {version} but install failed. "
                f"To retry: mc-update pin {version}",
                file=sys.stderr,
            )
            return 1
    except FileNotFoundError:
        print(
            "Error: mc-update not found on PATH. Re-install MC CLI and try again.",
            file=sys.stderr,
        )
        return 1

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
        f"  Environment : {_current_env_label()}",
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

    from mc.config.manager import ConfigManager

    version_config = ConfigManager().get_version_config()
    pinned = version_config.get("pinned_mc", "latest")
    if pinned != "latest":
        print(f"Version pinned to {pinned}. Run mc-update unpin first.", file=sys.stderr)
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


def list_releases(count: int) -> ExitCode:
    """List the most recent available releases from GitHub.

    Fetches release data from GitHub and prints a formatted list to stdout.

    Args:
        count: Number of releases to display.

    Returns:
        0 on success, 1 on failure.
    """
    from mc.runtime import is_agent_mode

    if is_agent_mode():
        print(
            "mc-update list is not available in agent mode.",
            file=sys.stderr,
        )
        return 1

    if count < 1:
        print(
            f"Invalid count: {count}. Must be a positive integer.",
            file=sys.stderr,
        )
        return 1

    try:
        releases = _fetch_releases(count)
    except Exception:
        print(
            "Cannot fetch releases: network unreachable. Try again when online.",
            file=sys.stderr,
        )
        return 1

    print(f"Available releases (latest {len(releases)}):")
    for tag, name in releases:
        print(f"  {tag}  {name}")

    return 0


def main() -> None:
    """mc-update CLI entry point.

    Parses arguments and dispatches to the appropriate subcommand.
    Defaults to 'check' when no subcommand is given.
    Registered as the 'mc-update' console_scripts entry point in pyproject.toml.
    """
    parser = argparse.ArgumentParser(
        prog="mc-update",
        description="MC CLI updater (default: check)",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("upgrade", help="Upgrade MC CLI via uv tool upgrade mc")
    pin_parser = subparsers.add_parser("pin", help="Pin MC CLI to a specific version")
    pin_parser.add_argument("version", help="Version to pin to (e.g. 2.0.3 or v2.0.3)")
    subparsers.add_parser("unpin", help="Remove version pin")
    subparsers.add_parser("check", help="Show current version, latest version, and pin status")
    list_parser = subparsers.add_parser("list", help="List available releases from GitHub")
    list_parser.add_argument(
        "count", nargs="?", default=5, type=int,
        help="Number of releases to show (default: 5)",
    )

    args = parser.parse_args()

    if args.command == "upgrade":
        sys.exit(upgrade())
    elif args.command == "pin":
        sys.exit(pin(args.version))
    elif args.command == "unpin":
        sys.exit(unpin())
    elif args.command == "check":
        sys.exit(check())
    elif args.command == "list":
        sys.exit(list_releases(args.count))
    else:
        sys.exit(check())


if __name__ == "__main__":
    main()
