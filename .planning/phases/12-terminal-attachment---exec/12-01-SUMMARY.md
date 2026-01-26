---
phase: 12-terminal-attachment---exec
plan: 01
subsystem: infra
tags: [terminal, applescript, subprocess, cross-platform, iterm2, gnome-terminal]

# Dependency graph
requires:
  - phase: 11-container-lifecycle---state-management
    provides: Container manager with exec() foundation for terminal attachment
provides:
  - Cross-platform terminal launcher abstraction (macOS and Linux)
  - Terminal detection via environment variables
  - Platform-specific implementations (iTerm2, Terminal.app, gnome-terminal, konsole, xfce4-terminal)
affects: [12-02, 12-03]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Protocol-based launcher abstraction with platform-specific implementations
    - AppleScript automation with proper escaping for macOS terminal launching
    - Non-blocking subprocess execution with background cleanup
    - Terminal auto-detection via environment variable checking

key-files:
  created:
    - src/mc/terminal/__init__.py
    - src/mc/terminal/launcher.py
    - src/mc/terminal/detector.py
    - src/mc/terminal/macos.py
    - src/mc/terminal/linux.py
    - tests/unit/test_terminal_launcher.py
  modified: []

key-decisions:
  - "Protocol-based launcher abstraction for platform-independent terminal launching"
  - "Non-blocking subprocess execution with background thread cleanup to prevent zombie processes"
  - "AppleScript escaping for injection safety on macOS terminal automation"
  - "Priority-based terminal detection with environment variable checking"

patterns-established:
  - "Platform detection with get_launcher() factory function returning protocol-compliant launchers"
  - "LaunchOptions dataclass pattern for terminal configuration"
  - "AppleScript string escaping (backslashes and quotes) for security"
  - "Terminal priority order: macOS (iTerm2 > Terminal.app), Linux (gnome-terminal > konsole > xfce4-terminal)"

# Metrics
duration: 4min
completed: 2026-01-26
---

# Phase 12 Plan 01: Terminal PTY Allocation & Control Summary

**Cross-platform terminal launcher abstraction supporting macOS (iTerm2, Terminal.app) and Linux (gnome-terminal, konsole, xfce4-terminal) with AppleScript automation and non-blocking subprocess execution**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-26T11:34:26Z
- **Completed:** 2026-01-26T11:38:42Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- Terminal launcher abstraction with protocol-based design for cross-platform compatibility
- macOS terminal automation via AppleScript with proper escaping for injection safety
- Linux terminal support for gnome-terminal, konsole, and xfce4-terminal with direct CLI invocation
- Terminal auto-detection via environment variables ($TERM_PROGRAM, $ITERM_SESSION_ID, $KONSOLE_DBUS_SERVICE, $COLORTERM)
- Non-blocking terminal launch with background cleanup to prevent zombie processes
- 45 comprehensive unit tests with 93-97% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Create terminal launcher interface and platform detection** - `e6315be` (feat)
2. **Task 2: Implement macOS and Linux terminal launchers** - `c2fcccb` (feat)
3. **Task 3: Create comprehensive unit tests for terminal launcher** - `6f7ed4d` (test)

**Plan metadata:** (pending - will commit with STATE.md updates)

## Files Created/Modified

- `src/mc/terminal/__init__.py` - Public API exports for terminal launcher module
- `src/mc/terminal/launcher.py` - TerminalLauncher protocol, LaunchOptions dataclass, get_launcher() factory
- `src/mc/terminal/detector.py` - Terminal detection via environment variables and binary availability checking
- `src/mc/terminal/macos.py` - MacOSLauncher with iTerm2 and Terminal.app support via AppleScript
- `src/mc/terminal/linux.py` - LinuxLauncher with gnome-terminal, konsole, xfce4-terminal support
- `tests/unit/test_terminal_launcher.py` - 45 unit tests covering all launcher functionality

## Decisions Made

**1. Protocol-based launcher abstraction**
- Rationale: Python Protocol enables static type checking while allowing platform-specific implementations without inheritance overhead
- Impact: Clean separation between interface and implementation, easy to test and extend

**2. Non-blocking subprocess execution with background cleanup**
- Rationale: Terminal launch must return control to original shell immediately, but we need to prevent zombie processes
- Implementation: subprocess.Popen() with background threading.Thread for cleanup
- Impact: User gets prompt back immediately, no process table pollution

**3. AppleScript string escaping for injection safety**
- Rationale: Case descriptions from Salesforce could contain quotes or special characters
- Implementation: Escape backslashes first, then quotes (order matters)
- Impact: Prevents AppleScript syntax errors and potential command injection

**4. Priority-based terminal detection**
- Rationale: Multiple terminals may be installed, need predictable selection
- Priority: macOS (iTerm2 > Terminal.app), Linux (gnome-terminal > konsole > xfce4-terminal > xterm)
- Impact: iTerm2 preferred for developers (better features), GNOME terminal for RHEL/Fedora Workstation

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly following RESEARCH.md patterns.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 12 Plan 02 (Shell customization and banner generation):**
- Terminal launcher abstraction complete and tested
- Platform detection working for macOS and Linux
- Non-blocking execution verified
- AppleScript escaping prevents injection vulnerabilities

**Next steps:**
- Plan 02: Shell customization with custom bashrc and welcome banners
- Plan 03: Container attachment workflow integrating terminal launch with podman exec

**No blockers or concerns.**

---
*Phase: 12-terminal-attachment---exec*
*Completed: 2026-01-26*
