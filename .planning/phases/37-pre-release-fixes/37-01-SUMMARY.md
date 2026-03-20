---
phase: 37-pre-release-fixes
plan: 01
subsystem: agent
tags: [backplane, statedb, sqlite, pathlib, bug-fix]

# Dependency graph
requires:
  - phase: 35-backplane-login
    provides: StateDatabase cluster_id persistence and _get_state_db injection point
  - phase: 36-ocm-token-monitor
    provides: OCM token monitor completing v2.0.7 feature work

provides:
  - Fixed _get_state_db() using explicit ~/mc/state/containers.db path via pathlib
  - Unit test asserting StateDatabase constructor receives correct db_path keyword argument

affects:
  - container-agent-startup
  - backplane-login-cluster-id-persistence

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Use Path.home() / 'mc' / 'state' / 'containers.db' as canonical host-mounted state path inside container"
    - "Pass db_path= keyword to StateDatabase() explicitly — never call StateDatabase() with no args from agent code"

key-files:
  created: []
  modified:
    - src/mc/agent/backplane_login.py
    - tests/unit/test_agent_backplane_login.py

key-decisions:
  - "db_path hardcoded to Path.home() / 'mc' / 'state' / 'containers.db' — matches the host-mounted path ContainerManager mounts at container creation"
  - "StateDatabase() with no args uses platformdirs default (~/.local/share/mc/containers.db on Linux) which is NOT the host-mounted path — never use the no-arg form from agent code"

patterns-established:
  - "Agent code constructing StateDatabase must always pass explicit db_path= to avoid platformdirs defaulting to wrong location"

# Metrics
duration: 1min
completed: 2026-03-20
---

# Phase 37 Plan 01: Pre-Release Fix BPL-04 Summary

**Fixed `_get_state_db()` to pass `db_path=~/mc/state/containers.db` to StateDatabase, restoring cluster_id reuse across container sessions (BPL-04)**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-20T23:23:52Z
- **Completed:** 2026-03-20T23:24:57Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Fixed the root cause of BPL-04: `StateDatabase()` called with no args defaulted to platformdirs path (`~/.local/share/mc/containers.db`), which is not the host-mounted state at `~/mc/state/containers.db` inside the container
- Added `from pathlib import Path` import and replaced no-arg call with `StateDatabase(db_path=str(Path.home() / "mc" / "state" / "containers.db"))`
- Added `test_get_state_db_uses_explicit_path` to pin the correct path for future regressions; all 26 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix _get_state_db() to use explicit ~/mc/state/containers.db path** - `29084e0` (fix)
2. **Task 2: Add unit test asserting _get_state_db uses the correct db_path** - `5b8d201` (test)

**Plan metadata:** (see final commit below)

## Files Created/Modified

- `src/mc/agent/backplane_login.py` - Added `from pathlib import Path`; replaced `StateDatabase()` with `StateDatabase(db_path=str(Path.home() / "mc" / "state" / "containers.db"))`
- `tests/unit/test_agent_backplane_login.py` - Added `_get_state_db` to imports; added `test_get_state_db_uses_explicit_path`

## Decisions Made

- db_path hardcoded to `Path.home() / "mc" / "state" / "containers.db"` — this matches the exact path ContainerManager mounts via `~/mc/state:/root/mc/state` volume bind when creating containers
- No-arg `StateDatabase()` is explicitly wrong for agent code: platformdirs computes `~/.local/share/mc/containers.db` which is a different, ephemeral path inside the container filesystem

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- BPL-04 fixed; cluster_id stored by user in one session will be correctly read in subsequent sessions
- Ready to proceed to 37-02

---
*Phase: 37-pre-release-fixes*
*Completed: 2026-03-20*
