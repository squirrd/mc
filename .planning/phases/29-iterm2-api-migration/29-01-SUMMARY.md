---
phase: 29-iterm2-api-migration
plan: 01
subsystem: terminal
tags: [iterm2, macos, asyncio, applescript, terminal-automation, python-api]

# Dependency graph
requires:
  - phase: 16-window-registry
    provides: WindowRegistry and _window_exists_by_id / focus_window_by_id callbacks used in MacOSLauncher
provides:
  - iterm2 Python library as optional macOS extra in pyproject.toml
  - MacOSLauncher with Python API primary path for window creation (MCC-Term profile, command= hidden)
  - Terminal.app AppleScript fallback preserved for when API is unavailable
  - _ITERM2_LIB_AVAILABLE module flag with ImportError guard
  - Once-per-day fallback notice via ~/.cache/mc/iterm2_fallback_notice_date sentinel
  - .flake8 config with max-line-length=100 matching Black configuration
affects:
  - 29-02-tests (will add comprehensive unit tests for new API methods)
  - any phase touching MacOSLauncher or terminal window creation

# Tech tracking
tech-stack:
  added:
    - iterm2==2.14 (optional, macos extra, darwin-only)
    - protobuf==7.34.0 (transitive dependency of iterm2)
    - websockets==16.0 (transitive dependency of iterm2)
  patterns:
    - Sync bridge to async iterm2 API using iterm2.run_until_complete()
    - asyncio.timeout(5) inside coroutine (not outside run_until_complete)
    - _last_api_window_id instance attribute passes window_id from launch() to _capture_window_id()
    - API-first with AppleScript fallback for each operation (exists, focus, launch)
    - ImportError guard at module level for optional library availability

key-files:
  created:
    - .flake8 (max-line-length=100 to match Black)
  modified:
    - pyproject.toml (iterm2>=2.14 optional dependency, mypy override)
    - uv.lock (iterm2 v2.14, protobuf v7.34.0, websockets v16.0 added)
    - src/mc/terminal/macos.py (Python API methods, refactored launch())
    - tests/unit/test_terminal_launcher.py (test_macos_launcher_launch_iterm2 updated)

key-decisions:
  - "iterm2 added as optional extra [macos], not core dependency — keeps Linux installs clean"
  - "asyncio.timeout(5) applied INSIDE the coroutine, not outside run_until_complete()"
  - "_last_api_window_id instance attribute (not return value) passes window_id through launch() to _capture_window_id()"
  - "Fallback prints to stderr once per day via file sentinel; suppressed after first show"
  - "_build_iterm_script() retained for backwards-compat and tests (referenced in plan 02 tests)"
  - "Added .flake8 config (max-line-length=100) to fix pre-existing project misconfiguration"

patterns-established:
  - "Pattern: sync bridge for async iterm2 — use iterm2.run_until_complete(coro), timeout inside coro"
  - "Pattern: API-first with fallback — try Python API, return None on failure, fall through to AppleScript"
  - "Pattern: mutable list as result holder [None] for async result capture from sync context"

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 29 Plan 01: iTerm2 Python API Migration Summary

**MacOSLauncher now creates iTerm2 windows via iterm2 Python API (MCC-Term profile, command= hidden from scrollback) with Terminal.app AppleScript fallback; iterm2>=2.14 added as optional macOS dependency**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T03:57:05Z
- **Completed:** 2026-03-12T04:01:47Z
- **Tasks:** 2
- **Files modified:** 5 (+ 1 created)

## Accomplishments

- Added iterm2>=2.14 as optional `[macos]` dependency with darwin-only platform marker, keeping Linux installs unaffected
- Refactored `MacOSLauncher.launch()` to try `iterm2.Window.async_create(profile="MCC-Term", command=...)` via Python API first — raw podman command no longer echoed to terminal scrollback
- Preserved all Terminal.app AppleScript paths as fallback; fallback notice prints to stderr once per day via file sentinel
- Added API methods for window existence check and focus (`_window_exists_by_id_api`, `_focus_window_by_id_api`) using `app.get_window_by_id()` and `app/window.async_activate()`

## Task Commits

