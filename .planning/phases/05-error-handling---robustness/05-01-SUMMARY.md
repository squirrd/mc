---
phase: 05-error-handling---robustness
plan: 01
subsystem: error-handling
tags: [exceptions, logging, exit-codes, error-formatting, cli]

# Dependency graph
requires:
  - phase: 04-security-hardening
    provides: Token caching and SSL verification infrastructure
provides:
  - Custom exception hierarchy with exit codes (MCError, AuthenticationError, APIError, ValidationError, WorkspaceError, FileOperationError)
  - Error formatting and display utilities (format_error_message, handle_cli_error)
  - Global error handling wrapper in main() with logging configuration
  - Debug mode support with full tracebacks
affects: [06-infrastructure-observability, future API integration, workspace operations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Custom exception hierarchy with exit codes following sysexits.h
    - Centralized error handling via handle_cli_error()
    - Errors to stderr with actionable suggestions
    - Debug mode controlled via --debug flag

key-files:
  created:
    - src/mc/exceptions.py
    - src/mc/utils/errors.py
  modified:
    - src/mc/cli/main.py

key-decisions:
  - "Exit codes follow sysexits.h: 65=auth, 69=API, 2=validation, 73=workspace, 74=file I/O"
  - "HTTPAPIError.from_response() maps status codes to actionable suggestions"
  - "Logging to stderr at DEBUG/WARNING levels based on --debug flag"
  - "KeyboardInterrupt returns exit code 130 (standard SIGINT)"

patterns-established:
  - "Exception pattern: MCError base class with exit_code and suggestion attributes"
  - "Error display pattern: format_error_message() + print to stderr"
  - "CLI error handling: try/except in main() routing to handle_cli_error()"
  - "Debug mode pattern: --debug flag enables full tracebacks and DEBUG logging"

# Metrics
duration: 3min
completed: 2026-01-22
---

# Phase 5 Plan 1: Global Error Handling Summary

**Exception hierarchy with sysexits.h exit codes, stderr error formatting with suggestions, and debug mode support**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-22T07:08:57Z
- **Completed:** 2026-01-22T07:12:07Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- Custom exception hierarchy with 6+ domain-specific exceptions (auth, API, validation, workspace, file operations)
- HTTPAPIError.from_response() classmethod mapping HTTP status codes to user-friendly messages with actionable suggestions
- Error formatting utilities outputting to stderr with suggestions
- Global error handling wrapper in main() with try/except for MCError, KeyboardInterrupt, and generic exceptions
- Logging configured to stderr with DEBUG/WARNING levels based on --debug flag

## Task Commits

Each task was committed atomically:

1. **Task 1: Create custom exception hierarchy** - `7fe182a` (feat)
2. **Task 2: Create error formatting utilities** - `35d38f8` (feat)
3. **Task 3: Integrate error handling in main entry point** - `88f3033` (feat)

## Files Created/Modified

### Created
- `src/mc/exceptions.py` - Custom exception hierarchy with MCError base class and domain-specific exceptions (AuthenticationError, APIError, HTTPAPIError, APITimeoutError, APIConnectionError, ValidationError, WorkspaceError, FileOperationError)
- `src/mc/utils/errors.py` - Error formatting (format_error_message) and CLI error handling (handle_cli_error) utilities

### Modified
- `src/mc/cli/main.py` - Added error handling imports, logging configuration, --debug flag, try/except wrapper around main() logic, and sys.exit(main()) for proper exit codes

## Decisions Made

**Exit code strategy:**
- Followed Unix sysexits.h conventions for specific error types
- 65 (EX_DATAERR) for authentication failures
- 69 (EX_UNAVAILABLE) for API unavailability
- 2 for command line validation errors
- 73 (EX_CANTCREAT) for workspace creation failures
- 74 (EX_IOERR) for file operation failures
- 130 for KeyboardInterrupt (standard SIGINT)
- Rationale: Enables scripting to distinguish error types and implement appropriate retry/recovery logic

**HTTPAPIError status mapping:**
- Implemented classmethod from_response() to map common HTTP status codes to actionable suggestions
- 401 → "Try: mc auth login"
- 403 → "Check: Your account has case access permissions"
- 404 → "Check: Case number is correct"
- 429/500/503 → "Try: Wait/retry in a few minutes"
- Rationale: Provides immediate guidance without requiring users to look up documentation

**Logging configuration:**
- Configured at start of main() before any operations
- DEBUG level when --debug flag present, WARNING otherwise
- All logs to stderr (not stdout)
- Rationale: Separates data output from logs, enables verbose debugging when needed

**Error handling architecture:**
- Centralized in handle_cli_error() rather than scattered throughout code
- MCError caught specifically, generic Exception caught as fallback
- Debug mode shows full traceback, normal mode shows simple error message
- Rationale: Consistent error display, easy to enhance error handling in one place

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all imports, verifications, and commits succeeded on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**What's ready:**
- Exception hierarchy ready for use in API client, workspace manager, auth, and LDAP operations
- Error formatting infrastructure ready for all CLI error output
- Debug mode infrastructure ready for troubleshooting
- Exit code strategy defined for scripting/automation use cases

**Next steps:**
- Future phases can now raise domain-specific exceptions (AuthenticationError, APIError, ValidationError, etc.) instead of generic exceptions
- API client should be updated to use HTTPAPIError.from_response() for HTTP errors
- Workspace operations should raise WorkspaceError with suggestions
- File operations should raise FileOperationError with actionable guidance

**No blockers:** Foundation complete for robust error handling across all CLI operations.

---
*Phase: 05-error-handling---robustness*
*Completed: 2026-01-22*
