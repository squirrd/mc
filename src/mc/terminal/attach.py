"""Terminal attachment orchestration for container access.

Integrates container lifecycle, shell customization, and terminal launching to
provide seamless terminal attachment via 'mc case <number>' command with
auto-create, auto-start, and TTY detection.
"""

import os
import sys
import logging
from typing import Any

from mc.config.manager import ConfigManager
from mc.container.manager import ContainerManager
from mc.integrations.redhat_api import RedHatAPIClient
from mc.terminal.launcher import LaunchOptions, get_launcher
from mc.terminal.registry import WindowRegistry
from mc.terminal.shell import write_bashrc
from mc.utils.validation import validate_case_number
from mc.utils.cache import get_case_metadata
from mc.utils.formatters import shorten_and_format

logger = logging.getLogger(__name__)


def should_launch_terminal() -> bool:
    """Check if stdout is a TTY for terminal launch.

    Returns:
        True if interactive terminal, False if piped/redirected

    Example:
        >>> should_launch_terminal()  # In terminal
        True
        >>> should_launch_terminal()  # When piped (e.g., mc case 12345678 | grep foo)
        False
    """
    return sys.stdout.isatty()


def build_exec_command(container_id: str, bashrc_path: str, case_number: str) -> str:
    """Build podman exec command string for terminal attachment.

    Args:
        container_id: Container ID or name
        bashrc_path: Absolute path to custom bashrc file on host
        case_number: Case number for PS1 prompt

    Returns:
        Complete podman exec command string with auto-close on exit

    Example:
        >>> build_exec_command("mc-12345678", "/path/to/bashrc", "12345678")
        'podman exec -it --env BASH_ENV=/path/to/bashrc --env PS1=[MC-12345678] \\w\\$ mc-12345678 /bin/bash; exit'
    """
    # Build command with BASH_ENV for custom config and PS1 for prompt
    # Use single quotes to prevent shell glob expansion of brackets and handle paths with spaces
    # Append '; exit' to auto-close terminal when shell exits
    return (
        f"podman exec -it "
        f"--env 'BASH_ENV={bashrc_path}' "
        f"--env 'PS1=[MC-{case_number}] \\w\\$ ' "
        f"{container_id} /bin/bash; exit"
    )


def build_window_title(case_number: str, customer_name: str, description: str, vm_path: str = "/case") -> str:
    """Format window title per CONTEXT.md requirements.

    Truncates description if total length exceeds 100 characters to keep
    window title readable.

    Args:
        case_number: Case number (e.g., "12345678")
        customer_name: Customer name
        description: Case description/summary
        vm_path: Virtual machine path (default: "/case")

    Returns:
        Formatted window title string

    Example:
        >>> build_window_title("12345678", "ACME Corp", "Server down")
        "12345678:ACME Corp:Server down:/case"
    """
    # Build base title with colon separators
    # Format: {case}:{customer}:{description}:/{vm-path}
    base = f"{case_number}:{customer_name}:"
    suffix = f":/{vm_path}"
    base_len = len(base) + len(suffix)

    # Truncate description if needed to keep under 100 chars total
    max_desc_len = 100 - base_len
    if len(description) > max_desc_len and max_desc_len > 3:
        description = description[:max_desc_len - 3] + "..."

    return base + description + suffix


