---
phase: 04-security-hardening
plan: 02
subsystem: api
tags: [ssl, https, requests, security, download-safety, disk-space]

# Dependency graph
requires:
  - phase: 02-critical-path-testing
    provides: API client tests with mocked responses
provides:
  - SSL certificate verification for all HTTPS requests
  - Custom CA bundle support via environment variables
  - Large file download safety checks with disk space validation
  - Graceful error handling for download failures
affects: [deployment, operations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SSL verification via verify parameter on all requests calls"
    - "Environment variable CA bundle configuration (REQUESTS_CA_BUNDLE, CURL_CA_BUNDLE)"
    - "HEAD request before streaming downloads to check file size"
    - "Disk space validation with 10% buffer for large downloads"

key-files:
  created:
    - tests/unit/test_redhat_api.py (download safety tests)
  modified:
    - src/mc/integrations/redhat_api.py
    - src/mc/utils/auth.py
    - src/mc/cli/commands/case.py

key-decisions:
  - "SSL verification enabled by default with environment variable override support"
  - "3GB threshold for large file warnings (configurable)"
  - "10% disk space buffer required beyond file size"
  - "RuntimeError used to signal download failures to CLI layer"
  - "Force parameter at API level (CLI flag deferred to future enhancement)"

patterns-established:
  - "get_ca_bundle() helper pattern for environment-based SSL configuration"
  - "Safety check functions return (is_safe, warning_msg) tuples"
  - "HEAD requests before GET for download size validation"

# Metrics
duration: 5min
completed: 2026-01-22
---

# Phase 04 Plan 02: SSL Verification and Download Safety Summary

**All HTTPS requests explicitly verify SSL certificates with CA bundle support, downloads >3GB show warnings with disk space validation**

## Performance

- **Duration:** 5 min (272 seconds)
- **Started:** 2026-01-22T06:37:09Z
- **Completed:** 2026-01-22T06:41:41Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- All requests.get(), requests.post(), and requests.head() calls include explicit SSL verification
- Custom CA bundles configurable via REQUESTS_CA_BUNDLE and CURL_CA_BUNDLE environment variables
- Large file downloads (>3GB) show warnings with file size, free disk space, and estimated download time
- Downloads blocked when insufficient disk space (file size + 10% buffer exceeds available space)
- CLI gracefully handles download failures and continues processing remaining attachments

## Task Commits

Each task was committed atomically:

1. **Task 1: Add explicit SSL verification to all HTTP requests** - `f362228` (feat)
2. **Task 2: Implement large file download safety checks** - `d3c97f5` (feat)
3. **Test fix: Update download test to mock HEAD request** - `d38a908` (fix)

## Files Created/Modified
- `src/mc/integrations/redhat_api.py` - Added get_ca_bundle(), check_download_safety() helpers, SSL verification to all requests, HEAD request for file size check
- `src/mc/utils/auth.py` - Added get_ca_bundle() helper, SSL verification to token endpoint
- `src/mc/cli/commands/case.py` - Added RuntimeError handling in attach() function
- `tests/unit/test_redhat_api.py` - Added three download safety tests, fixed download test to mock HEAD request

## Decisions Made

1. **SSL verification defaults to True with environment variable override**
   - Rationale: Security by default, flexibility for corporate environments with custom CA certificates

2. **3GB threshold for large file warnings**
   - Rationale: Balances user awareness (large downloads can take time) with avoiding alert fatigue on smaller files

3. **10% disk space buffer beyond file size**
   - Rationale: Prevents running out of space mid-download due to filesystem overhead, temp files, or concurrent writes

4. **RuntimeError for download failures instead of SystemExit**
   - Rationale: Allows CLI to handle failures gracefully and continue processing remaining attachments

5. **Force parameter at API level only (no CLI flag yet)**
   - Rationale: Satisfies CONTEXT.md requirement for batch script override capability. CLI flag deferred to avoid scope creep.

6. **HEAD request before streaming download**
   - Rationale: Gets file size without downloading full file, minimal overhead for safety validation

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed existing test to match new download_file behavior**
- **Found during:** Task 2 verification
- **Issue:** test_download_file_success failed because download_file() now makes HEAD request before GET, but test only mocked GET
- **Fix:** Added responses.HEAD mock with content-length header to test
- **Files modified:** tests/unit/test_redhat_api.py
- **Verification:** Test now passes with full download flow (HEAD then GET)
- **Committed in:** d38a908 (separate fix commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Bug fix necessary for test suite to pass. No scope creep.

## Issues Encountered
None - plan executed smoothly with expected test update after implementation.

## User Setup Required
None - no external service configuration required.

SSL verification works automatically with certifi default bundle. Users with corporate CA certificates can set REQUESTS_CA_BUNDLE or CURL_CA_BUNDLE environment variables.

## Next Phase Readiness
- All HTTPS requests secured with SSL verification
- Large file downloads protected by disk space validation
- Ready for remaining security hardening tasks (input validation, error message sanitization)
- Download safety mechanism in place for production use

---
*Phase: 04-security-hardening*
*Completed: 2026-01-22*
