---
phase: 16-macos-window-tracking
plan: 01
subsystem: terminal
tags: [macos, applescript, window-management, iterm2, terminal-app]

# Dependency graph
requires:
  - phase: 15-window-registry-foundation
    provides: Window ID capture and validation infrastructure (_capture_window_id, _window_exists_by_id)
provides:
  - focus_window_by_id() method in MacOSLauncher for reliable duplicate prevention
  - Cross-Space window focusing with activate + set index pattern
  - Dock-minimized window un-minimize support
affects: [16-02, duplicate-prevention, window-lifecycle]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AppleScript activate + set index to 1 for cross-Space focusing"
    - "Explicit miniaturized check before window focusing"

key-files:
  created: []
  modified:
    - src/mc/terminal/macos.py

key-decisions:
  - "Use activate + set index to 1 pattern for reliable cross-Space window focusing"
  - "Explicitly un-minimize Dock-minimized windows before focusing"
  - "Accept window_id as string parameter for cross-platform compatibility"
  - "5-second timeout with graceful error handling (matches existing patterns)"

patterns-established:
  - "Window ID operations grouped together in MacOSLauncher (after _window_exists_by_id)"
  - "Consistent error handling: check osascript availability, escape IDs, timeout=5, return bool"

# Metrics
duration: 1min
completed: 2026-02-08
---

# Phase 16 Plan 01: Window Focusing Foundation Summary

**AppleScript window focusing with cross-Space switching and Dock un-minimize support for duplicate terminal prevention**

## Performance

- **Duration:** 1 min 4 sec
- **Started:** 2026-02-08T00:47:04Z
- **Completed:** 2026-02-08T00:48:08Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- Added focus_window_by_id() method to MacOSLauncher for reliable window focusing
- Implemented cross-Space window switching using activate + set index pattern
- Added Dock-minimized window un-minimize support (set miniaturized to false)
- Maintained consistent error handling (5-second timeout, graceful fallback)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add focus_window_by_id method to MacOSLauncher** - `198d732` (feat)

## Files Created/Modified
- `src/mc/terminal/macos.py` - Added focus_window_by_id() method after _window_exists_by_id() (line 309-374)

## Decisions Made

**1. AppleScript activate + set index pattern for cross-Space focusing**
- Research (16-RESEARCH.md lines 392-457) confirmed this is the standard macOS pattern
- No accessibility permissions required (unlike AXRaise approach)
- Works reliably across macOS Spaces

**2. Explicit miniaturized check for Dock-minimized windows**
- Check `if miniaturized of theWindow` before focusing
- Set miniaturized to false to un-minimize from Dock
- Ensures all window states handled (background, minimized, cross-Space)

**3. Consistent error handling pattern**
- Check osascript availability (shutil.which)
- 5-second timeout (matches _window_exists_by_id)
- Catch TimeoutExpired explicitly
- Return bool for clear success/failure signal

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation followed existing patterns from _window_exists_by_id() and focus_window_by_title().

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for 16-02:** Window focusing capability operational. Next plan can integrate this with window registry for full duplicate prevention flow:
1. Check registry for existing window
2. Validate window still exists (_window_exists_by_id)
3. Focus existing window (focus_window_by_id) ← now complete
4. Handle stale entries and app unavailability

**No blockers:** All window ID operations now complete (capture, validate, focus).

---
*Phase: 16-macos-window-tracking*
*Completed: 2026-02-08*
