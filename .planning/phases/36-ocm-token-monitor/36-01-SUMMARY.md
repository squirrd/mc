---
phase: 36-ocm-token-monitor
plan: 01
subsystem: monitoring
tags: [ocm, jwt, threading, daemon, pid-lock, rich, subprocess, base64]

requires:
  - phase: 35-backplane-auto-login
    provides: get_ocm_config_path() in container/manager.py used as import source
provides:
  - src/mc/utils/ocm_monitor.py — full OCM token background monitor module
  - tests/unit/test_ocm_monitor.py — 21-test suite for all module functions
affects:
  - 36-02 or later plans that wire start_background_monitor() into CLI startup (main.py)

tech-stack:
  added: []
  patterns:
    - "Daemon thread with PID file lock for cross-process deduplication"
    - "Module-level _CONSOLE = Console(stderr=True) for Rich stderr output"
    - "Convenience module-level function (start_background_monitor) wrapping class method — mirrors check_for_updates() in version_check.py"
    - "try/except Exception: return None pattern for all JWT/file parsing helpers"

key-files:
  created:
    - src/mc/utils/ocm_monitor.py
    - tests/unit/test_ocm_monitor.py
  modified: []

key-decisions:
  - "_read_refresh_token casts dict value via str(value) to satisfy mypy no-any-return — avoids Any from json.loads"
  - "PID lock uses ~/mc/state/ocm-monitor.pid — colocated with containers.db and cluster_id state"
  - "subprocess.run for ocm login inherits terminal (no stdout=/stderr= redirection) so interactive auth code flow streams to user"
  - "PermissionError in os.kill treated as alive (process exists, belongs to another user) — conservative to prevent duplicate monitors"

patterns-established:
  - "Daemon thread pattern: match VersionChecker — _stop_event + _worker_thread + atexit.register(_cleanup)"
  - "PID lock pattern: _check_and_acquire_lock(path) returns bool, caller checks before starting thread"

duration: 3min
completed: 2026-03-20
---

# Phase 36 Plan 01: OCM Token Monitor Summary

**OCM refresh token background monitor with JWT decode, 60-min expiry warning, PID-locked daemon thread, and 21-test unit suite**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T12:16:51Z
- **Completed:** 2026-03-20T12:20:33Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `src/mc/utils/ocm_monitor.py` — full module: `OCMMonitor` class, 8 helper functions, module-level `start_background_monitor()` convenience function, mypy strict compliant
- `tests/unit/test_ocm_monitor.py` — 21 tests across 5 classes covering all code paths
- PID lock at `~/mc/state/ocm-monitor.pid` prevents duplicate daemon threads across processes; stale PIDs cleaned automatically

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/mc/utils/ocm_monitor.py** - `aeb0cb7` (feat)
2. **Task 2: Write tests/unit/test_ocm_monitor.py** - `de4a21e` (test)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `/Users/dsquirre/Repos/mc/src/mc/utils/ocm_monitor.py` — OCM monitor implementation with OCMMonitor class and all helpers
- `/Users/dsquirre/Repos/mc/tests/unit/test_ocm_monitor.py` — Unit tests (21 tests, all passing)

## Decisions Made

- `_read_refresh_token` casts the dict value with `str(value)` to satisfy mypy `no-any-return` rule — avoids `Any` from `json.loads`
- PID lock at `~/mc/state/ocm-monitor.pid` — colocated with `containers.db` in the same state directory
- `subprocess.run` for `ocm login` inherits the terminal (no stdout/stderr redirection) so the interactive auth code flow streams to the user unmodified
- `PermissionError` in `os.kill` treated as "alive" (process exists, owned by another user) — conservative to prevent false "stale" cleanup

## Deviations from Plan

None — plan executed exactly as written. The only minor fix was removing 3 unused imports (`MagicMock`, `_is_pid_alive`, `_read_pid_file`) from the test file flagged by flake8 — not a deviation, just cleanup during verification.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- `start_background_monitor()` is ready to be wired into CLI startup (`src/mc/cli/main.py`) in a future plan
- Module is importable: `from mc.utils.ocm_monitor import start_background_monitor` succeeds
- All 21 tests pass; no regressions in existing 647-test suite (2 pre-existing failures in container manager tests unrelated to this work)

---
*Phase: 36-ocm-token-monitor*
*Completed: 2026-03-20*
