"""Unit tests for JiraClient -- jr CLI wrapper.

Tests the JiraClient class which shells out to `jr issue view` to fetch
Jira ticket data and extracts linked SFDC case numbers from custom fields
and comment fallback.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest.mock import patch, MagicMock

import pytest

from mc.integrations.jira import JiraClient
from mc.exceptions import MCError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> JiraClient:
    """JiraClient with no config_path (default)."""
    return JiraClient()


@pytest.fixture
def client_with_config(tmp_path: Any) -> JiraClient:
    """JiraClient with an explicit config_path."""
    config = tmp_path / "jr-config.yml"
    config.write_text("dummy: true\n")
    return JiraClient(config_path=str(config))


@pytest.fixture
def sample_ticket_json() -> dict[str, Any]:
    """Minimal Jira ticket JSON as returned by `jr issue view --raw`."""
    return {
        "key": "OHSS-52338",
        "fields": {
            "summary": "Customer cluster upgrade failure",
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Jane Doe"},
            "customfield_12345": "12345678",
            "comment": {
                "comments": [
                    {"body": "Linked to case 87654321 for tracking."},
                    {"body": "No case reference here."},
                    {"body": "Also see 11112222 and 33334444."},
                ],
            },
        },
    }


# ---------------------------------------------------------------------------
# Constructor tests
# ---------------------------------------------------------------------------


class TestJiraClientConstructor:
    """JiraClient.__init__ accepts optional config_path."""

    def test_default_config_path_is_none(self) -> None:
        """Constructor without config_path sets it to None."""
        client = JiraClient()
        assert client.config_path is None

    def test_explicit_config_path_stored(self, tmp_path: Any) -> None:
        """Constructor with config_path stores the value."""
        path = str(tmp_path / "config.yml")
        client = JiraClient(config_path=path)
        assert client.config_path == path


# ---------------------------------------------------------------------------
# fetch_ticket -- happy path
# ---------------------------------------------------------------------------


class TestFetchTicketSuccess:
    """fetch_ticket() returns parsed JSON from jr CLI output."""

    @patch("mc.integrations.jira.subprocess.run")
    def test_returns_parsed_json(
        self, mock_run: MagicMock, client: JiraClient, sample_ticket_json: dict[str, Any]
    ) -> None:
        """fetch_ticket() parses jr stdout JSON into a dict."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["jr"],
            returncode=0,
            stdout=json.dumps(sample_ticket_json),
            stderr="",
        )

        result = client.fetch_ticket("OHSS-52338")

        assert result["key"] == "OHSS-52338"
        assert result["fields"]["summary"] == "Customer cluster upgrade failure"

    @patch("mc.integrations.jira.subprocess.run")
    def test_calls_jr_without_config_flag(
        self, mock_run: MagicMock, client: JiraClient, sample_ticket_json: dict[str, Any]
    ) -> None:
        """When config_path is None, jr is called without -c flag."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["jr"], returncode=0, stdout=json.dumps(sample_ticket_json), stderr=""
        )

        client.fetch_ticket("OHSS-52338")

        args_used = mock_run.call_args[0][0]
        assert "-c" not in args_used
        assert "OHSS-52338" in args_used
        assert "--raw" in args_used

    @patch("mc.integrations.jira.subprocess.run")
    def test_calls_jr_with_config_flag(
        self,
        mock_run: MagicMock,
        client_with_config: JiraClient,
        sample_ticket_json: dict[str, Any],
    ) -> None:
        """When config_path is set, jr is called with -c <path>."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["jr"], returncode=0, stdout=json.dumps(sample_ticket_json), stderr=""
        )

        client_with_config.fetch_ticket("MC-1")

        args_used = mock_run.call_args[0][0]
        assert "-c" in args_used
        config_idx = args_used.index("-c")
        assert args_used[config_idx + 1] == client_with_config.config_path


# ---------------------------------------------------------------------------
# fetch_ticket -- error paths
# ---------------------------------------------------------------------------


