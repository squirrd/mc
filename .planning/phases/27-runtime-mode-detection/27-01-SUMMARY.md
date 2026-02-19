---
phase: 27-runtime-mode-detection
plan: 01
subsystem: infra
tags: [runtime-detection, container, auto-update, rich, pathlib]

# Dependency graph
requires:
  - phase: 26-configuration-foundation
    provides: Configuration schema and manager infrastructure
provides:
  - Layered container detection (environment variable + filesystem fallback)
  - Auto-update guard preventing version checks in agent mode
  - Informational messaging via Rich Console for container context
affects: [28-version-checking, auto-update]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Defense-in-depth container detection (env var primary, file fallback)
    - Auto-update guard pattern (disable in-container updates)
    - Rich Console informational messaging (stderr, styled output)

key-files:
  created: []
  modified:
    - src/mc/runtime.py

key-decisions:
  - "Use MC_RUNTIME_MODE environment variable as primary detection (explicit)"
  - "Fallback to filesystem indicators for edge cases (defensive)"
  - "Block auto-update in agent mode with informational message"
  - "Use Rich Console for styled output matching existing CLI patterns"

patterns-established:
  - "Layered detection: Primary method (env var) + defensive fallback (files)"
  - "Auto-update guard returns bool + displays message (not silent)"
  - "Console uses stderr to avoid stdout piping interference"

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 27 Plan 01: Runtime Mode Detection Summary

**Layered container detection with environment variable primary and filesystem fallback, plus auto-update guard blocking version checks in agent mode**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T07:31:12Z
- **Completed:** 2026-02-19T07:33:44Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- Added is_running_in_container() function with layered detection approach (MC_RUNTIME_MODE env var primary, filesystem indicators fallback)
- Added should_check_for_updates() function blocking auto-update in agent mode with Rich banner message
- Updated module docstring documenting auto-update guard and fallback detection behavior

## Task Commits

Each task was committed atomically:

1. **Task 1: Add fallback container detection using filesystem indicators** - `03d2fa1` (feat)
2. **Task 2: Add auto-update guard function with Rich informational messaging** - `7f94e07` (feat)
3. **Task 3: Update module docstring to document new functions** - `9c205b9` (docs)

## Files Created/Modified
- `src/mc/runtime.py` - Added layered container detection (is_running_in_container) and auto-update guard (should_check_for_updates) with Rich Console messaging

## Decisions Made

1. **Primary detection via MC_RUNTIME_MODE environment variable**
   - Rationale: Explicit contract, set by our Containerfile (line 183), most reliable
   - Fallback exists but env var is preferred for correctness

2. **Filesystem fallback checks three indicator files**
   - /run/.containerenv (Podman v1.0+ standard)
   - /.containerenv (Podman legacy)
   - /.dockerenv (Docker standard)
   - Rationale: Defense-in-depth for edge cases (manual podman runs, third-party containers)

3. **Avoided cgroups parsing**
   - Rationale: Fragile, deprecated in cgroups v2, broken by Linux 6.12+ (per RESEARCH.md Pitfall 2)

4. **Rich Console for informational messaging**
   - Rationale: Matches existing MC CLI output patterns (see STACK.md)
   - Uses stderr to prevent stdout piping interference

5. **Auto-update guard displays message when blocking**
   - Rationale: Informational, not silent - users understand why update isn't running
   - Only shows when check would occur (no spam)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 28 (Version Checking):**
- Auto-update guard (should_check_for_updates) available for version checking integration
- Container detection (is_running_in_container) available for defensive checks
- Informational messaging pattern established for container context communication

**Integration points:**
- Phase 28 will call should_check_for_updates() before GitHub API version checks
- Message "Updates managed via container builds" will display when running in agent mode
- Version checking will be skipped in containers (updates via image rebuilds)

**No blockers or concerns.**

---
*Phase: 27-runtime-mode-detection*
*Completed: 2026-02-19*
