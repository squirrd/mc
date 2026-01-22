---
phase: 05-error-handling---robustness
plan: 02
subsystem: api
tags: [http-retry, urllib3, error-handling, resilience, requests]

# Dependency graph
requires:
  - phase: 05-01
    provides: Exception hierarchy and error formatting
provides:
  - HTTP retry logic with urllib3.Retry for transient failures
  - Timeout configuration on all HTTP requests
  - Comprehensive exception handling for API and auth operations
  - Batch download resilience with failure tracking
affects: [06-infrastructure-observability, future-api-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [requests-session-with-retry, context-manager-for-cleanup, batch-error-tracking]

key-files:
  created: []
  modified:
    - src/mc/integrations/redhat_api.py
    - src/mc/utils/auth.py
    - src/mc/cli/commands/case.py

key-decisions:
  - "3 retries default with configurable max_retries parameter"
  - "Retry on 429, 500, 502, 503, 504 status codes with exponential backoff"
  - "Timeout (3.05s connect, 27s read) prevents indefinite hangs"
  - "Respect Retry-After header when present"
  - "Batch downloads continue on error, report failures at end"
  - "Session cleanup via context manager support"
  - "Debug logging for all HTTP operations"

patterns-established:
  - "Session with retry: Create requests.Session with urllib3.Retry mounted on HTTPAdapter"
  - "Timeout tuple: (connect_timeout, read_timeout) pattern for all requests"
  - "Exception mapping: requests exceptions → custom MCError hierarchy"
  - "Batch resilience: Continue processing on individual failures, aggregate errors"

# Metrics
duration: 5min
completed: 2026-01-22
---

# Phase 05 Plan 02: HTTP Retry & Error Handling Summary

**HTTP client with automatic retry on transient failures, timeout protection, and resilient batch downloads**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-22T07:14:48Z
- **Completed:** 2026-01-22T07:19:21Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- RedHatAPIClient uses requests.Session with urllib3.Retry for automatic retry on transient failures
- All HTTP requests have timeout=(3.05, 27) to prevent hanging indefinitely
- Comprehensive exception handling maps HTTP errors to actionable user messages
- Batch file downloads continue on individual failures and report summary

## Task Commits

Each task was committed atomically:

1. **Task 1: Add retry logic to RedHatAPIClient** - `8ac3eac` (feat)
2. **Task 2: Add retry and error handling to auth module** - `b92fd76` (feat)
3. **Task 3: Update command layer to handle API exceptions** - `ba1b2a0` (feat)

**Plan metadata:** (pending final commit)

## Files Created/Modified
- `src/mc/integrations/redhat_api.py` - Session-based HTTP client with retry strategy, timeout parameters, and exception handling for all API methods
- `src/mc/utils/auth.py` - SSO authentication with retry logic, timeout, and mapped exceptions for auth failures
- `src/mc/cli/commands/case.py` - Command-level exception handling with batch download resilience and failure tracking

## Decisions Made

**Retry configuration:**
- 3 retries default (configurable via max_retries parameter)
- Retry on status codes 429, 500, 502, 503, 504
- Exponential backoff with 0.3 factor
- Respect Retry-After header when present

**Timeout strategy:**
- (3.05, 27) tuple: 3.05s connect timeout, 27s read timeout
- Applied to all HTTP requests (API calls and SSO authentication)
- Prevents indefinite hangs on network issues

**Batch download resilience:**
- Continue downloading remaining files if one fails
- Track statistics: downloaded, skipped, failed
- Print summary at end
- Raise APIError if any failures occurred (for scripting)

**Exception mapping:**
- requests.HTTPError → HTTPAPIError.from_response()
- requests.Timeout → APITimeoutError
- requests.ConnectionError → APIConnectionError
- requests.RequestException → APIError (catch-all)

**Context manager support:**
- Added __enter__/__exit__ to RedHatAPIClient
- Ensures session.close() cleanup

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly.

## Next Phase Readiness

HTTP client is now resilient to transient failures and provides actionable error messages. Ready for:
- Infrastructure/observability enhancements (logging, metrics)
- Additional API integration work
- Production deployment scenarios

**Blockers:** None

**Concerns:** None

---
*Phase: 05-error-handling---robustness*
*Completed: 2026-01-22*
