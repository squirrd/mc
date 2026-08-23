"""Integration tests for agent case data file operations.

Tests verify that SFDC files are written to and read from the correct
filesystem paths within the case directory structure.
"""
from __future__ import annotations

import json

import pytest


# ---------------------------------------------------------------------------
# MC-106 quiet startup regression tests
# ---------------------------------------------------------------------------

CASE_NUMBER = "12345678"


@pytest.mark.integration
def test_mc_106_quiet_startup_no_token_silent_regression(tmp_path, mocker, capsys) -> None:
    """Regression test for fix/MC-106-quiet-startup (MC-106).

    Bug discovered: 2026-08-23
    Platform: In-container
    Severity: minor
    Source: MC-106

    Problem:
    When a container shell opens, attach.py runs
    'mc agent init-case || true; mc agent backplane-login || true' before the
    interactive bash session. If no offline token is configured, init_case_data()
    prints to stdout:

        Warning: No offline token in config — cannot fetch case data

    This message appears before the first bash prompt, degrading the UX with
    unexpected noise.

    Steps to reproduce:
    1. Ensure no offline token is in the mc config (e.g., first-run container)
    2. Attach to a container: the init-case command runs before exec bash
    3. Observe "Warning: No offline token in config — cannot fetch case data" in terminal

    Expected: init_case_data() silently skips when no token is configured —
              no stdout output (use logger.debug() for internal diagnostics only).
    Actual:   print("Warning: No offline token in config — cannot fetch case data")
              is called, producing noise before the bash prompt.

    This test ensures the bug does not regress.
    """
    from mc.agent.case_data import init_case_data

    # Simulate container with no offline token in config (common on first run)
    mock_config_mgr = mocker.MagicMock()
    mock_config_mgr.load.return_value = {"api": {}}  # no token key
    mocker.patch("mc.config.manager.ConfigManager", return_value=mock_config_mgr)

    init_case_data(CASE_NUMBER, case_dir=str(tmp_path))

    captured = capsys.readouterr()
    assert captured.out == "", (
        f"init_case_data() must produce no stdout when token is absent "
        f"(use logger.debug not print for skipped-fetch conditions), got:\n{captured.out!r}"
    )


@pytest.mark.integration
def test_mc_106_quiet_startup_ocm_failure_silent_regression(tmp_path, mocker, capsys) -> None:
    """Regression test for fix/MC-106-quiet-startup — OCM lookup path (MC-106).

    Bug discovered: 2026-08-23
    Platform: In-container
    Severity: minor
    Source: MC-106

    Problem:
    When the SFDC case has an openshiftClusterID and OCM is not logged in,
    init_case_data() prints to stdout:

        Warning: ocm get cluster failed (exit 1): Cluster not found

    This appears before the bash prompt.

    Expected: OCM lookup failures are logged at debug level only — no stdout.
    Actual:   print("Warning: ocm get cluster failed ...") produces terminal noise.

    This test ensures the bug does not regress.
    """
    from mc.agent.case_data import init_case_data

    # Config with valid token so we get past the token check
    mock_config_mgr = mocker.MagicMock()
    mock_config_mgr.load.return_value = {"api": {"rh_api_offline_token": "fake-token"}}
    mocker.patch("mc.config.manager.ConfigManager", return_value=mock_config_mgr)
    mocker.patch("mc.utils.auth.get_access_token", return_value="access_token")

    # SFDC API returns a case that has a cluster external ID
    case_details = {
        "caseNumber": CASE_NUMBER,
        "customerName": "ACME Corp",
        "summary": "Cluster node NotReady",
        "severity": "3 (Normal)",
        "status": "Waiting on Customer",
        "product": "OpenShift Container Platform",
        "openshiftClusterID": "abc-cluster-ext-id-123",
    }
    mock_api = mocker.MagicMock()
    mock_api.fetch_case_details.return_value = case_details
    mock_api.fetch_case_comments.return_value = []
    mocker.patch("mc.integrations.redhat_api.RedHatAPIClient", return_value=mock_api)

    # OCM is not logged in — lookup fails with non-zero exit code (404)
    mocker.patch(
        "subprocess.run",
        return_value=mocker.MagicMock(returncode=1, stderr="Cluster not found (404)"),
    )

    init_case_data(CASE_NUMBER, case_dir=str(tmp_path))

    captured = capsys.readouterr()
    assert captured.out == "", (
        f"init_case_data() must produce no stdout when OCM lookup fails "
        f"(use logger.debug not print), got:\n{captured.out!r}"
    )


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


