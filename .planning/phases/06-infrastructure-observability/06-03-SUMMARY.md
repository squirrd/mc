---
phase: 06-infrastructure-observability
plan: 03
subsystem: infra
tags: [tqdm, tenacity, progress-bars, retry-logic, observability, downloads]

# Dependency graph
requires:
  - phase: 06-01
    provides: Logging infrastructure and configuration
  - phase: 06-02
    provides: Print to logging migration across codebase
  - phase: 05-02
    provides: HTTP retry strategy with urllib3.Retry
provides:
  - Progress bars with tqdm for file downloads showing percentage, size, speed, ETA
  - Automatic retry logic with tenacity and exponential backoff for transient failures
  - Resumable downloads using HTTP Range headers for interrupted transfers
  - Sequential download orchestration in attach command
affects: [07-performance-optimization, future-download-features]

# Tech tracking
tech-stack:
  added: [tqdm>=4.66.0, tenacity>=8.3.0]
  patterns: [decorator-based-retry, progress-bar-integration, resumable-downloads, fail-fast-auth-errors]

key-files:
  created: []
  modified:
    - src/mc/integrations/redhat_api.py
    - src/mc/cli/commands/case.py

key-decisions:
  - "tenacity retry decorator with exponential backoff (1s, 2s, 4s max) for network errors and transient API failures"
  - "tqdm progress bars with 100ms update interval and binary byte scaling (1024-based)"
  - "HTTP Range header support for resumable downloads from partial file position"
  - "401/403 authentication errors fail fast without retry, 429/503 trigger retry"
  - "Retry attempts logged at WARNING level via before_sleep_log"
  - "Progress bars show initial position when resuming interrupted downloads"
  - "Sequential downloads (one at a time) to keep terminal output clean"

patterns-established:
  - "Pattern: @retry decorator on download methods with selective exception retry"
  - "Pattern: Progress bar context manager with tqdm for streaming operations"
  - "Pattern: Resume logic checking file existence and size before download"
  - "Pattern: Status code-based retry decisions (fail fast vs retry with backoff)"

# Metrics
duration: 2min
completed: 2026-01-22
---

# Phase 06 Plan 03: Download Progress & Retry Summary

**File downloads now show real-time progress bars with speed and ETA, automatically retry on transient failures with exponential backoff, and resume interrupted downloads from last byte position**

## Performance

- **Duration:** 2 min
- **Started:** 2026-01-22T07:59:33Z
- **Completed:** 2026-01-22T08:01:58Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Progress bars integrated into download_file() showing filename, percentage, transfer speed, and ETA
- Automatic retry with exponential backoff (1s, 2s, 4s) for network timeouts, connection errors, and transient API failures
- Resumable downloads using HTTP Range headers to continue from last downloaded byte
- Authentication failures (401, 403) fail fast without retry; rate limits (429) and service errors (503) trigger retry
- Attach command updated for clean integration with sequential download progress bars

## Task Commits

Each task was committed atomically:

1. **Task 1: Add progress bars and retry logic to downloads** - `9173645` (feat)
2. **Task 2: Update attachment download command for progress visibility** - `4411946` (feat)

## Files Created/Modified
- `src/mc/integrations/redhat_api.py` - Enhanced download_file() with tqdm progress bar, tenacity retry decorator, HTTP Range header resume logic
- `src/mc/cli/commands/case.py` - Updated attach() command to log batch start and integrate cleanly with progress bars

## Decisions Made

1. **tenacity for retry logic over custom implementation**
   - Rationale: Declarative API with exponential backoff, selective exception filtering, and before_sleep logging hooks

2. **tqdm for progress bars over rich.progress**
   - Rationale: Minimal dependency (no heavy terminal library), 60ns overhead, automatic byte scaling

3. **Exponential backoff with 1s min, 4s max**
   - Rationale: Follows RESEARCH.md recommendation, prevents thundering herd, reasonable user wait time

4. **Fail fast on 401/403, retry on 429/503**
   - Rationale: Auth errors are permanent and won't resolve with retry; rate limits and service errors are transient

5. **Resume logic trusts partial file without checksum validation**
   - Rationale: HTTP GET is idempotent, corruption rare, simpler implementation (can add checksums later if needed)

6. **100ms progress bar update interval (mininterval=0.1)**
   - Rationale: Balance between responsive UI and terminal rendering overhead per RESEARCH.md guidance

7. **Sequential downloads (not parallel yet)**
   - Rationale: Cleaner terminal output with stacked progress bars, parallel downloads deferred to Phase 7 performance optimization

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation followed RESEARCH.md patterns directly. tqdm and tenacity worked as expected with no integration issues.

## User Setup Required

None - no external service configuration required. tqdm and tenacity dependencies already in pyproject.toml.

## Next Phase Readiness

**Ready for Phase 7 (Performance Optimization):**
- Progress bars provide visibility into download performance
- Retry logic makes downloads resilient to transient failures
- Resume support prevents re-downloading large files from scratch
- Sequential download architecture can be extended to parallel downloads with tqdm's multi-bar support

**No blockers or concerns.**

---
*Phase: 06-infrastructure-observability*
*Completed: 2026-01-22*
