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
import subprocess
import sys
from typing import Literal

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
