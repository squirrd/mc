"""OCM refresh token expiry monitor for MC CLI.

Checks OCM refresh token expiry at startup and every 30 minutes.
Runs on host only (not in agent/container mode). When the token
expires within 60 minutes, prints a warning and triggers re-login.
"""
from __future__ import annotations

import atexit
import base64
import json
import logging
import os
import socket
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from mc.container.manager import get_ocm_config_path

logger = logging.getLogger(__name__)

_EXPIRY_WARNING_MINUTES = 60     # warn when token expires within this window
_POLL_INTERVAL_SECONDS = 1800    # 30 minutes
_OCM_LOGIN_PORT = 9998           # port used by ocm login --use-auth-code
_OCM_LOGIN_TIMEOUT = 300         # 5-minute timeout for ocm login subprocess
_CONSOLE = Console(stderr=True)  # stderr keeps stdout clean for scripts


def _get_pid_path() -> Path:
    """Return the PID file path for the OCM monitor daemon.

    Returns:
        Path to ~/mc/state/ocm-monitor.pid (creates parent dir if needed).
    """
    state_dir = Path.home() / "mc" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "ocm-monitor.pid"


def _is_pid_alive(pid: int) -> bool:
    """Check whether a process with the given PID is alive.

    Args:
        pid: Process ID to check.

    Returns:
        True if alive (or permission denied, meaning it belongs to another user),
        False if the process does not exist.
    """
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True  # alive but owned by another user
    except ProcessLookupError:
        return False


def _read_pid_file(path: Path) -> Optional[int]:
    """Read an integer PID from a file.

    Args:
        path: Path to PID file.

    Returns:
        Integer PID, or None on read/parse error.
    """
    try:
        return int(path.read_text().strip())
    except (ValueError, OSError):
        return None


def _write_pid_file(path: Path) -> None:
    """Write the current process PID to a file.

    Args:
        path: Path to write the PID file.
    """
    path.write_text(str(os.getpid()))


def _check_and_acquire_lock(pid_path: Path) -> bool:
    """Attempt to acquire the OCM monitor PID lock.

    Cleans up stale PID files (dead process). Returns False immediately
    if an alive process already holds the lock.

    Args:
        pid_path: Path to PID lock file.

    Returns:
        True if lock acquired, False if another process holds it.
    """
    existing_pid = _read_pid_file(pid_path)
    if existing_pid is not None:
        if _is_pid_alive(existing_pid):
            return False
        # Stale PID — clean up before acquiring
        pid_path.unlink(missing_ok=True)
    _write_pid_file(pid_path)
    return True


def _decode_jwt_exp(token: str) -> Optional[int]:
    """Decode a JWT and return the exp (expiry) claim.

    Only the middle (payload) segment is decoded. Does not verify signature.

    Args:
        token: JWT string in header.payload.signature format.

    Returns:
        Expiry timestamp as int, or None if decoding fails.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_segment = parts[1]
        # Restore base64 padding
        padding_needed = 4 - len(payload_segment) % 4
        if padding_needed != 4:
            payload_segment += "=" * padding_needed
        payload_bytes = base64.urlsafe_b64decode(payload_segment)
        payload = json.loads(payload_bytes)
        exp = payload.get("exp")
        if exp is None:
            return None
        return int(exp)
    except Exception:
        return None


def _read_refresh_token(ocm_path: Path) -> Optional[str]:
    """Read the refresh_token field from an OCM JSON config file.

    Args:
        ocm_path: Path to ocm.json.

    Returns:
        Refresh token string, or None if absent or unreadable.
    """
    try:
        data: dict[str, object] = json.loads(ocm_path.read_text())
        value = data.get("refresh_token")
        return str(value) if value is not None else None
    except Exception:
        return None


def _minutes_until_expiry(exp: int) -> int:
    """Calculate minutes remaining until a JWT expiry timestamp.

    Args:
        exp: Unix timestamp of token expiry.

    Returns:
        Minutes until expiry (negative if already expired).
    """
    return int((exp - time.time()) / 60)


def _is_port_bound(port: int, host: str = "127.0.0.1") -> bool:
    """Check whether a TCP port is already bound on the given host.

    Args:
        port: TCP port number to probe.
        host: Host address to check (default: loopback).

    Returns:
        True if the port is already in use, False if available.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        return result == 0
    except OSError:
        return False
    finally:
        sock.close()


