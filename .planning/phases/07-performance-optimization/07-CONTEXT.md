# Phase 7: Performance Optimization - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Making the CLI fast and efficient for typical workflows through parallel attachment downloads, intelligent caching with TTL, and smart resource management. Focus on reducing wait times and avoiding redundant API calls while maintaining data freshness.

</domain>

<decisions>
## Implementation Decisions

### Parallel download behavior
- 8 concurrent downloads by default (aggressive for speed)
- No user configurability - keep it simple, always 8 concurrent
- If one download fails, auto-retry that file while continuing with others (most resilient)
- Add `--serial` flag to disable parallelism for debugging purposes

### Cache strategy and invalidation
- Access tokens: Cache until expiration (based on token expiration time, not arbitrary TTL)
- Case metadata: Cache for 30 minutes with TTL
- Show subtle timestamp indicator when using cached data: "(cached 12m ago)" next to case number
- No caching for LDAP lookups (only tokens and case metadata)

### Progress and feedback
- Show per-file progress bars with file names for all active downloads
- Use rich library for dynamic updating - bars update in-place, clean terminal UI showing all active downloads in a table
- Support `--quiet` flag to suppress all progress (errors only)
- Auto-detect `--json` output mode and suppress progress (conflicts with JSON parsing)
- When download fails: Mark as failed in red (e.g., "[FAILED] file.tar.xz - Network error"), continue other downloads
- Show summary at end listing all failures

### Failure and retry handling
- Retry failed downloads up to 5 times with exponential backoff (resilient for flaky networks)
- Resume partial downloads using HTTP range requests (efficient for large files)
- On user abort (Ctrl+C): Delete partial files for clean state
- Auto-retry these error types:
  - Network timeouts/resets (transient issues)
  - HTTP 5xx server errors (API having issues)
  - HTTP 429 rate limiting (respect rate limits with longer backoff)
- Fail immediately without retry:
  - HTTP 404 not found (file doesn't exist)
  - HTTP 401/403 auth errors (no point retrying)

### Claude's Discretion
- Exact exponential backoff timing (e.g., 1s, 2s, 4s, 8s, 16s)
- Progress bar update frequency to balance smoothness vs CPU usage
- Cache file location and format (filesystem-based, JSON/pickle/etc.)
- Exact rich library layout and styling for progress display
- HTTP range request chunk size for partial downloads

</decisions>

<specifics>
## Specific Ideas

- Progress display should use rich library's table-based dynamic updating (not simple print statements)
- Error summary at the end should clearly list what failed and why
- Cache indicator should be subtle and unobtrusive - "(cached 12m ago)" format
- Retry logic should be invisible to user unless it ultimately fails

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 07-performance-optimization*
*Context gathered: 2026-01-22*
