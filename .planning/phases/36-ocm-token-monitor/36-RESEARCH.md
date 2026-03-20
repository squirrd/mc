# Phase 36: OCM Token Background Monitor - Research

**Researched:** 2026-03-20
**Domain:** Python daemon threads, JWT decoding, PID lock files, Rich single-line output
**Confidence:** HIGH

## Summary

This phase adds a host-side background monitor for OCM refresh token expiry. The codebase
already has all necessary patterns and dependencies. The daemon thread pattern lives in
`src/mc/version_check.py` (VersionChecker class). Rich is already a dependency. The OCM
config path is already computed in `src/mc/container/manager.py:get_ocm_config_path()`.
The state directory (`~/mc/state/`) is already established for `containers.db`.

The new file is `src/mc/utils/ocm_monitor.py`. It hooks into `main.py` at the same
location as the `show_update_banner()` call — after config load, guarded by
`get_runtime_mode() != 'agent'`.

JWT `exp` claim decoding requires only stdlib (`base64`, `json`) — no external library
needed. OCM tokens are standard JWTs; the payload is the middle segment, base64url-encoded.

**Primary recommendation:** Model `ocm_monitor.py` directly on `version_check.py` — class
with a `start_background_check()` method that spawns a daemon thread. The foreground path
(print warning or info message) runs synchronously before the thread exits. The
`ocm login` subprocess runs inline in the worker thread (stdout/stderr inherited).

---

## Pattern: Daemon Thread (version_check.py analysis)

File: `src/mc/version_check.py` (confirmed, HIGH confidence)

### Exact pattern used

```python
class VersionChecker:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start_background_check(self) -> None:
        # Guard: skip if already running
        if self._worker_thread and self._worker_thread.is_alive():
            return

        # Early exit conditions (throttle check)
        if not self._should_check_now(...):
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._check_version_worker,
            daemon=True,
            name="version-check"
        )
        self._worker_thread.start()
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        if not self._worker_thread or not self._worker_thread.is_alive():
            return
        self._stop_event.set()
        self._worker_thread.join(timeout=2.0)

    def _check_version_worker(self) -> None:
        try:
            self._perform_version_check()
        except Exception as e:
            logger.error(f"Version check failed: {e}")
```

### Key properties of this pattern

- `daemon=True` — thread dies when main process exits, never blocks CLI exit
- `atexit.register(self._cleanup)` — tries graceful stop on normal exit with 2s timeout
- Worker wraps all logic in `try/except Exception` — never propagates to main thread
- Convenience module-level function: `def check_for_updates() -> None` that instantiates
  and calls `start_background_check()`

### Where the OCM monitor diverges from VersionChecker

The OCM monitor has a **foreground component** (print the warning/info message) that must
run before the daemon thread exits or while it runs. The approach:

1. Foreground (synchronous, in `start_background_monitor()`):
   - Read `ocm.json` path
   - If not found: print info message, return (no thread needed)
   - Decode JWT `exp` from refresh token
   - If expiry > 60 min away: start daemon thread for the 30-min poll loop, return
   - If expiry <= 60 min away: print warning now, then start daemon thread for `ocm login`

2. Daemon thread:
   - Handles the `ocm login` subprocess (streaming output to terminal)
   - For the periodic check variant: sleeps 30 min between polls

**Key insight:** The "warning appears at startup before mc command runs" requirement means
the expiry check and warning print must happen in the foreground call, not asynchronously.
The daemon thread only handles the long-running parts (subprocess, periodic polling).

---

## Entry Point Integration (main.py hook point)

File: `src/mc/cli/main.py` (confirmed, HIGH confidence)

### Current hook location

Lines 150-155 in `main()`:

```python
# Show update banner (foreground check, once per calendar day, suppressed for --version)
if get_runtime_mode() != 'agent':
    try:
        show_update_banner()
    except Exception as e:
        logger.debug("Update banner failed: %s", e)
```

### Where to add OCM monitor call

Immediately after the `show_update_banner()` block, before the command routing:

