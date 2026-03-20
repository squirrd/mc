---
phase: 35-backplane-auto-login
plan: 03
subsystem: cli
tags: [backplane, ocm, agent, terminal, argparse, exec-command]

# Dependency graph
requires:
  - phase: 35-02
    provides: run_backplane_login() in mc.agent.backplane_login — the core login logic called by this CLI layer
  - phase: 34-03
    provides: build_exec_command() and mc agent init-case in the exec chain — this plan extends that chain

provides:
  - backplane_login(args) function in src/mc/cli/commands/agent.py
  - backplane-login subparser registered in main.py under mc agent subparsers
  - Updated exec command sequence: init-case || true; backplane-login || true; exec bash
  - Updated test assertions in test_terminal_attach.py to match new exec format

affects:
  - Any future plan modifying build_exec_command() or the exec chain
  - Any plan adding more mc agent subcommands (follow the lazy-import-per-elif pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy per-elif import: each agent subcommand import lives inside its elif block (not at module top or in a shared import)"
    - "Non-fatal exec chain: every agent command in /bin/bash -c uses || true so interactive shell always opens"

key-files:
  created: []
  modified:
    - src/mc/cli/commands/agent.py
    - src/mc/cli/main.py
    - src/mc/terminal/attach.py
    - tests/unit/test_terminal_attach.py

key-decisions:
  - "backplane_login(args) uses lazy import of run_backplane_login inside function body — matches init_case() pattern, avoids import-time side effects"
  - "init-case routing split to per-command import style (from single shared import) so backplane-login follows the same pattern consistently"
  - "|| true applied to backplane-login in exec chain — matches init-case treatment; interactive shell guaranteed even if login fails"

patterns-established:
  - "agent subcommand registration: add_parser in agent_subparsers + elif in agent routing block + lazy import per elif"

# Metrics
duration: 4min
completed: 2026-03-20
---

# Phase 35 Plan 03: CLI Wiring — backplane-login Summary

**mc agent backplane-login subcommand wired into CLI and inserted into terminal exec chain as third step: init-case || true; backplane-login || true; exec bash**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-20T11:57:22Z
- **Completed:** 2026-03-20T12:00:55Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- backplane_login(args) added to agent.py with lazy import of run_backplane_login and CASE_NUMBER guard
- backplane-login subparser registered in main.py; routing added as elif block with per-command lazy import
- build_exec_command() updated — exec chain now: `mc agent init-case || true; mc agent backplane-login || true; exec bash`
- test_terminal_attach.py assertions updated to match new exec command format; all 27 terminal attach tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add backplane_login() to agent.py and register in main.py** - `ea2aae0` (feat)
2. **Task 2: Update build_exec_command() in attach.py and fix test assertions** - `a932274` (feat)

**Plan metadata:** (pending docs commit)

## Files Created/Modified

- `src/mc/cli/commands/agent.py` - Added backplane_login(args) function; added logger import
- `src/mc/cli/main.py` - Registered backplane-login subparser; added routing elif with lazy import; split init-case to per-command import style
- `src/mc/terminal/attach.py` - Updated build_exec_command() exec chain to include backplane-login || true; updated docstring
- `tests/unit/test_terminal_attach.py` - Updated 2 assertions to match new exec command format

## Decisions Made

- **backplane_login() lazy import pattern:** Import of `run_backplane_login` placed inside function body, matching the established `init_case()` pattern. Avoids import-time side effects (no backplane_login module executed unless command is invoked).
- **Per-command import in routing block:** The existing `from mc.cli.commands.agent import init_case` was split so each elif gets its own import. Enables the pattern to be consistent and extensible for future agent subcommands.
- **|| true in exec chain:** backplane-login gets the same non-fatal treatment as init-case. The interactive bash shell must always open regardless of login outcome.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

- Two pre-existing test failures in `test_container_manager_create.py` and `test_container_manager_mounts.py` confirmed to be pre-existing (failed before any changes in this plan). Not introduced by this plan.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 35 (backplane-auto-login) is now complete: StateDatabase schema (35-01), run_backplane_login() logic (35-02), and CLI wiring + exec chain (35-03) all done.
- The full end-to-end flow is operational: when `mc case <N>` opens a terminal, it runs init-case then backplane-login automatically before handing control to the user's bash shell.
- No blockers for next phase.

---
*Phase: 35-backplane-auto-login*
*Completed: 2026-03-20*
