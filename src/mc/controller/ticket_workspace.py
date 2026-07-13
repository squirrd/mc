"""Workspace management for Jira tickets."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TicketWorkspaceManager:
    """Manages Jira ticket workspace files and directories.

    Scaffolds ``~/mc/jira/{ticket-id}/`` with ticket JSON data and note files.
    The ``jira/`` directory is created lazily on first use.

    Args:
        base_dir: Base directory for all MC data (e.g. ``~/mc``).
        ticket_id: Normalized Jira ticket ID (e.g. ``OHSS-52338``).
    """

    def __init__(self, base_dir: str, ticket_id: str) -> None:
        self.base_dir = Path(base_dir)
        self.ticket_id = ticket_id
        self.ticket_dir = self.base_dir / "jira" / ticket_id

    def create_workspace(self, ticket_data: dict[str, Any]) -> Path:
        """Create the ticket workspace directory structure.

        Creates::

            {base_dir}/jira/{ticket-id}/
                {ticket-id}.json   -- raw ticket data
                notes-01.md
                notes-02.md
                notes-03.md
                tmp.md

        Args:
            ticket_data: Parsed Jira ticket dict (as returned by
                :meth:`~mc.integrations.jira.JiraClient.fetch_ticket`).

        Returns:
            Path to the created ticket workspace directory.
        """
        # Create directory lazily (including parent jira/ dir)
        self.ticket_dir.mkdir(parents=True, exist_ok=True)
        logger.debug("Created ticket workspace: %s", self.ticket_dir)

        # Write ticket JSON
        json_path = self.ticket_dir / f"{self.ticket_id}.json"
        json_path.write_text(json.dumps(ticket_data, indent=2) + "\n")
        logger.debug("Wrote ticket data to %s", json_path)

        # Create note files
        for note_file in ("notes-01.md", "notes-02.md", "notes-03.md", "tmp.md"):
            note_path = self.ticket_dir / note_file
            if not note_path.exists():
                note_path.touch()
                logger.debug("Created note file: %s", note_path)

        return self.ticket_dir