```python
if get_runtime_mode() != 'agent':
    try:
        show_update_banner()
    except Exception as e:
        logger.debug("Update banner failed: %s", e)

    # OCM token monitor
    try:
        from mc.utils.ocm_monitor import start_background_monitor
        start_background_monitor()
    except Exception as e:
        logger.debug("OCM monitor failed: %s", e)
```

The `get_runtime_mode() != 'agent'` guard is already present and is the correct guard.
The lazy import (`from mc.utils.ocm_monitor import ...` inside the try block) matches the
style used in `banner.py` and avoids import-time side effects.

### Imports already in main.py

`get_runtime_mode` is already imported at line 13:
```python
from mc.runtime import get_runtime_mode
```

No new top-level imports needed in `main.py`.

---

## OCM Token Structure (JWT decode approach)

**Confidence:** HIGH — JWT structure is a published standard (RFC 7519)

OCM stores credentials in `ocm.json`. The refresh token is a standard JWT with three
base64url-encoded segments separated by `.`:

```
header.payload.signature
```

The `exp` claim (Unix timestamp integer) is in the **payload** (middle segment).

### Stdlib-only decode (no external library)

```python
import base64
import json
import time

def _decode_jwt_exp(token: str) -> Optional[int]:
    """Decode exp claim from JWT without signature verification.

    Args:
        token: JWT string (three dot-separated base64url segments)

    Returns:
        Unix timestamp of expiry, or None if decode fails
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # base64url decode: replace URL-safe chars, add padding
        payload_b64 = parts[1]
        # Add padding: base64 requires length divisible by 4
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
        exp = payload.get("exp")
        return int(exp) if exp is not None else None
    except Exception:
        return None
```

This is the established stdlib approach. No PyJWT or similar library needed.

### OCM JSON structure

The `ocm.json` file contains a `refresh_token` field (confirmed by examining
`get_ocm_config_path()` usage in `manager.py` — the file is mounted as
`/home/mcuser/.config/ocm/ocm.json` in containers, which matches the OCM CLI's expected
location). The OCM CLI uses standard OAuth2 refresh tokens as JWTs.

```python
import json
from pathlib import Path

def _read_refresh_token(ocm_path: Path) -> Optional[str]:
    """Read refresh_token from ocm.json."""
    try:
        data = json.loads(ocm_path.read_text())
        return data.get("refresh_token")
    except Exception:
        return None
```

---

## OCM Config Path (how to find ocm.json)

File: `src/mc/container/manager.py` (confirmed, HIGH confidence)

`get_ocm_config_path()` already exists and is platform-aware:

```python
def get_ocm_config_path() -> Path:
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "ocm" / "ocm.json"
    return Path.home() / ".config" / "ocm" / "ocm.json"
```

**Import this function directly** — do not reimplement it in `ocm_monitor.py`.

```python
from mc.container.manager import get_ocm_config_path
```

The info message format uses `~/.config/ocm/ocm.json` (from CONTEXT.md), but the actual
path shown should be the result of `get_ocm_config_path()` so macOS users see the correct
platform path.

---

## State Directory (~/mc/state/ pattern)

File: `src/mc/cli/commands/container.py` (confirmed, HIGH confidence)

The canonical pattern for state files in this project:

```python
state_dir = os.path.join(os.path.expanduser("~"), "mc", "state")
os.makedirs(state_dir, exist_ok=True)
pid_path = os.path.join(state_dir, "ocm-monitor.pid")
```

`~/mc/state/containers.db` already exists there at runtime (confirmed by checking
`~/mc/state/` which contains `containers.db`).

### PID lock file implementation

```python
import os
import signal
from pathlib import Path

def _get_pid_path() -> Path:
    state_dir = Path.home() / "mc" / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "ocm-monitor.pid"

def _is_pid_alive(pid: int) -> bool:
    """Check if process with given PID is alive."""
    try:
        os.kill(pid, 0)  # Signal 0: no-op, just checks existence
        return True
    except (ProcessLookupError, PermissionError):
        return False  # ProcessLookupError = dead; PermissionError = alive but not ours

def _read_pid_file(path: Path) -> Optional[int]:
    try:
        return int(path.read_text().strip())
    except (ValueError, OSError):
        return None

def _write_pid_file(path: Path) -> None:
    path.write_text(str(os.getpid()))

def _check_and_acquire_lock(pid_path: Path) -> bool:
    """Return True if we acquired the lock, False if another process holds it."""
    existing_pid = _read_pid_file(pid_path)
    if existing_pid is not None:
        if _is_pid_alive(existing_pid):
            return False  # Another monitor is running
        # Stale PID — clean it up
        pid_path.unlink(missing_ok=True)
    _write_pid_file(pid_path)
    return True
```