@pytest.mark.integration
def test_MC_85_vpn_hint_api_errors_regression(tmp_path, mocker):
    """Regression test for fix/MC-85-vpn-hint-api-errors (MC-85).

    Bug discovered: 2026-05-26
    Platform: Both
    Severity: high
    Source: MC-85

    Problem:
    APIConnectionError is raised with a suggestion containing the VPN hint
    ("Check: VPN connection and network access"), but str(e) only returns
    the message, not the suggestion. Any caller that catches the exception
    and displays it via str(e) or f"{e}" (e.g., case_data.py line 58:
    ``print(f"Warning: Failed to fetch case details: {e}")``) loses the
    VPN hint entirely.

    The root cause is that MCError inherits Exception.__str__() which only
    returns the first positional argument (the message). The suggestion
    attribute is set but never included in the string representation.

    Steps to reproduce:
    1. Create an APIConnectionError with message and suggestion
    2. Call str() on it
    3. Observe that the suggestion (VPN hint) is missing

    Expected: str(APIConnectionError) includes both the message and the
              suggestion so callers using str(e) see the VPN hint.
    Actual:   str(APIConnectionError) returns only the message; the VPN
              hint in the suggestion attribute is silently dropped.

    This test ensures the bug does not regress.
    """
    from mc.exceptions import APIConnectionError, MCError

    # Verify at the MCError base level — all subclasses inherit this behavior
    base_error = MCError(
        "Something went wrong",
        suggestion="Try: check your configuration",
    )
    base_str = str(base_error)
    assert "check your configuration" in base_str, (
        f"MCError.__str__() must include suggestion but got: {base_str!r}"
    )

    # Verify the specific APIConnectionError case from the bug report
    api_error = APIConnectionError(
        "Failed to connect to API for case 04448394",
        "Check: VPN connection and network access",
    )
    api_str = str(api_error)
    assert "VPN" in api_str, (
        f"str(APIConnectionError) must include VPN hint but got: {api_str!r}"
    )
    assert "Failed to connect to API for case 04448394" in api_str, (
        f"str(APIConnectionError) must still include the message but got: {api_str!r}"
    )

    # Verify that errors WITHOUT a suggestion still work correctly
    no_suggestion_error = MCError("Plain error message")
    no_suggestion_str = str(no_suggestion_error)
    assert no_suggestion_str == "Plain error message", (
        f"MCError without suggestion should return just the message but got: "
        f"{no_suggestion_str!r}"
    )

    # Verify the end-to-end path: case_data.py uses f"{e}" in warning messages.
    # Simulate what case_data.py does when it catches an APIConnectionError.
    warning_message = f"Warning: Failed to fetch case details: {api_error}"
    assert "VPN" in warning_message, (
        f"f-string interpolation of APIConnectionError must show VPN hint "
        f"but got: {warning_message!r}"
    )


@pytest.mark.integration
def test_mc_119_ocm_external_id_lookup_regression(tmp_path, mocker):
    """Regression test for fix/MC-119-ocm-external-id-lookup (MC-119).

    Bug discovered: 2026-08-11
    Platform: In-container
    Severity: major
    Source: MC-119

    Problem:
    init_case_data() passes the SFDC external_id UUID directly to
    ``ocm get cluster <external_id>``, but OCM's ``get cluster`` command
    expects an internal cluster ID. When given an external_id UUID, OCM
    returns a 404:

        {"kind": "Error", "id": "404", "code": "CLUSTERS-MGMT-404",
         "reason": "Cluster '6b22598e-...' not found"}

    The fix is to use the OCM search API endpoint:
        ocm get /api/clusters_mgmt/v1/clusters --parameter search="external_id='<uuid>'"

    Steps to reproduce:
    1. Have a case with openshiftClusterID set to an external_id UUID
    2. Call init_case_data() for that case
    3. Observe the subprocess.run command constructed for OCM

    Expected: Command uses the search API with external_id filter.
    Actual:   Command passes external_id directly as ``ocm get cluster <uuid>``,
              causing a 404 on OCM.

    This test ensures the bug does not regress.
    """
    from mc.agent.case_data import init_case_data

    external_id = "6b22598e-5bdc-408f-a500-5c8a6d091413"

    case_details = {
        "summary": "Pod OOMKilled on prod",
        "accountNumberRef": "9876543",
        "status": "Open",
        "severity": "2 (High)",
        "product": "OpenShift Container Platform",
        "customerName": "Acme Corp",
        "openshiftClusterID": external_id,
    }

    # Mock external dependencies (API calls, auth) — not subprocess under test
    mock_config_mgr = mocker.MagicMock()
    mock_config_mgr.load.return_value = {"api": {"rh_api_offline_token": "tok"}}
    mocker.patch("mc.config.manager.ConfigManager", return_value=mock_config_mgr)
    mocker.patch("mc.utils.auth.get_access_token", return_value="access_token")

    mock_api = mocker.MagicMock()
    mock_api.fetch_case_details.return_value = case_details
    mock_api.fetch_case_comments.return_value = []
    mocker.patch(
        "mc.integrations.redhat_api.RedHatAPIClient", return_value=mock_api
    )

    # Mock subprocess.run so we can inspect the command without calling ocm
    mock_subprocess = mocker.patch(
        "subprocess.run",
        return_value=mocker.MagicMock(
            returncode=0,
            stdout='{"items": [{"kind": "Cluster", "id": "abc-internal-123"}]}',
        ),
    )

    init_case_data("12345678", case_dir=str(tmp_path))

    # subprocess.run must have been called for the OCM lookup
    mock_subprocess.assert_called_once()

    actual_cmd = mock_subprocess.call_args[0][0]

    # The command must NOT be the naive "ocm get cluster <external_id>" form
    assert actual_cmd != ["ocm", "get", "cluster", external_id], (
        f"Bug present: code passes external_id directly to 'ocm get cluster' "
        f"instead of using the OCM search API. Got: {actual_cmd}"
    )

    # The command must use the OCM search API endpoint
    cmd_str = " ".join(actual_cmd)
    assert "/api/clusters_mgmt/v1/clusters" in cmd_str, (
        f"Expected OCM search API endpoint in command, got: {actual_cmd}"
    )

    # The command must include external_id in a search parameter
    assert "external_id" in cmd_str, (
        f"Expected external_id filter in search parameter, got: {actual_cmd}"
    )
