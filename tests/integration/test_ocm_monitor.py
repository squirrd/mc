"""Integration tests for OCM monitor — ocm login retry / port conflict handling.

Tests for the _run_ocm_login() method in mc.utils.ocm_monitor, validating that
concurrent ocm login invocations are handled gracefully rather than crashing with
'address already in use' errors.
"""
from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from mc.integrations.podman import PodmanClient
from mc.utils.ocm_monitor import (
    OCMMonitor,
    _decode_jwt_exp,
    _minutes_until_expiry,
)


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


def _podman_available() -> bool:
    """Check if Podman is available and accessible."""
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


def _make_expired_jwt(minutes_ago: int = 10) -> str:
    """Create a JWT with an exp claim that expired `minutes_ago` minutes ago.

    Use negative values for a token that expires in the future.
    """
    header = (
        base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        )
        .decode()
        .rstrip("=")
    )
    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"exp": int(time.time()) - (minutes_ago * 60)}).encode()
        )
        .decode()
        .rstrip("=")
    )
    sig = base64.urlsafe_b64encode(b"fake-signature").decode().rstrip("=")
    return f"{header}.{payload}.{sig}"


@pytest.mark.integration
@pytest.mark.skipif(not _podman_available(), reason="Podman not available")
def test_mc_78_ocm_sync_login_regression() -> None:
    """Regression test for MC-78 / ocm-sync-login — async OCM login race condition.

    Bug discovered: 2026-05-20
    Platform: Both
    Severity: major
    Source: MC-78

    Problem:
    start_background_monitor() detects an expired OCM refresh token but spawns
    'ocm login' in a daemon thread and returns immediately. The caller
    (cli/main.py) then proceeds to attach_terminal() which creates a container
    that bind-mounts the host's ocm.json. Because start_background_monitor()
    returned before 'ocm login' completed, the container receives the stale
    (still-expired) ocm.json. Inside the container, 'mc agent init-case' and
    'mc agent backplane-login' fail because the mounted token is expired.

    Steps to reproduce:
    1. Have an expired OCM refresh token in ocm.json
    2. Run 'mc case 12345678'
    3. start_background_monitor() detects expiry, prints warning, spawns daemon thread
    4. start_background_monitor() returns immediately (daemon thread still running ocm login)
    5. attach_terminal() creates container, bind-mounting the stale ocm.json
    6. mc agent init-case / backplane-login fail inside container with expired credentials

    Expected: When OCM token is near or past expiry, start_background_monitor() blocks
              until 'ocm login' completes (or fails) before returning, so the container
              receives a fresh token.
    Actual:   start_background_monitor() returns before 'ocm login' finishes; container
              is created with the stale expired token.

    This test ensures the bug does not regress.
    """
    # 1. Create a temporary ocm.json with an expired refresh token
    expired_token = _make_expired_jwt(minutes_ago=10)
    ocm_json_content = json.dumps({"refresh_token": expired_token})

    with tempfile.TemporaryDirectory() as tmpdir:
        ocm_dir = Path(tmpdir) / "ocm"
        ocm_dir.mkdir()
        ocm_json_path = ocm_dir / "ocm.json"
        ocm_json_path.write_text(ocm_json_content)

        # 2. Call start_background_monitor() with our expired token.
        # Mock _run_ocm_login to simulate a slow login (sleeps 5s, then writes fresh token).
        monitor = OCMMonitor()

        def slow_ocm_login(self_ref: OCMMonitor) -> None:
            """Simulate a slow ocm login that takes time to refresh the token."""
            time.sleep(5)
            fresh_token = _make_expired_jwt(minutes_ago=-120)  # expires 2h from now
            ocm_json_path.write_text(json.dumps({"refresh_token": fresh_token}))

        pid_path = Path(tmpdir) / "ocm-monitor.pid"

        with (
            patch(
                "mc.utils.ocm_monitor.get_ocm_config_path",
                return_value=ocm_json_path,
            ),
            patch("mc.utils.ocm_monitor._get_pid_path", return_value=pid_path),
            patch.object(
                OCMMonitor,
                "_run_ocm_login",
                lambda self: slow_ocm_login(self),
            ),
        ):
            # This detects the expired token, prints a warning, and spawns the
            # daemon thread. With the bug present it returns IMMEDIATELY while
            # the thread is still "logging in" (sleeping 5s).
            monitor.start_background_monitor()

        # 3. Immediately after start_background_monitor() returns, create a real
        # container that bind-mounts the (potentially still stale) ocm.json.
        # In the real code flow, attach_terminal() does exactly this.
        container_name = "mc-99998877"
        client = PodmanClient()
        container = None

        try:
            workspace_path = os.path.join(tmpdir, "workspace")
            os.makedirs(workspace_path, exist_ok=True)

            container = client.client.containers.create(
                image="mc-rhel10:latest",
                name=container_name,
                command=["/bin/bash", "-c", "tail -f /dev/null"],
                detach=True,
                labels={"mc.managed": "true", "mc.case_number": "99998877"},
                environment={
                    "CASE_NUMBER": "99998877",
                    "MC_RUNTIME_MODE": "agent",
                },
                volumes={
                    workspace_path: {"bind": "/case", "mode": "rw"},
                    str(ocm_json_path): {
                        "bind": "/home/mcuser/.config/ocm/ocm.json",
                        "mode": "ro",
                    },
                },
                userns_mode="keep-id",
                tty=True,
                stdin_open=True,
            )
            container.start()

            # 4. Read the token from INSIDE the container via podman exec.
            result = subprocess.run(
                [
                    "podman",
                    "exec",
                    container_name,
                    "cat",
                    "/home/mcuser/.config/ocm/ocm.json",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            assert result.returncode == 0, (
                f"Failed to read ocm.json from container: {result.stderr}"
            )

            container_ocm = json.loads(result.stdout)
            container_token = container_ocm.get("refresh_token", "")
            exp = _decode_jwt_exp(container_token)
            assert exp is not None, "Could not decode JWT from container's ocm.json"

            minutes_left = _minutes_until_expiry(exp)

            # THE BUG ASSERTION (host->container boundary):
            # If start_background_monitor() blocked until ocm login completed,
            # the token on disk would be fresh (>0 min to expiry) and the container
            # would receive the fresh token. With the bug present, the daemon thread
            # is still sleeping and the container has the stale expired token.
            assert minutes_left > 0, (
                f"Container has an expired OCM token (expires in {minutes_left} min). "
                f"start_background_monitor() returned before ocm login completed, "
                f"so the container was created with the stale token. "
                f"The fix must ensure the token is refreshed BEFORE the container "
                f"is created."
            )

        finally:
            if container is not None:
                try:
                    container.stop(timeout=2)
                except Exception:
                    pass
                try:
                    container.remove()
                except Exception:
                    pass
            monitor._stop_event.set()
            if monitor._worker_thread:
                monitor._worker_thread.join(timeout=3)