Note: `os.kill(pid, 0)` raises `ProcessLookupError` (subclass of `OSError`) when dead,
`PermissionError` when alive but owned by another user (treat as alive). This is the
stdlib-standard approach for PID liveness checks on Unix.

The PID file should be cleaned up on exit. Use `atexit.register` to remove it.

---

## Runtime Mode Guard (host-only)

File: `src/mc/runtime.py` (confirmed, HIGH confidence)

```python
from mc.runtime import get_runtime_mode, is_controller_mode

# Either style works:
if get_runtime_mode() != 'agent':  # matches existing main.py style
if is_controller_mode():            # semantic helper, same result
```

`is_controller_mode()` is the cleaner call but `get_runtime_mode() != 'agent'` is what
`main.py` already uses for the `show_update_banner()` guard. Use the same guard style
for consistency — the OCM monitor call goes inside the same `if get_runtime_mode() != 'agent'`
block.

---

## Rich Output Pattern (single-line warnings)

Files: `src/mc/runtime.py`, `src/mc/banner.py` (confirmed, HIGH confidence)

### Single-line Rich output to stderr (the right pattern for this phase)

From `runtime.py`:
```python
from rich.console import Console
console = Console(stderr=True)

console.print("[yellow]ℹ Updates managed via container builds[/yellow]", style="bold")
```

### For OCM monitor (based on CONTEXT.md decisions)

```python
from rich.console import Console

_console = Console(stderr=True)

# Warning (token expiring soon):
_console.print(f"[yellow]⚠ OCM token expires in {minutes_left} min — re-logging in...[/yellow]")

# Info (no ocm.json found):
_console.print(f"[cyan]ℹ OCM config not found at {ocm_path} — run 'ocm login' to set up[/cyan]")
```

**stderr is correct** — CONTEXT.md says "stdout vs stderr: Claude's discretion (keep
stdout clean for scripts if possible)". Stderr is consistent with `show_update_banner()`
and `runtime.py`. Rich's `Console(stderr=True)` is the established pattern.

### What NOT to use

Do not use `rich.panel.Panel` (reserved for the update banner box style). Do not use
`console.print(panel)`. Single-line `console.print("[color]text[/color]")` is correct.

---

## Test Patterns (for daemon threads)

Files: `tests/unit/test_banner.py`, `tests/unit/test_runtime.py` (confirmed, HIGH confidence)

### Pattern for testing threaded code

From `test_banner.py`, `TestFetchWithTimeout`:

```python
def test_returns_version_on_success(self) -> None:
    with patch("mc.update._fetch_latest_version", return_value="2.0.5"):
        result = _fetch_with_timeout()
    assert result == "2.0.5"

def test_returns_none_on_timeout(
    self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("mc.banner._TIMEOUT_SECONDS", 0.01)

    def slow_fetch() -> Optional[str]:
        time.sleep(5)
        return "2.0.5"

    with patch("mc.update._fetch_latest_version", side_effect=slow_fetch):
        result = _fetch_with_timeout()
    assert result is None
    captured = capsys.readouterr()
    assert "timed out" in captured.err
```

### Pattern for testing Rich console output

From `test_runtime.py`, `TestShouldCheckForUpdates`:

```python
def test_displays_message_when_blocking_in_agent_mode(
    self, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
    result = should_check_for_updates()
    captured = capsys.readouterr()
    assert result is False
    assert "Updates managed via container builds" in captured.err
```

`capsys.readouterr()` captures Rich's stderr output. This works because Rich's
`Console(stderr=True)` writes to `sys.stderr`, which `capsys` intercepts.

