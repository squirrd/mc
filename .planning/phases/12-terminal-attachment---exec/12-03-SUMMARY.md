---
phase: 12-terminal-attachment---exec
plan: 03
subsystem: terminal
tags: [terminal-attachment, podman-exec, tty-detection, salesforce-integration, container-orchestration]

# Dependency graph
requires:
  - phase: 11-container-lifecycle-a-state-management
    provides: ContainerManager with create/status/lifecycle operations
  - phase: 10-salesforce-integration-a-case-resolution
    provides: SalesforceAPIClient for case metadata
  - phase: 12-01
    provides: Terminal launcher abstraction for macOS and Linux
  - phase: 12-02
    provides: Custom bashrc and banner generation
provides:
  - Terminal attachment orchestration combining lifecycle + launcher + shell
  - CLI commands (mc case <number> and mc <number> shorthand)
  - TTY detection for preventing pipe/script breakage
  - Auto-create and auto-start workflow for containers
affects: [13-container-image, future-terminal-features]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TTY detection via sys.stdout.isatty() prevents terminal launch in non-interactive contexts"
    - "Complete workflow orchestration: validate → fetch metadata → auto-create/start → generate bashrc → launch terminal"
    - "Non-blocking terminal launch returns control to host prompt immediately"

key-files:
  created:
    - src/mc/terminal/attach.py
    - tests/unit/test_terminal_attach.py
    - tests/integration/test_case_terminal.py
  modified:
    - src/mc/cli/commands/case.py
    - src/mc/cli/commands/container.py
    - src/mc/cli/main.py
    - src/mc/utils/cache.py

key-decisions:
  - "TTY detection mandatory: Prevents terminal launch when stdout piped/redirected (protects scripting use cases)"
  - "Case number validation: Enforce 8-digit format at attachment layer for early failure detection"
  - "Metadata fallbacks: account_name defaults to 'Unknown', description uses subject if case_summary missing"
  - "Error messages brief with fix hints: 'Terminal launch failed. Run: mc --check-terminal' per CONTEXT.md"
  - "CLI routing via import inside main.py: Avoids circular dependency with container commands module"

patterns-established:
  - "Workflow orchestration pattern: Single entry point (attach_terminal) coordinates multiple subsystems"
  - "Helper function extraction: build_exec_command() and build_window_title() testable independently"
  - "Non-blocking terminal launch: launcher.launch() returns immediately, terminal runs in background"

# Metrics
duration: 3min
completed: 2026-01-27
---

# Phase 12 Plan 03: Container Terminal Attachment Summary

**Complete terminal attachment workflow with TTY detection, auto-create/auto-start orchestration, and CLI integration for mc case <number> command**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-27T00:25:07Z
- **Completed:** 2026-01-27T00:28:30Z
- **Tasks:** 3 (1 checkpoint + 1 testing task executed after approval)
- **Files modified:** 7

## Accomplishments

- Terminal attachment orchestration integrating container lifecycle, shell customization, and terminal launching
- CLI commands `mc case <number>` and `mc <number>` shorthand for seamless terminal access
- TTY detection prevents terminal launch in piped/scripted contexts (preserves automation use cases)
- Comprehensive test coverage: 90% for attach module with 20 unit tests + 1 integration test
- Auto-create and auto-start workflow provides transparent container lifecycle management

## Task Commits

Each task was committed atomically:

1. **Tasks 1-2: Terminal attachment orchestration & CLI integration** - `f34c796` (feat)
2. **Task 3: Create unit and integration tests** - `0436610` (test)

**Plan metadata:** (pending - final commit)

## Files Created/Modified

- `src/mc/terminal/attach.py` - Terminal attachment orchestration with TTY detection, auto-create/start, bashrc generation
- `src/mc/cli/commands/container.py` - case_terminal() and quick_access() CLI command functions
- `src/mc/cli/main.py` - CLI argument parsing for case command and shorthand routing
- `src/mc/utils/cache.py` - Cache utilities used for metadata retrieval
- `tests/unit/test_terminal_attach.py` - 20 unit tests covering TTY detection, workflow, error handling (90% coverage)
- `tests/integration/test_case_terminal.py` - End-to-end integration test with real Podman and Salesforce
- `src/mc/cli/commands/case.py` - Existing case commands (not modified in this plan, context reference)

## Decisions Made

**TTY detection mandatory:**
- Use `sys.stdout.isatty()` to check for interactive terminal
- Raise error immediately if not TTY: prevents terminal launch breaking pipes/scripts
- Critical for preserving automation use cases (e.g., `mc case 12345678 | grep foo` must fail gracefully)

**Case number validation at attachment layer:**
- Validate 8-digit format in `attach_terminal()` before Salesforce call
- Early failure prevents wasted API calls and provides clear error message
- Complements existing validation in CLI layer

**Metadata fallbacks for robustness:**
- `account_name` defaults to "Unknown" if missing from Salesforce response
- `description` uses `subject` field if `case_summary` missing
- Ensures terminal can launch even with incomplete metadata

**Error messages brief with fix hints:**
- "Terminal launch failed. Run: mc --check-terminal" (includes remediation)
- "Failed to fetch case metadata. Check network and credentials." (actionable guidance)
- Per CONTEXT.md requirement: brief messages with fix hints

**CLI routing avoids circular imports:**
- `case_terminal()` imported inside `main.py` command routing
- Prevents circular dependency: main → container → attach → manager → client
- Lazy import pattern maintains clean module structure

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all components integrated cleanly with existing Phase 11 and Phase 12 implementations.

## Next Phase Readiness

**Phase 13 (Container Image & Deployment) ready to proceed:**

- Terminal attachment workflow complete and tested
- Container lifecycle operations fully integrated
- CLI commands provide user-facing interface
- Auto-create and auto-start patterns established for container management

**Integration points for Phase 13:**
- Container image will include mc CLI agent mode
- Terminal attachment will launch into RHEL 10 container environment
- Bashrc customization ready for container shell experience

**No blockers or concerns.**

---
*Phase: 12-terminal-attachment---exec*
*Completed: 2026-01-27*