1. **Task 1: Add iterm2 optional dependency and mypy override** - `f20ccbc` (chore)
2. **Task 2: Refactor MacOSLauncher to use iterm2 Python API** - `33f6007` (feat)

**Plan metadata:** (created below in final commit)

## Files Created/Modified

- `.flake8` - Added max-line-length=100 to match Black config (project was missing this)
- `pyproject.toml` - iterm2>=2.14 in [project.optional-dependencies].macos; mypy override for iterm2.*
- `uv.lock` - iterm2 v2.14 + transitive deps (protobuf v7.34.0, websockets v16.0) added
- `src/mc/terminal/macos.py` - Python API methods, refactored launch()/_capture_window_id()/_window_exists_by_id()/focus_window_by_id()
- `tests/unit/test_terminal_launcher.py` - test_macos_launcher_launch_iterm2 updated to test API path

## Decisions Made

- **iterm2 as optional extra** — Added under `[project.optional-dependencies].macos`, not in core `[project.dependencies]`. Platform marker `; sys_platform == 'darwin'` provides best-effort Linux protection; the real gate is the `ImportError` guard at runtime.
- **asyncio.timeout(5) inside coroutine** — `run_until_complete()` is synchronous; `asyncio.timeout()` must live inside the `async def` coroutine. Wrapping `run_until_complete()` itself would not work.
- **_last_api_window_id as instance attribute** — `launch()` returns `None` (matches the protocol). The window ID captured by the API is threaded through as `self._last_api_window_id` so `_capture_window_id()` can return it immediately after launch.
- **_build_iterm_script() retained** — Kept in place (referenced in existing tests, plan 02 will add new iTerm2-specific tests). Dead code when API succeeds but removing it would break test references.
- **.flake8 config added** — Project had Black set to 100 chars but no flake8 config, causing E501 false positives throughout the codebase. Added `.flake8` with `max-line-length = 100` to fix the project-wide misconfiguration.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added .flake8 config with max-line-length=100**

- **Found during:** Task 2 (verifying flake8 passes 0 errors)
- **Issue:** Project used Black with 100-char line length but had no .flake8 config, causing flake8 to default to 79-char limit and report E501 errors on ALL project files (pre-existing condition)
- **Fix:** Created `.flake8` with `max-line-length = 100` and `extend-ignore = E203` (matches Black's slice formatting)
- **Files modified:** `.flake8` (created)
- **Verification:** `uv run flake8 src/mc/terminal/macos.py` — 0 errors
- **Committed in:** `33f6007` (Task 2 commit)

**2. [Rule 1 - Bug] Updated test_macos_launcher_launch_iterm2 for new API path**

- **Found during:** Task 2 (running pytest after refactor)
- **Issue:** Test expected `"iTerm"` in the AppleScript passed to Popen, but launch() now tries Python API first (returns None in test env since iterm2 not installed), falls through to Terminal.app script
- **Fix:** Updated test to mock `_try_iterm2_api` returning a window_id and verify `_last_api_window_id` is set correctly and consumed by `_capture_window_id()`
- **Files modified:** `tests/unit/test_terminal_launcher.py`
- **Verification:** All 40 tests pass
- **Committed in:** `33f6007` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 blocking project config, 1 bug in existing test)
**Impact on plan:** Both auto-fixes necessary for correctness. No scope creep.

## Issues Encountered

None — implementation followed the plan and research patterns exactly. The asyncio bridge, API availability guard, and fallback sentinel all worked as specified in RESEARCH.md.

## User Setup Required

None - no external service configuration required. However, to use the iTerm2 Python API path:

1. Install the macos extra: `uv pip install "mc-cli[macos]"` or `uv sync --extra macos`
2. Enable iTerm2 Python API: iTerm2 > Settings > General > Magic > Enable Python API

Without these steps, the fallback path (Terminal.app AppleScript) is used automatically.

## Next Phase Readiness

- Plan 02 can now add comprehensive unit tests for `_launch_via_iterm2_api`, `_window_exists_by_id_api`, `_focus_window_by_id_api`, and the fallback sentinel logic
- All new methods have correct type signatures and pass mypy strict mode
- The `.flake8` fix unblocks flake8 verification across the entire codebase for future phases

---
*Phase: 29-iterm2-api-migration*
*Completed: 2026-03-12*