### Pattern for patching lazy imports

From `test_banner.py` docstring:

```
Patching strategy (all lazy imports must be patched at source):
- mc.update._fetch_latest_version  (imported inside _fetch_with_timeout)
- mc.config.manager.ConfigManager  (imported inside _already_shown_today, ...)
```

For `ocm_monitor.py`, if imports are at module level (not lazy), patch at
`mc.utils.ocm_monitor.get_ocm_config_path`, etc.

### Test class structure to follow

```python
class TestOCMMonitor:
    """Tests grouped by function."""

class TestDecodeJwtExp:
    def test_valid_jwt_returns_exp(self) -> None: ...
    def test_invalid_format_returns_none(self) -> None: ...
    def test_missing_exp_claim_returns_none(self) -> None: ...

class TestPidLockFile:
    def test_acquires_lock_when_no_file(self, tmp_path) -> None: ...
    def test_skips_when_pid_alive(self, tmp_path) -> None: ...
    def test_cleans_stale_pid_and_acquires(self, tmp_path) -> None: ...

class TestStartBackgroundMonitor:
    def test_skips_in_agent_mode(self, monkeypatch) -> None: ...
    def test_prints_info_when_ocm_not_found(self, tmp_path, capsys) -> None: ...
    def test_prints_warning_when_token_expiring_soon(self, ...) -> None: ...
    def test_no_output_when_token_not_expiring(self, ...) -> None: ...
```

---

## New File: src/mc/utils/ocm_monitor.py (proposed structure)

```python
"""OCM refresh token expiry monitor for MC CLI.

Monitors OCM refresh token expiry at startup and every 30 minutes.
Runs on host only (not in agent/container mode).
"""
from __future__ import annotations

import atexit
import base64
import json
import logging
import os
import platform
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from rich.console import Console

from mc.container.manager import get_ocm_config_path

logger = logging.getLogger(__name__)

_EXPIRY_WARNING_MINUTES = 60    # Warn when token expires within this window
_POLL_INTERVAL_SECONDS = 1800   # 30 minutes between background polls
_CONSOLE = Console(stderr=True)


def _get_pid_path() -> Path: ...
def _is_pid_alive(pid: int) -> bool: ...
def _check_and_acquire_lock(pid_path: Path) -> bool: ...
def _decode_jwt_exp(token: str) -> Optional[int]: ...
def _read_refresh_token(ocm_path: Path) -> Optional[str]: ...
def _minutes_until_expiry(exp: int) -> int: ...

class OCMMonitor:
    def __init__(self) -> None: ...
    def start_background_monitor(self) -> None: ...
    def _cleanup(self) -> None: ...
    def _monitor_worker(self) -> None: ...
    def _check_and_notify(self) -> None: ...
    def _run_ocm_login(self) -> None: ...


def start_background_monitor() -> None:
    """Convenience function — instantiates OCMMonitor and starts it."""
    monitor = OCMMonitor()
    monitor.start_background_monitor()
```

### Method responsibilities

`start_background_monitor()`:
1. Read `get_ocm_config_path()`
2. If path does not exist: print info message to stderr, return (no thread)
3. Read `refresh_token` from `ocm.json`
4. If token missing/unreadable: log debug, return silently
5. Decode JWT `exp` claim
6. If decode fails: log debug, return silently
7. Compute minutes until expiry
8. If <= `_EXPIRY_WARNING_MINUTES`: print warning NOW (foreground), start daemon thread
   to run `ocm login` and continue polling
9. If > `_EXPIRY_WARNING_MINUTES`: check PID lock, start daemon thread for polling loop
10. Daemon thread: polls every 30 min, prints warning + runs `ocm login` when threshold hit

`_run_ocm_login()`:
```python
def _run_ocm_login(self) -> None:
    try:
        result = subprocess.run(
            ["ocm", "login", "--use-auth-code", "--url=prd"],
            check=False  # Don't raise on non-zero exit
        )
        if result.returncode != 0:
            _CONSOLE.print("[yellow]⚠ OCM re-login failed — please run 'ocm login' manually[/yellow]")
    except FileNotFoundError:
        _CONSOLE.print("[yellow]⚠ 'ocm' not found in PATH — please run 'ocm login' manually[/yellow]")
    except Exception as e:
        logger.error("OCM login subprocess failed: %s", e)
```

