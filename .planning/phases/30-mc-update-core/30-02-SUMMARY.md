---
phase: 30-mc-update-core
plan: 02
subsystem: testing
tags: [pytest, subprocess, agent-mode-guard, FileNotFoundError, security, coverage, flake8, mypy]

# Dependency graph
requires:
  - phase: 30-mc-update-core
    plan: 01
    provides: src/mc/update.py with all upgrade logic and 12 primary-flow tests

provides:
  - tests/unit/test_update.py — 17 unit tests (12 from 30-01 + 5 edge case tests)
  - Full edge case coverage: FileNotFoundError paths, subprocess security (list form/no shell=True), RESEARCH Pitfall 3, agent mode guard, recovery instructions text

affects:
  - 31-release (Phase 30 complete — mc-update module fully tested and quality-gated)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Separate edge-case test plan pattern (30-01 happy path, 30-02 failure paths)
    - MagicMock side_effect list for multi-call subprocess sequences
    - noqa inline comment for unavoidable long inline comment in test code

key-files:
  created: []
  modified:
    - tests/unit/test_update.py

key-decisions:
  - "shell=False assertion pattern: call_args.kwargs.get('shell', False) is False — tests subprocess security without requiring explicit kwarg"
  - "test_upgrade_verify_step_fails_after_success asserts 'Upgrade complete' absent from stdout — success message must not appear on partial failure"
  - "Pre-existing test_mc_version[inprocess] failure (asserts 2.0.1, actual 2.0.4) documented as known issue; not introduced by Phase 30"

patterns-established:
  - "Pattern: Test 'negative' message absence (assert X not in stdout) to prevent misleading success messages on failure paths"
  - "Pattern: Agent mode guard test patches subprocess.run AND asserts call_count == 0 to prove no subprocess escapes the guard"

# Metrics
duration: 5min
completed: 2026-03-12
---

# Phase 30 Plan 02: mc-update Edge Case Tests Summary

**Five additional unit tests covering FileNotFoundError paths, subprocess security (no shell=True), RESEARCH Pitfall 3 post-upgrade mc failure, agent mode zero-subprocess guard, and exact recovery text — Phase 30 quality gate passed at 75% total coverage**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-12T04:59:59Z
- **Completed:** 2026-03-12T05:05:00Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Expanded `tests/unit/test_update.py` from 12 to 17 tests covering all edge cases from RESEARCH pitfall analysis
- All quality gates passed: mypy 0 errors, flake8 0 violations, 75% total coverage (above 60% minimum)
- Confirmed agent mode guard fires before any subprocess call (call_count == 0 assertion)
- Confirmed "Upgrade complete" is absent from stdout when post-upgrade mc verify fails (RESEARCH Pitfall 3)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add FileNotFoundError and broken-mc edge case tests** - `964d725` (test)
2. **Task 2: Fix flake8 E501 violations from Task 1 additions** - `5f56e52` (style)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `tests/unit/test_update.py` - Added 5 tests: test_run_upgrade_uses_list_form_not_shell, test_verify_mc_not_found_stderr_message, test_upgrade_verify_step_fails_after_success, test_upgrade_agent_mode_does_not_call_uv, TestPrintRecoveryInstructions.test_recovery_instructions_content

## Decisions Made
- **shell=False check pattern:** `mock_run.call_args.kwargs.get('shell', False) is False` correctly handles the case where `shell` is not passed explicitly (defaults to False) without requiring explicit kwarg presence
- **Negative assertion for success message:** `assert "Upgrade complete" not in captured.out` in Pitfall 3 test ensures failure path doesn't falsely claim success
- **noqa for long inline comment:** One `# noqa: E501` applied to a test mock comment that would require awkward restructuring to shorten — used sparingly as per flake8 convention

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed flake8 E501 violations introduced in Task 1**
- **Found during:** Task 2 (quality gate)
- **Issue:** Two lines exceeded 100-char limit: docstring on line 134 (101 chars) and inline mock comment on line 159 (102 chars)
- **Fix:** Shortened docstring; added `# noqa: E501` to unavoidable long inline comment
- **Files modified:** tests/unit/test_update.py
- **Verification:** `uv run flake8 src/mc/update.py tests/unit/test_update.py` exits 0
- **Committed in:** 5f56e52 (Task 2 style commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug/style in test file)
**Impact on plan:** Flake8 fix is a standard code-quality correction. No scope creep, no logic changes.

## Issues Encountered
- Pre-existing `tests/integration/test_entry_points.py::test_mc_version[inprocess]` failure (asserts version `'2.0.1'`, actual `2.0.4`). Confirmed pre-existing by reverting changes and rerunning — failure exists on main before any Phase 30 changes. Not introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 30 complete: mc-update module implemented, entry point registered, 17 unit tests, quality gate passed
- Phase 31 (release) can proceed: v2.0.5 mc-update entry point is ready for packaging

---
*Phase: 30-mc-update-core*
*Completed: 2026-03-12*
