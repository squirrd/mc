---
phase: 07-performance-optimization
plan: 01
subsystem: cache
tags: [caching, performance, file-cache, ttl]

# Dependency graph
requires:
  - phase: 04-security-hardening
    plan: 01
    provides: File-based token caching pattern with secure permissions
  - phase: 05-error-handling
    provides: Structured error handling in API client
affects: [07-02-connection-pooling, 07-03-batch-optimization]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - File-based case metadata cache with 30-minute TTL
    - Cache age indicators for user transparency
    - Transparent caching wrapper pattern (returns same data structure)

key-files:
  created:
    - src/mc/utils/cache.py
    - tests/unit/test_cache.py
  modified:
    - src/mc/cli/commands/case.py

key-decisions:
  - "File-based cache at ~/.mc/cache/ with 0o700 permissions following token cache pattern"
  - "30-minute TTL (1800 seconds) balances freshness with performance"
  - "Cache age indicator shows '(cached Xm ago)' for user transparency"
  - "Transparent wrapper returns (case_details, account_details, was_cached) tuple"
  - "Corrupted cache auto-deleted and refetched from API (graceful degradation)"
  - "Cache file per case: case_{case_number}.json for fine-grained invalidation"
  - "case_comments() uses cache wrapper but ignores account_details (not needed)"

patterns-established:
  - "Cache wrapper pattern: check cache → validate TTL → return cached OR fetch → cache → return"
  - "User transparency: show cache age when using cached data"
  - "Atomic file write with secure permissions (0o600) for cache files"
  - "Test isolation: tmp_path fixture overrides cache directory for clean tests"

# Metrics
duration: 3min
completed: 2026-01-22
---

# Phase 07 Plan 01: Performance Optimization - Case Metadata Caching Summary

**File-based case metadata caching with 30-minute TTL eliminates redundant API calls across all case commands**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-22T08:34:55Z
- **Completed:** 2026-01-22T08:38:45Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Case metadata (case_details + account_details) cached for 30 minutes at ~/.mc/cache/
- Cache hit indicator "(cached Xm ago)" shows users when cached data is used
- All case commands (attach, check, create, case_comments) transparently use cache
- No redundant API calls within TTL window when same case accessed multiple times
- 11 comprehensive tests verify TTL expiration, cache age calculation, force refresh
- 96% coverage for cache module with all edge cases tested

## Task Commits

Each task was committed atomically:

1. **Task 1: Create cache module with TTL support** - `adf841b` (feat)
2. **Task 2: Update case commands to use cache** - `d367c61` (feat)

## Files Created/Modified

- `src/mc/utils/cache.py` - 155 lines, cache module with TTL validation and atomic file writes
- `tests/unit/test_cache.py` - 246 lines, comprehensive test suite for caching logic
- `src/mc/cli/commands/case.py` - Updated all 4 commands to use get_case_metadata() wrapper

## Decisions Made

**Cache storage approach:**
- File-based cache at ~/.mc/cache/ directory (follows token cache pattern from Phase 4)
- One file per case: case_{case_number}.json for fine-grained cache management
- Cache directory created with 0o700 permissions for security
- Cache files written with 0o600 permissions using atomic os.open() pattern
- JSON structure: `{data: {case_details, account_details}, cached_at: timestamp}`

**Cache TTL approach:**
- 30-minute TTL (1800 seconds) balances data freshness with performance
- TTL validation: current_time >= (cached_at + ttl_seconds)
- Expired cache triggers fresh API fetch and cache update
- force_refresh parameter bypasses cache for manual refresh scenarios

**User transparency:**
- Cache age indicator "(cached Xm ago)" printed when using cached data
- Age calculated in minutes for user-friendly display
- Visible feedback builds trust that cache is working correctly

**Error handling:**
- Missing cache gracefully falls back to API fetch
- Corrupted JSON cache auto-deleted and refetched (no user intervention)
- Cache operations logged at DEBUG level for troubleshooting

**Integration pattern:**
- Transparent wrapper: get_case_metadata() returns same data structure as direct API calls
- Returns tuple: (case_details, account_details, was_cached) for cache hit detection
- case_comments() uses wrapper but ignores account_details (not needed for that command)
- No changes to function signatures or caller logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - execution smooth with no blockers.

## Performance Impact

**Before caching:**
- Every command made 2 API calls (fetch_case_details + fetch_account_details)
- Repeated commands on same case caused redundant API roundtrips

**After caching:**
- First command: 2 API calls + cache write
- Subsequent commands (within 30min): 0 API calls, instant response from cache
- 100% elimination of redundant API calls within TTL window

**Example scenario:**
```bash
mc create 12345678         # 2 API calls, cache saved
mc check 12345678          # 0 API calls (cache hit)
mc attach 12345678         # 0 API calls (cache hit)
# ... 31 minutes later ...
mc create 12345678         # 2 API calls (cache expired, refreshed)
```

## Next Phase Readiness

- Case metadata caching reduces API load for repeated operations on same case
- Cache pattern established can be extended to other API data (attachments list, comments)
- Ready for Phase 07-02 (connection pooling) which will optimize concurrent API requests
- Cache age transparency provides good UX without hiding what's happening
- Test isolation pattern (tmp_path fixture) works well for cache testing

**Blockers/Concerns:** None

---
*Phase: 07-performance-optimization*
*Completed: 2026-01-22*