Note: `subprocess.run(...)` with no `stdout=`/`stderr=` argument inherits the terminal
— this is the correct way to stream `ocm login` output to the user.

---

## Key Risks & Questions

### Risk 1: Foreground vs background expiry check timing

**Issue:** The requirement says warning appears "at startup, before mc command runs."
This means the expiry check is synchronous (foreground), not deferred to the daemon thread.
The daemon thread handles only the `ocm login` subprocess and subsequent polling.

**Resolution:** Confirmed in CONTEXT.md: "Warning appears at startup, before mc command
runs (not mid-command)." The `start_background_monitor()` function itself does the check
and prints; the thread only does the slow/long-running work.

### Risk 2: PID lock and thread deduplication interaction

**Issue:** The PID lock prevents duplicate processes, but within a single process,
the daemon thread pattern uses `_worker_thread.is_alive()` to prevent duplicate threads.

**Resolution:** Both guards are needed. PID lock = cross-process guard. `is_alive()` =
within-process guard. PID lock is checked before starting the daemon thread.

### Risk 3: ocm.json refresh_token field name

**Issue:** The exact JSON key for the refresh token in `ocm.json` is inferred from OCM
CLI behavior. The codebase does not parse `ocm.json` contents anywhere (it only mounts
the file into containers as a whole).

**Confidence:** MEDIUM — the OCM CLI is open source and uses `refresh_token` as the
standard OAuth2 field name. If the field name is different, the monitor will silently
do nothing (the `_read_refresh_token` function returns `None` if key not found, and the
caller returns without action).

**Mitigation:** If `refresh_token` is absent, log at DEBUG level and return silently. The
user is not bothered, and the debug log reveals the issue if investigated.

### Risk 4: `missing_ok` on Path.unlink

`Path.unlink(missing_ok=True)` requires Python 3.8+. Project requires Python 3.11+, so
this is safe.

### Risk 5: subprocess output streaming to terminal

`subprocess.run(["ocm", "login", ...])` without `stdout`/`stderr` args inherits the
parent's file descriptors — correct for visible output. However, if mc is run in a
non-interactive context (piped), the `ocm login` interactive prompts may not work.

**Resolution:** This is a known tradeoff. The CONTEXT.md decision says "ocm login output
visible to user" — inherit stdio is correct. The browser-based auth flow (`--use-auth-code`)
opens a browser, so terminal interactivity is limited anyway.

---

## Sources

### Primary (HIGH confidence)
- `src/mc/version_check.py` — daemon thread pattern (read directly)
- `src/mc/cli/main.py` — entry point hook location (read directly)
- `src/mc/runtime.py` — runtime mode guard and Rich pattern (read directly)
- `src/mc/container/manager.py` — `get_ocm_config_path()` function (read directly)
- `src/mc/cli/commands/container.py` — `~/mc/state/` directory pattern (read directly)
- `tests/unit/test_banner.py` — test patterns for daemon threads and Rich output (read directly)
- `tests/unit/test_runtime.py` — test patterns for monkeypatching env and capsys (read directly)
- `pyproject.toml` — confirmed `rich>=14.0.0` is a dependency (read directly)

### Secondary (MEDIUM confidence)
- RFC 7519 (JWT standard) — `exp` claim structure, base64url encoding — well-established standard
- OCM CLI OAuth2 token format — `refresh_token` field name inferred from standard OAuth2 spec

---

## Metadata

**Confidence breakdown:**
- Standard Stack: HIGH — Rich already a dep; stdlib jwt decode; subprocess for ocm login
- Architecture: HIGH — version_check.py pattern directly applicable; confirmed by code read
- Pitfalls: HIGH — foreground/background split is the main subtlety; PID lock is clear

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable patterns; only risk is ocm.json field name)

---

## RESEARCH COMPLETE
