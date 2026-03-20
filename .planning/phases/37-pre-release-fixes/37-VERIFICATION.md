---
phase: 37-pre-release-fixes
verified: 2026-03-20T23:34:39Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 37: Pre-Release Fixes Verification Report

**Phase Goal:** Close three known defects before archiving the v2.0.7 milestone: fix the StateDatabase path bug that silently breaks BPL-04, add missing test coverage for the banner agent-mode guard, and resolve orphaned helper functions by wiring `should_check_for_updates()` into `main.py`.
**Verified:** 2026-03-20T23:34:39Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                  | Status     | Evidence                                                                                     |
|----|--------------------------------------------------------------------------------------------------------|------------|----------------------------------------------------------------------------------------------|
| 1  | `_get_state_db()` uses explicit path `~/mc/state/containers.db`                                       | VERIFIED   | Lines 58-62 of `backplane_login.py`: `Path.home() / "mc" / "state" / "containers.db"` passed as `db_path=` kwarg |
| 2  | Unit tests confirm `show_update_banner` is called in host mode and suppressed in agent mode            | VERIFIED   | `TestBannerAgentModeGuard` class at line 108 of `test_main.py` with two substantive test methods |
| 3  | `should_check_for_updates()` replaces the raw `get_runtime_mode() != 'agent'` guard in `main.py`      | VERIFIED   | Line 160 of `main.py`: `if should_check_for_updates():` — OCM monitor guard at line 167 correctly left as raw check |
| 4  | `check_for_updates()` deleted from `version_check.py` (no callers, no tests)                         | VERIFIED   | `grep -n "def check_for_updates" src/mc/version_check.py` returns no matches                |
| 5  | All existing tests still pass after changes                                                            | VERIFIED   | 673 unit tests pass with zero failures                                                       |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact                                         | Expected                                            | Status     | Details                                                                                              |
|--------------------------------------------------|-----------------------------------------------------|------------|------------------------------------------------------------------------------------------------------|
| `src/mc/agent/backplane_login.py`                | Fixed `_get_state_db()` with explicit db_path        | VERIFIED   | Has `from pathlib import Path`; `_get_state_db` passes `db_path=str(Path.home() / ...)` to StateDatabase |
| `tests/unit/test_agent_backplane_login.py`       | Test asserting StateDatabase receives correct path   | VERIFIED   | `test_get_state_db_uses_explicit_path` at line 340, uses `mocker.patch` and `assert_called_once_with(db_path=expected_path)` |
| `tests/unit/test_main.py`                        | Two banner guard tests                               | VERIFIED   | `TestBannerAgentModeGuard` class with `test_show_update_banner_called_in_host_mode` and `test_show_update_banner_not_called_in_agent_mode` |
| `src/mc/cli/main.py`                             | Banner guard using `should_check_for_updates()`     | VERIFIED   | Line 13 imports `should_check_for_updates`; line 160 uses it as the guard condition              |
| `src/mc/version_check.py`                        | No `check_for_updates()` function                   | VERIFIED   | Function absent from file; grep confirms no matches                                              |

### Key Link Verification

| From                                              | To                                              | Via                                 | Status     | Details                                                                         |
|---------------------------------------------------|-------------------------------------------------|-------------------------------------|------------|---------------------------------------------------------------------------------|
| `backplane_login.py:_get_state_db`               | `state.py:StateDatabase.__init__`               | `db_path=` keyword argument          | WIRED      | Line 60: `StateDatabase(db_path=str(db_path))` — no-arg form eliminated        |
| `main.py:~160`                                    | `runtime.py:should_check_for_updates`           | import + direct call                | WIRED      | Line 13 imports both; line 160 calls `should_check_for_updates()` as condition  |
| `test_main.py:TestBannerAgentModeGuard`          | `main.py:~160` banner guard                     | patches `should_check_for_updates`  | WIRED      | `patch('mc.cli.main.should_check_for_updates', return_value=not is_agent)` drives both modes |
| `test_agent_backplane_login.py:test_get_state_db_uses_explicit_path` | `backplane_login.py:_get_state_db` | `mocker.patch` + `assert_called_once_with` | WIRED | Patches `StateDatabase` at the module level; asserts `db_path=expected_path` |

### Requirements Coverage

All three defects targeted by this phase are closed:

| Requirement                        | Status    | Evidence                                           |
|------------------------------------|-----------|---------------------------------------------------|
| BPL-04 StateDatabase path fix      | SATISFIED | `_get_state_db()` now uses explicit host-mounted path |
| Banner agent-mode test coverage    | SATISFIED | Two tests in `TestBannerAgentModeGuard` pass       |
| Dead public API (`check_for_updates`) removed | SATISFIED | Function deleted from `version_check.py`; `should_check_for_updates()` wired into `main.py` |

### Anti-Patterns Found

None. No TODO/FIXME comments, empty handlers, or placeholder patterns found in modified files.

### Human Verification Required

None. All success criteria are verifiable programmatically.

## Gaps Summary

No gaps. All five must-have truths are verified against the actual codebase. The three defects targeted by this phase are closed.

---

_Verified: 2026-03-20T23:34:39Z_
_Verifier: Claude (gsd-verifier)_
