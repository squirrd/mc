---
phase: 37-pre-release-fixes
plan: 03
subsystem: cli
tags: [runtime, version-check, agent-mode, mypy, dead-code]

# Dependency graph
requires:
  - phase: 36-ocm-token-monitor
    provides: should_check_for_updates() in runtime.py (unused in production before this plan)
  - phase: 35-backplane-login
    provides: ~/mc/state mount in ContainerManager.create() (tests not updated at the time)
provides:
  - main.py banner guard uses should_check_for_updates() — agent users see informational message
  - check_for_updates() removed from version_check.py (dead public API surface gone)
  - VersionChecker.__init__ has -> None annotation (mypy clean)
  - _fetch_latest_release 304 branch returns str not Optional[str] (mypy clean)
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Banner guard: use should_check_for_updates() semantic wrapper not raw get_runtime_mode() != 'agent'"
    - "Dead function removal: zero-caller functions with no tests deleted, not left as public API"

key-files:
  created: []
  modified:
    - src/mc/cli/main.py
    - src/mc/version_check.py
    - tests/unit/test_main.py
    - tests/unit/test_container_manager_create.py
    - tests/unit/test_container_manager_mounts.py

key-decisions:
  - "Mock should_check_for_updates in test_main.py (not get_runtime_mode) for banner guard tests — matches the actual call site"
  - "etag or '' in 304 return branch — coerces Optional[str] to str to satisfy declared return type"
  - "Path.home() / 'mc' / 'state' computed in test assertions — mirrors production code, no mock of Path needed"

patterns-established:
  - "Semantic guards: prefer named functions (should_check_for_updates) over raw comparisons (get_runtime_mode() != 'agent') in main.py"

# Metrics
duration: 5min
completed: 2026-03-20
---

# Phase 37 Plan 03: Orphaned Helper Cleanup Summary

**Wired should_check_for_updates() into main.py banner guard and deleted the zero-caller check_for_updates() wrapper from version_check.py**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-20T23:23:51Z
- **Completed:** 2026-03-20T23:28:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- Banner guard in main.py now calls should_check_for_updates() — agent-mode users see "Updates managed via container builds" instead of silent suppression
- Deleted check_for_updates() (zero callers, zero tests) — removes dead public API surface from version_check.py
- Fixed 2 pre-existing mypy errors in VersionChecker (__init__ return annotation, 304-branch Optional[str] coercion)
- Fixed 3 pre-existing test failures from Phase 35 ~/mc/state mount not being reflected in unit tests

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire should_check_for_updates() into main.py banner guard** - `29084e0` (feat)
2. **Task 2: Delete orphaned check_for_updates() and fix pre-existing type/test bugs** - `41d1b84` (fix)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/mc/cli/main.py` - Import and call should_check_for_updates() for banner guard
- `src/mc/version_check.py` - Remove check_for_updates(), fix __init__ annotation, fix 304 etag coercion
- `tests/unit/test_main.py` - Mock should_check_for_updates instead of get_runtime_mode for banner tests
- `tests/unit/test_container_manager_create.py` - Add ~/mc/state to expected volumes dict
- `tests/unit/test_container_manager_mounts.py` - Update mount count from 4 to 5, assert state mount present

## Decisions Made

- Mock `mc.cli.main.should_check_for_updates` (not `get_runtime_mode`) in banner guard tests — the mock must match the actual call site in main.py after the change
- `etag or ''` in 304 return branch — `etag` is Optional[str] but declared return type is `str`; `or ''` coerces None to empty string cleanly
- `Path.home() / "mc" / "state"` computed directly in test assertions — mirrors production code; no need to mock Path since state path is always the real home

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed pre-existing mypy error: VersionChecker.__init__ missing -> None annotation**

- **Found during:** Task 2 (Delete check_for_updates())
- **Issue:** mypy reported "Function is missing a return type annotation" on line 34 — pre-existed before this plan
- **Fix:** Added `-> None` to `__init__` signature
- **Files modified:** src/mc/version_check.py
- **Verification:** uv run mypy src/mc/version_check.py passes
- **Committed in:** 41d1b84 (Task 2 commit)

**2. [Rule 1 - Bug] Fixed pre-existing mypy error: 304 branch returns Optional[str] where str is declared**

- **Found during:** Task 2 (Delete check_for_updates())
- **Issue:** `return None, etag, 304` with `etag: Optional[str]` violates declared return type `tuple[Optional[dict], str, int]` — pre-existed before this plan
- **Fix:** Changed to `return None, etag or '', 304`
- **Files modified:** src/mc/version_check.py
- **Verification:** uv run mypy src/mc/version_check.py passes
- **Committed in:** 41d1b84 (Task 2 commit)

**3. [Rule 1 - Bug] Fixed 3 pre-existing unit test failures from Phase 35 ~/mc/state mount**

- **Found during:** Task 2 unit test run (673 pass needed; 3 were pre-existing failures)
- **Issue:** Phase 35 added `~/mc/state` mount to ContainerManager.create() but two unit tests were not updated: test_create_new_container (strict volumes dict equality) and test_all_mounts_present_when_all_paths_exist (len == 4). test_main.py banner guard test was also failing after Task 1 changed the call site.
- **Fix:** Added `Path.home() / "mc" / "state"` to expected volumes in create test; updated mounts count to 5 and added state key assertion; updated test_main.py to mock should_check_for_updates.
- **Files modified:** tests/unit/test_main.py, tests/unit/test_container_manager_create.py, tests/unit/test_container_manager_mounts.py
- **Verification:** 673 tests pass, 0 failures
- **Committed in:** 41d1b84 (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3x Rule 1 bugs — all pre-existing, not introduced by this plan)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the pre-existing bugs documented above.

## Next Phase Readiness

- All pre-release fixes in phase 37 can proceed — test suite is clean at 673 passing
- No blockers

---
*Phase: 37-pre-release-fixes*
*Completed: 2026-03-20*
