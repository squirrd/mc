---
phase: 34-case-data-store
plan: "02"
subsystem: agent
tags: [agent-mode, case-data, sfdc, ocm, env-file, subprocess, cli]

# Dependency graph
requires:
  - phase: 34-01
    provides: fetch_case_comments() and CaseDetails TypedDict extensions (openshiftClusterID, customerName)

provides:
  - init_case_data() in src/mc/agent/case_data.py — writes sfdc-case.json, sfdc-comments.json, case.env, and ocm-cluster.json to /case/
  - mc agent init-case CLI subcommand wired in main.py
  - 19 unit tests covering all scenarios including failure paths

affects:
  - 34-03 (if exists): any plan that wires init-case into container startup
  - 35-backplane-auto-login: reads MC_CLUSTER_EXTERNAL_ID from case.env

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Lazy imports inside function body to prevent circular imports and speed agent startup
    - MC_ prefix convention for all case environment variables in case.env
    - Non-fatal error handling pattern: print("Warning: ...") then return/continue

key-files:
  created:
    - src/mc/agent/case_data.py
    - src/mc/cli/commands/agent.py
    - tests/unit/test_agent_case_data.py
  modified:
    - src/mc/cli/main.py

key-decisions:
  - "ConfigManager, get_access_token, RedHatAPIClient imported inside init_case_data() body to avoid circular imports and keep agent startup fast"
  - "case_number passed as CASE_NUMBER env var to mc agent init-case (not a CLI arg), matching what ContainerManager sets"
  - "Mocking in unit tests patches at original module paths (mc.config.manager.ConfigManager) not mc.agent.case_data.ConfigManager, because lazy imports bypass module-level attribute lookup"

patterns-established:
  - "Lazy imports inside function: import inside function body when module-level import would cause circular dependency"
  - "Non-fatal warning pattern: all SFDC/OCM failures print Warning: prefix and return/continue without raising"
  - "case_dir parameter on init_case_data() defaults to /case but overridable in tests via tmp_path"

# Metrics
duration: 4min
completed: "2026-03-20"
---

# Phase 34 Plan 02: Agent Case Data Init Summary

**init_case_data() writes sfdc-case.json, sfdc-comments.json, case.env (MC_ prefixed), and conditional ocm-cluster.json to /case/ — wired as mc agent init-case CLI subcommand with 19 unit tests**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-20T11:28:31Z
- **Completed:** 2026-03-20T11:32:44Z
- **Tasks:** 2
- **Files modified:** 4 (3 created, 1 modified)

## Accomplishments

- Created `src/mc/agent/case_data.py` with `init_case_data()` — fetches SFDC data, writes 3-4 files to /case/, runs ocm get cluster when cluster ID present
- Wired `mc agent init-case` subcommand in main.py routing to `src/mc/cli/commands/agent.py`
- 19 unit tests covering case.env format, file writing, OCM conditional behavior, and all failure handling paths — 617 total unit tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Create src/mc/agent/case_data.py with init_case_data()** - `42b8ab1` (feat)
2. **Task 2: Wire mc agent init-case CLI command and write unit tests** - `20de4c1` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/mc/agent/case_data.py` - init_case_data() — fetches SFDC case + comments, writes JSON files and case.env, runs ocm get cluster conditionally
- `src/mc/cli/commands/agent.py` - init_case() CLI handler; reads CASE_NUMBER from env
- `src/mc/cli/main.py` - Registered agent subparser with init-case subcommand
- `tests/unit/test_agent_case_data.py` - 19 unit tests for all scenarios

## Decisions Made

- ConfigManager, get_access_token, RedHatAPIClient imported inside `init_case_data()` body (not at module level) to avoid circular imports and keep agent container startup fast
- `case_number` for `mc agent init-case` is read from the `CASE_NUMBER` environment variable (set by ContainerManager), not a CLI positional argument
- Unit test mocking patches at original module paths (`mc.config.manager.ConfigManager`) rather than `mc.agent.case_data.ConfigManager` because lazy imports bypass module-level attribute lookup

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

Initial test run failed because mocks were patching `mc.agent.case_data.ConfigManager` etc., but those names don't exist at module level (they're lazy imports inside the function). Fixed by patching at the original module paths (`mc.config.manager.ConfigManager`, `mc.utils.auth.get_access_token`, `mc.integrations.redhat_api.RedHatAPIClient`). All 19 tests pass after fix.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `mc agent init-case` is ready to be called from the container entrypoint/bashrc before the interactive shell opens
- `MC_CLUSTER_EXTERNAL_ID` is always written to case.env — Phase 35 (backplane auto-login) can source case.env and use this value directly
- All file writes use `case_dir` parameter — testable and overridable without touching real /case/

---
*Phase: 34-case-data-store*
*Completed: 2026-03-20*