class TestFetchTicketErrors:
    """fetch_ticket() raises MCError on jr failures."""

    @patch("mc.integrations.jira.subprocess.run")
    def test_raises_on_nonzero_exit(self, mock_run: MagicMock, client: JiraClient) -> None:
        """Non-zero exit code from jr raises MCError."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["jr"], returncode=1, stdout="", stderr="ticket not found"
        )

        with pytest.raises(MCError, match="jr.*failed"):
            client.fetch_ticket("OHSS-99999")

    @patch("mc.integrations.jira.subprocess.run")
    def test_raises_on_invalid_json(self, mock_run: MagicMock, client: JiraClient) -> None:
        """Invalid JSON in jr stdout raises MCError."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=["jr"], returncode=0, stdout="not valid json{{{", stderr=""
        )

        with pytest.raises(MCError, match="[Jj][Ss][Oo][Nn]|parse"):
            client.fetch_ticket("MC-1")

    @patch("mc.integrations.jira.subprocess.run")
    def test_raises_on_file_not_found(self, mock_run: MagicMock, client: JiraClient) -> None:
        """FileNotFoundError (jr not installed) raises MCError."""
        mock_run.side_effect = FileNotFoundError("jr: command not found")

        with pytest.raises(MCError, match="jr.*not found|not installed"):
            client.fetch_ticket("MC-1")

    @patch("mc.integrations.jira.subprocess.run")
    def test_raises_on_timeout(self, mock_run: MagicMock, client: JiraClient) -> None:
        """subprocess.TimeoutExpired raises MCError."""
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="jr", timeout=30)

        with pytest.raises(MCError, match="[Tt]imeout|timed out"):
            client.fetch_ticket("MC-1")


# ---------------------------------------------------------------------------
# extract_linked_cases -- custom field (primary path)
# ---------------------------------------------------------------------------


class TestExtractLinkedCasesCustomField:
    """extract_linked_cases() finds case numbers from a custom field value."""

    def test_single_case_from_custom_field(self, client: JiraClient) -> None:
        """A single 8-digit case number in a custom field is extracted."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "customfield_12345": "12345678",
                "comment": {"comments": []},
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert "12345678" in cases

    def test_multiple_cases_in_custom_field_string(self, client: JiraClient) -> None:
        """Multiple 8-digit case numbers in a single custom field string are all extracted."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "customfield_12345": "Cases: 12345678, 87654321",
                "comment": {"comments": []},
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert "12345678" in cases
        assert "87654321" in cases

    def test_custom_field_none_falls_through_to_comments(self, client: JiraClient) -> None:
        """When custom field is None, comments are scanned instead."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "customfield_12345": None,
                "comment": {
                    "comments": [
                        {"body": "See case 44445555 for details."},
                    ]
                },
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert "44445555" in cases


# ---------------------------------------------------------------------------
# extract_linked_cases -- comment fallback
# ---------------------------------------------------------------------------


class TestExtractLinkedCasesCommentFallback:
    """extract_linked_cases() falls back to scanning comments for 8-digit case numbers."""

    def test_finds_case_numbers_in_comments(self, client: JiraClient) -> None:
        """8-digit numbers in comment bodies are extracted as case numbers."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "comment": {
                    "comments": [
                        {"body": "Linked to case 87654321 for tracking."},
                        {"body": "No case reference here."},
                        {"body": "Also see 11112222 and 33334444."},
                    ]
                }
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert "87654321" in cases
        assert "11112222" in cases
        assert "33334444" in cases

    def test_deduplicates_case_numbers(self, client: JiraClient) -> None:
        """Duplicate case numbers across comments are returned only once."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "comment": {
                    "comments": [
                        {"body": "Case 12345678"},
                        {"body": "Same case 12345678 mentioned again."},
                    ]
                }
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert cases.count("12345678") == 1

    def test_no_comments_returns_empty_list(self, client: JiraClient) -> None:
        """No comments and no custom field returns empty list."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "comment": {"comments": []},
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert cases == []

    def test_no_comment_field_returns_empty_list(self, client: JiraClient) -> None:
        """Missing comment field entirely returns empty list."""
        ticket_data: dict[str, Any] = {
            "fields": {}
        }

        cases = client.extract_linked_cases(ticket_data)
        assert cases == []


# ---------------------------------------------------------------------------
# extract_linked_cases -- combined paths
# ---------------------------------------------------------------------------


class TestExtractLinkedCasesCombined:
    """extract_linked_cases() merges custom field and comment results."""

    def test_custom_field_and_comments_merged(self, client: JiraClient) -> None:
        """Case numbers from both custom field and comments are merged and deduplicated."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "customfield_12345": "12345678",
                "comment": {
                    "comments": [
                        {"body": "Also linked to 87654321."},
                        {"body": "And again 12345678."},
                    ]
                },
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert "12345678" in cases
        assert "87654321" in cases
        # Deduplicated
        assert len(cases) == len(set(cases))

    def test_ignores_numbers_that_are_not_8_digits(self, client: JiraClient) -> None:
        """Numbers that are not exactly 8 digits are not treated as case numbers."""
        ticket_data: dict[str, Any] = {
            "fields": {
                "customfield_12345": "short 1234567 and long 123456789",
                "comment": {
                    "comments": [
                        {"body": "Phone 5551234567 and zip 90210."},
                    ]
                },
            }
        }

        cases = client.extract_linked_cases(ticket_data)
        assert cases == []
