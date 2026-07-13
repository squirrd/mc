"""Unit tests for CaseResolver.discover_linked_tickets."""

from __future__ import annotations

from mc.controller.case_resolver import CaseResolver


class TestDiscoverLinkedTicketsExists:
    """Verify discover_linked_tickets exists and is callable."""

    def test_has_discover_linked_tickets_method(self) -> None:
        assert hasattr(CaseResolver, "discover_linked_tickets")

    def test_discover_linked_tickets_is_callable(self) -> None:
        assert callable(getattr(CaseResolver, "discover_linked_tickets"))


class TestExtractTicketIdsFromSfdc:
    """Tests for CaseResolver._extract_ticket_ids_from_sfdc."""

    def test_extracts_from_jira_tickets_field(self) -> None:
        case_data = {"jira_tickets": "OHSS-52338"}
        result = CaseResolver._extract_ticket_ids_from_sfdc(case_data)
        assert "OHSS-52338" in result

    def test_extracts_multiple_tickets(self) -> None:
        case_data = {"jira_tickets": "OHSS-52338, OCPBUGS-123"}
        result = CaseResolver._extract_ticket_ids_from_sfdc(case_data)
        assert "OHSS-52338" in result
        assert "OCPBUGS-123" in result

    def test_deduplicates_tickets(self) -> None:
        case_data = {
            "jira_tickets": "OHSS-52338",
            "linked_tickets": "OHSS-52338",
        }
        result = CaseResolver._extract_ticket_ids_from_sfdc(case_data)
        assert result.count("OHSS-52338") == 1

    def test_returns_empty_when_no_fields(self) -> None:
        case_data = {"case_summary": "something unrelated"}
        result = CaseResolver._extract_ticket_ids_from_sfdc(case_data)
        assert result == []