def attach_terminal(
    case_number: str,
    config_manager: ConfigManager,
    api_client: RedHatAPIClient,
    container_manager: ContainerManager,
) -> None:
    """Complete workflow for terminal attachment to case container.

    Orchestrates the entire terminal attachment process:
    1. Validates case number format
    2. Checks TTY (must be interactive terminal)
    3. Fetches case metadata from Red Hat API (with caching)
    4. Auto-creates container if missing
    5. Auto-starts container if stopped
    6. Generates custom bashrc with welcome banner
    7. Launches new terminal window with podman exec command

    Args:
        case_number: Case number (must be 8 digits)
        config_manager: Configuration manager for base directory
        api_client: Red Hat API client for case metadata
        container_manager: Container manager for lifecycle operations

    Raises:
        RuntimeError: If TTY check fails, Red Hat API fails, container
                     operations fail, or terminal launch fails
    """
    logger.info("Attaching terminal for case %s", case_number)

    # Import platform-specific launchers
    from mc.terminal.macos import MacOSLauncher

    # 1. Check TTY - must be interactive terminal
    if not should_launch_terminal():
        raise RuntimeError(
            "mc case command requires interactive terminal. "
            "This command cannot be used in pipes or scripts."
        )

    # 2. Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        raise RuntimeError(str(e)) from e

    # 3. Fetch case metadata from Red Hat API (with caching)
    try:
        logger.debug("Fetching case metadata from Red Hat API for case %s", case_number)
        case_details, account_details, was_cached = get_case_metadata(case_number, api_client)
        if was_cached:
            logger.debug("Using cached case metadata for case %s", case_number)
    except Exception as e:
        error_msg = (
            f"Failed to fetch case metadata for case {case_number}. "
            f"Check network and credentials. Error: {e}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    # Extract metadata with fallbacks
    customer_name = account_details.get("name", "Unknown")
    description = case_details.get("summary", "")

    # 4. Check if container exists, auto-create if missing
    status_info = container_manager.status(case_number)

    if status_info["status"] == "missing":
        # Auto-create container
        print("Creating container...")
        logger.info("Container missing for case %s, auto-creating", case_number)

        try:
            # Get workspace path from config
            base_dir = config_manager.get("base_directory", os.path.expanduser("~/mc"))

            # Format customer and description for path
            customer_formatted = shorten_and_format(customer_name)
            description_formatted = shorten_and_format(description)

            # Construct workspace path: {base_dir}/cases/{customer}/{case}-{description}
            workspace_path = f"{base_dir}/cases/{customer_formatted}/{case_number}-{description_formatted}"

            # Create container with workspace mount
            container_manager.create(
                case_number=case_number,
                workspace_path=workspace_path,
                customer_name=customer_name
            )
        except Exception as e:
            error_msg = (
                f"Failed to create container for case {case_number}. "
                f"Podman error: {e}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    elif status_info["status"] in ("stopped", "exited"):
        # Container exists but stopped - auto-start handled by _get_or_restart
        logger.debug("Container stopped for case %s, will auto-start on exec", case_number)

    # 5. Get workspace path (from status or construct)
    workspace_path = status_info.get("workspace_path")  # type: ignore[assignment]
    if not workspace_path:
        # Format customer and description for path
        customer_formatted = shorten_and_format(customer_name)
        description_formatted = shorten_and_format(description)

        # Construct workspace path: {base_dir}/cases/{customer}/{case}-{description}
        base_dir = config_manager.get("base_directory", os.path.expanduser("~/mc"))
        workspace_path = f"{base_dir}/cases/{customer_formatted}/{case_number}-{description_formatted}"

    # 6. Build case metadata dict for bashrc
    case_metadata: dict[str, Any] = {
        "case_number": case_number,
        "customer_name": customer_name,
        "description": description,
        "summary": case_details.get("summary", ""),
        "status": case_details.get("status", ""),
        "severity": case_details.get("severity", ""),
    }

    # 7. Generate and write custom bashrc
    try:
        logger.debug("Generating custom bashrc for case %s", case_number)
        bashrc_path = write_bashrc(case_number, case_metadata)
    except Exception as e:
        error_msg = f"Failed to generate bashrc for case {case_number}: {e}"
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    # 8. Build podman exec command
    container_id = f"mc-{case_number}"
    exec_command = build_exec_command(container_id, bashrc_path, case_number)

    # 9. Build window title
    window_title = build_window_title(case_number, customer_name, description)

    # 10. Get terminal launcher
    try:
        launcher = get_launcher()
    except Exception as e:
        error_msg = (
            f"Failed to detect terminal launcher. "
            f"Run: mc --check-terminal. Error: {e}"
        )
        logger.error(error_msg)
        raise RuntimeError(error_msg) from e

    # 11. Check WindowRegistry for existing window (macOS only - Phase 16)
    window_exists = False
    if isinstance(launcher, MacOSLauncher):
        # Initialize registry and check for existing window ID
        registry = WindowRegistry()

        # Look up window ID with lazy validation
        window_id = registry.lookup(case_number, launcher._window_exists_by_id)

        if window_id:
            # Window exists in registry and validation passed - focus it
            logger.info("Found existing window for case %s (ID: %s), attempting focus", case_number, window_id)

            success = launcher.focus_window_by_id(window_id)
            if success:
                # Successfully focused existing window
                print(f"Focused existing terminal for case {case_number}")
                window_exists = True
                logger.info("Successfully focused existing window for case %s", case_number)
            else:
                # Focus failed after validation - race condition (user closed window between validation and focus)
                # Ask user whether to create new window
                logger.warning("Window focus failed for case %s after validation - window may have closed", case_number)
                response = input(
                    f"Window focus failed (window may have closed). "
                    f"Create new terminal instead? (y/n): "
                ).lower()

                if response != 'y':
                    # User chose not to create new window - abort
                    print("Aborted")
                    logger.info("User aborted terminal creation after focus failure")
                    return
                # User chose to create new window - fall through to launch
                print("Previous window closed, creating new terminal")
                logger.info("Creating new terminal after focus failure for case %s", case_number)
        else:
            # No existing window in registry (either never created or stale entry removed by lazy validation)
            logger.debug("No existing window found in registry for case %s", case_number)

    # 12. Launch terminal with command and title if no existing window
    if not window_exists:
        try:
            logger.info(
                "Launching terminal for case %s with title: %s",
                case_number, window_title
            )
            launch_options = LaunchOptions(
                title=window_title,
                command=exec_command,
                auto_focus=True
            )
            launcher.launch(launch_options)
            logger.info("Terminal launched successfully for case %s", case_number)

            # Register window ID in registry (macOS only - Phase 16)
            if isinstance(launcher, MacOSLauncher):
                # Give terminal brief moment to fully create window
                import time
                time.sleep(0.5)

                # Capture window ID
                window_id = launcher._capture_window_id()
                if window_id:
                    # Register in WindowRegistry
                    registry = WindowRegistry()
                    registered = registry.register(case_number, window_id, launcher.terminal)
                    if registered:
                        logger.info("Registered window ID %s for case %s", window_id, case_number)
                    else:
                        # Duplicate registration - another process beat us (rare race condition)
                        logger.warning("Window ID registration failed for case %s - duplicate entry", case_number)
                else:
                    # Window ID capture failed - log warning but don't block
                    logger.warning("Failed to capture window ID for case %s - duplicate prevention disabled", case_number)
        except Exception as e:
            error_msg = (
                f"Terminal launch failed for case {case_number}. "
                f"Run: mc --check-terminal. Error: {e}"
            )
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e

    # 12. Return immediately (non-blocking - host terminal returns to prompt)
    logger.debug("Terminal attachment complete, returning to host prompt")
