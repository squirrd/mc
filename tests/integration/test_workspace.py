"""Integration tests for WorkspaceManager."""

import pytest
from pathlib import Path
from mc.controller.workspace import WorkspaceManager


@pytest.mark.integration
def test_attach_workspace_path_regression(tmp_path):
    """Regression test for fix/attach-workspace-path — three workspace bugs.

    Bug discovered: 2026-03-16
    Platform: macOS
    Severity: major
    Source: ad-hoc

    Problem:
    Running `mc attach <case_number>` fails with [Errno 2] No such file or directory
    because (1) the case directory is created at the wrong path (missing /cases/ prefix),
    (2) the workspace uses the old directory layout instead of the new canonical structure,
    and (3) get_attachment_dir() returns the path to the old 'files/attach' directory
    instead of the new 'sfdc/atts' directory, causing the download to target a path that
    was never created.

    Steps to reproduce:
    1. Run: mc attach 04389182
    2. Observe error: [Errno 2] No such file or directory: '.../files/attach/image.jpg'
    3. Observe the case directory is at ~/mc/Banque_Misr/... (missing /cases/)

    Expected: Case directory at <base_dir>/cases/<account>/<case> with the canonical
              structure (dt/logs, dt/metrics, jira/atts, notes/ai, oc, sfdc/atts) and
              get_attachment_dir() returning the sfdc/atts path so downloads land there.

    Actual:   Case directory at <base_dir>/<account>/<case> (missing /cases/), old
              structure (files/attach, files/dp, files/cp + numbered .md files),
              get_attachment_dir() returning 'files/attach' which is never created.

    This test ensures the bug does not regress.
    """
    ws = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Banque Misr",
        case_summary="Unable to deploy appli",
    )
    ws.create_files()

    # --- Bug 1: Case directory must be under cases/ subdirectory ---
    case_dir = tmp_path / "cases" / "Banque_Misr" / "12345678-Unable_to_deploy_appli"
    assert case_dir.is_dir(), (
        f"Case directory must exist at cases/<account>/<case>, not directly under base_dir. "
        f"Expected: {case_dir}"
    )

    # --- Bug 2: New canonical directory structure ---
    assert (case_dir / "sfdc" / "atts").is_dir(), "sfdc/atts must exist"
    assert (case_dir / "sfdc").is_dir(), "sfdc/ must exist"
    assert (case_dir / "dt" / "logs").is_dir(), "dt/logs must exist"
    assert (case_dir / "dt" / "metrics").is_dir(), "dt/metrics must exist"
    assert (case_dir / "jira" / "atts").is_dir(), "jira/atts must exist"
    assert (case_dir / "notes" / "ai").is_dir(), "notes/ai must exist"
    assert (case_dir / "oc").is_dir(), "oc/ must exist"

    # Notes files must be created
    assert (case_dir / "notes" / "notes-01.md").is_file(), "notes/notes-01.md must exist"
    assert (case_dir / "notes" / "notes-02.md").is_file(), "notes/notes-02.md must exist"
    assert (case_dir / "notes" / "notes-03.md").is_file(), "notes/notes-03.md must exist"
    assert (case_dir / "notes" / "tmp.md").is_file(), "notes/tmp.md must exist"

    # Old structure must NOT be created
    assert not (case_dir / "files").exists(), "Old 'files/' directory must NOT be created"

    # --- Bug 3: get_attachment_dir() must return sfdc/atts ---
    attach_dir = ws.get_attachment_dir()
    assert attach_dir is not None, "get_attachment_dir() must not return None"
    assert attach_dir.name == "atts", (
        f"Expected attachment dir name 'atts', got '{attach_dir.name}'"
    )
    assert "sfdc/atts" in str(attach_dir), (
        f"Expected attachment dir path to contain 'sfdc/atts', got: {attach_dir}"
    )
    # The directory must actually exist for downloads to land correctly
    assert attach_dir.is_dir(), "sfdc/atts directory must exist on disk after create_files()"
