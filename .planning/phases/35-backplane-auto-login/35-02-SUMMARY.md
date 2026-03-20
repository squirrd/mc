---
phase: 35-backplane-auto-login
plan: "02"
subsystem: agent
tags: [backplane, ocm, cluster-id, subprocess, sfdc, state-db, agent-mode]

# Dependency graph
requires:
  - phase: 35-01
    provides: ContainerMetadata.cluster_id, StateDatabase.update_container(), ~/mc/state rw mount
  - phase: 34-01
    provides: sfdc-case.json written to /case/ by init_case_data()
provides:
  - run_backplane_login() — full backplane login flow with 3-source priority chain
  - validate_cluster_id() — regex format guard (8-64 chars, alphanumeric + hyphens)
  - _read_sfdc_cluster_id() — reads openshiftClusterID from /case/sfdc-case.json
  - _is_token_expired() — detects OCM token expiry signals in stderr
  - _get_state_db() — injectable StateDatabase with graceful degradation on failure
  - 25 unit tests covering all scenarios in must_haves spec
affects:
  - 35-03 (wires run_backplane_login() into exec command build_exec_command())

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Injectable dependency pattern: state_db param defaults to None, _get_state_db() constructs or returns None on failure"
    - "3-source priority chain: sfdc-case.json > StateDatabase > user prompt"
    - "cluster_id_source sentinel tracks which source won, controls persistence behaviour"
    - "All subprocess exceptions handled as non-fatal: FileNotFoundError, TimeoutExpired"

key-files:
  created:
    - src/mc/agent/backplane_login.py
    - tests/unit/test_agent_backplane_login.py
    - .planning/phases/35-backplane-auto-login/35-02-SUMMARY.md
  modified: []

key-decisions:
  - "run_backplane_login() only persists user-entered cluster_id — sfdc and state_db sources are authoritative externally and must not be overwritten on success"
  - "Failed login clears StateDatabase cluster_id — ensures stale ID does not silently repeat a failing cluster on next session"
  - "Token expiry detected in stderr triggers targeted message ('run ocm login') separate from generic warning"
  - "state_db=None injection point with _get_state_db() wrapper enables unit testing without filesystem"

patterns-established:
  - "Agent injectable DB pattern: func(... state_db: StateDatabase | None = None) + _get_state_db() helper"

# Metrics
duration: 3min
completed: 2026-03-20
---

# Phase 35 Plan 02: Backplane Login Module Summary

**run_backplane_login() with sfdc-case.json > StateDatabase > user-prompt priority chain, token-expiry detection, graceful OCM failure handling, and 25 unit tests covering all must_have scenarios**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-20T11:52:48Z
- **Completed:** 2026-03-20T11:55:49Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- Created `src/mc/agent/backplane_login.py` implementing full backplane login flow with 3-source priority chain
- `run_backplane_login()` reads sfdc-case.json first, falls back to StateDatabase, then prompts user interactively
- Persistence logic: only user-entered cluster_id is written to StateDatabase on success; sfdc and stored IDs are never re-persisted
- Failed login clears StateDatabase cluster_id; token expiry in stderr triggers specific re-auth message
- FileNotFoundError (missing ocm binary) and TimeoutExpired both handled as non-fatal warnings
- StateDatabase construction failure (pre-Phase-35 container without ~/mc/state mount) degrades gracefully via `_get_state_db()` returning None
- 25 unit tests pass covering all scenarios; mypy strict mode passes with no issues

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/mc/agent/backplane_login.py** - `02de6ca` (feat)
2. **Task 2: Create tests/unit/test_agent_backplane_login.py** - `95c394d` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/mc/agent/backplane_login.py` - Full backplane login module with run_backplane_login(), validate_cluster_id(), _is_token_expired(), _read_sfdc_cluster_id(), _get_state_db()
- `tests/unit/test_agent_backplane_login.py` - 25 unit tests covering all must_have scenarios

## Decisions Made

- **Only persist user-entered cluster_id** — sfdc-case.json is the authoritative external source (we do not want to shadow it with a DB copy); state_db source already exists so no-op on success
- **Failed login clears DB cluster_id** — stale cluster IDs silently failing on every attach would be worse UX than re-prompting; clearing forces a fresh prompt next time
- **Token expiry targeted message** — "run 'ocm login'" is much more actionable than a generic warning; users see this frequently when their offline token expires
- **`_get_state_db()` wrapper** — keeps `run_backplane_login()` parameter list clean; injectable state_db enables unit testing; wrapper isolates the try/except from the main flow

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 2 pre-existing test failures in `test_container_manager_create.py` and `test_container_manager_mounts.py` — both verified to predate this plan (fail with no staged changes). Not caused by our changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `run_backplane_login()` is ready for Plan 35-03 to wire into `build_exec_command()` as `mc agent backplane-login <case_number>` in the terminal exec chain
- No blockers for next plan

---
*Phase: 35-backplane-auto-login*
*Completed: 2026-03-20*
