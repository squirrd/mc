# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently
**Current focus:** v2.0.2 Window Tracking - Phase 15 (Window Registry Foundation)

## Current Position

Phase: 19 of 19 (Test Suite & Validation)
Plan: 1 of 1
Status: In progress
Last activity: 2026-02-08 — Completed 19-01-PLAN.md

Progress: [████████████████████████] 100% (19/19 phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 47 (across v1.0, v2.0, v2.0.1, v2.0.2)
- Previous milestones:
  - v1.0: 18 plans (8 phases) — shipped 2026-01-22
  - v2.0: 16 plans (6 phases) — shipped 2026-02-01
  - v2.0.1: 5 plans (1 phase) — shipped 2026-02-02

**By Recent Phase:**

| Phase | Plans | Status |
|-------|-------|--------|
| 19 (Test Suite & Validation) | 1/1 | Complete (v2.0.2) |
| 18 (Linux Support) | 2/2 | Complete (v2.0.2) |
| 17 (Registry Cleanup) | 2/2 | Complete (v2.0.2) |
| 16 (macOS Window Tracking) | 2/2 | Complete (v2.0.2) |
| 15 (Window Registry) | 2/2 | Complete (v2.0.2) |

**Recent Trend:**
- v2.0.1 delivered in 1 day (5 plans)
- v2.0 delivered in 6 days (16 plans)
- Trend: Fast iteration on focused milestones

*Updated: 2026-02-04 after roadmap creation*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- 18-02: Extend isinstance checks to (MacOSLauncher, LinuxLauncher) for registry operations (cross-platform via API compatibility)
- 18-02: Registry cleanup already cross-platform via get_launcher() duck typing (no changes needed)
- 18-01: Use wmctrl for window focusing by ID (more reliable than xdotool for ID-based operations)
- 18-01: Remove xfce4-terminal support completely (limit to gnome-terminal and konsole per 18-CONTEXT.md)
- 18-01: Strict Wayland validation - fail fast with RuntimeError instead of silent fallback
- 18-01: Desktop-native terminal preference using XDG_CURRENT_DESKTOP (konsole on KDE, gnome-terminal on GNOME)
- 18-01: Distro-specific installation instructions using /etc/os-release parsing
- 17-02: Sample size 100 for manual reconcile (5x larger than automatic cleanup)
- 17-02: Detailed reporting for reconcile command (entries validated, stale entries removed, status)
- 17-01: Sample oldest 20 entries by last_validated timestamp for cleanup efficiency
- 17-01: Aggressive cleanup - treat validation errors as stale entries
- 17-01: Incremental deletion (commit per entry) avoids long-running locks
- 17-01: Non-blocking cleanup failures - log warning but don't block terminal launch
- 16-02: Prompt user on focus failure after validation (handles race condition where window closes between validation and focus)
- 16-02: 0.5s delay after launch before capturing window ID (gives terminal time to fully create window)
- 16-02: Log warning but don't block if window ID capture fails (graceful degradation)
- 16-02: Remove all title-based duplicate detection code (find_window_by_title, focus_window_by_title)
- 16-01: Use activate + set index to 1 pattern for cross-Space window focusing
- 16-01: Explicitly un-minimize Dock-minimized windows before focusing
- 16-01: 5-second timeout with graceful error handling for focus operations
- 15-02: Use 'id of current window' (iTerm2) / 'id of front window' (Terminal.app) for window ID capture
- 15-02: Return window ID as string for cross-platform compatibility
- 15-02: Escape window ID in AppleScript validation to prevent injection
- 15-01: Callback-based validator in lookup() for platform-agnostic window validation
- 15-01: Return bool from register() to signal first-write-wins outcome (True=success, False=duplicate)
- 15-01: Auto-commit transactions to avoid lock upgrade issues in concurrent scenarios
- v2.0.2: Window ID tracking system chosen over title-based search (titles volatile in iTerm2)
- v2.0.2: Extend existing StateDatabase with window_registry table (zero new dependencies)
- v2.0.2: AppleScript window `id` property for macOS, wmctrl for Linux X11

### Pending Todos

**Phase 19-01 complete:** All 10 failing unit tests fixed
- Unit test suite: 521 passing, 0 failures
- Coverage: 74% (exceeds 60% threshold)
- All test assertions updated to match current implementation

Remaining:
- v2.x deferred containerization features (planning)

### Blockers/Concerns

**Phase 19-01 complete:** Unit test suite clean
- All 10 failing unit tests fixed
- 521 tests passing, 0 failures
- 74% coverage maintained
- Test assertions track implementation changes from phases 15-18

**v2.0.2 window tracking complete:**
- Cross-platform duplicate prevention working (macOS and Linux X11)
- Registry cleanup cross-platform via duck typing
- Window ID lifecycle complete (lookup → validate → focus → register)

**Known limitation:**
- Wayland not supported - strict validation raises RuntimeError with clear message

## Session Continuity

Last session: 2026-02-08
Stopped at: Completed 19-01-PLAN.md (Unit Test Fixes) - Phase 19 complete (1/1 plans)
Resume file: None
Next action: All phases complete - v2.0.2 ready for release
