"""Unit tests for WorkspaceManager."""

from pathlib import Path
import pytest
from mc.controller.workspace import WorkspaceManager


def create_workspace(tmp_path, case_number="12345678", account="Red Hat Inc", summary="Test Summary"):
    """Helper function to create WorkspaceManager instance with tmp_path."""
    return WorkspaceManager(
        base_dir=str(tmp_path),
        case_number=case_number,
        account_name=account,
        case_summary=summary
    )


def test_workspace_initialization(tmp_path):
    """Test workspace initialization with formatted names and correct entry counts."""
    ws = create_workspace(
        tmp_path,
        case_number="12345678",
        account="Red Hat Inc",
        summary="Test Summary"
    )

    assert ws.account_name_formatted == "Red_Hat_Inc"
    assert ws.case_summary_formatted == "Test_Summary"

    # New structure: 10 dirs + 4 files = 14 entries
    assert len(ws.file_dir_list) == 14

    types = [entry[0] for entry in ws.file_dir_list]
    assert types.count("D") == 10
    assert types.count("F") == 4


def test_workspace_create_files_structure(tmp_path):
    """Test workspace creation with the canonical directory and file structure."""
    ws = create_workspace(
        tmp_path,
        case_number="12345678",
        account="Red Hat Inc",
        summary="Test Summary"
    )

    ws.create_files()

    # Case dir is now under cases/
    base_case_path = tmp_path / "cases" / "Red_Hat_Inc" / "12345678-Test_Summary"

    # Directories
    assert (base_case_path / "dt").is_dir()
    assert (base_case_path / "dt" / "logs").is_dir()
    assert (base_case_path / "dt" / "metrics").is_dir()
    assert (base_case_path / "jira").is_dir()
    assert (base_case_path / "jira" / "atts").is_dir()
    assert (base_case_path / "notes").is_dir()
    assert (base_case_path / "notes" / "ai").is_dir()
    assert (base_case_path / "oc").is_dir()
    assert (base_case_path / "sfdc").is_dir()
    assert (base_case_path / "sfdc" / "atts").is_dir()

    # Files
    assert (base_case_path / "notes" / "notes-01.md").is_file()
    assert (base_case_path / "notes" / "notes-02.md").is_file()
    assert (base_case_path / "notes" / "notes-03.md").is_file()
    assert (base_case_path / "notes" / "tmp.md").is_file()

    # Old structure must not exist
    assert not (base_case_path / "files").exists()

    # Path is under cases/
    assert str(base_case_path).endswith("cases/Red_Hat_Inc/12345678-Test_Summary")


def test_workspace_check_status_ok(tmp_path, caplog):
    """Test check() returns OK when all files exist."""
    import logging
    caplog.set_level(logging.INFO)

    ws = create_workspace(tmp_path)
    ws.create_files()

    status = ws.check()

    assert status == "OK"
    assert "CheckStatus: OK" in caplog.text


def test_workspace_check_status_warn(tmp_path, caplog):
    """Test check() returns WARN when files don't exist."""
    import logging
    caplog.set_level(logging.WARNING)

    ws = create_workspace(tmp_path)
    # Don't call create_files() - files won't exist

    status = ws.check()

    assert status == "WARN"
    assert "does not exist" in caplog.text


def test_workspace_check_status_fatal(tmp_path, caplog):
    """Test check() returns FATAL when file type is wrong."""
    import logging
    caplog.set_level(logging.ERROR)

    ws = create_workspace(tmp_path)
    ws.create_files()

    # Replace a file with directory (wrong file type)
    base_case_path = tmp_path / "cases" / "Red_Hat_Inc" / "12345678-Test_Summary"
    file_path = base_case_path / "notes" / "notes-01.md"
    file_path.unlink()  # Remove file
    file_path.mkdir()   # Create directory at file path

    status = ws.check()

    assert status == "FATAL"
    assert "Expected file, found directory" in caplog.text


def test_get_attachment_dir(tmp_path):
    """Test get_attachment_dir() returns sfdc/atts path."""
    ws = create_workspace(tmp_path)

    attach_dir = ws.get_attachment_dir()

    assert attach_dir is not None
    assert attach_dir.name == 'atts'
    assert "sfdc/atts" in str(attach_dir)


def test_workspace_with_special_characters_in_names(tmp_path):
    """Test workspace creation with special characters in account and summary."""
    ws = create_workspace(
        tmp_path,
        case_number="99999999",
        account="Test@Company#123",
        summary="Issue with special chars!"
    )

    assert "@" not in ws.account_name_formatted
    assert "#" not in ws.account_name_formatted
    assert "!" not in ws.case_summary_formatted
    assert "_" in ws.account_name_formatted

    ws.create_files()

    # New structure — verify sfdc/atts exists under cases/
    base_case_path = tmp_path / "cases" / ws.account_name_formatted / f"99999999-{ws.case_summary_formatted}"
    assert (base_case_path / "sfdc" / "atts").is_dir()
