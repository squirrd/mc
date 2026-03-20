---
phase: 37-pre-release-fixes
plan: 02
subsystem: testing
tags: [pytest, mock, banner, agent-mode, update-guard, main-py]

# Dependency graph
requires:
  - phase: 36-ocm-token-monitor
    provides: OCM monitor integration wired into main.py startup
  - phase: 37-pre-release-fixes-01
    provides: BPL-04 fix and _get_state_db path test
provides:
  - Two unit tests covering banner agent-mode guard (TestBannerAgentModeGuard)
  - test_show_update_banner_called_in_host_mode asserts banner fires in host mode
  - test_show_update_banner_not_called_in_agent_mode asserts banner suppressed in agent mode
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Patch should_check_for_updates (not get_runtime_mode) to control banner guard — guard indirection requires patching the correct call site"
    - "Use mc.cli.commands.other.ls patch + ['mc', 'ls', 'someuid'] argv to drive main() past the banner guard without triggering real LDAP"

key-files:
  created: []
  modified:
    - tests/unit/test_main.py

key-decisions:
  - "Patch mc.cli.main.should_check_for_updates (return_value=True/False) rather than get_runtime_mode — the banner guard calls should_check_for_updates() which internally calls is_agent_mode() via mc.runtime, so patching get_runtime_mode at mc.cli.main does not affect the guard"
  - "Use ['mc', 'ls', 'someuid'] with patch('mc.cli.commands.other.ls') as the command vector — this reaches line 160 (after config load) without SystemExit from --help"
  - "Keep get_runtime_mode patch alongside should_check_for_updates patch — needed for OCM monitor guard at line 167 which calls get_runtime_mode directly"

patterns-established:
  - "Test agent-mode guards: patch the exact function the guard calls, not a function it calls internally"

# Metrics
duration: 15min
completed: 2026-03-20
---

# Phase 37 Plan 02: Banner Agent-Mode Guard Tests Summary

**Two unit tests for the banner agent-mode guard in main.py using should_check_for_updates() mock, closing the v2.0.5 audit tech debt item**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-20T23:15:00Z
- **Completed:** 2026-03-20T23:30:36Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added `TestBannerAgentModeGuard` class to `tests/unit/test_main.py` with two tests
- Tests confirm `show_update_banner` is called when `should_check_for_updates()` returns True (host mode)
- Tests confirm `show_update_banner` is NOT called when `should_check_for_updates()` returns False (agent mode)
- Closes the tech debt gap identified in the v2.0.5 audit (STATE.md "Banner agent-mode guard test coverage")

## Task Commits

The banner guard tests were committed as part of plan 37-03 (which ran before 37-02 was explicitly executed):

1. **Task 1: Add banner agent-mode guard tests** - `41d1b84` (test — included in fix(37-03) commit)

**Plan metadata:** See docs commit for 37-02

## Files Created/Modified

- `tests/unit/test_main.py` - Added `TestBannerAgentModeGuard` class with `_run_main_with_mode()` helper and two test methods

## Decisions Made

- **Patch `should_check_for_updates` not `get_runtime_mode`:** The banner guard in main.py uses `if should_check_for_updates():` (not `if get_runtime_mode() != 'agent':`). The `should_check_for_updates()` function calls `is_agent_mode()` → `get_runtime_mode()` through the `mc.runtime` module's own reference, bypassing any patch on `mc.cli.main.get_runtime_mode`. Patching `mc.cli.main.should_check_for_updates` directly is the correct approach.

- **Keep `get_runtime_mode` patch for OCM monitor:** Line 167 has `if get_runtime_mode() != 'agent':` for the OCM monitor block which uses `mc.cli.main.get_runtime_mode` (the local import). This patch IS effective for that guard.

- **`['mc', 'ls', 'someuid']` as command vector:** Using `--help` causes `sys.exit(0)` before line 160. The `ls` command routes through `other.ls` which is independently patched, allowing clean execution through the banner guard.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Banner guard uses `should_check_for_updates()`, not `get_runtime_mode() != 'agent'`**

- **Found during:** Task 1 (test execution)
- **Issue:** Plan described the guard as `if get_runtime_mode() != 'agent':` at lines 160-164. The actual code (refactored in 37-03) is `if should_check_for_updates():`. Patching `get_runtime_mode` did not affect the banner guard — `should_check_for_updates()` calls `is_agent_mode()` via `mc.runtime`, not through the local import.
- **Fix:** Patched `mc.cli.main.should_check_for_updates` with `return_value=not is_agent` in addition to `get_runtime_mode`. The `should_check_for_updates` patch controls whether the banner fires; the `get_runtime_mode` patch handles the OCM monitor guard at line 167.
- **Files modified:** `tests/unit/test_main.py`
- **Verification:** Both tests pass: `test_show_update_banner_called_in_host_mode` and `test_show_update_banner_not_called_in_agent_mode`
- **Committed in:** `41d1b84` (part of fix(37-03) commit — tests were added during 37-03 execution)

---

**Total deviations:** 1 auto-fixed (Rule 1 — codebase evolved since plan was written)
**Impact on plan:** The deviation was a discovery that the code had already been refactored to use `should_check_for_updates()`. The fix required adjusting the mock target, not changing the production code. Tests pass correctly.

## Issues Encountered

The `test_main.py` changes were already committed as part of plan 37-03 (`41d1b84`) before plan 37-02 was explicitly executed. This happened because 37-03 included the same tests as part of its fix for the banner guard refactoring. Plan 37-02 execution verified the tests are correct and passing, and created this SUMMARY.md to formally close the plan.

## Next Phase Readiness

- Banner agent-mode guard is tested and passing
- All pre-existing tests in test_main.py continue to pass (7/7 tests)
- Phase 37 pre-release fixes ongoing (37-01 and 37-03 also complete)

---
*Phase: 37-pre-release-fixes*
*Completed: 2026-03-20*
