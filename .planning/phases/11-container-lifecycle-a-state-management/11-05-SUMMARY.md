---
phase: 11-container-lifecycle-a-state-management
plan: 05
subsystem: container-orchestration
tags: [podman-py, cli, argparse, container-exec]

# Dependency graph
requires:
  - phase: 11-02
    provides: ContainerManager.create() with auto-restart pattern
provides:
  - ContainerManager.exec() method with auto-restart on stopped containers
  - Complete CLI interface (mc container create/list/stop/delete/exec)
  - Quick access pattern (mc <case_number>)
  - Workspace resolution via ConfigManager
affects: [12-terminal-automation, user-workflows]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Auto-restart pattern via _get_or_restart() helper (reusable for attach, logs streaming)"
    - "CLI workspace resolution via ConfigManager (Phase 10 will enhance with Salesforce data)"
    - "Quick access pattern for streamlined UX (mc <case_number>)"

key-files:
  created:
    - src/mc/cli/commands/container.py
    - tests/unit/test_container_manager_exec.py
    - tests/unit/test_cli_container_commands.py
  modified:
    - src/mc/container/manager.py
    - src/mc/cli/main.py

key-decisions:
  - "Auto-restart helper (_get_or_restart) extracted for reusability across operations needing auto-restart (attach, logs streaming, etc.)"
  - "Quick access pattern (mc <case_number>) integrated via sys.argv manipulation before argument parsing"
  - "Workspace resolution uses ConfigManager base_directory (Phase 11 baseline) - Phase 10 will enhance with Salesforce customer data"
  - "CLI commands use _get_manager() helper to avoid duplication across command functions"

patterns-established:
  - "_get_or_restart(case_number) -> Container: Reusable helper for transparent stopped container handling"
  - "CLI commands use argparse.Namespace for argument passing"
  - "Quick access via sys.argv manipulation: Insert 'quick_access' command before parsing"

# Metrics
duration: 8min
completed: 2026-01-26
---

# Phase 11 Plan 05: Container Command Execution & CLI Integration Summary

**exec() with auto-restart, complete CLI commands (create/list/stop/delete/exec), mc <case_number> quick access, and workspace resolution via ConfigManager**

## Performance

- **Duration:** 8 min
- **Started:** 2026-01-26T16:51:03+10:00
- **Completed:** 2026-01-26T16:59:33+10:00
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments

- exec() method executes commands inside containers with auto-restart (CONT-05, CONT-08)
- Complete CLI interface provides mc container create/list/stop/delete/exec commands
- Quick access pattern (mc <case_number>) creates/accesses container with single command
- Auto-restart helper (_get_or_restart) is reusable for future operations (attach, logs streaming)
- 31 comprehensive tests covering exec() and all CLI commands with 100% coverage on CLI module

## Task Commits

Each task was committed atomically:

1. **Task 1 & 2: Implement exec() and CLI commands** - `e075f72` (feat: exec method, CLI commands, main.py integration)
2. **Task 3: Create tests** - `e075f72` (test: 13 exec tests, 18 CLI tests)

Note: Tasks 1 and 2 were implemented and committed together as the code was auto-formatted/linted after writing.

## Files Created/Modified

**Created:**
- `src/mc/cli/commands/container.py` - CLI commands for container operations (create, list, stop, delete, exec, quick_access)
- `tests/unit/test_container_manager_exec.py` - 13 tests for exec() method covering auto-restart, error handling
- `tests/unit/test_cli_container_commands.py` - 18 tests for CLI commands covering all operations

**Modified:**
- `src/mc/container/manager.py` - Added exec() and _get_or_restart() methods
- `src/mc/cli/main.py` - Integrated container subcommands and quick access pattern

## Decisions Made

**Auto-restart helper extraction:**
Extracted _get_or_restart(case_number) as standalone method rather than inlining in exec(). Rationale: This helper will be reused for attach (Phase 12), logs streaming, and any future operation needing transparent stopped container handling. Promotes DRY principle.

**Quick access pattern implementation:**
Implemented quick access (mc <case_number>) via sys.argv manipulation before argument parsing. Alternative was custom parser logic, but argv manipulation is simpler and cleaner. Pattern detects 8-digit case number and inserts 'quick_access' command transparently.

**Workspace resolution strategy (Phase 11 baseline):**
Quick access and create commands resolve workspace paths via ConfigManager (base_directory + case_number). This is the Phase 11 baseline approach. Phase 10 (Salesforce integration) will enhance this by reading customer information from Salesforce and constructing customer-based workspace paths. For now, config-based fallback ensures functionality.

**CLI commands helper pattern:**
Created _get_manager() helper to instantiate ContainerManager with correct dependencies (PodmanClient, StateDatabase from platformdirs location). Avoids code duplication across create, list, stop, delete, exec, quick_access functions.

## Deviations from Plan

None - plan executed exactly as written.

All functionality implemented as specified:
- exec() method with auto-restart
- _get_or_restart() helper
- Complete CLI commands (create, list, stop, delete, exec)
- Quick access pattern (mc <case_number>)
- Workspace resolution via ConfigManager
- Integration with main.py
- Comprehensive tests (31 tests, all passing)

## Issues Encountered

**ContainerMetadata updated_at field:**
Tests initially failed because ContainerMetadata requires updated_at field (added in Phase 11-01). Fixed by adding updated_at=1234567890 to all test metadata instances. This was a straightforward fix aligning tests with the established model.

## Next Phase Readiness

**Phase 12 (Terminal Automation) is ready:**
- All 8 CONT requirements (CONT-01 through CONT-08) now satisfied
- exec() provides foundation for attach workflow
- _get_or_restart() pattern ready for terminal attach operations
- CLI commands provide user-facing interface for Phase 12 attach command

**No blockers or concerns.**

Quick access already prints "To attach a terminal, use 'mc attach {case_number}' (Phase 12)" message, preparing users for next phase capabilities.

---
*Phase: 11-container-lifecycle-a-state-management*
*Completed: 2026-01-26*
