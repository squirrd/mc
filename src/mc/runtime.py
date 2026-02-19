"""Runtime mode detection for MC CLI.

This module detects whether the MC CLI is running in controller mode (on the host)
or agent mode (inside a container). This enables different behavior patterns:

- Controller mode: Manages containers, launches terminals, orchestrates workflows,
  checks for updates via GitHub API
- Agent mode: Executes within containers, provides case workspace environment,
  disables auto-update (updates managed via container builds)

Detection uses the MC_RUNTIME_MODE environment variable set by the container
entrypoint. Host environments default to controller mode.

Fallback detection checks filesystem indicators (/run/.containerenv, /.dockerenv)
for edge cases where environment variable is missing.

Auto-update guard (should_check_for_updates) prevents version checking when
running in agent mode, with informational messaging via Rich Console.
"""

import os
from pathlib import Path
from typing import Literal

from rich.console import Console

RuntimeMode = Literal["controller", "agent"]

console = Console(stderr=True)


def get_runtime_mode() -> RuntimeMode:
    """Get current runtime mode (controller or agent).

    The runtime mode is determined by the MC_RUNTIME_MODE environment variable:
    - "agent": Running inside a container (set by container entrypoint)
    - "controller": Running on host (default when variable not set)

    Invalid values default to "controller" for safety (host mode is safer default).

    Returns:
        "controller" if running on host, "agent" if running in container

    Example:
        >>> import os
        >>> os.environ["MC_RUNTIME_MODE"] = "agent"
        >>> get_runtime_mode()
        'agent'
        >>> del os.environ["MC_RUNTIME_MODE"]
        >>> get_runtime_mode()
        'controller'
    """
    mode = os.environ.get("MC_RUNTIME_MODE", "controller")

    # Validate mode value - must be exactly "controller" or "agent"
    if mode not in ("controller", "agent"):
        # Invalid value defaults to controller (safer default)
        return "controller"

    return mode  # type: ignore[return-value]


def is_agent_mode() -> bool:
    """Check if running in agent mode (inside container).

    Returns:
        True if running inside container, False if on host

    Example:
        >>> import os
        >>> os.environ["MC_RUNTIME_MODE"] = "agent"
        >>> is_agent_mode()
        True
        >>> is_controller_mode()
        False
    """
    return get_runtime_mode() == "agent"


def is_controller_mode() -> bool:
    """Check if running in controller mode (on host).

    Returns:
        True if running on host, False if inside container

    Example:
        >>> import os
        >>> del os.environ.get("MC_RUNTIME_MODE", None)
        >>> is_controller_mode()
        True
        >>> is_agent_mode()
        False
    """
    return get_runtime_mode() == "controller"


def is_running_in_container() -> bool:
    """Detect if running inside container using layered approach.

    Uses defense-in-depth strategy combining explicit environment variable
    (primary) with filesystem indicators (fallback):

    Priority:
    1. MC_RUNTIME_MODE environment variable (explicit, set by our Containerfile)
    2. Container indicator files (defensive fallback for edge cases)

    Container indicator files checked:
    - /run/.containerenv (Podman standard location)
    - /.containerenv (Podman legacy location)
    - /.dockerenv (Docker standard location)

    Returns:
        True if running in any container context, False if on host

    Example:
        >>> import os
        >>> os.environ["MC_RUNTIME_MODE"] = "agent"
        >>> is_running_in_container()
        True
        >>> del os.environ["MC_RUNTIME_MODE"]
        >>> # Assuming no container indicator files exist
        >>> is_running_in_container()
        False
    """
    # Primary: Check explicit environment variable (most reliable)
    if os.environ.get("MC_RUNTIME_MODE") == "agent":
        return True

    # Fallback: Check filesystem indicators for edge cases
    # (manual podman run, third-party containers, missing ENV directive)
    container_files = [
        Path("/run/.containerenv"),  # Podman v1.0+ standard
        Path("/.containerenv"),       # Podman legacy
        Path("/.dockerenv")           # Docker standard
    ]

    return any(f.exists() for f in container_files)


def should_check_for_updates() -> bool:
    """Determine if version checking should proceed.

    Auto-update functionality should only run in controller mode (on host).
    When running in agent mode (inside container), updates are managed via
    container image builds, not in-place package upgrades.

    Displays informational message when blocking updates in agent mode.

    Returns:
        False if running in agent mode (container), True otherwise

    Example:
        >>> import os
        >>> os.environ["MC_RUNTIME_MODE"] = "agent"
        >>> should_check_for_updates()
        ℹ Updates managed via container builds
        False
        >>> del os.environ["MC_RUNTIME_MODE"]
        >>> should_check_for_updates()
        True
    """
    if is_agent_mode():
        console.print(
            "[yellow]ℹ Updates managed via container builds[/yellow]",
            style="bold"
        )
        return False

    return True
