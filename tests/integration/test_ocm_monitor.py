"""Integration tests for OCM monitor — ocm login retry / port conflict handling.

Tests for the _run_ocm_login() method in mc.utils.ocm_monitor, validating that
concurrent ocm login invocations are handled gracefully rather than crashing with
'address already in use' errors.
"""
from __future__ import annotations

import socket
from unittest.mock import MagicMock, patch

import pytest

from mc.utils.ocm_monitor import OCMMonitor


@pytest.mark.integration
class TestOcmLoginRetryRegression:
    """Regression test for MC-6 / ocm-login-retry.

    Bug discovered: 2026-05-06
    Platform: Both (macOS / Linux)
    Severity: major
    Source: MC-6

    Problem:
    When ocm login is already running (holding port 9998), a second mc
    invocation triggers another ocm login which fails with 'address already
    in use' because _run_ocm_login() has no timeout, no check for existing
    ocm login processes, and no user-friendly error handling for port
    conflicts.

    Steps to reproduce:
    1. Start mc case <number> in one terminal (triggers ocm login, binds port 9998)
    2. Start mc case <number> in a second terminal concurrently
    3. Second instance calls _run_ocm_login() which also tries to bind port 9998
    4. 'listen tcp :9998: bind: address already in use' error appears

    Expected: _run_ocm_login() detects port conflict or existing ocm login process,
              provides a user-friendly message, and does not hang indefinitely.
    Actual:   Generic 'OCM re-login failed' message with no port-conflict context,
              and subprocess.run called without timeout (can hang forever).

    This test ensures the bug does not regress.
    """

    @patch("mc.utils.ocm_monitor._is_port_bound", return_value=False)
    def test_ocm_login_retry_regression_port_conflict_message(
        self,
        _mock_port: MagicMock,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When ocm login fails with 'address already in use', the user must see
        a message that indicates another ocm login is already running or that
        port 9998 is occupied — not just a generic failure message.
        """
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "listen tcp :9998: bind: address already in use"

        monitor = OCMMonitor()

        with patch("mc.utils.ocm_monitor.subprocess.run", return_value=mock_result):
            monitor._run_ocm_login()

        captured = capsys.readouterr()
        combined = (captured.out + captured.err).lower()
        assert "already running" in combined or "port" in combined or "in use" in combined, (
            f"Expected user-friendly message about port conflict / existing ocm login, "
            f"but got stdout={captured.out!r}, stderr={captured.err!r}"
        )

    @patch("mc.utils.ocm_monitor._is_port_bound", return_value=False)
    def test_ocm_login_retry_regression_timeout(self, _mock_port: MagicMock) -> None:
        """_run_ocm_login() must pass a timeout to subprocess.run so that it
        cannot hang indefinitely when ocm login blocks on port acquisition
        or user interaction.
        """
        monitor = OCMMonitor()

        with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            monitor._run_ocm_login()

            assert mock_run.called, "subprocess.run was not called"
            _, kwargs = mock_run.call_args
            assert "timeout" in kwargs, (
                "subprocess.run called without timeout= keyword argument — "
                "_run_ocm_login() can hang indefinitely"
            )

    def test_ocm_login_retry_regression_skips_when_port_bound(self) -> None:
        """When port 9998 is already bound (another ocm login is in progress),
        _run_ocm_login() should detect the conflict and either skip the login
        entirely or perform a pre-check before launching 'ocm login'.

        It must NOT blindly launch 'ocm login' when the port is occupied.
        """
        monitor = OCMMonitor()

        # Bind port 9998 to simulate an existing ocm login holding it
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 9998))
            sock.listen(1)

            with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                monitor._run_ocm_login()

                # Collect the calls to subprocess.run
                calls = mock_run.call_args_list
                login_calls = [
                    c
                    for c in calls
                    if c[0] and "ocm" in str(c[0][0]) and "login" in str(c[0][0])
                ]

                # The code should either:
                # a) Not call 'ocm login' at all (detected port in use, skipped), OR
                # b) Have made a pre-check call before calling 'ocm login'
                check_calls = [c for c in calls if c not in login_calls]
                assert len(check_calls) > 0 or not login_calls, (
                    "_run_ocm_login() launched 'ocm login' without checking "
                    "whether port 9998 is already in use — will cause "
                    "'listen tcp :9998: bind: address already in use'"
                )
        finally:
            sock.close()


@pytest.mark.integration
class TestOcmPortGuardTestsRegression:
    """Regression test for MC-70 / ocm-port-guard-tests

    Bug discovered: 2026-05-19
    Platform: Both
    Severity: minor
    Source: MC-70

    Problem:
    Tests that call _run_ocm_login() with subprocess.run mocked do not
    also mock _is_port_bound(). When a real process happens to listen on
    port 9998, the port guard inside _run_ocm_login() sees the port as
    bound, early-returns before reaching subprocess.run, and the mock
    assertion "subprocess.run was called" fails. The tests are
    environment-dependent: they pass when port 9998 is free and fail
    when it is occupied.

    Steps to reproduce:
    1. Start any process that listens on port 9998 (e.g. another ocm login)
    2. Run a test that mocks subprocess.run but not _is_port_bound()
    3. _is_port_bound() returns True (real port check), guard early-returns
    4. subprocess.run mock is never invoked, assertion fails

    Expected: Tests that exercise the subprocess.run code path in
              _run_ocm_login() must mock _is_port_bound() so they are
              deterministic regardless of host port state.
    Actual:   Tests omit the _is_port_bound mock and fail when port 9998
              is occupied — AssertionError: subprocess.run was not called.

    This test ensures the bug does not regress.
    """

    @patch("mc.utils.ocm_monitor._is_port_bound", return_value=False)
    def test_ocm_port_guard_tests_regression(self, _mock_port: MagicMock) -> None:
        """Verify that mocking _is_port_bound prevents the port guard from
        short-circuiting _run_ocm_login() even when port 9998 is bound.

        This test binds port 9998 to simulate a real-world condition where
        another process occupies the OCM login port, then calls
        _run_ocm_login() with BOTH subprocess.run AND _is_port_bound mocked.
        Because _is_port_bound returns False (mocked), the port guard does
        not early-return, and subprocess.run IS called.

        Before the fix, tests omitted the _is_port_bound mock and failed
        when port 9998 happened to be occupied on the host.
        """
        monitor = OCMMonitor()

        # Bind port 9998 to simulate real-world condition
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("127.0.0.1", 9998))
            sock.listen(1)

            with patch("mc.utils.ocm_monitor.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                monitor._run_ocm_login()

                # With _is_port_bound mocked to False, the port guard
                # no longer blocks, so subprocess.run IS called.
                assert mock_run.called, (
                    "subprocess.run was not called — _is_port_bound() mock "
                    "did not prevent the port guard from early-returning"
                )
        finally:
            sock.close()
