"""Jira integration client wrapping the jr CLI."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from typing import Any

from mc.exceptions import MCError

logger = logging.getLogger(__name__)

# Matches exactly 8 consecutive digits that are not part of a longer number
_CASE_NUMBER_RE = re.compile(r"(?<!\d)\d{8}(?!\d)")


class JiraClient:
    """Wrapper around the ``jr`` CLI for fetching Jira ticket data.

    Shells out to ``jr issue view <ticket-id> --raw`` to retrieve raw JSON
    ticket data, and provides helpers to extract linked SFDC case numbers.

    Args:
        config_path: Optional path to a jr configuration file.  When set,
            ``-c <config_path>`` is appended to every ``jr`` invocation.
    """

    def __init__(self, config_path: str | None = None) -> None:
        self.config_path = config_path

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_ticket(self, ticket_id: str) -> dict[str, Any]:
        """Fetch a Jira ticket by ID using the ``jr`` CLI.

        Runs ``jr issue view <ticket_id> --raw [-c <config_path>]`` and
        parses the JSON output.

        Args:
            ticket_id: Jira ticket identifier (e.g. ``OHSS-52338``).

        Returns:
            Parsed ticket data as a dict.

        Raises:
            MCError: If ``jr`` is not installed, returns a non-zero exit code,
                times out, or produces unparseable output.
        """
        cmd = ["jr", "issue", "view", ticket_id, "--raw"]
        if self.config_path is not None:
            cmd.extend(["-c", self.config_path])

        logger.debug("Running jr command: %s", cmd)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except FileNotFoundError:
            raise MCError(
                "jr CLI not found. Is it installed and on your PATH?",
                suggestion="Install jr: https://github.com/ankitpokhrel/jira-cli",
            )
        except subprocess.TimeoutExpired:
            raise MCError(
                f"jr command timed out while fetching ticket {ticket_id}",
                suggestion="Check network connectivity and Jira server status",
            )

        if result.returncode != 0:
            logger.error("jr failed (exit %d): %s", result.returncode, result.stderr)
            raise MCError(
                f"jr command failed (exit {result.returncode}): {result.stderr.strip()}",
                suggestion="Check ticket ID and jr configuration",
            )

        try:
            ticket_data: dict[str, Any] = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise MCError(
                f"Failed to parse JSON from jr output: {exc}",
                suggestion="Ensure jr returns valid JSON with --raw flag",
            )

        logger.debug("Fetched ticket %s successfully", ticket_id)
        return ticket_data

    def extract_linked_cases(self, ticket_data: dict[str, Any]) -> list[str]:
        """Extract linked SFDC case numbers from ticket data.

        Primary path: scans ``customfield_12345`` for 8-digit case numbers.
        Fallback: regex-scans all comment bodies for 8-digit numbers.

        Results are deduplicated and returned in discovery order.

        Args:
            ticket_data: Parsed Jira ticket dict (as returned by
                :meth:`fetch_ticket`).

        Returns:
            List of unique 8-digit SFDC case number strings.
        """
        seen: set[str] = set()
        cases: list[str] = []

        fields = ticket_data.get("fields", {})

        # Primary path: custom field
        custom_value = fields.get("customfield_12345")
        if custom_value is not None:
            for match in _CASE_NUMBER_RE.findall(str(custom_value)):
                if match not in seen:
                    seen.add(match)
                    cases.append(match)

        # Fallback: scan comments
        comment_section = fields.get("comment", {})
        comments = comment_section.get("comments", []) if isinstance(comment_section, dict) else []
        for comment in comments:
            body = comment.get("body", "")
            for match in _CASE_NUMBER_RE.findall(body):
                if match not in seen:
                    seen.add(match)
                    cases.append(match)

        logger.debug("Extracted %d linked case(s) from ticket data", len(cases))
        return cases
