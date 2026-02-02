"""Container lifecycle commands.

Authentication Architecture:
- Container lifecycle commands (create, list, stop, delete, exec): No authentication required
- Terminal attachment (case_terminal, quick_access): Red Hat API credentials required for metadata
- Red Hat API credentials only validated at terminal attachment time
"""

import argparse
import os
import sys

from mc.config.manager import ConfigManager
from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient
from mc.integrations.redhat_api import RedHatAPIClient
from mc.terminal.attach import attach_terminal
from mc.utils.auth import get_access_token
from mc.utils.validation import validate_case_number


def _get_manager() -> ContainerManager:
    """Get ContainerManager instance (helper to avoid duplication)."""
    podman_client = PodmanClient()

    # Consolidated location: ~/mc/state/containers.db
    state_dir = os.path.join(os.path.expanduser("~"), "mc", "state")
    os.makedirs(state_dir, exist_ok=True)
    db_path = os.path.join(state_dir, "containers.db")

    # Auto-migration: Move from old platformdirs location if needed
    if not os.path.exists(db_path):
        try:
            from platformdirs import user_data_dir
            old_db_path = os.path.join(user_data_dir("mc", "redhat"), "containers.db")
            if os.path.exists(old_db_path):
                import shutil
                shutil.copy2(old_db_path, db_path)
                print(f"Migrated state database from {old_db_path} to {db_path}")
        except ImportError:
            pass

    state_db = StateDatabase(db_path)
    return ContainerManager(podman_client, state_db)


def create(args: argparse.Namespace) -> None:
    """Create container for case number.

    Args:
        args: Parsed arguments with case_number
    """
    # Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(args.case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    manager = _get_manager()

    # Get workspace path from ConfigManager
    config = ConfigManager()
    base_dir = config.get("workspace.base_directory", os.path.expanduser("~/mc"))
    workspace_path = os.path.join(base_dir, case_number)

    # Create workspace directory if missing
    os.makedirs(workspace_path, exist_ok=True)

    # Create container
    try:
        container = manager.create(case_number, workspace_path)
        print(f"Created container for case {case_number}")
        print(f"Container ID: {container.short_id}")
        print(f"Workspace: {workspace_path}")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def list_containers(args: argparse.Namespace) -> None:
    """List all containers.

    Args:
        args: Parsed arguments
    """
    manager = _get_manager()

    try:
        containers = manager.list()

        if not containers:
            print("No containers found. Create one with: mc container create <case_number>")
            return

        # Format as ASCII table
        # Header
        print(f"{'CASE':<12} {'STATUS':<10} {'CUSTOMER':<20} {'DESCRIPTION':<40} {'CREATED':<20}")
        print("-" * 102)

        # Rows
        for container in containers:
            case_number = container["case_number"]
            status = container["status"]
            customer = container["customer"]
            workspace_path = container["workspace_path"]
            created_at = container["created_at"]

            # Truncate long customer names
            if len(customer) > 20:
                customer = customer[:17] + "..."

            # Extract description from workspace path
            # New structure: {base_dir}/cases/{customer}/{case_number}-{description}
            # Old structure: {base_dir}/{case_number}
            description = "N/A"
            if workspace_path and workspace_path != "N/A":
                # Try to extract description from new path structure
                # Split by '/' and get last component, then split by '-' after case number
                path_parts = workspace_path.split('/')
                if path_parts:
                    last_part = path_parts[-1]  # e.g., "04347611-Server_Down_Critica_Pr"
                    # Split on first hyphen after 8-digit case number
                    if '-' in last_part and len(last_part) > 9:
                        # Extract everything after the case number and hyphen
                        desc_part = last_part.split('-', 1)[1] if '-' in last_part else ""
                        if desc_part:
                            # Replace underscores with spaces for readability
                            description = desc_part.replace('_', ' ')

            # Truncate long descriptions
            if len(description) > 40:
                description = description[:37] + "..."

            print(f"{case_number:<12} {status:<10} {customer:<20} {description:<40} {created_at:<20}")

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def stop(args: argparse.Namespace) -> None:
    """Stop container.

    Args:
        args: Parsed arguments with case_number
    """
    # Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(args.case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    manager = _get_manager()

    try:
        was_stopped = manager.stop(case_number)
        if was_stopped:
            print(f"Stopped container for case {case_number}")
        else:
            print(f"Container for case {case_number} was already stopped")
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def delete(args: argparse.Namespace) -> None:
    """Delete container.

    Args:
        args: Parsed arguments with case_number
    """
    # Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(args.case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    manager = _get_manager()

    # Print warning
    print("This will delete the container but preserve the workspace.")

    try:
        manager.delete(case_number)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def exec_command(args: argparse.Namespace) -> None:
    """Execute command in container.

    Args:
        args: Parsed arguments with case_number and command
    """
    # Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(args.case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    command = args.command  # List of command parts
    manager = _get_manager()

    try:
        # Execute command
        exit_code, output = manager.exec(case_number, command)

        # Print output
        print(output, end="")

        # Exit with command's exit code
        sys.exit(exit_code)

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def case_terminal(args: argparse.Namespace) -> None:
    """Attach terminal to case container (mc case <number>).

    Primary entry point for terminal attachment workflow. Launches new terminal
    window attached to case container with auto-create/auto-start.

    Args:
        args: Parsed arguments with case_number
    """
    # Validate case number format early (fail fast before expensive operations)
    try:
        case_number = validate_case_number(args.case_number)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize dependencies
    config_manager = ConfigManager()

    # Get Red Hat API offline token from config
    try:
        config = config_manager.load()

        # Try new key first, fall back to old key for backwards compatibility
        offline_token = config["api"].get("rh_api_offline_token") or config["api"].get("offline_token")

        if not offline_token:
            config_path = config_manager.get_config_path()
            print(
                f"Error: Red Hat API offline token not configured. "
                f"Update config at {config_path}",
                file=sys.stderr
            )
            sys.exit(1)

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize Red Hat API client
    try:
        access_token = get_access_token(offline_token)
        api_client = RedHatAPIClient(access_token)
    except Exception as e:
        print(f"Error authenticating with Red Hat API: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize container manager
    container_manager = _get_manager()

    try:
        # Launch terminal attachment workflow
        attach_terminal(
            case_number=case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager
        )
        # Terminal launched - host terminal returns to prompt

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def quick_access(args: argparse.Namespace) -> None:
    """Quick access shorthand (mc <case_number>).

    Alias for case_terminal - same behavior as 'mc case <number>'.

    Args:
        args: Parsed arguments with case_number
    """
    # Route to case_terminal function
    case_terminal(args)
