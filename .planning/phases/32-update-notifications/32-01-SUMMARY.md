---
phase: 32-update-notifications
plan: 01
subsystem: cli
tags: [rich, banner, update-notification, config, version-check, threading]

# Dependency graph
requires:
  - phase: 31-version-pinning
    provides: pinned_mc config field and ConfigManager.get_version_config()
  - phase: 30-mc-update
    provides: _fetch_latest_version() and mc-update upgrade/unpin commands
provides:
  - show_update_banner() public function in src/mc/banner.py
  - Calendar-day suppression via last_banner_shown ISO timestamp in config
  - Pin-aware Rich Panel banner rendered to stderr
  - ConfigManager.get_version_config() now returns last_banner_shown key
  - ConfigManager.update_version_config() accepts last_banner_shown parameter
affects:
  - 32-02 (tests for banner.py)
  - cli/main.py integration (hook show_update_banner() into startup)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Daemon thread + threading.Event for bounded network timeout"
    - "All lazy imports inside function bodies to keep module importable with no side effects"
    - "Calendar-day suppression: compare date() portion of stored ISO timestamp to date.today()"

key-files:
  created:
    - src/mc/banner.py
  modified:
    - src/mc/config/manager.py

key-decisions:
  - "threading.Event + daemon thread used for 1.5s timeout — thread result stored in mutable list container"
  - "Network failure (None from _fetch_latest_version) treated same as timeout — no suppression written"
  - "piped/non-interactive runs guard at show_update_banner level (isatty) and redundantly in _write_suppression_timestamp"
  - "pinned_mc == 'latest' maps to pinned_arg=None for clean None-checks in _render_banner"

patterns-established:
  - "Lazy import pattern: mc.config.manager, mc.version, mc.update, packaging all imported inside function bodies"
  - "Rich Console(stderr=True) for all banner output — never touches stdout"

# Metrics
duration: 2min
completed: 2026-03-12
---

# Phase 32 Plan 01: Update Notification Banner Module Summary

**Rich Panel update banner with 1.5s threaded timeout, calendar-day suppression, and pin-aware messaging — all in a single importable src/mc/banner.py with zero module-level side effects**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-12T11:00:57Z
- **Completed:** 2026-03-12T11:02:12Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Created `src/mc/banner.py` with `show_update_banner()` as the single public entry point
- Extended `ConfigManager.get_version_config()` to return `last_banner_shown` key
- Extended `ConfigManager.update_version_config()` to accept and persist `last_banner_shown` ISO timestamp
- Banner uses Rich Panel to stderr with yellow border; blank lines above/below for visual separation
- Pin-aware: when `pinned_mc != 'latest'`, shows "v{latest} available (pinned at v{current})" + unpin instruction

## Task Commits

Each task was committed atomically:

1. **Task 1: Extend ConfigManager with last_banner_shown support** - `e19e1cd` (feat)
2. **Task 2: Create src/mc/banner.py with show_update_banner()** - `d2de30c` (feat)

**Plan metadata:** (docs commit below)

## Files Created/Modified
- `src/mc/banner.py` - Update notification banner module; show_update_banner() public function and all helpers
- `src/mc/config/manager.py` - Added last_banner_shown field to get/update_version_config

## Decisions Made
- threading.Event + daemon thread for the 1.5s timeout — result captured in `result = [None]` mutable list; if event not set within timeout, prints "Update check timed out." to stderr and returns None
- Network failure (None returned by _fetch_latest_version) is treated identically to timeout — no suppression timestamp written so it retries next invocation
- Calendar-day comparison uses `datetime.fromisoformat(stored).date() == date.today()` — straightforward, no rolling-window complexity
- `pinned_mc == 'latest'` sentinel maps to `pinned_arg = None` so `_render_banner` receives a clean None/str distinction

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `show_update_banner()` is fully functional and importable — ready for Phase 32-02 unit tests
- `cli/main.py` hook (call show_update_banner() at startup) can proceed once tests are in place
- All success criteria met: importable with no side effects, mypy clean, test_update.py unaffected (35 passing)

---
*Phase: 32-update-notifications*
*Completed: 2026-03-12*
