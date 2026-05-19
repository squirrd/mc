"""Integration tests for agent case data file operations.

Tests verify that SFDC files are written to and read from the correct
filesystem paths within the case directory structure.
"""
from __future__ import annotations

import json

import pytest


@pytest.mark.integration
def test_sfdc_file_save_path_regression(tmp_path, mocker):
    """Regression test for fix/sfdc-file-save-path (MC-73).

    Bug discovered: 2026-05-19
    Platform: Both
    Severity: minor
    Source: MC-73

    Problem:
    init_case_data() writes sfdc-case.json and sfdc-comments.json to the case
    root directory instead of the sfdc/ subdirectory. The reader function
    _read_sfdc_cluster_id() in backplane_login.py also reads from the wrong
    path (case root instead of sfdc/), masking the write-side bug when both
    writer and reader are equally wrong.

    Steps to reproduce:
    1. Call init_case_data("12345678", case_dir=<tmp>)
    2. Check whether sfdc-case.json exists at <tmp>/sfdc/sfdc-case.json
    3. Check whether sfdc-comments.json exists at <tmp>/sfdc/sfdc-comments.json

    Expected: Files are written to <case_dir>/sfdc/sfdc-case.json and
              <case_dir>/sfdc/sfdc-comments.json.
    Actual:   Files are written to <case_dir>/sfdc-case.json and
              <case_dir>/sfdc-comments.json (case root, not sfdc/ subdir).

    This test ensures the bug does not regress.
    """
    from mc.agent.case_data import init_case_data

    case_details = {
        "summary": "Test case",
        "status": "Open",
        "severity": "2 (High)",
        "product": "OpenShift",
        "customerName": "Acme",
        "openshiftClusterID": "",
    }

    # Mock external dependencies (API calls, auth) — not the file I/O under test
    mock_config_mgr = mocker.MagicMock()
    mock_config_mgr.load.return_value = {"api": {"rh_api_offline_token": "tok"}}
    mocker.patch("mc.config.manager.ConfigManager", return_value=mock_config_mgr)
    mocker.patch("mc.utils.auth.get_access_token", return_value="access_token")

    mock_api = mocker.MagicMock()
    mock_api.fetch_case_details.return_value = case_details
    mock_api.fetch_case_comments.return_value = [{"id": "c1", "text": "First comment"}]
    mocker.patch("mc.integrations.redhat_api.RedHatAPIClient", return_value=mock_api)

    # Create the sfdc/ subdirectory (workspace creates this; init_case_data should write into it)
    sfdc_dir = tmp_path / "sfdc"
    sfdc_dir.mkdir()

    init_case_data("12345678", case_dir=str(tmp_path))

    # Assert files land in sfdc/ subdirectory, not in case root
    assert (sfdc_dir / "sfdc-case.json").exists(), (
        f"sfdc-case.json not found at {sfdc_dir}/sfdc-case.json — "
        "init_case_data wrote to case root instead of sfdc/ subdirectory"
    )
    assert (sfdc_dir / "sfdc-comments.json").exists(), (
        f"sfdc-comments.json not found at {sfdc_dir}/sfdc-comments.json — "
        "init_case_data wrote to case root instead of sfdc/ subdirectory"
    )

    # Verify file contents are valid JSON with expected data
    with open(sfdc_dir / "sfdc-case.json") as f:
        saved_case = json.load(f)
    assert saved_case["summary"] == "Test case"

    with open(sfdc_dir / "sfdc-comments.json") as f:
        saved_comments = json.load(f)
    assert len(saved_comments) == 1
    assert saved_comments[0]["id"] == "c1"


@pytest.mark.integration
def test_backplane_login_reads_sfdc_from_subdirectory_regression(tmp_path):
    """Regression test for fix/sfdc-file-save-path reader side (MC-73).

    Bug discovered: 2026-05-19
    Platform: Both
    Severity: minor
    Source: MC-73

    Problem:
    _read_sfdc_cluster_id() reads sfdc-case.json from the case root directory
    instead of the sfdc/ subdirectory. When the file is placed at the correct
    path (sfdc/sfdc-case.json), the reader cannot find it and returns an
    empty string.

    Steps to reproduce:
    1. Create <case_dir>/sfdc/sfdc-case.json with a valid openshiftClusterID
    2. Call _read_sfdc_cluster_id(case_dir)
    3. Observe return value

    Expected: Returns the cluster ID from <case_dir>/sfdc/sfdc-case.json.
    Actual:   Returns empty string because it looks for <case_dir>/sfdc-case.json.

    This test ensures the bug does not regress.
    """
    from mc.agent.backplane_login import _read_sfdc_cluster_id

    # Place sfdc-case.json in the CORRECT location (sfdc/ subdirectory)
    sfdc_dir = tmp_path / "sfdc"
    sfdc_dir.mkdir()
    sfdc_file = sfdc_dir / "sfdc-case.json"
    sfdc_file.write_text(json.dumps({"openshiftClusterID": "correct-cluster-123"}))

    # Reader should find it in the sfdc/ subdirectory
    result = _read_sfdc_cluster_id(str(tmp_path))
    assert result == "correct-cluster-123", (
        f"Expected 'correct-cluster-123' from sfdc/sfdc-case.json, got '{result}' — "
        "_read_sfdc_cluster_id reads from case root instead of sfdc/ subdirectory"
    )
