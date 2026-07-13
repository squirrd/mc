"""Unit tests for TicketWorkspaceManager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mc.controller.ticket_workspace import TicketWorkspaceManager


class TestTicketWorkspaceManagerInit:
    """Tests for TicketWorkspaceManager constructor."""

    def test_init_stores_base_dir_as_path(self, tmp_path: Path) -> None:
        """Constructor converts string base_dir to Path and stores it."""
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-1234")
        assert mgr.base_dir == tmp_path
        assert isinstance(mgr.base_dir, Path)

    def test_init_stores_ticket_id(self, tmp_path: Path) -> None:
        """Constructor stores the ticket_id."""
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-1234")
        assert mgr.ticket_id == "OCPBUGS-1234"

    def test_init_accepts_path_base_dir(self, tmp_path: Path) -> None:
        """Constructor also accepts Path objects for base_dir."""
        mgr = TicketWorkspaceManager(base_dir=tmp_path, ticket_id="OCPBUGS-5678")
        assert mgr.base_dir == tmp_path


class TestTicketWorkspaceManagerCreate:
    """Tests for TicketWorkspaceManager.create_workspace()."""

    def _sample_ticket(self) -> dict:
        return {"key": "OHSS-52338", "fields": {"summary": "Test ticket"}}

    def test_creates_ticket_directory(self, tmp_path: Path) -> None:
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
        mgr.create_workspace(self._sample_ticket())
        assert (tmp_path / "jira" / "OHSS-52338").is_dir()

    def test_writes_ticket_json(self, tmp_path: Path) -> None:
        ticket_data = self._sample_ticket()
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
        mgr.create_workspace(ticket_data)
        json_path = tmp_path / "jira" / "OHSS-52338" / "OHSS-52338.json"
        assert json_path.is_file()
        stored = json.loads(json_path.read_text())
        assert stored["key"] == "OHSS-52338"

    def test_creates_note_files(self, tmp_path: Path) -> None:
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
        mgr.create_workspace(self._sample_ticket())
        ticket_dir = tmp_path / "jira" / "OHSS-52338"
        for note in ("notes-01.md", "notes-02.md", "notes-03.md", "tmp.md"):
            assert (ticket_dir / note).is_file()

    def test_returns_ticket_directory_path(self, tmp_path: Path) -> None:
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
        result = mgr.create_workspace(self._sample_ticket())
        assert result == tmp_path / "jira" / "OHSS-52338"

    def test_idempotent_workspace_creation(self, tmp_path: Path) -> None:
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OHSS-52338")
        mgr.create_workspace(self._sample_ticket())
        # Write something to a note file
        (tmp_path / "jira" / "OHSS-52338" / "notes-01.md").write_text("my notes")
        # Create again — should not overwrite notes
        mgr.create_workspace(self._sample_ticket())
        assert (tmp_path / "jira" / "OHSS-52338" / "notes-01.md").read_text() == "my notes"

    def test_lazy_jira_directory_creation(self, tmp_path: Path) -> None:
        """jira/ parent directory should not exist until create_workspace is called."""
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="MC-42")
        assert not (tmp_path / "jira").exists()
        mgr.create_workspace({"key": "MC-42", "fields": {}})
        assert (tmp_path / "jira").is_dir()

    def test_note_files_are_empty(self, tmp_path: Path) -> None:
        """Note files are created empty (like workspace.py pattern)."""
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-1234")
        mgr.create_workspace({"key": "OCPBUGS-1234"})
        ticket_dir = tmp_path / "jira" / "OCPBUGS-1234"
        for name in ("notes-01.md", "notes-02.md", "notes-03.md", "tmp.md"):
            assert (ticket_dir / name).read_text() == ""

    def test_idempotent_does_not_overwrite_existing_json(self, tmp_path: Path) -> None:
        """Calling create_workspace twice does not overwrite existing JSON."""
        mgr = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-1234")
        original_data = {"key": "OCPBUGS-1234", "summary": "original"}
        mgr.create_workspace(ticket_data=original_data)
        # Second call with different data should not overwrite
        mgr.create_workspace(ticket_data={"key": "OCPBUGS-1234", "summary": "changed"})
        json_file = tmp_path / "jira" / "OCPBUGS-1234" / "OCPBUGS-1234.json"
        written = json.loads(json_file.read_text())
        assert written == original_data

    def test_different_ticket_ids_get_separate_dirs(self, tmp_path: Path) -> None:
        """Two different ticket IDs get separate directories."""
        mgr1 = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-1111")
        mgr1.create_workspace(ticket_data={"key": "OCPBUGS-1111"})
        mgr2 = TicketWorkspaceManager(base_dir=str(tmp_path), ticket_id="OCPBUGS-2222")
        mgr2.create_workspace(ticket_data={"key": "OCPBUGS-2222"})
        assert (tmp_path / "jira" / "OCPBUGS-1111").is_dir()
        assert (tmp_path / "jira" / "OCPBUGS-2222").is_dir()


class TestStateDatabaseTicketLinks:
    """Tests for StateDatabase case_ticket_links CRUD methods."""

    def test_add_and_get_tickets_for_case(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        assert "OHSS-52338" in db.get_tickets_for_case("04416520")

    def test_add_and_get_cases_for_ticket(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        assert "04416520" in db.get_cases_for_ticket("OHSS-52338")

    def test_idempotent_add(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        db.add_case_ticket_link("04416520", "OHSS-52338")  # should not raise
        assert db.get_tickets_for_case("04416520") == ["OHSS-52338"]

    def test_remove_link(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        db.remove_case_ticket_link("04416520", "OHSS-52338")
        assert "OHSS-52338" not in db.get_tickets_for_case("04416520")

    def test_remove_nonexistent_link(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        # Should not raise
        db.remove_case_ticket_link("04416520", "OHSS-99999")

    def test_empty_results(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        assert db.get_tickets_for_case("00000000") == []
        assert db.get_cases_for_ticket("NOPE-1") == []

    def test_multiple_tickets_per_case(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        db.add_case_ticket_link("04416520", "OHSS-99999")
        tickets = db.get_tickets_for_case("04416520")
        assert set(tickets) == {"OHSS-52338", "OHSS-99999"}

    def test_multiple_cases_per_ticket(self) -> None:
        from mc.container.state import StateDatabase
        db = StateDatabase(db_path=":memory:")
        db.add_case_ticket_link("04416520", "OHSS-52338")
        db.add_case_ticket_link("11111111", "OHSS-52338")
        cases = db.get_cases_for_ticket("OHSS-52338")
        assert set(cases) == {"04416520", "11111111"}
