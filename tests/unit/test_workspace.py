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
    """Test workspace initialization with formatted names."""
    ws = create_workspace(
        tmp_path,
        case_number="12345678",
        account="Red Hat Inc",
        summary="Test Summary"
    )

    # Verify formatted names use shorten_and_format
    assert ws.account_name_formatted == "Red_Hat_Inc"
    assert ws.case_summary_formatted == "Test_Summary"

    # Verify file_dir_list is generated (should have 9 entries: 4 dirs + 5 files)
    assert len(ws.file_dir_list) == 9

    # Verify structure includes expected types
    types = [entry[0] for entry in ws.file_dir_list]
    assert types.count("D") == 4  # directories
    assert types.count("F") == 5  # files


def test_workspace_create_files_structure(tmp_path):
    """Test workspace creation with proper directory and file structure."""
    ws = create_workspace(
        tmp_path,
        case_number="12345678",
        account="Red Hat Inc",
        summary="Test Summary"
    )

    # Create files and directories
    ws.create_files()

    # Expected base path
    base_case_path = tmp_path / "Red_Hat_Inc" / "12345678-Test_Summary"

    # Verify directories created
    assert (base_case_path / "files").exists()
    assert (base_case_path / "files" / "attach").is_dir()
    assert (base_case_path / "files" / "dp").is_dir()
    assert (base_case_path / "files" / "cp").is_dir()

    # Verify files created
    assert (base_case_path / "00-caseComments.md").is_file()
    assert (base_case_path / "10-notes.md").is_file()
    assert (base_case_path / "20-notes.md").is_file()
    assert (base_case_path / "30-notes.md").is_file()
    assert (base_case_path / "80-scratch.md").is_file()

    # Verify directory structure pattern
    assert str(base_case_path).endswith("Red_Hat_Inc/12345678-Test_Summary")


def test_workspace_check_status_ok(tmp_path, caplog):
    """Test check() returns OK when all files exist."""
    import logging
    caplog.set_level(logging.INFO)

    ws = create_workspace(tmp_path)
    ws.create_files()

    status = ws.check()

    # Verify status
    assert status == "OK"
    assert "CheckStatus: OK" in caplog.text


def test_workspace_check_status_warn(tmp_path, caplog):
    """Test check() returns WARN when files don't exist."""
    import logging
    caplog.set_level(logging.WARNING)

    ws = create_workspace(tmp_path)
    # Don't call create_files() - files won't exist

    status = ws.check()

    # Verify status
    assert status == "WARN"
    assert "does not exist" in caplog.text


def test_workspace_check_status_fatal(tmp_path, caplog):
    """Test check() returns FATAL when file type is wrong."""
    import logging
    caplog.set_level(logging.ERROR)

    ws = create_workspace(tmp_path)
    ws.create_files()

    # Replace a file with directory (wrong file type)
    base_case_path = tmp_path / "Red_Hat_Inc" / "12345678-Test_Summary"
    file_path = base_case_path / "00-caseComments.md"
    file_path.unlink()  # Remove file
    file_path.mkdir()   # Create directory at file path

    status = ws.check()

    # Verify status
    assert status == "FATAL"
    assert "Expected file, found directory" in caplog.text


def test_get_attachment_dir(tmp_path):
    """Test get_attachment_dir() returns correct path."""
    ws = create_workspace(tmp_path)

    attach_dir = ws.get_attachment_dir()

    # Verify it's a Path object
    assert attach_dir is not None
    assert attach_dir.name == 'attach'

    # Verify path structure
    assert "Red_Hat_Inc/12345678-Test_Summary/files/attach" in str(attach_dir)


def test_workspace_with_special_characters_in_names(tmp_path):
    """Test workspace creation with special characters in account and summary."""
    ws = create_workspace(
        tmp_path,
        case_number="99999999",
        account="Test@Company#123",
        summary="Issue with special chars!"
    )

    # Verify formatted names use underscores (via shorten_and_format)
    assert "@" not in ws.account_name_formatted
    assert "#" not in ws.account_name_formatted
    assert "!" not in ws.case_summary_formatted
    assert "_" in ws.account_name_formatted  # Spaces/special chars replaced

    # Create files and verify structure created successfully
    ws.create_files()

    # Verify at least one directory exists (proves structure was created)
    base_case_path = tmp_path / ws.account_name_formatted / f"99999999-{ws.case_summary_formatted}"
    assert (base_case_path / "files").exists()
