# Phase 6: Infrastructure & Observability - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace all print() statements with structured logging, add debug mode (--debug flag), implement automatic retry logic for transient failures, and add progress indicators for long-running operations (especially large file downloads). Goal is to make operations observable and recoverable.

</domain>

<decisions>
## Implementation Decisions

### Logging structure and content
- **Format:** Configurable - default to human-readable text for terminal use, --json-logs flag for structured JSON output (automation/CI)
- **Log fields:** Timestamp (ISO 8601), log level (INFO/WARNING/ERROR), module/function name
- **Sensitive data:** Redact all passwords completely. For other sensitive data (tokens), show last 4 chars if >20 chars (e.g., "token ending in ...7a3f"), otherwise redact completely
- **INFO level content:** Claude's discretion - balance between showing major operations and avoiding noise

### Debug mode behavior
- **Scope:** --debug reveals HTTP request/response details, performance timings, and full stack traces on errors
- **HTTP verbosity:** Summary with body preview (first 500 chars) - balances detail with readability
- **Presentation:** Mixed with normal logs at DEBUG level
- **File output:** Only write to file if --debug-file flag specified (keeps filesystem clean by default)

### Progress indicators
- **Visual style:** Progress bar with percentage
  - Format: `Downloading sosreport.tar.gz [████████░░] 80% (2.4GB/3GB) 15s remaining`
- **Information displayed:**
  - Current/total size (2.4GB/3GB)
  - Percentage complete (80%)
  - Time remaining/ETA (15s remaining)
  - Transfer speed (25 MB/s)
- **Multiple files:** Separate progress bars per file, stacked vertically
- **Update frequency:** Every 100ms for smooth, responsive updates

### Retry and recovery
- **Strategy:** Exponential backoff - retry 3 times with increasing delays (1s, 2s, 4s)
- **Retry scope:** Automatic retry for:
  - Network/HTTP errors (timeouts, 503 Service Unavailable)
  - API rate limits (429 Too Many Requests)
- **No retry for:** File I/O errors, authentication failures (fail fast with clear messages)
- **Resume downloads:** Yes, use HTTP Range requests to resume interrupted downloads from where they left off
- **Retry notification:** Claude's discretion - choose appropriate notification based on operation visibility

### Claude's Discretion
- What gets logged at INFO level (major operations vs all operations)
- How to notify users about retries in progress (verbose logging vs progress bar integration vs silent)
- Implementation details of resume logic and partial file validation

</decisions>

<specifics>
## Specific Ideas

- Logging should work well in both terminal (human-readable) and CI/automation (JSON structured)
- Debug mode is for troubleshooting issues - full context without requiring code changes
- Progress bars should feel responsive (100ms updates) and show all relevant information
- Retry logic should handle transient failures gracefully without user intervention

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-infrastructure-observability*
*Context gathered: 2026-01-22*
