"""Container lifecycle commands."""

import argparse
import os
import sys

from mc.config.manager import ConfigManager
from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient
from mc.integrations.salesforce_api import SalesforceAPIClient
from mc.terminal.attach import attach_terminal
from platformdirs import user_data_dir


def _get_manager() -> ContainerManager:
    """Get ContainerManager instance (helper to avoid duplication)."""
    podman_client = PodmanClient()
    data_dir = user_data_dir("mc", "redhat")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "containers.db")
    state_db = StateDatabase(db_path)
    return ContainerManager(podman_client, state_db)


def create(args: argparse.Namespace) -> None:
    """Create container for case number.

    Args:
        args: Parsed arguments with case_number
    """
    case_number = args.case_number
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
        print(f"{'CASE':<12} {'STATUS':<10} {'CUSTOMER':<20} {'WORKSPACE PATH':<40} {'CREATED':<20}")
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

            # Truncate long workspace paths
            if len(workspace_path) > 40:
                workspace_path = "..." + workspace_path[-37:]

            print(f"{case_number:<12} {status:<10} {customer:<20} {workspace_path:<40} {created_at:<20}")

    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def stop(args: argparse.Namespace) -> None:
    """Stop container.

    Args:
        args: Parsed arguments with case_number
    """
    case_number = args.case_number
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
    case_number = args.case_number
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
    case_number = args.case_number
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
    case_number = args.case_number

    # Initialize dependencies
    config_manager = ConfigManager()

    # Get Salesforce credentials from config
    try:
        config = config_manager.load()
        sf_config = config.get("salesforce", {})
        sf_username = sf_config.get("username")
        sf_password = sf_config.get("password")
        sf_token = sf_config.get("security_token")

        if not all([sf_username, sf_password, sf_token]):
            print(
                "Error: Salesforce credentials not configured. "
                "Update config at ~/.config/mc/config.toml",
                file=sys.stderr
            )
            sys.exit(1)

    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Initialize Salesforce client
    salesforce_client = SalesforceAPIClient(sf_username, sf_password, sf_token)

    # Initialize container manager
    container_manager = _get_manager()

    try:
        # Launch terminal attachment workflow
        attach_terminal(
            case_number=case_number,
            config_manager=config_manager,
            salesforce_client=salesforce_client,
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
