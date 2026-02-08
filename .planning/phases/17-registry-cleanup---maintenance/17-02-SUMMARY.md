---
phase: 17-registry-cleanup---maintenance
plan: 02
subsystem: cli
tags: [cli, commands, reconcile, troubleshooting, maintenance]

# Dependency graph
requires:
  - phase: 17-registry-cleanup---maintenance
    provides: WindowRegistry.cleanup_stale_entries() method
provides:
  - mc container reconcile command for manual registry cleanup
  - Detailed reconciliation reporting with entries validated/removed
  - Larger sample size (100) for thorough manual validation
affects: [testing, troubleshooting]

# Tech tracking
tech-stack:
  added: []
  patterns: [manual-reconciliation-command]

key-files:
  created: []
  modified:
    - src/mc/cli/commands/container.py
    - src/mc/cli/main.py

key-decisions:
  - "Sample size 100 for manual reconcile (5x larger than automatic cleanup)"
  - "Detailed reporting: entries validated, stale entries removed, status"

patterns-established:
  - "Manual reconciliation command pattern: explicit user control for troubleshooting"

# Metrics
duration: 2min
completed: 2026-02-08
---

# Phase 17 Plan 02: Manual Registry Reconciliation Summary

**mc container reconcile command with detailed reporting validates 100 oldest registry entries for manual troubleshooting**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-08T20:03:44Z
- **Completed:** 2026-02-08T20:05:37Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Users can run `mc container reconcile` for manual registry cleanup
- Reconcile validates 100 oldest entries (5x larger than automatic cleanup's 20)
- Detailed report shows entries validated, stale entries removed, and cleanup status
- Command follows existing container command patterns with argparse.Namespace

## Task Commits

Each task was committed atomically:

1. **Task 1: Add reconcile_windows command function** - `9851bfa` (feat)
2. **Task 2: Wire reconcile subcommand to CLI parser** - `287565c` (feat)

## Files Created/Modified
- `src/mc/cli/commands/container.py` - Added reconcile_windows() function with sample_size=100, detailed reporting
- `src/mc/cli/main.py` - Added reconcile subparser and elif dispatch routing to container commands

## Decisions Made
- **Sample size 100:** Manual reconcile uses 5x larger sample than automatic cleanup (100 vs 20) for thorough validation when troubleshooting
- **Detailed reporting:** Show entries validated, stale entries removed, and status to give user visibility into cleanup operations
- **WindowRegistry default location:** Uses WindowRegistry() without explicit path to leverage platformdirs default location

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Manual reconciliation command complete and operational
- Users have explicit control over registry cleanup for troubleshooting
- Ready for Terminal.app window tracking support (Phase 18)
- Ready for Linux window tracking implementation (Phase 19)

**Phase 17 Complete:** Both automatic (plan 01) and manual (plan 02) registry cleanup infrastructure delivered.

---
*Phase: 17-registry-cleanup---maintenance*
*Completed: 2026-02-08*
