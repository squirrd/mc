# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-04)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently
**Current focus:** v2.0.2 Window Tracking - Phase 15 (Window Registry Foundation)

## Current Position

Phase: 16 of 19 (macOS Window Tracking)
Plan: 2 of 2 complete
Status: Phase complete
Last activity: 2026-02-08 — Phase 16 verified and complete

Progress: [████████████████████░░░░] 84% (16/19 phases complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 43 (across v1.0, v2.0, v2.0.1, v2.0.2)
- Previous milestones:
  - v1.0: 18 plans (8 phases) — shipped 2026-01-22
  - v2.0: 16 plans (6 phases) — shipped 2026-02-01
  - v2.0.1: 5 plans (1 phase) — shipped 2026-02-02

**By Recent Phase:**

| Phase | Plans | Status |
|-------|-------|--------|
| 16 (macOS Window Tracking) | 2/2 | Complete (v2.0.2) |
| 15 (Window Registry) | 2/2 | Complete (v2.0.2) |
| 14.1 (Critical Fixes) | 5/5 | Complete (v2.0.1) |
| 14 (Distribution) | 2/2 | Complete (v2.0) |
| 13 (Container Image) | 3/3 | Complete (v2.0) |

**Recent Trend:**
- v2.0.1 delivered in 1 day (5 plans)
- v2.0 delivered in 6 days (16 plans)
- Trend: Fast iteration on focused milestones

*Updated: 2026-02-04 after roadmap creation*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

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

6 remaining todos from v2.0.1 (all in testing area):
- Fix HTTP error handling tests (14 test failures)
- Fix container management tests (6 test failures)
- Fix terminal attachment tests (17 test failures)
- Fix validation and integration tests (5 test failures/errors)
- Fix workspace and metadata tests (5 test failures)
- v2.x deferred containerization features (planning)

### Blockers/Concerns

**Phase 16 complete:** macOS window tracking fully operational - duplicate terminal prevention working via window ID registry
**Linux complexity:** X11 vs Wayland support requires platform detection and graceful fallback (Phase 17)
**Test coverage:** Integration test `test_duplicate_terminal_prevention_regression` should now pass with Phase 16 complete

## Session Continuity

Last session: 2026-02-08
Stopped at: Completed 16-02-PLAN.md (macOS Window Registry Integration) - Phase 16 complete
Resume file: None
Next action: Ready for Phase 17 (Linux Window Tracking) or Phase 18 (Terminal App Tracking) planning
