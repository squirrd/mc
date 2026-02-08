---
phase: 16-macos-window-tracking
plan: 02
subsystem: terminal
tags: [window-registry, duplicate-prevention, macos, applescript, sqlite]

# Dependency graph
requires:
  - phase: 15-window-registry-foundation
    provides: WindowRegistry class with lookup/register operations and lazy validation
  - phase: 16-01
    provides: focus_window_by_id() method for cross-Space window focusing
provides:
  - Complete duplicate terminal prevention on macOS via window ID tracking
  - Registry integration in attach_terminal() workflow (lookup before create, register after)
  - Lazy validation with stale entry auto-cleanup during lookup
  - User prompt on focus failure (race condition handling)
affects: [integration-tests, duplicate-prevention, terminal-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Registry lookup with validator callback before terminal creation"
    - "Window ID registration after launch with 0.5s delay for window creation"
    - "User confirmation prompt on focus failure after validation"

key-files:
  created: []
  modified:
    - src/mc/terminal/attach.py

key-decisions:
  - "Prompt user on focus failure after validation (handles race condition where window closes between validation and focus)"
  - "0.5s delay after launch before capturing window ID (gives terminal time to fully create window)"
  - "Log warning but don't block if window ID capture fails (graceful degradation)"
  - "Remove all title-based duplicate detection code (find_window_by_title, focus_window_by_title)"

patterns-established:
  - "WindowRegistry pattern: Initialize → lookup with validator → focus if found → register after create"
  - "macOS-only guards: isinstance(launcher, MacOSLauncher) wraps registry operations"
  - "User feedback: 'Focused existing terminal for case XXXXX' on success"

# Metrics
duration: 1min
completed: 2026-02-08
---

# Phase 16 Plan 02: macOS Window Registry Integration Summary

**Window ID tracking in attach_terminal() workflow replaces title-based duplicate detection with registry lookup, validation, and focus**

## Performance

- **Duration:** 1 min 38 sec
- **Started:** 2026-02-08T00:50:05Z
- **Completed:** 2026-02-08T00:51:43Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- WindowRegistry integrated into attach_terminal() workflow
- Registry lookup with lazy validation before terminal creation (prevents duplicates)
- Existing window focus via focus_window_by_id() instead of title search
- Window ID registration after terminal launch (0.5s delay for window creation)
- User prompt "Create new terminal instead? (y/n)" on focus failure after validation
- Complete removal of title-based duplicate detection (find_window_by_title, focus_window_by_title)

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace title-based duplicate check with window ID registry integration** - `25f2504` (feat)

## Files Created/Modified
- `src/mc/terminal/attach.py` - Added WindowRegistry import, replaced title-based duplicate check (lines 244-258) with registry lookup/validation/focus logic (lines 248-286), added window ID registration after launch (lines 303-322)

## Decisions Made

**1. User prompt on focus failure after validation**
- **Rationale:** Handles race condition where window closes between validation and focus attempt
- **Implementation:** Prompt "Window focus failed (window may have closed). Create new terminal instead? (y/n)"
- **Benefit:** User controls outcome when window state changes mid-operation

**2. 0.5-second delay before window ID capture**
- **Rationale:** Terminal window needs brief moment to fully initialize after launcher.launch()
- **Implementation:** `time.sleep(0.5)` before `launcher._capture_window_id()`
- **Benefit:** Ensures window ID capture succeeds reliably

**3. Graceful degradation on registration failure**
- **Rationale:** Window ID capture failure shouldn't block terminal launch (user already has terminal)
- **Implementation:** Log warning "Failed to capture window ID - duplicate prevention disabled" but don't raise
- **Benefit:** Terminal launch succeeds even if registry operation fails

**4. Remove all title-based code**
- **Rationale:** Window ID tracking is superior (reliable, not affected by title changes)
- **Implementation:** Deleted find_window_by_title and focus_window_by_title calls
- **Benefit:** Single code path for duplicate detection, no fallback confusion

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - WindowRegistry API and focus_window_by_id() worked as designed from Phase 15 and 16-01.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Phase 16 complete:** macOS window tracking fully operational. Integration test `test_duplicate_terminal_prevention_regression` should now pass:
1. First `mc case XXXXX` creates terminal and registers window ID
2. Second `mc case XXXXX` finds ID in registry, validates window exists, focuses it
3. Manual window close triggers stale entry cleanup on next lookup

**Ready for Phase 17 (Linux Window Tracking):**
- WindowRegistry already platform-agnostic (validator callback pattern)
- Linux implementation needs wmctrl/X11 window ID capture and validation
- Same workflow pattern applies (lookup → validate → focus → register)

**Ready for Phase 18 (Terminal App Tracking):**
- Window registry stores terminal app type (iTerm2 vs Terminal.app)
- App-specific focus logic needs per-case terminal app tracking
- Prompt user if previous window's app unavailable

**No blockers** - duplicate prevention foundation complete on macOS.

---
*Phase: 16-macos-window-tracking*
*Completed: 2026-02-08*