class OCMMonitor:
    """Background OCM refresh token expiry monitor.

    Checks the OCM token at startup and polls every 30 minutes.
    Triggers re-login via 'ocm login --use-auth-code --url=prd'
    when the token is within 60 minutes of expiry.
    """

    def __init__(self) -> None:
        """Initialize the OCM monitor."""
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start_background_monitor(self) -> None:
        """Check OCM token expiry and start a daemon polling thread.

        Runs synchronously: checks token, prints warning if near expiry,
        then starts daemon thread for ongoing polling. No-op if OCM config
        is absent or token cannot be decoded.
        """
        ocm_path = get_ocm_config_path()

        if not ocm_path.exists():
            _CONSOLE.print(
                f"[cyan]\u2139 OCM config not found at {ocm_path} \u2014 "
                f"run 'ocm login' to set up[/cyan]"
            )
            return

        token = _read_refresh_token(ocm_path)
        if token is None:
            logger.debug("OCM refresh_token not found in %s", ocm_path)
            return

        exp = _decode_jwt_exp(token)
        if exp is None:
            logger.debug("OCM JWT decode failed for token in %s", ocm_path)
            return

        minutes_left = _minutes_until_expiry(exp)

        if minutes_left <= _EXPIRY_WARNING_MINUTES:
            _CONSOLE.print(
                f"[yellow]\u26a0 OCM token expires in {minutes_left} min "
                f"\u2014 re-logging in...[/yellow]"
            )
            # Fall through to start daemon thread (will run ocm login immediately)

        # Guard: skip if already running in this process
        if self._worker_thread and self._worker_thread.is_alive():
            return

        pid_path = _get_pid_path()
        if not _check_and_acquire_lock(pid_path):
            return  # Another process is already monitoring

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._monitor_worker,
            args=(minutes_left,),
            daemon=True,
            name="ocm-monitor",
        )
        self._worker_thread.start()

        atexit.register(self._cleanup)
        atexit.register(lambda: pid_path.unlink(missing_ok=True))

    def _cleanup(self) -> None:
        """Gracefully stop the daemon thread before process exit."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            return
        self._stop_event.set()
        self._worker_thread.join(timeout=2.0)

    def _monitor_worker(self, initial_minutes_left: int) -> None:
        """Daemon thread worker: runs ocm login if needed and polls every 30 min.

        Args:
            initial_minutes_left: Minutes until expiry at thread start time.
        """
        try:
            if initial_minutes_left <= _EXPIRY_WARNING_MINUTES:
                self._run_ocm_login()

            while not self._stop_event.wait(timeout=_POLL_INTERVAL_SECONDS):
                ocm_path = get_ocm_config_path()
                token = _read_refresh_token(ocm_path)
                if token is None:
                    continue
                exp = _decode_jwt_exp(token)
                if exp is None:
                    continue
                minutes_left = _minutes_until_expiry(exp)
                if minutes_left <= _EXPIRY_WARNING_MINUTES:
                    _CONSOLE.print(
                        f"[yellow]\u26a0 OCM token expires in {minutes_left} min "
                        f"\u2014 re-logging in...[/yellow]"
                    )
                    self._run_ocm_login()
        except Exception as e:
            logger.error("OCM monitor error: %s", e)

    def _run_ocm_login(self) -> None:
        """Run 'ocm login --use-auth-code --url=prd' to refresh the OCM token.

        Pre-checks port 9998 to avoid 'address already in use' errors when
        another ocm login process is already running. Passes a timeout to
        prevent indefinite hangs.
        """
        if _is_port_bound(_OCM_LOGIN_PORT):
            _CONSOLE.print(
                "[yellow]\u26a0 OCM login already running on port "
                f"{_OCM_LOGIN_PORT} \u2014 skipping re-login[/yellow]"
            )
            return

        try:
            result = subprocess.run(
                ["ocm", "login", "--use-auth-code", "--url=prd"],
                check=False,  # never raise; we handle returncode manually
                timeout=_OCM_LOGIN_TIMEOUT,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                stderr = result.stderr or ""
                if "address already in use" in stderr:
                    _CONSOLE.print(
                        "[yellow]\u26a0 OCM login port already in use \u2014 "
                        "another 'ocm login' is already running[/yellow]"
                    )
                else:
                    _CONSOLE.print(
                        "[yellow]\u26a0 OCM re-login failed \u2014 "
                        "please run 'ocm login' manually[/yellow]"
                    )
        except subprocess.TimeoutExpired:
            _CONSOLE.print(
                "[yellow]\u26a0 OCM login timed out \u2014 "
                "please run 'ocm login' manually[/yellow]"
            )
        except FileNotFoundError:
            _CONSOLE.print(
                "[yellow]\u26a0 'ocm' not found in PATH \u2014 "
                "please run 'ocm login' manually[/yellow]"
            )
        except Exception as e:
            logger.error("OCM login subprocess failed: %s", e)


def start_background_monitor() -> None:
    """Start OCM token background monitor. No-op if already running."""
    monitor = OCMMonitor()
    monitor.start_background_monitor()
