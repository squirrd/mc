---
phase: 06-infrastructure-observability
plan: 02
subsystem: infra
tags: [logging, structured-logging, observability, print-migration]

# Dependency graph
requires:
  - phase: 06-01
    provides: Logging infrastructure with dual-mode formatters and SensitiveDataFilter
provides:
  - Complete migration from print() to structured logging across all operational code
  - Module-level loggers in 8 core modules
  - Appropriate log level assignment for operational visibility
affects: [06-03, all future phases using logging]

# Tech tracking
tech-stack:
  added: []
  patterns: [Lazy % formatting for logging performance, Intentional user output marked with # print OK]

key-files:
  created: []
  modified:
    - src/mc/cli/commands/case.py
    - src/mc/cli/commands/other.py
    - src/mc/integrations/redhat_api.py
    - src/mc/integrations/ldap.py
    - src/mc/controller/workspace.py
    - src/mc/config/wizard.py
    - src/mc/utils/auth.py
    - src/mc/cli/main.py

key-decisions:
  - "Lazy % formatting for performance (avoid f-strings in logging calls)"
  - "Intentional user output preserved with # print OK markers"
  - "Log levels: INFO for operations, DEBUG for details, WARNING/ERROR for issues"
  - "Interactive prompts kept as print() for user experience"

patterns-established:
  - "Pattern: logger.info/debug/warning/error with lazy % formatting for all operational messages"
  - "Pattern: # print OK marker for intentional user output (URLs, LDAP cards, prompts)"
  - "Pattern: Module-level logger creation: logger = logging.getLogger(__name__)"

# Metrics
duration: 6min
completed: 2026-01-22
---

# Phase 06 Plan 02: Print to Logging Migration Summary

**74 print() statements replaced with structured logging using module-level loggers and lazy % formatting**

## Performance

- **Duration:** 6 min
- **Started:** 2026-01-22T07:50:45Z
- **Completed:** 2026-01-22T07:56:45Z
- **Tasks:** 2
- **Files modified:** 8

## Accomplishments
- Migrated 74 print() statements to structured logging across 8 files
- Added module-level loggers to all operational modules
- Assigned appropriate log levels based on message importance
- Preserved intentional user output with # print OK markers
- Installed tqdm and tenacity dependencies for future progress/retry features

## Task Commits

Each task was committed atomically:

1. **Task 1: Migrate print() to logging in all source files** - `f01da25` (refactor)

Task 2 (Install dependencies) required no commit as dependencies were already in pyproject.toml from Plan 06-01.

## Files Created/Modified
- `src/mc/cli/commands/case.py` - Replaced 23 print() statements with logger calls
- `src/mc/cli/commands/other.py` - Added logger, kept URL print for user output
- `src/mc/integrations/redhat_api.py` - Replaced 2 print() statements with logger.info/warning
- `src/mc/integrations/ldap.py` - Added search logging, kept LDAP card output as print
- `src/mc/controller/workspace.py` - Replaced 11 print() statements with appropriate log levels
- `src/mc/config/wizard.py` - Added logger, kept interactive prompts as print
- `src/mc/utils/auth.py` - Enhanced token cache logging with expiry info
- `src/mc/cli/main.py` - Kept pre-logging errors as print, converted post-logging to logger

## Decisions Made

**1. Use lazy % formatting instead of f-strings in logging calls**
- Rationale: Performance optimization - prevents expensive string formatting when log level is disabled
- Based on RESEARCH.md Pitfall 2 - lazy evaluation
- Example: `logger.info("Downloading %s", filename)` not `logger.info(f"Downloading {filename}")`

**2. Preserve intentional user output with # print OK markers**
- Rationale: Not all print() calls are logging - some are intentional CLI output
- Preserved: URLs for copy/paste, LDAP cards, interactive prompts, pre-logging errors
- Marker enables verification grep to exclude legitimate print() statements

**3. Log level assignment based on message importance**
- INFO: Major operations users should know about (downloads, workspace creation)
- DEBUG: Detailed operation info for troubleshooting (API calls, file paths)
- WARNING: Non-fatal issues (large files, missing files)
- ERROR: Fatal issues requiring user action (auth failures, validation errors)

**4. Keep interactive prompts as print() for user experience**
- Rationale: Setup wizard needs direct console output before logging is configured
- Logged final status ("Configuration saved successfully") after user input complete

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - migration proceeded smoothly following established patterns from Plan 06-01.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Plan 3 (Progress bars & retry logic):**
- All operational messages now use structured logging
- tqdm and tenacity dependencies installed and verified
- Module-level loggers established across codebase
- Debug mode (-debug flag) will reveal detailed operation logs

**No blockers or concerns**

---
*Phase: 06-infrastructure-observability*
*Completed: 2026-01-22*
