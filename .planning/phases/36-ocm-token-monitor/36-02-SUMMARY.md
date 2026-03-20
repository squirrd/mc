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

duration: 2min
completed: 2026-03-20
---

# Phase 36 Plan 02: OCM Monitor CLI Integration Summary

**OCM token background monitor wired into mc CLI host-mode startup via lazy import in main.py — daemon thread runs on every mc invocation without blocking any command**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-20T12:22:03Z
- **Completed:** 2026-03-20T12:24:05Z
- **Tasks:** 1 of 2 (Task 2 is checkpoint:human-verify — awaiting user approval)
- **Files modified:** 1

## Accomplishments

- Added OCM monitor call to `src/mc/cli/main.py` immediately after the `show_update_banner` block
- Separate `if get_runtime_mode() != 'agent':` guard keeps concerns independent
- Lazy import pattern matches existing style in the file
- `uv run mc --help` exits cleanly (no hang)
- Zero mypy errors introduced
- Zero regressions in unit test suite (2 pre-existing failures unrelated to this change)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add OCM monitor call to main.py** - `a7215dc` (feat)

**Plan metadata:** (docs commit — see below)

## Files Created/Modified

- `/Users/dsquirre/Repos/mc/src/mc/cli/main.py` — Added 8-line OCM monitor block after show_update_banner

## Decisions Made

- Two separate `if get_runtime_mode() != 'agent':` blocks kept adjacent rather than combined — each startup concern remains independently guarded, consistent with the codebase approach of keeping distinct concerns separate
- Lazy import inside try/except at call site — failures silently logged at debug level so no mc command is ever blocked by monitor errors

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- OCM monitor is active on every host-mode `mc` invocation
- Awaiting human verification at checkpoint (Task 2) before plan is considered complete
- On approval: phase 36 is functionally complete (36-01 + 36-02 deliver the full OCM token monitor feature)

---
*Phase: 36-ocm-token-monitor*
*Completed: 2026-03-20*
