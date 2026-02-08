---
phase: 17-registry-cleanup---maintenance
plan: 01
subsystem: database
tags: [sqlite, cleanup, maintenance, registry, self-healing]

# Dependency graph
requires:
  - phase: 15-window-registry-foundation
    provides: WindowRegistry class with SQLite database, last_validated timestamp tracking
  - phase: 16-macos-window-tracking
    provides: MacOSLauncher._window_exists_by_id() for window validation
provides:
  - WindowRegistry.cleanup_stale_entries() method for automatic maintenance
  - idx_last_validated index for efficient oldest-entry queries
  - Automatic cleanup integration in attach_terminal workflow
affects: [18-terminal-app-tracking, 19-linux-window-tracking, testing]

# Tech tracking
tech-stack:
  added: []
  patterns: [incremental-cleanup, sampling-based-validation, self-healing-registry]

key-files:
  created: []
  modified:
    - src/mc/terminal/registry.py
    - src/mc/terminal/attach.py

key-decisions:
  - "Sample oldest 20 entries by last_validated timestamp for cleanup efficiency"
  - "Aggressive cleanup: treat validation errors as stale entries"
  - "Incremental deletion (commit per entry) avoids long-running locks"
  - "Non-blocking cleanup failures - log warning but don't block terminal launch"

patterns-established:
  - "Reconciliation-based cleanup: validate external state (window existence) against internal state (registry)"
  - "Before-operation cleanup pattern: automatic maintenance triggered at workflow entry points"
  - "Sampling-based validation: balance cleanup thoroughness with performance via oldest-entry sampling"

# Metrics
duration: 2min
completed: 2026-02-08
---

# Phase 17 Plan 01: Registry Cleanup & Maintenance Summary

**Self-healing window registry with sampling-based cleanup that validates oldest 20 entries before terminal operations**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-08T19:25:49Z
- **Completed:** 2026-02-08T19:27:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- WindowRegistry automatically removes stale entries via sampling-based validation
- Cleanup integrated into attach_terminal workflow for proactive maintenance
- Efficient oldest-entry queries via idx_last_validated index
- Non-blocking cleanup failures prevent terminal launch disruption

## Task Commits

Each task was committed atomically:

1. **Task 1: Add cleanup infrastructure to WindowRegistry** - `ed43ff2` (feat)
2. **Task 2: Integrate automatic cleanup into attach_terminal** - `4216d03` (feat)

## Files Created/Modified
- `src/mc/terminal/registry.py` - Added cleanup_stale_entries(), _get_oldest_entries(), _validate_window_exists() methods; idx_last_validated index
- `src/mc/terminal/attach.py` - Automatic cleanup before registry lookup operations

## Decisions Made
- **Sample size 20:** Balances cleanup thoroughness with performance (validates oldest 20 entries per operation)
- **Aggressive cleanup:** Treat validation errors as stale entries - better to remove questionable entries than accumulate crud
- **Incremental deletion:** Call remove() per entry rather than batch delete to avoid long-running locks
- **Non-blocking failures:** Cleanup exceptions logged as warnings, don't prevent terminal launch
- **Before-operation cleanup:** Trigger cleanup at workflow entry point (before lookup) rather than background process

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Registry cleanup infrastructure complete and operational on macOS
- Automatic maintenance runs before terminal operations
- Ready for Linux window tracking implementation (Phase 19)
- Ready for Terminal.app support (Phase 18)
- Platform-specific functional test confirms stale entry removal works correctly

**Concerns:**
- Cleanup currently only runs on macOS (when MacOSLauncher detected). Linux platforms need _window_exists_by_id() implementation before cleanup is functional there.
- Integration test `test_duplicate_terminal_prevention_regression` should benefit from cleanup infrastructure

---
*Phase: 17-registry-cleanup---maintenance*
*Completed: 2026-02-08*
