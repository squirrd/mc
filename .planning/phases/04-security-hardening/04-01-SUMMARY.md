---
phase: 04-security-hardening
plan: 01
subsystem: auth
tags: [token-caching, input-validation, security, oauth2, regex]

# Dependency graph
requires:
  - phase: 03-code-cleanup
    provides: Config migration with platformdirs and TOML format
provides:
  - Token caching at ~/.mc/token with 0600 permissions
  - Input validation for case numbers before API calls
  - Automated token refresh with 5-minute expiry buffer
affects: [04-02-ssl-verification, 05-logging]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - File-based token cache with atomic write and secure permissions
    - Fail-fast input validation at command entry points
    - OAuth2 token expiration with buffer for mid-request protection

key-files:
  created:
    - src/mc/utils/validation.py
    - tests/unit/test_validation.py
  modified:
    - src/mc/utils/auth.py
    - src/mc/cli/commands/case.py
    - tests/unit/test_auth.py

key-decisions:
  - "File-based token cache over keyring library (simpler, no external dependencies)"
  - "Atomic file write using os.open with O_CREAT flag for secure permissions from creation"
  - "5-minute expiry buffer prevents tokens expiring mid-request"
  - "1-hour default TTL when SSO doesn't provide expires_in"
  - "Validation at command layer (not API client) for fail-fast error handling"
  - "Regex validation for exactly 8 digits (Red Hat case number format)"
  - "Auto-fix test cache cleanup as Rule 1 bug (tests must work with new features)"

patterns-established:
  - "Token cache pattern: load → check expiry → return cached OR fetch → save → return"
  - "Secure file creation: os.open with mode parameter → os.fdopen → verify permissions"
  - "Input validation pattern: try validate → catch ValueError → print error → exit(1)"
  - "Test isolation: autouse fixture clears cache before/after each test"

# Metrics
duration: 3min
completed: 2026-01-22
---

# Phase 04 Plan 01: Security Hardening - Input Validation Summary

**Token caching with 5-minute expiry buffer and case number validation rejecting non-8-digit formats before API calls**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-22T06:37:10Z
- **Completed:** 2026-01-22T06:40:40Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Access tokens cached at ~/.mc/token with 0600 permissions, reducing SSO calls
- Token expiration validation with 5-minute buffer prevents mid-request expirations
- Case number validation rejects invalid formats (not exactly 8 digits) before making any API calls
- Clear error messages with examples guide users to fix input immediately
- Comprehensive test coverage (3 auth tests + 9 validation tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement token caching with expiration validation** - `3755f5d` (feat)
2. **Task 2: Add input validation for case numbers** - `e889b22` (feat)

## Files Created/Modified
- `src/mc/utils/auth.py` - Added token caching with load/save/expiry functions, updated get_access_token()
- `src/mc/utils/validation.py` - New validation module with validate_case_number() function
- `src/mc/cli/commands/case.py` - Added validation to attach(), check(), create(), case_comments() commands
- `tests/unit/test_auth.py` - Added cache cleanup fixture to prevent test interference
- `tests/unit/test_validation.py` - Comprehensive test suite for input validation

## Decisions Made

**Token caching approach:**
- File-based cache at ~/.mc/token instead of keyring library (simpler, no dependencies)
- Atomic file write using `os.open(path, O_CREAT | O_WRONLY | O_TRUNC, 0o600)` prevents permission race condition
- 5-minute expiry buffer (EXPIRY_BUFFER_SECONDS = 300) prevents tokens expiring during API requests
- 1-hour default TTL (DEFAULT_TTL_SECONDS = 3600) handles cases where SSO doesn't provide expires_in
- JSON format for cache structure: {access_token, expires_at, token_type}

**Input validation approach:**
- Validation at command layer (not API client) enables fail-fast before any network calls
- Regex pattern `r'^\d{8}$'` validates exactly 8 digits (Red Hat case number format)
- ValueError with clear message including example: "Case number must be exactly 8 digits. Example: 12345678"
- Separate validation module (mc.utils.validation) follows single responsibility principle

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test cache cleanup required for caching feature**
- **Found during:** Task 1 (Running existing auth tests after adding cache)
- **Issue:** Tests failed because cached tokens from previous tests caused HTTP errors not to be raised (cache hit instead of SSO call)
- **Fix:** Added autouse fixture `clear_token_cache()` that removes ~/.mc/token before and after each test
- **Files modified:** tests/unit/test_auth.py
- **Verification:** All 3 auth tests pass with cache cleanup fixture
- **Committed in:** 3755f5d (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix)
**Impact on plan:** Auto-fix necessary for test correctness with new caching feature. No scope creep.

## Issues Encountered
None - plan executed smoothly

## User Setup Required
None - no external service configuration required.

Token cache is created automatically on first authentication with secure 0600 permissions.

## Next Phase Readiness
- Token caching reduces unnecessary SSO calls, improving performance and reducing API load
- Input validation prevents invalid case numbers from reaching API, improving error messages
- Ready for Phase 04-02 (SSL verification) which will add explicit verify=True to API calls
- Token cache file location (~/.mc/token) is user-specific and works across sessions

**Blockers/Concerns:** None

---
*Phase: 04-security-hardening*
*Completed: 2026-01-22*
