"""Unit tests for mc.utils.ocm_monitor module.

Tests cover:
- _decode_jwt_exp(): valid JWT, missing exp, malformed segments
- _read_refresh_token(): present/absent key, missing file, invalid JSON
- _minutes_until_expiry(): future and past expiry
- PID lock helpers: acquire, detect alive, clean stale
- start_background_monitor() / OCMMonitor.start_background_monitor(): OCM file absent,
  token missing, token expiring soon, token fresh, PID lock already held

Patching strategy:
- mc.utils.ocm_monitor.get_ocm_config_path — controls OCM path used by module
- mc.utils.ocm_monitor._check_and_acquire_lock — skips thread start in most tests
- mc.utils.ocm_monitor._get_pid_path — controls PID file location
- mc.utils.ocm_monitor._is_pid_alive — controls aliveness result in PID lock tests
"""
from __future__ import annotations

import base64
import json
import os
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mc.utils.ocm_monitor import (
    OCMMonitor,
    _check_and_acquire_lock,
    _decode_jwt_exp,
    _minutes_until_expiry,
    _read_refresh_token,
    _write_pid_file,
    start_background_monitor,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_jwt(payload: dict[str, Any]) -> str:
    """Create a JWT-shaped string with base64url-encoded payload."""
    payload_bytes = json.dumps(payload).encode()
    b64 = base64.urlsafe_b64encode(payload_bytes).rstrip(b"=").decode()
    return f"header.{b64}.signature"


# ---------------------------------------------------------------------------
# TestDecodeJwtExp
# ---------------------------------------------------------------------------


class TestDecodeJwtExp:
    """Tests for _decode_jwt_exp()."""

    def test_valid_jwt_returns_exp(self) -> None:
        """Returns exp value from a well-formed JWT."""
        token = _make_jwt({"exp": 9999999999})
        assert _decode_jwt_exp(token) == 9999999999

    def test_expired_jwt_returns_exp(self) -> None:
        """Returns exp even when in the past (caller decides meaning)."""
        token = _make_jwt({"exp": 1})
        assert _decode_jwt_exp(token) == 1

    def test_missing_exp_claim_returns_none(self) -> None:
        """Returns None when payload lacks the exp field."""
        token = _make_jwt({"sub": "user"})
        assert _decode_jwt_exp(token) is None

    def test_invalid_format_not_three_parts_returns_none(self) -> None:
        """Returns None when the token has more than three dot-separated parts."""
        assert _decode_jwt_exp("not.a.valid.jwt.extra") is None

    def test_empty_string_returns_none(self) -> None:
        """Returns None for empty string input."""
        assert _decode_jwt_exp("") is None

    def test_malformed_base64_returns_none(self) -> None:
        """Returns None when payload segment is not valid base64."""
        assert _decode_jwt_exp("header.!!!notbase64!!!.sig") is None


# ---------------------------------------------------------------------------
# TestReadRefreshToken
# ---------------------------------------------------------------------------


class TestReadRefreshToken:
    """Tests for _read_refresh_token()."""

    def test_reads_refresh_token(self, tmp_path: Path) -> None:
        """Returns refresh_token value when present in JSON file."""
        f = tmp_path / "ocm.json"
        f.write_text(json.dumps({"refresh_token": "tok123"}))
        assert _read_refresh_token(f) == "tok123"

    def test_returns_none_when_key_absent(self, tmp_path: Path) -> None:
        """Returns None when refresh_token key is not in the JSON."""
        f = tmp_path / "ocm.json"
        f.write_text(json.dumps({"other": "data"}))
        assert _read_refresh_token(f) is None

    def test_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        """Returns None when the file does not exist."""
        assert _read_refresh_token(tmp_path / "missing.json") is None

    def test_returns_none_when_invalid_json(self, tmp_path: Path) -> None:
        """Returns None when the file contains non-JSON content."""
        f = tmp_path / "ocm.json"
        f.write_text("not json")
        assert _read_refresh_token(f) is None


# ---------------------------------------------------------------------------
# TestMinutesUntilExpiry
# ---------------------------------------------------------------------------


class TestMinutesUntilExpiry:
    """Tests for _minutes_until_expiry()."""

    def test_future_expiry_positive(self) -> None:
        """Returns a positive value close to 60 when expiry is 1 hour out."""
        exp = int(time.time()) + 3600
        result = _minutes_until_expiry(exp)
        assert abs(result - 60) <= 2

    def test_past_expiry_negative(self) -> None:
        """Returns a negative value close to -60 when expiry was 1 hour ago."""
        exp = int(time.time()) - 3600
        result = _minutes_until_expiry(exp)
        assert abs(result - (-60)) <= 2


# ---------------------------------------------------------------------------
# TestPidLock
# ---------------------------------------------------------------------------


class TestPidLock:
    """Tests for _check_and_acquire_lock() and PID file helpers."""

    def test_acquires_lock_when_no_file(self, tmp_path: Path) -> None:
        """Acquires lock and creates PID file when none exists."""
        pid_path = tmp_path / "test.pid"
        assert _check_and_acquire_lock(pid_path) is True
        assert pid_path.exists()

    def test_written_pid_is_current_process(self, tmp_path: Path) -> None:
        """PID written to file equals os.getpid()."""
        pid_path = tmp_path / "test.pid"
        _check_and_acquire_lock(pid_path)
        assert int(pid_path.read_text()) == os.getpid()

    def test_returns_false_when_alive_pid_exists(self, tmp_path: Path) -> None:
        """Returns False when a live process already holds the lock."""
        pid_path = tmp_path / "test.pid"
        # Current process PID is guaranteed alive
        _write_pid_file(pid_path)
        assert _check_and_acquire_lock(pid_path) is False

    def test_cleans_stale_pid_and_acquires(self, tmp_path: Path) -> None:
        """Removes stale PID file and writes current PID when process is dead."""
        pid_path = tmp_path / "test.pid"
        pid_path.write_text("99999999")  # almost certainly dead
        with patch("mc.utils.ocm_monitor._is_pid_alive", return_value=False):
            result = _check_and_acquire_lock(pid_path)
        assert result is True
        assert pid_path.read_text() == str(os.getpid())


# ---------------------------------------------------------------------------
# TestStartBackgroundMonitor
# ---------------------------------------------------------------------------


class TestStartBackgroundMonitor:
    """Tests for OCMMonitor.start_background_monitor() and start_background_monitor()."""

    def test_prints_info_when_ocm_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints info message to stderr when ocm.json does not exist."""
        missing = tmp_path / "missing.json"
        with patch("mc.utils.ocm_monitor.get_ocm_config_path", return_value=missing):
            start_background_monitor()
        captured = capsys.readouterr()
        assert "OCM config not found" in captured.err
        assert "ocm login" in captured.err

    def test_no_output_when_refresh_token_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Silent (debug-only) when ocm.json exists but has no refresh_token."""
        ocm_file = tmp_path / "ocm.json"
        ocm_file.write_text(json.dumps({"other": "data"}))
        with patch("mc.utils.ocm_monitor.get_ocm_config_path", return_value=ocm_file):
            start_background_monitor()
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_prints_warning_when_token_expiring_soon(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Prints yellow warning when token expires within 60-minute window."""
        exp = int(time.time()) + (30 * 60)  # 30 minutes from now
        token = _make_jwt({"exp": exp})
        ocm_file = tmp_path / "ocm.json"
        ocm_file.write_text(json.dumps({"refresh_token": token}))
        with patch("mc.utils.ocm_monitor.get_ocm_config_path", return_value=ocm_file):
            with patch(
                "mc.utils.ocm_monitor._check_and_acquire_lock", return_value=False
            ):
                start_background_monitor()
        captured = capsys.readouterr()
        assert "OCM token expires in" in captured.err
        assert "re-logging in" in captured.err

    def test_no_warning_when_token_fresh(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No warning printed when token expires more than 60 minutes from now."""
        exp = int(time.time()) + (120 * 60)  # 2 hours from now
        token = _make_jwt({"exp": exp})
        ocm_file = tmp_path / "ocm.json"
        ocm_file.write_text(json.dumps({"refresh_token": token}))
        with patch("mc.utils.ocm_monitor.get_ocm_config_path", return_value=ocm_file):
            with patch(
                "mc.utils.ocm_monitor._check_and_acquire_lock", return_value=False
            ):
                start_background_monitor()
        captured = capsys.readouterr()
        assert "OCM token expires" not in captured.err

    def test_skips_monitor_when_pid_lock_held(self, tmp_path: Path) -> None:
        """Worker thread is never started when another process holds the PID lock."""
        exp = int(time.time()) + (120 * 60)
        token = _make_jwt({"exp": exp})
        ocm_file = tmp_path / "ocm.json"
        ocm_file.write_text(json.dumps({"refresh_token": token}))
        with patch("mc.utils.ocm_monitor.get_ocm_config_path", return_value=ocm_file):
            with patch("mc.utils.ocm_monitor._get_pid_path", return_value=tmp_path / "test.pid"):
                with patch(
                    "mc.utils.ocm_monitor._check_and_acquire_lock", return_value=False
                ):
                    monitor = OCMMonitor()
                    monitor.start_background_monitor()
        assert monitor._worker_thread is None

    def test_start_background_monitor_blocks_until_login_complete(
        self, tmp_path: Path
    ) -> None:
        """MC-78: start_background_monitor() must call _run_ocm_login() synchronously
        on the calling thread when the token is expired/near-expiry.

        Bug: _run_ocm_login() was only called inside the daemon thread, meaning
        start_background_monitor() returned immediately with the stale token
        still on disk. The container was then created with the expired token.

        This test verifies that _run_ocm_login() is called on the main thread
        (the thread that called start_background_monitor()), not on a daemon thread.
        """
        import threading

        # Create an expired token (10 minutes ago)
        exp = int(time.time()) - (10 * 60)
        token = _make_jwt({"exp": exp})
        ocm_file = tmp_path / "ocm.json"
        ocm_file.write_text(json.dumps({"refresh_token": token}))
        pid_path = tmp_path / "test.pid"

        login_thread_name: Optional[str] = None
        calling_thread_name = threading.current_thread().name

        def tracking_login(self_ref: OCMMonitor) -> None:
            nonlocal login_thread_name
            login_thread_name = threading.current_thread().name

        monitor = OCMMonitor()
        with (
            patch(
                "mc.utils.ocm_monitor.get_ocm_config_path",
                return_value=ocm_file,
            ),
            patch("mc.utils.ocm_monitor._get_pid_path", return_value=pid_path),
            patch.object(OCMMonitor, "_run_ocm_login", tracking_login),
        ):
            monitor.start_background_monitor()

        # Give the daemon thread a moment to run if it calls login
        time.sleep(0.5)

        # _run_ocm_login must have been called
        assert login_thread_name is not None, (
            "start_background_monitor() never called _run_ocm_login() despite "
            "expired token."
        )
        # It must have been called on the calling thread, not the daemon thread
        assert login_thread_name == calling_thread_name, (
            f"_run_ocm_login() was called on thread '{login_thread_name}' "
            f"instead of the calling thread '{calling_thread_name}'. "
            f"When the OCM token is expired, login must run synchronously on "
            f"the caller's thread so the token is refreshed before the caller "
            f"proceeds to create the container."
        )

        # Cleanup
        monitor._stop_event.set()
        if monitor._worker_thread:
            monitor._worker_thread.join(timeout=3)


# ---------------------------------------------------------------------------
# TestRunOcmLoginPortGuard
# ---------------------------------------------------------------------------


class TestRunOcmLoginPortGuard:
    """Tests for _run_ocm_login() port-conflict detection, timeout, and messaging.

    Regression tests for MC-6 / ocm-login-retry: _run_ocm_login() must:
    1. Pass a timeout to subprocess.run to prevent indefinite hangs
    2. Check if port 9998 is already bound before launching 'ocm login'
    3. Print a user-friendly message when port conflict is detected
    """

    @patch("mc.utils.ocm_monitor._is_port_bound", return_value=False)
    def test_run_ocm_login_passes_timeout_to_subprocess(
        self, _mock_port: MagicMock
    ) -> None:
        """subprocess.run must be called with a timeout= kwarg."""
        monitor = OCMMonitor()
        with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            monitor._run_ocm_login()

            assert mock_run.called, "subprocess.run was not called"
            _, kwargs = mock_run.call_args
            assert "timeout" in kwargs, (
                "subprocess.run called without timeout= — _run_ocm_login() can hang indefinitely"
            )
            assert isinstance(kwargs["timeout"], (int, float))
            assert kwargs["timeout"] > 0

    def test_run_ocm_login_skips_when_port_9998_bound(self) -> None:
        """When port 9998 is already bound, _run_ocm_login() must not launch 'ocm login'."""
        import socket

        monitor = OCMMonitor()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 9998))
            sock.listen(1)

            with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                monitor._run_ocm_login()

                login_calls = [
                    c
                    for c in mock_run.call_args_list
                    if c[0] and "ocm" in str(c[0][0]) and "login" in str(c[0][0])
                ]
                assert not login_calls, (
                    "_run_ocm_login() launched 'ocm login' while port 9998 was already bound"
                )
        finally:
            sock.close()

    def test_run_ocm_login_port_conflict_message(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When port 9998 is already bound, the output must mention the conflict."""
        import socket

        monitor = OCMMonitor()

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 9998))
            sock.listen(1)

            with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                monitor._run_ocm_login()

            captured = capsys.readouterr()
            combined = (captured.out + captured.err).lower()
            assert (
                "already running" in combined
                or "port" in combined
                or "in use" in combined
            ), (
                f"Expected user-friendly port-conflict message, "
                f"got stdout={captured.out!r}, stderr={captured.err!r}"
            )
        finally:
            sock.close()

    @patch("mc.utils.ocm_monitor._is_port_bound", return_value=False)
    def test_run_ocm_login_address_in_use_stderr_message(
        self, _mock_port: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When ocm login returns 'address already in use' in stderr, the user
        must see a message about port conflict, not just a generic failure."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "listen tcp :9998: bind: address already in use"

        monitor = OCMMonitor()

        with patch("mc.utils.ocm_monitor.subprocess.run", return_value=mock_result):
            monitor._run_ocm_login()

        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert (
            "already running" in combined
            or "port" in combined
            or "in use" in combined
        ), (
            f"Expected port-conflict context in output, "
            f"got stdout={captured.out!r}, stderr={captured.err!r}"
        )
