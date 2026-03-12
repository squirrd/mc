---
phase: 32-update-notifications
plan: 02
subsystem: cli
tags: [banner, update-notification, pytest, unit-tests, version-check, rich]

# Dependency graph
requires:
  - phase: 32-01
    provides: show_update_banner() function in src/mc/banner.py and ConfigManager extension
  - phase: 30-mc-update
    provides: _fetch_latest_version() used inside _fetch_with_timeout
affects:
  - cli/main.py is now the single wiring point for update notifications

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy-imported symbols patched at source module (mc.update._fetch_latest_version, mc.version.get_version, mc.config.manager.ConfigManager, rich.console.Console, rich.panel.Panel)"
    - "show_update_banner wired into main() behind get_runtime_mode() != 'agent' guard"

key-files:
  created:
    - tests/unit/test_banner.py
  modified:
    - src/mc/cli/main.py
    - tests/unit/test_main.py

key-decisions:
  - "Patch lazy imports at their source module, not at mc.banner (which has no module-level attribute for them)"
  - "rich.console.Console and rich.panel.Panel both patched at rich.* source for _render_banner tests"
  - "test_main.py helper _run_main_go updated to patch show_update_banner instead of removed VersionChecker"

patterns-established:
  - "When removing an import from cli/main.py, check existing tests that patch that symbol and update them"

# Metrics
duration: 6min
completed: 2026-03-12
---

# Phase 32 Plan 02: Banner CLI Hook and Unit Tests Summary

**show_update_banner() wired into cli/main.py at startup (VersionChecker removed), 21-test suite for banner.py added with correct lazy-import patch targets, all 579 unit tests passing at 67.84% coverage**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-12T11:03:46Z
- **Completed:** 2026-03-12T11:09:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Replaced `VersionChecker` background check in `cli/main.py` with foreground `show_update_banner()` call, guarded by `get_runtime_mode() != 'agent'`
- Created `tests/unit/test_banner.py` with 21 tests covering all 6 functions in `src/mc/banner.py`
- Fixed pre-existing test breakage in `test_main.py` caused by removing the `VersionChecker` import (patched stale symbol swapped for `show_update_banner`)
- Full quality gate passes: pytest (579/579), flake8 (clean), bandit (no issues), mypy (pre-existing platform_detect.py error only)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire banner hook into cli/main.py** - `17dba1c` (feat)
2. **Task 2: Write unit tests for banner.py and run quality gate** - `cb6deb8` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified
- `src/mc/cli/main.py` - Replaced VersionChecker import/block with show_update_banner import and call
- `tests/unit/test_banner.py` - 21 unit tests for _is_version_invocation, _already_shown_today, _fetch_with_timeout, _write_suppression_timestamp, _render_banner, show_update_banner
- `tests/unit/test_main.py` - Updated _run_main_go helper to patch show_update_banner instead of removed VersionChecker

## Decisions Made
- Lazy imports inside banner.py functions require patching at source modules (`mc.update._fetch_latest_version`, `mc.version.get_version`, `mc.config.manager.ConfigManager`, `rich.console.Console`, `rich.panel.Panel`); patching at `mc.banner.*` raises AttributeError
- `test_main.py` helper updated inline as part of Task 2 (deviation rule 1 auto-fix for broken tests)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed stale VersionChecker patch in test_main.py**
- **Found during:** Task 2 (full unit suite run after writing test_banner.py)
- **Issue:** `_run_main_go` helper in `test_main.py` patched `mc.cli.main.VersionChecker` which was removed in Task 1; caused 2 tests to fail with AttributeError
- **Fix:** Replaced `patch('mc.cli.main.VersionChecker')` with `patch('mc.cli.main.show_update_banner')`
- **Files modified:** `tests/unit/test_main.py`
- **Verification:** `uv run pytest tests/unit/test_main.py` — all 5 tests pass
- **Committed in:** cb6deb8 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Essential fix — Task 1 removed VersionChecker causing test_main.py regression. Auto-fixed inline.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 32 complete — update notification system fully shipped (banner module + CLI hook + tests)
- v2.0.5 Auto-Update & Terminal milestone complete
- No blockers

---
*Phase: 32-update-notifications*
*Completed: 2026-03-12*
