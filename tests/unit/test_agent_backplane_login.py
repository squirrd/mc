"""Unit tests for mc.agent.backplane_login."""

from __future__ import annotations

import json
import subprocess
from unittest.mock import MagicMock

import pytest

from mc.agent.backplane_login import (
    _is_token_expired,
    _read_sfdc_cluster_id,
    run_backplane_login,
    validate_cluster_id,
)
from mc.container.state import StateDatabase


# --- validate_cluster_id ---


def test_validate_cluster_id_accepts_valid_id() -> None:
    assert validate_cluster_id("abc-cluster-123") is True


def test_validate_cluster_id_rejects_empty() -> None:
    assert validate_cluster_id("") is False


def test_validate_cluster_id_rejects_too_short() -> None:
    assert validate_cluster_id("abc") is False


def test_validate_cluster_id_rejects_spaces() -> None:
    assert validate_cluster_id("abc cluster 123") is False


# --- _is_token_expired ---


def test_token_expired_detects_token_expired_phrase() -> None:
    assert _is_token_expired("Error: token is expired") is True


def test_token_expired_detects_401() -> None:
    assert _is_token_expired("HTTP 401 Unauthorized") is True


def test_token_expired_returns_false_for_generic_error() -> None:
    assert _is_token_expired("connection refused") is False


# --- _read_sfdc_cluster_id ---


def test_read_sfdc_cluster_id_returns_value(tmp_path: pytest.TempPathFactory) -> None:
    sfdc = tmp_path / "sfdc-case.json"  # type: ignore[operator]
    sfdc.write_text(json.dumps({"openshiftClusterID": "abc-123-xyz"}))
    assert _read_sfdc_cluster_id(str(tmp_path)) == "abc-123-xyz"


def test_read_sfdc_cluster_id_returns_empty_when_file_missing(tmp_path: pytest.TempPathFactory) -> None:
    assert _read_sfdc_cluster_id(str(tmp_path)) == ""


def test_read_sfdc_cluster_id_returns_empty_when_field_absent(tmp_path: pytest.TempPathFactory) -> None:
    sfdc = tmp_path / "sfdc-case.json"  # type: ignore[operator]
    sfdc.write_text(json.dumps({"caseNumber": "12345678"}))
    assert _read_sfdc_cluster_id(str(tmp_path)) == ""


def test_read_sfdc_cluster_id_returns_empty_when_field_is_none(tmp_path: pytest.TempPathFactory) -> None:
    sfdc = tmp_path / "sfdc-case.json"  # type: ignore[operator]
    sfdc.write_text(json.dumps({"openshiftClusterID": None}))
    assert _read_sfdc_cluster_id(str(tmp_path)) == ""


# --- Source priority ---


def test_sfdc_case_json_cluster_id_wins_over_state_db(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """sfdc-case.json cluster_id takes priority; subprocess is called with sfdc cluster_id."""
    sfdc = tmp_path / "sfdc-case.json"  # type: ignore[operator]
    sfdc.write_text(json.dumps({"openshiftClusterID": "sfdc-cluster-id"}))

    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="state-cluster-id")

    mock_run = mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "sfdc-cluster-id" in call_args


def test_state_db_cluster_id_used_when_sfdc_absent(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """StateDatabase cluster_id is used when sfdc-case.json has no cluster_id."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="stored-cluster-id")

    mock_run = mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "stored-cluster-id" in call_args


def test_user_prompted_when_no_cluster_id_available(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """User is prompted when neither sfdc nor StateDatabase has a cluster_id."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")

    mocker.patch("mc.agent.backplane_login.input", return_value="user-cluster-abc")
    mock_run = mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "user-cluster-abc" in call_args


def test_user_skip_opens_shell_without_login(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """Empty user input causes early return; subprocess is never called."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")

    mocker.patch("mc.agent.backplane_login.input", return_value="")
    mock_run = mocker.patch("mc.agent.backplane_login.subprocess.run")

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    mock_run.assert_not_called()


# --- Persistence ---


def test_successful_login_persists_user_entered_id_to_state_db(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """User-entered cluster_id is written to StateDatabase on successful login."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")

    mocker.patch("mc.agent.backplane_login.input", return_value="user-cluster-abc")
    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    result = db.get_container("12345678")
    assert result is not None
    assert result.cluster_id == "user-cluster-abc"


