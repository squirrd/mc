---
phase: 30-mc-update-core
plan: 01
subsystem: cli
tags: [argparse, subprocess, console_scripts, entry-point, upgrade, uv, agent-mode-guard]

# Dependency graph
requires:
  - phase: 28-version-check
    provides: runtime.is_agent_mode() for agent mode guard
  - phase: 29-iterm2-api
    provides: no direct dependency; completed before this phase

provides:
  - src/mc/update.py — standalone mc-update module with upgrade(), _run_upgrade(), _verify_mc_version(), _print_recovery_instructions(), main()
  - pyproject.toml mc-update console_scripts entry point
  - tests/unit/test_update.py — 12 unit tests covering all primary flows

affects:
  - 30-02 (mc-update integration/notification update in version_check.py)
  - 31-release (v2.0.5 release packaging uses mc-update entry point)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Standalone entry point module pattern (independent from mc.cli.main)
    - Lazy import pattern for agent-mode guard (from mc.runtime import is_agent_mode inside function body)
    - capture_output=False for streaming upgrade output; capture_output=True for version inspection

key-files:
  created:
    - src/mc/update.py
    - tests/unit/test_update.py
  modified:
    - pyproject.toml

key-decisions:
  - "mc-update module is intentionally independent from mc.cli.main — survives partial package upgrades"
  - "Lazy import of is_agent_mode() inside upgrade() function body keeps module importable without mc CLI machinery"
  - "capture_output=False for uv tool upgrade mc (streams live progress); capture_output=True for mc --version (inspect/print)"
  - "Recovery instructions always include 'uv tool install --force mc' regardless of failure mode"

patterns-established:
  - "Pattern 1: Standalone console_scripts module at src/mc/update.py mirrors mc.cli.main:main structure"
  - "Pattern 2: Lazy import guard — import is_agent_mode() inside function, not at module level"
  - "Pattern 3: subprocess.run check=False + manual returncode handling for user-facing recovery instructions"

# Metrics
duration: 8min
completed: 2026-03-12
---

# Phase 30 Plan 01: mc-update Core Summary

**Standalone `mc-update upgrade` command that runs `uv tool upgrade mc`, streams live output, verifies `mc --version` post-upgrade, and prints `uv tool install --force mc` recovery instructions on failure**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-12T04:50:10Z
- **Completed:** 2026-03-12T04:58:14Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created `src/mc/update.py` as a self-contained 131-line module with full type hints, docstrings, and mypy compliance
- Registered `mc-update = "mc.update:main"` in `[project.scripts]` alongside existing `mc` entry point
- Wrote 12 unit tests covering all primary flows: success paths, failure paths, agent mode guard, uv/mc not found

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/mc/update.py with full upgrade logic** - `7a5107b` (feat)
2. **Task 2: Register mc-update entry point in pyproject.toml** - `b7dc3b0` (chore)
3. **Task 3: Write unit tests covering all primary flows** - `aa233fd` (test)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified
- `src/mc/update.py` - mc-update entry point: upgrade(), _run_upgrade(), _verify_mc_version(), _print_recovery_instructions(), main()
- `pyproject.toml` - Added mc-update = "mc.update:main" to [project.scripts]
- `tests/unit/test_update.py` - 12 unit tests across TestRunUpgrade, TestVerifyMcVersion, TestUpgrade, TestMain

## Decisions Made
- **Independent module:** mc-update intentionally avoids importing from mc.cli.main so it survives package replacement during upgrade
- **Lazy import:** `from mc.runtime import is_agent_mode` inside upgrade() function body (not at module level) keeps mc.update importable even if mc's CLI is partially broken
- **Streaming vs capture:** capture_output=False for uv tool upgrade mc (live progress to terminal), capture_output=True for mc --version (need to inspect and print output)
- **Unified recovery message:** Both upgrade failure and post-upgrade verify failure use the same `uv tool install --force mc` recovery instruction

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failure in `tests/integration/test_entry_points.py::test_mc_version` asserts version `'2.0.1'` but current version is `2.0.4`. This is unrelated to this plan (test was last updated at v2.0.1). Not introduced by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- mc-update module complete and tested, ready for Phase 30 Plan 02
- `mc-update upgrade` is functional as a standalone command
- version_check.py notification message (`uvx --reinstall mc-cli@latest`) could be updated to advertise `mc-update upgrade` — deferred to next plan if in scope

---
*Phase: 30-mc-update-core*
*Completed: 2026-03-12*
