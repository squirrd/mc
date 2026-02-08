---
phase: 18-linux-support
plan: 01
subsystem: terminal
tags: [linux, x11, wmctrl, xdotool, window-management]

# Dependency graph
requires:
  - phase: 16-macos-window-tracking
    provides: Window ID-based tracking API surface (MacOSLauncher methods)
  - phase: 15-window-registry
    provides: WindowRegistry for cross-platform window ID storage
provides:
  - X11 window management methods for LinuxLauncher (_capture_window_id, _window_exists_by_id, focus_window_by_id)
  - Display server detection (X11 vs Wayland)
  - Tool validation with distro-specific installation instructions
  - Desktop-native terminal preference (konsole on KDE, gnome-terminal on GNOME)
affects: [18-02, registry-cleanup, cross-platform-window-tracking]

# Tech tracking
tech-stack:
  added: [wmctrl 1.07, xdotool 3.x]
  patterns: [X11 detection via environment variables, distro detection via /etc/os-release, strict validation with actionable errors]

key-files:
  created: []
  modified: [src/mc/terminal/linux.py, src/mc/terminal/detector.py, tests/unit/test_terminal_launcher.py]

key-decisions:
  - "Use wmctrl for window focusing (more reliable for ID-based operations than xdotool)"
  - "Remove xfce4-terminal support completely (limit to gnome-terminal and konsole)"
  - "Strict Wayland validation - fail fast with clear error instead of silent fallback"
  - "Desktop-native terminal preference using XDG_CURRENT_DESKTOP"
  - "Distro-specific installation instructions using /etc/os-release parsing"

patterns-established:
  - "Pattern: X11 detection -> tool validation -> window operations (matches Phase 16 structure)"
  - "Pattern: 0.5s delay after terminal launch before window ID capture (timing-sensitive for gnome-terminal server model)"
  - "Pattern: Hex window ID format (0x...) for consistency with wmctrl output"
  - "Pattern: 5-second timeout with graceful error handling for all subprocess calls"

# Metrics
duration: 5min
completed: 2026-02-08
---

# Phase 18 Plan 01: Linux X11 Window Management Summary

**X11 window tracking with wmctrl/xdotool, matching MacOSLauncher API surface for cross-platform duplicate terminal prevention**

## Performance

- **Duration:** 5 min
- **Started:** 2026-02-08T03:33:05Z
- **Completed:** 2026-02-08T03:38:29Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- LinuxLauncher enhanced with complete X11 window management lifecycle (detect, capture, validate, focus)
- Display server detection with strict Wayland validation
- Tool validation with distro-specific installation instructions (apt/dnf/yum)
- Desktop-native terminal preference (konsole on KDE, gnome-terminal on GNOME)
- Removed xfce4-terminal support completely (codebase and tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add X11 detection and tool validation** - `5e0856d` (feat)
   - X11/Wayland detection via environment variables
   - wmctrl validation with distro-detected install commands
   - Desktop-native terminal preference
   - xfce4-terminal removal
   - mypy bug fix in detector.py (variable name collision)

2. **Task 2: Remove xfce4-terminal tests** - `22b3337` (fix)
   - Removed 5 xfce4-terminal test cases
   - All Linux tests passing (16/16)

## Files Created/Modified
- `src/mc/terminal/linux.py` - Enhanced with X11 detection, tool validation, and window management methods (_detect_display_server, _detect_distro, _validate_wmctrl_available, _capture_window_id, _window_exists_by_id, focus_window_by_id)
- `src/mc/terminal/detector.py` - Removed xfce4-terminal detection, fixed mypy variable name collision
- `tests/unit/test_terminal_launcher.py` - Removed xfce4-terminal test cases

## Decisions Made
- **wmctrl vs xdotool:** Chose wmctrl for window focusing by ID (RESEARCH.md identified wmctrl as more reliable for ID-based operations, xdotool better for search/matching)
- **xfce4-terminal removal:** Per 18-CONTEXT.md decision to support only gnome-terminal and konsole (focused approach, test thoroughly against two terminals)
- **Wayland handling:** Strict validation with RuntimeError instead of silent fallback (18-CONTEXT.md strict validation philosophy)
- **Desktop preference:** Use XDG_CURRENT_DESKTOP to prefer native terminal (konsole on KDE, gnome-terminal on GNOME)
- **Installation instructions:** Detect distro via /etc/os-release and provide exact install commands (sudo apt/dnf/yum install wmctrl)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed mypy variable name collision in detector.py**
- **Found during:** Task 1 type checking
- **Issue:** detector.py had `terminals` variable defined in both macOS and Linux branches, causing mypy no-redef error
- **Fix:** Renamed to `macos_terminals` and `linux_terminals` for clarity
- **Files modified:** src/mc/terminal/detector.py
- **Verification:** mypy passes on detector.py
- **Committed in:** 5e0856d (Task 1 commit)

**2. [Rule 1 - Bug] Removed xfce4-terminal tests after feature removal**
- **Found during:** Task 2 test execution
- **Issue:** 4 test cases for xfce4-terminal failing because LinuxLauncher no longer supports it
- **Fix:** Removed test_detect_terminal_xfce4, test_find_available_terminal_linux_xfce4, test_linux_launcher_xfce4_detection, test_linux_launcher_xfce4_terminal_args, test_linux_launcher_launch_xfce4_terminal
- **Files modified:** tests/unit/test_terminal_launcher.py
- **Verification:** All Linux tests pass (16/16 passing)
- **Committed in:** 22b3337 (separate fix commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both auto-fixes necessary for code correctness. mypy error was pre-existing bug uncovered during type checking. Test removal is expected cleanup after feature removal.

## Issues Encountered
None - plan executed smoothly with RESEARCH.md patterns and MacOSLauncher API surface as reference.

## User Setup Required
None - no external service configuration required. Window tracking will require wmctrl/xdotool installation on Linux X11 systems, but this is validated at runtime with clear error messages including distro-specific install commands.

## Next Phase Readiness
- LinuxLauncher has complete window management API matching MacOSLauncher
- Ready for Phase 18 Plan 02 (CLI integration and end-to-end testing)
- Window tracking now supports both macOS (Phase 16) and Linux X11 (Phase 18)
- Registry cleanup (Phase 17) will benefit from _window_exists_by_id() implementation on Linux

**Limitation noted:** Cleanup currently only runs on macOS (STATE.md line 88). Linux platforms need _window_exists_by_id() implementation before cleanup is functional - this was delivered in this plan, so cleanup should now work on Linux X11 after CLI integration wires it up.

---
*Phase: 18-linux-support*
*Completed: 2026-02-08*