def test_sfdc_cluster_id_not_persisted_to_state_db(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """sfdc-sourced cluster_id is NOT written to StateDatabase after login."""
    sfdc = tmp_path / "sfdc-case.json"  # type: ignore[operator]
    sfdc.write_text(json.dumps({"openshiftClusterID": "sfdc-cluster-id"}))

    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    result = db.get_container("12345678")
    assert result is not None
    assert result.cluster_id == ""  # unchanged


def test_state_db_cluster_id_not_re_persisted(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """StateDatabase-sourced cluster_id is NOT re-persisted after successful login."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="stored-cluster-id")

    mock_update = mocker.patch.object(db, "update_container")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=0, stdout="", stderr=""),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    # update_container should not have been called (no persistence for state_db source)
    mock_update.assert_not_called()


# --- Failure paths ---


def test_failed_login_clears_state_db_cluster_id(tmp_path: pytest.TempPathFactory, mocker: MagicMock) -> None:
    """Failed login clears stored cluster_id from StateDatabase."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="old-cluster-id")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="connection refused"),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    result = db.get_container("12345678")
    assert result is not None
    assert result.cluster_id == ""


def test_failed_login_prints_warning(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """Non-zero exit prints generic warning message."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="some-cluster-id")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="connection refused"),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    captured = capsys.readouterr()
    assert "Warning" in captured.out
    assert "backplane login failed" in captured.out


def test_token_expiry_prints_targeted_message(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """Token expiry in stderr prints targeted re-authentication message, not generic warning."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="some-cluster-id")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        return_value=MagicMock(returncode=1, stdout="", stderr="Error: token is expired"),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    captured = capsys.readouterr()
    assert "OCM token expired" in captured.out
    assert "ocm login" in captured.out
    assert "backplane login failed" not in captured.out


def test_ocm_not_found_warns_and_skips(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """Missing ocm binary prints warning and returns without error."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="some-cluster-id")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        side_effect=FileNotFoundError("No such file: ocm"),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    captured = capsys.readouterr()
    assert "ocm binary not found" in captured.out


def test_timeout_warns_and_skips(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """subprocess.TimeoutExpired prints warning and returns without error."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")
    db.update_container("12345678", cluster_id="some-cluster-id")

    mocker.patch(
        "mc.agent.backplane_login.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["ocm"], timeout=120),
    )

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    captured = capsys.readouterr()
    assert "timed out" in captured.out


def test_invalid_cluster_id_format_prints_warning_and_skips(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """Invalid cluster_id format from user input skips login with warning."""
    db = StateDatabase(":memory:")
    db.add_container("12345678", "cid1", "/ws")

    mocker.patch("mc.agent.backplane_login.input", return_value="bad id!")
    mock_run = mocker.patch("mc.agent.backplane_login.subprocess.run")

    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=db)

    mock_run.assert_not_called()
    captured = capsys.readouterr()
    assert "invalid" in captured.out


def test_state_db_inaccessible_degrades_gracefully(tmp_path: pytest.TempPathFactory, mocker: MagicMock, capsys: pytest.CaptureFixture) -> None:
    """When StateDatabase cannot be constructed (no mount), backplane login still runs via prompt."""
    # Patch StateDatabase constructor to raise an exception (simulates missing mount)
    mocker.patch(
        "mc.agent.backplane_login.StateDatabase",
        side_effect=Exception("database not accessible"),
    )
    mocker.patch("mc.agent.backplane_login.input", return_value="")

    # Should not raise; should just skip login
    run_backplane_login("12345678", case_dir=str(tmp_path), state_db=None)

    captured = capsys.readouterr()
    # No crash — graceful return
    assert "Error" not in captured.out
