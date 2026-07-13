"""Case number to workspace path resolution using Salesforce metadata.

Resolves case numbers to workspace paths by fetching customer name and case
summary from Salesforce API (via cache), then constructing paths following
v1.0 workspace structure conventions.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from mc.exceptions import MCError, WorkspaceError
from mc.utils.formatters import shorten_and_format

if TYPE_CHECKING:
    from mc.controller.cache_manager import CacheManager
    from mc.controller.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


class CaseResolver:
    """Resolves case numbers to workspace paths using Salesforce metadata.

    Fetches case metadata from cache/Salesforce API and constructs workspace
    paths following v1.0 structure: {base_dir}/{account_name}/{case_number}-{summary}

    Attributes:
        cache_manager: CacheManager for fetching case metadata
        base_dir: Base directory for all workspaces
    """

    def __init__(self, cache_manager: "CacheManager", base_dir: Path) -> None:
        """Initialize case resolver.

        Args:
            cache_manager: CacheManager for fetching case metadata
            base_dir: Base directory for workspaces
        """
        self.cache_manager = cache_manager
        self.base_dir = base_dir

    def resolve(self, case_number: str) -> Path:
        """Resolve case number to workspace path.

        Fetches case metadata from cache or Salesforce, validates required
        fields, and constructs workspace path using v1.0 naming convention.

        Args:
            case_number: Case number to resolve

        Returns:
            Workspace path for the case

        Raises:
            WorkspaceError: If case metadata missing required fields
        """
        # Get metadata from cache or Salesforce
        case_data, account_data, was_cached = self.cache_manager.get_or_fetch(case_number)

        # Validate required fields
        self._validate_metadata(case_data)

        # Extract account name and case summary
        # Try case_data first, fallback to account_data for account name
        account_name = case_data.get("account_name") or account_data.get("name", "")
        case_summary = case_data.get("case_summary") or case_data.get("Subject", "")

        # Format using v1.0 pattern
        account_formatted = shorten_and_format(account_name)
        summary_formatted = shorten_and_format(case_summary)

        # Construct path: {base_dir}/{account_name}/{case_number}-{summary}
        workspace_path = self.base_dir / account_formatted / f"{case_number}-{summary_formatted}"

        logger.debug("Resolved case %s to workspace path: %s", case_number, workspace_path)
        return workspace_path

    def _validate_metadata(self, case_data: dict[str, str]) -> None:
        """Validate case metadata has required fields.

        Args:
            case_data: Case metadata dictionary

        Raises:
            WorkspaceError: If required fields are missing
        """
        # Check for case_summary or Subject (fallback)
        case_summary = case_data.get("case_summary") or case_data.get("Subject", "")
        if not case_summary:
            raise WorkspaceError(
                "Missing required case metadata field: case_summary",
                "Check: Case exists in Salesforce and user has read permissions"
            )

    def get_workspace_manager(self, case_number: str) -> "WorkspaceManager":
        """Get WorkspaceManager instance for case.

        Creates WorkspaceManager with metadata from Salesforce, pinning
        workspace path at resolution time (no auto-updates when metadata changes).

        Args:
            case_number: Case number

        Returns:
            WorkspaceManager instance with Salesforce-sourced metadata

        Raises:
            WorkspaceError: If case metadata missing required fields
        """
        from mc.controller.workspace import WorkspaceManager

        # Get metadata
        case_data, account_data, _ = self.cache_manager.get_or_fetch(case_number)

        # Extract fields (same logic as resolve())
        account_name = case_data.get("account_name") or account_data.get("name", "")
        case_summary = case_data.get("case_summary") or case_data.get("Subject", "")

        # Validate before creating WorkspaceManager
        if not account_name:
            raise WorkspaceError(
                "Missing required case metadata field: account_name",
                "Check: Case exists in Salesforce and user has read permissions"
            )
        if not case_summary:
            raise WorkspaceError(
                "Missing required case metadata field: case_summary",
                "Check: Case exists in Salesforce and user has read permissions"
            )

        return WorkspaceManager(
            base_dir=self.base_dir,
            case_number=case_number,
            account_name=account_name,
            case_summary=case_summary
        )

    def discover_linked_tickets(
        self,
        case_number: str,
        jira_config_path: str | None = None,
    ) -> list[str]:
        """Discover and process Jira tickets linked to a SFDC case.

        Fetches SFDC metadata for the case, extracts linked Jira ticket IDs,
        fetches each ticket via JiraClient, scaffolds Ticket Workspaces, and
        records case-ticket links in the StateDatabase.

        Args:
            case_number: 8-digit SFDC case number.
            jira_config_path: Optional path to jr config file.

        Returns:
            List of discovered Jira ticket IDs.
        """
        from mc.container.state import StateDatabase
        from mc.controller.ticket_workspace import TicketWorkspaceManager
        from mc.integrations.jira import JiraClient

        # Get SFDC metadata for this case
        case_data, _account_data, _was_cached = self.cache_manager.get_or_fetch(case_number)

        # Extract linked Jira ticket IDs from SFDC metadata
        # SFDC case data may contain linked ticket references in various fields
        linked_ticket_ids = self._extract_ticket_ids_from_sfdc(case_data)

        if not linked_ticket_ids:
            logger.info("No linked Jira tickets found for case %s", case_number)
            return []

        logger.info(
            "Found %d linked ticket(s) for case %s: %s",
            len(linked_ticket_ids),
            case_number,
            ", ".join(linked_ticket_ids),
        )

        client = JiraClient(config_path=jira_config_path)
        state_db = StateDatabase()
        discovered: list[str] = []

        for ticket_id in linked_ticket_ids:
            try:
                # Fetch ticket data
                ticket_data = client.fetch_ticket(ticket_id)

                # Scaffold workspace
                workspace_mgr = TicketWorkspaceManager(
                    base_dir=str(self.base_dir),
                    ticket_id=ticket_id,
                )
                workspace_mgr.create_workspace(ticket_data)

                # Record link
                state_db.add_case_ticket_link(case_number, ticket_id)
                discovered.append(ticket_id)

                logger.info(
                    "Processed linked ticket %s for case %s", ticket_id, case_number
                )
            except MCError as e:
                logger.warning(
                    "Failed to process linked ticket %s: %s", ticket_id, e
                )

        return discovered

    @staticmethod
    def _extract_ticket_ids_from_sfdc(case_data: dict[str, str]) -> list[str]:
        """Extract Jira ticket IDs from SFDC case metadata.

        Looks for ticket references in known SFDC fields.

        Args:
            case_data: SFDC case metadata dict.

        Returns:
            List of Jira ticket ID strings.
        """
        import re

        ticket_ids: list[str] = []
        ticket_pattern = re.compile(r"[A-Z]{1,10}-\d+")

        # Check known fields that may contain Jira references
        for field_name in ("jira_tickets", "linked_tickets", "external_references"):
            value = case_data.get(field_name, "")
            if value:
                for match in ticket_pattern.findall(str(value)):
                    if match not in ticket_ids:
                        ticket_ids.append(match)

        return ticket_ids
