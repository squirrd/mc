---
phase: 34-case-data-store
plan: "03"
subsystem: terminal
tags: [terminal, attach, podman, exec, agent-mode, init-case, case-data]

# Dependency graph
requires:
  - phase: 34-02
    provides: mc agent init-case CLI command and init_case_data() that writes sfdc-case.json, case.env, etc. to /case/

provides:
  - build_exec_command() now prepends 'mc agent init-case || true; exec bash' before the interactive shell
  - Case files refreshed on every mc case N invocation (CDS-04 satisfied)
  - 3 new focused unit tests for init-case integration behavior

affects:
  - 35-backplane-auto-login: case.env with MC_CLUSTER_EXTERNAL_ID is now written on every terminal attach

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Non-fatal init pattern with || true: prepend setup commands before exec to a long-running process using '|| true' to ensure the primary command always runs

key-files:
  created: []
  modified:
    - src/mc/terminal/attach.py
    - tests/unit/test_terminal_attach.py

key-decisions:
  - "bash -c 'mc agent init-case || true; exec bash' chosen over sourcing or running init-case in a subshell — exec bash replaces the subshell PID with the interactive shell, giving proper job control"
  - "|| true pattern ensures the interactive shell always opens even if mc agent init-case exits non-zero (e.g., no network, CASE_NUMBER unset)"

patterns-established:
  - "Non-fatal setup prepend: use 'cmd || true; exec target' to run setup before long-running process without blocking on failure"

# Metrics
duration: 3min
completed: "2026-03-20"
---

# Phase 34 Plan 03: Terminal Attach Init-Case Wiring Summary

**build_exec_command() now prepends 'mc agent init-case || true; exec bash' — case files refresh on every mc case N, completing Phase 34 CDS-01 through CDS-05**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-20T11:34:13Z
- **Completed:** 2026-03-20T11:37:16Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Modified `build_exec_command()` to run `mc agent init-case || true; exec bash` instead of `/bin/bash` directly — case data files (sfdc-case.json, case.env, etc.) are written fresh on every terminal attach
- Updated existing test assertions to match the new exec command format
- Added 3 focused tests: `test_build_exec_command_includes_init_case`, `test_build_exec_command_init_case_is_non_fatal`, `test_build_exec_command_uses_exec_bash`
- 620 unit tests pass at 68.77% coverage

## Task Commits

Each task was committed atomically:

1. **Task 1: Update build_exec_command() to prepend mc agent init-case** - `a19a6f9` (feat)
2. **Task 2: Update test_terminal_attach.py to match new exec command format** - `2e41fd0` (test)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/mc/terminal/attach.py` - build_exec_command() return value updated to `/bin/bash -c 'mc agent init-case || true; exec bash'`; docstring updated to document the init-case step
- `tests/unit/test_terminal_attach.py` - Updated 2 existing assertions; added 3 new tests for init-case integration

## Decisions Made

- `exec bash` used instead of plain `bash` — `exec` replaces the bash -c subshell PID with the interactive shell, providing proper job control and ensuring `BASH_ENV` is sourced correctly
- `|| true` pattern keeps the interactive shell guarantee: if `mc agent init-case` fails for any reason (no network, CASE_NUMBER missing, API down), the terminal still opens

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - mypy errors observed in output are pre-existing in `container/manager.py` and `integrations/platform_detect.py`, not in any file modified by this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 34 (Case Data Store) is complete — all 5 requirements satisfied:
  - CDS-01: sfdc-case.json written to /case/ at terminal attach time
  - CDS-02: case.env written to /case/ in KEY=VALUE bash-source format
  - CDS-03: case.env includes case_number, cluster_external_id, customer_name, summary, severity, status, product
  - CDS-04: Files overwritten on every mc case N (build_exec_command runs init-case each time)
  - CDS-05: MC_CLUSTER_EXTERNAL_ID always present even when empty
- Phase 35 (Backplane Auto-Login) can now source case.env and read MC_CLUSTER_EXTERNAL_ID reliably on every terminal attach

---
*Phase: 34-case-data-store*
*Completed: 2026-03-20*
