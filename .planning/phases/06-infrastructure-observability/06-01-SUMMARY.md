---
phase: 06-infrastructure-observability
plan: 01
subsystem: infra
tags: [logging, stdlib, json, filters, observability]

# Dependency graph
requires:
  - phase: 05-error-handling
    provides: Exception hierarchy, error handling patterns, exit codes
provides:
  - Logging infrastructure with dual-mode (text/JSON) formatters
  - SensitiveDataFilter for automatic credential redaction
  - CLI flags for debug mode and JSON output
  - Dependencies for future progress bars and retry logic
affects: [06-02, 06-03, all future phases needing logging]

# Tech tracking
tech-stack:
  added: [tqdm>=4.66.0, tenacity>=8.3.0]
  patterns: [Module-level logging with stdlib, SensitiveDataFilter for security, dual-mode formatters]

key-files:
  created:
    - src/mc/utils/logging.py
  modified:
    - src/mc/cli/main.py
    - pyproject.toml

key-decisions:
  - "stdlib logging module sufficient (no structlog dependency)"
  - "Dual-mode formatters: human-readable text default, JSON via --json-logs flag"
  - "SensitiveDataFilter redacts passwords, Bearer tokens, api_keys before output"
  - "Debug mode enables DEBUG level with optional file output via --debug-file"
  - "Logging setup called after argument parsing but before command routing"

patterns-established:
  - "Pattern: logging.getLogger('mc') as package root logger with propagate=False"
  - "Pattern: Custom logging.Filter subclass for sensitive data redaction"
  - "Pattern: Custom logging.Formatter subclass for JSON structured output"
  - "Pattern: setup_logging() called early in main() after parse_args()"

# Metrics
duration: 2min
completed: 2026-01-22
---

# Phase 06 Plan 01: Structured Logging Infrastructure Summary

**Dual-mode logging (text/JSON) with automatic credential redaction using stdlib logging module**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-22T07:46:01Z
- **Completed:** 2026-01-22T07:48:21Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Created logging infrastructure module with JSONFormatter and SensitiveDataFilter
- Added CLI flags for debug mode (--debug), JSON output (--json-logs), and file logging (--debug-file)
- Configured logging to execute before command routing but after argument parsing
- Added tqdm and tenacity dependencies for future plans (progress bars and retry logic)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create logging infrastructure module** - `b39ddad` (feat)
2. **Task 2: Add logging CLI flags and configuration** - `5703c6b` (feat)
3. **Task 3: Add logging dependencies** - `84e3339` (chore)

## Files Created/Modified
- `src/mc/utils/logging.py` - Logging configuration with JSONFormatter, SensitiveDataFilter, and setup_logging()
- `src/mc/cli/main.py` - Added --debug, --json-logs, --debug-file flags; integrated setup_logging() call
- `pyproject.toml` - Added tqdm>=4.66.0 and tenacity>=8.3.0 dependencies

## Decisions Made

**1. Use stdlib logging module instead of structlog**
- Rationale: Python's stdlib logging is sufficient for CLI needs; no need for extra dependency
- Based on RESEARCH.md findings: stdlib handles JSON formatting, filters, handlers natively
- Future enhancement: Can add structlog later if context binding becomes necessary

**2. Dual-mode formatter selection (text vs JSON)**
- Rationale: Human debugging needs readable text; CI/automation needs structured JSON
- Implementation: --json-logs flag switches formatter on same logger
- Follows RESEARCH.md Pattern 1

**3. Sensitive data filter on all handlers**
- Rationale: Prevents credential leakage in any output mode (text, JSON, file)
- Implementation: Custom logging.Filter that redacts via regex before formatting
- Patterns: password fields, Bearer tokens, api_key fields
- Follows RESEARCH.md Pattern 2

**4. Logging configuration after parse_args() but before command routing**
- Rationale: Prevents logger hierarchy issues (RESEARCH.md Pitfall 1)
- Critical ordering: parse → setup_logging → check env vars → execute commands
- Ensures all downstream code inherits configured logging

**5. Add dependencies for future plans in this commit**
- Rationale: Single dependency update prevents multiple pip install cycles
- tqdm for Plan 3 (progress bars), tenacity for Plan 3 (retry logic)
- Alphabetical ordering maintained

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly following RESEARCH.md patterns.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Plan 2 (Replace print() statements):**
- Logging infrastructure operational and tested
- CLI flags functional (--debug, --json-logs, --debug-file)
- SensitiveDataFilter verified to redact passwords/tokens
- Module-level logger pattern established for migration

**Dependencies staged for Plan 3 (Progress & retry):**
- tqdm>=4.66.0 ready for progress bar implementation
- tenacity>=8.3.0 ready for retry logic implementation

**No blockers or concerns**

---
*Phase: 06-infrastructure-observability*
*Completed: 2026-01-22*
