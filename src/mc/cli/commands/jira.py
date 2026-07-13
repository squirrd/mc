"""CLI command for Jira ticket operations."""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

from mc.config.manager import ConfigManager
from mc.exceptions import MCError
from mc.integrations.jira import JiraClient
from mc.controller.ticket_workspace import TicketWorkspaceManager
from mc.utils.validation import validate_ticket_id

logger = logging.getLogger(__name__)


def jira_command(args: argparse.Namespace) -> None:
    """Handle ``mc jira <ticket-id>`` command.

    Orchestrates:
    1. Validate and normalize ticket ID
    2. Fetch ticket data via jr CLI
    3. Extract linked SFDC case numbers
    4. Scaffold Ticket Workspace under ~/mc/jira/{ticket-id}/
    5. Create container named mc-{ticket-id}
    6. Launch terminal

    Args:
        args: Parsed CLI arguments (must have ``ticket_id`` attribute).
    """
    # 1. Validate ticket ID
    ticket_id = validate_ticket_id(args.ticket_id)
    logger.info("Processing ticket: %s", ticket_id)

    # Load config for base directory and jira config path
    config_mgr = ConfigManager()
    config = config_mgr.load()
    base_dir = config.get("base_directory", os.path.expanduser("~/mc"))
    jira_config_path = config.get("jira", {}).get("config_path")

    # 2. Fetch ticket data
    client = JiraClient(config_path=jira_config_path)
    ticket_data: dict[str, Any] = client.fetch_ticket(ticket_id)
    logger.info("Fetched ticket data for %s", ticket_id)

    # 3. Extract linked SFDC case numbers
    linked_cases = client.extract_linked_cases(ticket_data)
    if linked_cases:
        logger.info("Found %d linked case(s): %s", len(linked_cases), ", ".join(linked_cases))
    else:
        logger.info("No linked SFDC cases found for %s", ticket_id)

    # 4. Scaffold ticket workspace
    workspace_mgr = TicketWorkspaceManager(base_dir=base_dir, ticket_id=ticket_id)
    workspace_path = workspace_mgr.create_workspace(ticket_data)
    logger.info("Ticket workspace ready: %s", workspace_path)

    # 5. Record case-ticket links in SQLite
    if linked_cases:
        from mc.container.state import StateDatabase
        state_db = StateDatabase()
        for case_number in linked_cases:
            state_db.add_case_ticket_link(case_number, ticket_id)
            logger.debug("Recorded link: case %s <-> ticket %s", case_number, ticket_id)

    # Handle --link flag for manual association
    if hasattr(args, "link_case") and args.link_case:
        from mc.utils.validation import validate_case_number
        from mc.container.state import StateDatabase

        link_case = validate_case_number(args.link_case)
        state_db = StateDatabase()
        state_db.add_case_ticket_link(link_case, ticket_id)
        logger.info("Manually linked case %s to ticket %s", link_case, ticket_id)

    # 6. Create container and launch terminal
    # Container is named mc-{ticket_id} (e.g. mc-OHSS-52338)
    from mc.container.manager import ContainerManager
    container_mgr = ContainerManager()
    container_name = f"mc-{ticket_id}"

    try:
        container_mgr.create(
            case_number=ticket_id,
            workspace_path=str(workspace_path),
            container_name=container_name,
        )
        logger.info("Container %s created", container_name)
    except MCError as e:
        if "already exists" in str(e).lower():
            logger.info("Container %s already exists, reusing", container_name)
        else:
            raise

    # Launch terminal
    from mc.terminal.launcher import TerminalLauncher
    launcher = TerminalLauncher()
    launcher.launch(container_name=container_name, title=f"MC-{ticket_id}")
    logger.info("Terminal launched for %s", ticket_id)
