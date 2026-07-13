"""Acceptance tests for MC-16: Jira Integration feature.

These tests define the acceptance criteria for each vertical slice.
Each test must FAIL (RED) until the slice is implemented.
"""

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Slice 1: ticket-id-validator
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mc_16_jira_integration_ticket_id_validator_acceptance():
    """Acceptance test for ticket-id-validator slice.

    Feature: MC-16 Jira Integration
    Slice:   ticket-id-validator
    Criterion: validate_ticket_id() accepts PROJECT-123 format, normalizes
               lowercase to uppercase, rejects invalid formats.

    Expected RED reason: ImportError — validate_ticket_id does not exist yet.
    """
    from mc.utils.validation import validate_ticket_id

    # Valid ticket IDs should be accepted and returned uppercase
    assert validate_ticket_id("OHSS-52338") == "OHSS-52338"
    assert validate_ticket_id("ohss-52338") == "OHSS-52338"  # lowercase normalized
    assert validate_ticket_id("ABC-1") == "ABC-1"  # short project, single digit
    assert validate_ticket_id("LONGPROJ-99999") == "LONGPROJ-99999"  # long project

    # Invalid formats should raise ValueError
    with pytest.raises(ValueError):
        validate_ticket_id("")  # empty

    with pytest.raises(ValueError):
        validate_ticket_id("12345678")  # digits only (case number, not ticket)

    with pytest.raises(ValueError):
        validate_ticket_id("NOHYPHEN")  # no hyphen

    with pytest.raises(ValueError):
        validate_ticket_id("OHSS-")  # missing number after hyphen

    with pytest.raises(ValueError):
        validate_ticket_id("-12345")  # missing project prefix

    with pytest.raises(ValueError):
        validate_ticket_id("TOOLONGPREFIX-123")  # prefix > 10 chars


# ---------------------------------------------------------------------------
# Slice 2: jira-client
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mc_16_jira_integration_jira_client_acceptance():
    """Acceptance test for jira-client slice.

    Feature: MC-16 Jira Integration
    Slice:   jira-client
    Criterion: JiraClient wraps jr CLI -- fetch_ticket() returns parsed JSON,
               extract_linked_cases() finds SFDC case numbers from custom
               field and comment fallback.

    Expected RED reason: ImportError — JiraClient does not exist yet.
    """
    from mc.integrations.jira import JiraClient

    client = JiraClient()

    # fetch_ticket must return a dict parsed from jr JSON output
    assert callable(getattr(client, "fetch_ticket", None)), (
        "JiraClient must have a fetch_ticket method"
    )

    # extract_linked_cases must return a list of case number strings
    assert callable(getattr(client, "extract_linked_cases", None)), (
        "JiraClient must have an extract_linked_cases method"
    )

    # extract_linked_cases should accept ticket data dict and return case numbers
    sample_ticket_data = {
        "key": "OHSS-52338",
        "fields": {
            "summary": "Test ticket",
            "customfield_12345": "04416520",  # SFDC Cases Links field
        },
    }
    cases = client.extract_linked_cases(sample_ticket_data)
    assert isinstance(cases, list), "extract_linked_cases must return a list"


# ---------------------------------------------------------------------------
# Slice 3: ticket-workspace-and-db
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mc_16_jira_integration_ticket_workspace_and_db_acceptance(tmp_path):
    """Acceptance test for ticket-workspace-and-db slice.

    Feature: MC-16 Jira Integration
    Slice:   ticket-workspace-and-db
    Criterion: TicketWorkspaceManager scaffolds ~/mc/jira/{ticket-id}/ with
               JSON + notes; StateDatabase adds case_ticket_links table with
               CRUD; WorkspaceManager removes old jira/ dirs from case workspace.

    Expected RED reason: ImportError — TicketWorkspaceManager does not exist yet.
    """
    # --- Part A: TicketWorkspaceManager scaffolding ---
    from mc.controller.ticket_workspace import TicketWorkspaceManager

    ticket_data = {"key": "OHSS-52338", "fields": {"summary": "Test ticket"}}
    mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
    mgr.create_workspace(ticket_data)

    jira_dir = tmp_path / "jira" / "OHSS-52338"
    assert jira_dir.is_dir(), "Ticket workspace directory must be created"
    assert (jira_dir / "OHSS-52338.json").is_file(), "Ticket JSON must be written"
    assert (jira_dir / "notes-01.md").is_file(), "notes-01.md must be created"
    assert (jira_dir / "notes-02.md").is_file(), "notes-02.md must be created"
    assert (jira_dir / "notes-03.md").is_file(), "notes-03.md must be created"
    assert (jira_dir / "tmp.md").is_file(), "tmp.md must be created"

    # Verify ticket JSON content is valid
    with open(jira_dir / "OHSS-52338.json") as f:
        stored = json.load(f)
    assert stored["key"] == "OHSS-52338"

    # --- Part B: StateDatabase case_ticket_links CRUD ---
    from mc.container.state import StateDatabase

    db = StateDatabase(db_path=":memory:")
    db.add_case_ticket_link("04416520", "OHSS-52338")

    tickets = db.get_tickets_for_case("04416520")
    assert "OHSS-52338" in tickets, "Link must be retrievable by case number"

    cases = db.get_cases_for_ticket("OHSS-52338")
    assert "04416520" in cases, "Link must be retrievable by ticket ID"

    # Idempotent: adding same link again should not raise
    db.add_case_ticket_link("04416520", "OHSS-52338")

    db.remove_case_ticket_link("04416520", "OHSS-52338")
    assert "OHSS-52338" not in db.get_tickets_for_case("04416520"), (
        "Link must be removable"
    )


# ---------------------------------------------------------------------------
# Slice 4: mc-jira-command
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mc_16_jira_integration_mc_jira_command_acceptance():
    """Acceptance test for mc-jira-command slice.

    Feature: MC-16 Jira Integration
    Slice:   mc-jira-command
    Criterion: mc jira <ticket-id> CLI entry point orchestrates validation,
               fetch, workspace scaffold, container creation (mc-OHSS-52338),
               and terminal launch.

    Expected RED reason: ImportError — cli.commands.jira does not exist yet.
    """
    from mc.cli.commands.jira import jira_command

    # The jira_command function must exist and be callable
    assert callable(jira_command), "jira_command must be a callable entry point"


# ---------------------------------------------------------------------------
# Slice 5: mc-case-jira-discovery
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_mc_16_jira_integration_mc_case_jira_discovery_acceptance():
    """Acceptance test for mc-case-jira-discovery slice.

    Feature: MC-16 Jira Integration
    Slice:   mc-case-jira-discovery
    Criterion: mc case <case-number> auto-discovers linked Jira tickets from
               SFDC metadata, fetches ticket data, scaffolds Ticket Workspaces,
               records links in SQLite.

    Expected RED reason: ImportError — discover_linked_tickets does not exist yet.
    """
    from mc.controller.case_resolver import CaseResolver

    # CaseResolver must have a discover_linked_tickets method
    assert hasattr(CaseResolver, "discover_linked_tickets"), (
        "CaseResolver must have a discover_linked_tickets method for SFDC->Jira discovery"
    )

    # The method must be callable
    assert callable(getattr(CaseResolver, "discover_linked_tickets")), (
        "discover_linked_tickets must be callable"
    )
