"""Runtime mode detection for MC CLI.

This module detects whether the MC CLI is running in controller mode (on the host)
or agent mode (inside a container). This enables different behavior patterns:

- Controller mode: Manages containers, launches terminals, orchestrates workflows
- Agent mode: Executes within containers, provides case workspace environment

Detection uses the MC_RUNTIME_MODE environment variable set by the container
entrypoint. Host environments default to controller mode.
"""

import os
from typing import Literal

RuntimeMode = Literal["controller", "agent"]


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
