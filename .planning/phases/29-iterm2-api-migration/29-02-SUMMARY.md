---
phase: 29-iterm2-api-migration
plan: 02
subsystem: testing
tags: [iterm2, macos, asyncio, applescript, terminal-automation, python-api, unit-tests, pytest]

# Dependency graph
requires:
  - phase: 29-01
    provides: MacOSLauncher Python API methods (_try_iterm2_api, _launch_via_iterm2_api, _window_exists_by_id_api, _focus_window_by_id_api, fallback sentinel) under test
provides:
  - 24 new unit tests in test_terminal_macos_api.py covering all Python API decision branches
  - Updated test_terminal_launcher.py with explicit API-first/fallback test variants for iTerm2 launch path
  - Full quality gate validated: 523 unit tests pass, 67% coverage, mypy/flake8/bandit clean
affects:
  - any future phase touching MacOSLauncher or terminal window creation (tests serve as regression guard)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mocker.patch.object to isolate _try_iterm2_api, _window_exists_by_id_api, _focus_window_by_id_api without requiring iterm2 library"
    - "monkeypatch.setattr to redirect module-level _ITERM2_FALLBACK_SENTINEL to tmp_path for isolation"
    - "capsys.readouterr() to assert stderr fallback notice content"

key-files:
  created:
    - tests/unit/test_terminal_macos_api.py (24 tests, 6 test classes)
  modified:
    - tests/unit/test_terminal_launcher.py (iTerm2 tests updated, both API and fallback variants added)

key-decisions:
  - "test_macos_launcher_launch_iterm2 renamed to _via_api variant; _via_applescript_fallback added as separate test — both variants explicitly document the API-first dispatch"
  - "non_blocking, missing_osascript, launch_failure tests updated to explicitly mock _try_iterm2_api=None — removes reliance on library-absence side effect for test correctness"
  - "Fallback sentinel tests use monkeypatch.setattr on module-level path constant (not tmp_path fixture alone) for isolation without touching real ~/.cache/mc/"

patterns-established:
  - "Pattern: mock _try_iterm2_api at instance level via mocker.patch.object — tests API dispatch without iterm2 library installed"
  - "Pattern: redirect module-level Path constants via monkeypatch.setattr for file-based state isolation"
  - "Pattern: capsys for stderr assertion on once-per-day fallback notice"

# Metrics
duration: 4min
completed: 2026-03-12
---

# Phase 29 Plan 02: iTerm2 Python API Tests Summary

**24 unit tests covering iterm2 Python API path (all branches: success, lib missing, exception, timeout, fallback notice show/suppress) plus updated launcher tests with explicit API-first/fallback variants; full suite 523 passed at 67% coverage**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-12T04:04:59Z
- **Completed:** 2026-03-12T04:08:14Z
- **Tasks:** 2
- **Files modified:** 2 (1 created, 1 updated)

## Accomplishments

- Created `tests/unit/test_terminal_macos_api.py` with 24 test functions across 6 classes covering _try_iterm2_api (lib available, missing, exception), launch() API/fallback paths, _capture_window_id API consumption, _window_exists_by_id/_focus_window_by_id dispatch, and fallback sentinel logic
- Updated `test_terminal_launcher.py`: renamed iTerm2 launch test to `_via_api` variant, added `_via_applescript_fallback` variant, and updated non_blocking/missing_osascript/launch_failure tests to explicitly mock `_try_iterm2_api=None`
- Full quality gate passed: 523 unit tests, 67% coverage (above 60% threshold), mypy 0 errors, flake8 0 errors, bandit 0 high severity on macos.py

## Task Commits

1. **Task 1: Write new unit tests for the iterm2 Python API path** - `931ea6f` (test)
2. **Task 2: Update existing launcher tests and run full quality gate** - `302940f` (test)

**Plan metadata:** (created below in final commit)

## Files Created/Modified

- `tests/unit/test_terminal_macos_api.py` - 24 new tests: TestTryIterm2Api, TestLaunchApiPath, TestCaptureWindowId, TestWindowExistsById, TestFocusWindowById, TestFallbackNoticeSentinel
- `tests/unit/test_terminal_launcher.py` - Updated MacOSLauncher tests: API/fallback variants; explicit _try_iterm2_api mocking in 3 existing tests; removed unused imports

## Decisions Made

- **Both launch() variants as separate tests** — Having `_via_api` and `_via_applescript_fallback` as distinct named tests makes the API-first dispatch decision explicit in the test suite. A reader can see immediately that iTerm2 prefers the Python API but gracefully falls back.
- **Explicit `_try_iterm2_api=None` mocking in existing tests** — `test_macos_launcher_non_blocking`, `test_macos_launcher_missing_osascript`, and `test_macos_launcher_launch_failure` previously worked only because the iterm2 library is absent in the test environment. Explicitly mocking makes the tests robust to future iterm2 installation and clearly documents intent.
- **monkeypatch.setattr for sentinel path** — Redirecting `mc.terminal.macos._ITERM2_FALLBACK_SENTINEL` via monkeypatch isolates the sentinel tests without touching `~/.cache/mc/` on the developer's machine.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed unused imports causing flake8 F401 errors**

- **Found during:** Task 2 (running flake8 quality gate)
- **Issue:** `test_terminal_launcher.py` had unused `call` and `patch` imports; `test_terminal_macos_api.py` had unused `AsyncMock` and `patch` imports (AsyncMock was planned for use but the mocking strategy used mocker.patch.object instead)
- **Fix:** Removed unused imports from both files
- **Files modified:** `tests/unit/test_terminal_launcher.py`, `tests/unit/test_terminal_macos_api.py`
- **Verification:** `uv run flake8 ... 2>&1 && echo FLAKE8_OK` → FLAKE8_OK
- **Committed in:** `302940f` (Task 2 commit)

**2. [Rule 1 - Bug] Fixed 2 line-length violations in test_terminal_macos_api.py**

- **Found during:** Task 2 (running flake8 quality gate)
- **Issue:** Docstring on line 121 and fixture signature on line 394 exceeded 100-char limit
- **Fix:** Added `# noqa: E501` on docstring line; split fixture signature across lines
- **Files modified:** `tests/unit/test_terminal_macos_api.py`
- **Verification:** `uv run flake8 ... 2>&1 && echo FLAKE8_OK` → FLAKE8_OK
- **Committed in:** `302940f` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 style/lint bugs caught by quality gate)
**Impact on plan:** Both auto-fixes necessary for quality gate passage. No scope creep.

## Issues Encountered

None — test strategy was clear from 29-01 implementation. AsyncMock was listed in the plan's import list but was not needed in practice since mocker.patch.object on synchronous wrapper methods sufficed (no direct async testing required at the unit level).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 29 (iTerm2 Python API Migration) is now complete: implementation in 29-01, tests in 29-02
- MacOSLauncher has full test coverage for all API-first/fallback decision branches
- Quality gate is clean — safe base for Phase 30 (mc-update core)

---
*Phase: 29-iterm2-api-migration*
*Completed: 2026-03-12*
