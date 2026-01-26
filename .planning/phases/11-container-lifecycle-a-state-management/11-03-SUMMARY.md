---
phase: 11-container-lifecycle-a-state-management
plan: 03
subsystem: container-orchestration
tags: [podman, sqlite, container-listing, state-management]

# Dependency graph
requires:
  - phase: 11-01
    provides: StateDatabase for container metadata persistence with reconciliation
  - phase: 09-02
    provides: PodmanClient wrapper with lazy connection and retry logic
provides:
  - ContainerManager.list() method returning formatted container metadata
  - Uptime calculation for running containers
  - Comprehensive test suite (13 tests) for list operation
affects: [12-terminal-automation, 13-cli-commands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Reconcile-before-query pattern for state consistency"
    - "Metadata enrichment from multiple sources (Podman + state DB)"
    - "Human-readable duration formatting (days/hours/minutes/seconds)"

key-files:
  created:
    - tests/unit/test_container_manager_list.py
  modified:
    - src/mc/container/manager.py

key-decisions:
  - "Reconcile state before listing to ensure accuracy (detect external deletions)"
  - "Sort containers by created_at timestamp (newest first) for better UX"
  - "Return N/A for workspace_path when metadata missing (shouldn't happen with proper create flow)"
  - "Calculate uptime only for running containers (empty string for stopped/exited)"

patterns-established:
  - "Container list returns dict with case_number, status, customer, container_id, workspace_path, created_at, uptime"
  - "Uptime format: days+hours for >1 day, hours+minutes for <1 day, minutes+seconds for <1 hour, seconds only for <1 minute"
  - "Filter containers by mc.managed=true label (ignore user's other containers)"

# Metrics
duration: 10min
completed: 2026-01-26
---

# Phase 11 Plan 03: Container List Operation Summary

**ContainerManager.list() with state reconciliation, Podman querying, metadata enrichment, and uptime calculation for running containers**

## Performance

- **Duration:** 10 min
- **Started:** 2026-01-26T06:29:09Z
- **Completed:** 2026-01-26T06:39:09Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Implemented ContainerManager.list() method with full metadata enrichment
- Created comprehensive test suite with 13 tests covering all edge cases
- Integrated reconciliation before listing for state accuracy
- Added human-readable uptime calculation for running containers

## Task Commits

Each task was committed atomically:

1. **Task 1 & 2: Implement list() and create tests** - `c19a545` (feat)

**Note:** Implementation and tests committed together as single unit since list() method was already partially present from plan 11-02.

## Files Created/Modified
- `tests/unit/test_container_manager_list.py` - Comprehensive test suite for list operation (478 lines, 13 tests)
- `src/mc/container/manager.py` - Added list() and _calculate_uptime() methods (already existed from 11-02)

## Decisions Made

**Reconciliation timing:** Call `_reconcile()` before listing to detect external container deletions (prevents showing stale state)

**Sorting strategy:** Sort by `created_at` timestamp from state database (newest first) - better UX for developers working on recent cases

**Missing metadata handling:** Return "N/A" for workspace_path and "Unknown" for created_at when container not in state database (edge case - shouldn't happen if create() is used)

**Uptime calculation format:** Human-readable format prioritizes larger units (days > hours > minutes > seconds) for readability

**Empty uptime for stopped containers:** Only running containers show uptime (stopped/exited containers have empty string)

## Deviations from Plan

None - plan executed as written. The list() method implementation was already present from plan 11-02 (which implemented both create() and list() together). This plan's contribution was the comprehensive test suite.

## Issues Encountered

**Pre-existing implementation:** Found list() method already implemented in plan 11-02. Verified implementation matches plan specification, then created comprehensive test suite as planned.

**Test time calculations:** Initial uptime tests used manual time arithmetic (hour - 2, minute - 34) which wrapped to previous day. Fixed by using timedelta for reliable time offsets.

**Podman API call count:** Reconcile calls containers.list(), then list() calls it again. Tests initially expected single call, fixed to expect 2 calls (both necessary for correctness).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 12 (Terminal Automation):**
- list() method provides formatted container data for CLI display
- Uptime calculation enables developers to see container age at a glance
- Test coverage ensures list operation reliable for terminal integration

**Ready for Phase 13 (CLI Commands):**
- list() returns structured data ready for ASCII table formatting
- Empty list handling (returns []) enables friendly "no containers" message
- All metadata fields populated for rich CLI output

**Test coverage:** 13 tests covering empty list, running/stopped containers, multiple containers, sorting, metadata enrichment, and reconciliation behavior.

---
*Phase: 11-container-lifecycle-a-state-management*
*Completed: 2026-01-26*
