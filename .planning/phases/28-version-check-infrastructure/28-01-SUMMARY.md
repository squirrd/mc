---
phase: 28-version-check-infrastructure
plan: 01
subsystem: infra
tags: [version-check, github-api, etag, pep440, packaging, tenacity, daemon-thread]

# Dependency graph
requires:
  - phase: 26-config-extensions
    provides: ConfigManager with atomic writes and version config methods
  - phase: 01-foundation
    provides: TOML config format and ConfigManager infrastructure
provides:
  - VersionChecker class with background checking via daemon threads
  - GitHub API integration with ETag caching and retry logic
  - PEP 440 version comparison infrastructure
  - Once-per-day notification display to stderr
affects: [29-auto-update, cli-startup-integration]

# Tech tracking
tech-stack:
  added: [packaging>=26.0]
  patterns: [daemon-thread-with-atexit, etag-conditional-requests, pep440-version-comparison]

key-files:
  created: [src/mc/version_check.py]
  modified: [pyproject.toml]

key-decisions:
  - "Use daemon threads with atexit cleanup (not asyncio) to match existing CacheManager pattern"
  - "Store ETag, latest_known, latest_known_at, last_status_code in [version] section for conditional requests and offline resilience"
  - "Retry with tenacity for transient failures, fail fast on 4xx errors"
  - "Once-per-day notification throttle separate from hourly check throttle"

patterns-established:
  - "Pattern: Daemon thread lifecycle with atexit cleanup registration and threading.Event stop signal"
  - "Pattern: ETag conditional requests with If-None-Match header and 304 handling"
  - "Pattern: PEP 440 version comparison with InvalidVersion error handling"
  - "Pattern: ConfigManager.save_atomic() for thread-safe config updates from background threads"

# Metrics
duration: 3min
completed: 2026-02-19
---

# Phase 28 Plan 01: Version Check Infrastructure Summary

**Background version checking with GitHub Releases API using daemon threads, ETag caching, PEP 440 comparison, and hourly throttling**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-19T08:59:48Z
- **Completed:** 2026-02-19T09:02:46Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- VersionChecker class with daemon thread lifecycle and graceful atexit cleanup
- GitHub API integration with ETag conditional requests to preserve rate limits
- Retry logic with exponential backoff for transient network failures
- PEP 440 version comparison using packaging library
- Once-per-day notification display to stderr with throttling

## Task Commits

Each task was committed atomically:

1. **Task 1: Create VersionChecker class with daemon thread lifecycle** - `c7412e5` (feat)
2. **Task 2: Implement GitHub API integration with ETag and retry logic** - `ff6e27e` (feat)
3. **Task 3: Implement PEP 440 version comparison and notification display** - `390bac6` (feat)

## Files Created/Modified
- `src/mc/version_check.py` - VersionChecker class with background checking, GitHub API integration, ETag caching, version comparison, and notification display
- `pyproject.toml` - Added packaging>=26.0 dependency for PEP 440 version comparison

## Decisions Made

**Threading approach:** Used daemon threads with atexit cleanup (not asyncio) to match existing CacheManager pattern in src/mc/controller/cache_manager.py. This provides consistent threading semantics across the codebase and simplifies lifecycle management.

**ETag caching strategy:** Store ETag from GitHub API responses in config [version] section and send If-None-Match header in subsequent requests. This handles 304 Not Modified responses to preserve GitHub API rate limit quota (5000 requests/hour).

**Retry configuration:** Use tenacity decorator with exponential backoff (multiplier=1, min=1s, max=10s) and 3 attempts for transient network failures (timeout, connection errors). Fail fast on 4xx errors without retry to avoid wasting rate limit on permanent failures.

**Throttle separation:** Separate hourly check throttle (3600s) from daily notification throttle (86400s). This allows system to check frequently for updates but only notify users once per day. Store last_check and last_notification as separate timestamp fields in config.

**Offline resilience:** Store latest_known_at timestamp when version data is fetched (RESEARCH.md VCHK-06 requirement). This enables displaying cached update notifications even when offline, as long as version comparison shows newer version is available.

**Rate limit handling:** Extend check throttle to 24 hours (86400s) when last_status_code == 403 to avoid hammering GitHub API when rate limited. Store last_status_code in config for next check cycle.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all implementations followed established patterns from RESEARCH.md and existing MC codebase.

## User Setup Required

None - no external service configuration required. Version checking uses public GitHub API without authentication.

## Next Phase Readiness

Version check infrastructure complete and ready for:
- **CLI startup integration:** Call check_for_updates() from main CLI entry point for automatic background checks
- **Manual override command:** `mc version --update` command to bypass throttle and force immediate check (v2.0.5 scope)
- **Auto-update functionality:** VersionChecker can detect newer versions; installation logic is v2.0.5 MC Auto-Update milestone

**No blockers.** Infrastructure handles all version checking requirements:
- Non-blocking execution via daemon threads
- Hourly throttle with 24-hour extension on rate limits
- ETag caching for efficient API usage
- PEP 440 version comparison for pre-releases and complex versions
- Once-per-day notifications with stderr display
- Silent failure with structured logging for network/API errors
- Offline resilience with cached version data timestamps

---
*Phase: 28-version-check-infrastructure*
*Completed: 2026-02-19*
