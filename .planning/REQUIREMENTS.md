# Requirements: MC v2.0.2 Window Tracking

**Defined:** 2026-02-04
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently

## v2.0.2 Requirements

Requirements for window tracking system to fix duplicate terminal prevention.

### Window Registry (Core Infrastructure)

- [x] **WR-01**: System stores window ID when creating terminal window
- [x] **WR-02**: System retrieves window ID by case number
- [x] **WR-03**: Window registry persists across mc process restarts
- [x] **WR-04**: Window registry survives concurrent access (multiple mc processes)
- [x] **WR-05**: System detects and removes stale entries for closed windows
- [x] **WR-06**: Automatic cleanup on startup (reconcile registry with actual windows)
- [x] **WR-07**: Manual reconcile command for troubleshooting (`mc container reconcile`)

### Window Management (User-Facing)

- [x] **WM-01**: Running `mc case XXXXX` twice focuses existing window, doesn't create duplicate
- [x] **WM-02**: System validates window still exists before focusing
- [x] **WM-03**: System creates new window if previous window was closed manually
- [x] **WM-04**: Window focusing works on macOS (iTerm2, Terminal.app)
- [x] **WM-05**: Window focusing works on Linux (X11 with wmctrl/xdotool)
- [x] **WM-06**: System provides feedback when focusing existing window vs creating new

### Testing & Validation

- [x] **TEST-01**: Integration test `test_duplicate_terminal_prevention_regression` passes
- [x] **TEST-02**: Unit tests for WindowRegistry store/lookup/cleanup operations
- [x] **TEST-03**: Manual testing verifies no duplicates on macOS
- [x] **TEST-04**: Platform-specific tests for macOS and Linux

## Future Requirements

Deferred to future releases.

### Advanced Features

- **WR-08**: Grace period before cleanup (24-hour threshold vs immediate)
- **WR-09**: Cross-desktop tracking (macOS Spaces integration)
- **WM-07**: Wayland support for Linux terminals
- **WM-08**: Window state persistence (position, size)

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| Session restoration | Complex, unclear user demand - wait for feature requests |
| Window grouping | Over-engineered - one window per case is sufficient |
| Multi-window per case | Breaks isolation model, adds unnecessary complexity |
| Terminal emulator customization | Out of scope - users configure their own terminals |
| SSH/remote window tracking | Security and complexity nightmare - local only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| WR-01 | Phase 15 | Complete |
| WR-02 | Phase 15 | Complete |
| WR-03 | Phase 15 | Complete |
| WR-04 | Phase 15 | Complete |
| WR-05 | Phase 17 | Complete |
| WR-06 | Phase 17 | Complete |
| WR-07 | Phase 17 | Complete |
| WM-01 | Phase 16 | Complete |
| WM-02 | Phase 16 | Complete |
| WM-03 | Phase 16 | Complete |
| WM-04 | Phase 16 | Complete |
| WM-05 | Phase 18 | Complete |
| WM-06 | Phase 16 | Complete |
| TEST-01 | Phase 19 | Complete |
| TEST-02 | Phase 19 | Complete |
| TEST-03 | Phase 19 | Complete |
| TEST-04 | Phase 19 | Complete |

**Coverage:**
- v2.0.2 requirements: 17 total
- Mapped to phases: 17 ✓
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-04*
*Last updated: 2026-02-08 after Phase 19 completion*
