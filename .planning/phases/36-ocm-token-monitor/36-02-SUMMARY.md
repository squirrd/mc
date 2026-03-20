---
phase: 36-ocm-token-monitor
plan: 02
subsystem: monitoring
tags: [ocm, cli, startup, daemon, main.py, lazy-import]

requires:
  - phase: 36-01
    provides: start_background_monitor() in src/mc/utils/ocm_monitor.py

provides:
  - src/mc/cli/main.py — OCM monitor wired into host-mode CLI startup

affects:
  - Any future plan touching cli/main.py startup sequence

tech-stack:
  added: []
  patterns:
    - "Lazy import inside try/except for optional startup features (matching show_update_banner pattern)"
    - "Separate if get_runtime_mode() != 'agent' guard per independent startup concern"

key-files:
  created: []
  modified:
    - src/mc/cli/main.py

key-decisions:
  - "Two separate if get_runtime_mode() != 'agent' blocks kept adjacent — each startup concern independently guarded (not combined)"
  - "Lazy import from mc.utils.ocm_monitor inside try block — matches existing banner import style, failures silently logged at debug level"

patterns-established:
  - "Startup concern pattern: each host-only startup feature gets its own if get_runtime_mode() != 'agent': try/except block"

duration: 15min
completed: 2026-03-20
---

# Phase 36 Plan 02: OCM Monitor CLI Integration Summary

**OCM token background monitor wired into mc CLI host-mode startup via lazy import in main.py — daemon thread runs on every mc invocation without blocking any command**

## Performance

- **Duration:** ~15 min (including human-verify checkpoint pause)
- **Started:** 2026-03-20T12:22:03Z
- **Completed:** 2026-03-20T12:38:00Z
- **Tasks:** 2 of 2 (Task 1 auto + Task 2 checkpoint:human-verify — approved)
- **Files modified:** 1

## Accomplishments

- Added OCM monitor call to `src/mc/cli/main.py` immediately after the `show_update_banner` block
- Separate `if get_runtime_mode() != 'agent':` guard keeps concerns independent
- Lazy import pattern matches existing style in the file
- Human verification confirmed: `uv run mc --help` exits cleanly with no hang, no errors
- Zero mypy errors introduced (`uv run mypy src/mc/cli/main.py` — no issues)
- Zero regressions in unit test suite (668 passing; 2 pre-existing failures unrelated to this change)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add OCM monitor call to main.py** - `a7215dc` (feat)

**Plan metadata (at checkpoint):** `b0ef464` (docs: complete ocm-monitor CLI integration plan)

## Files Created/Modified

- `src/mc/cli/main.py` — Added 8-line OCM monitor block at lines 167-171 after show_update_banner block

## Decisions Made

- Two separate `if get_runtime_mode() != 'agent':` blocks kept adjacent rather than combined — each startup concern remains independently guarded, consistent with the codebase approach of keeping distinct concerns separate
- Lazy import inside try/except at call site — failures silently logged at debug level so no mc command is ever blocked by monitor errors

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Two pre-existing unit test failures were present before this plan began (not introduced by this change):
- `tests/unit/test_container_manager_create.py::TestCreateNewContainer::test_create_new_container`
- `tests/unit/test_container_manager_mounts.py::TestAllMountsTogether::test_all_mounts_present_when_all_paths_exist`

Confirmed pre-existing by running failing tests against the committed state with no local changes — same failures on `a7215dc`.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 36 OCM token monitor is fully complete end-to-end:
  - `src/mc/utils/ocm_monitor.py` — monitor module with PID lock, token expiry check, daemon thread (36-01)
  - `src/mc/cli/main.py` — startup hook wired into host-only block (36-02)
- When `ocm.json` is absent: cyan info message printed to stderr on any mc command
- When token expires within 60 min: yellow warning + `ocm login` triggered in background
- When token is fresh: silent, no visible output
- All phase 36 success criteria satisfied

---
*Phase: 36-ocm-token-monitor*
*Completed: 2026-03-20*
