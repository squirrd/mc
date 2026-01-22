# Phase 5: Error Handling & Robustness - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Making the MC CLI fail gracefully with helpful error messages across all operation types. Covers workspace path construction, LDAP parsing, file operations, HTTP error handling, retry logic for transient failures, and exit code strategy. This phase ensures the tool communicates failures clearly and recovers from problems automatically where possible.

</domain>

<decisions>
## Implementation Decisions

### Error message style
- **Detail level:** Balanced approach — user-friendly message + key technical info (error codes, failed endpoint) in same output
- **Actionability:** Always suggest next steps — every error includes "Try: ..." or "Check: ..." guidance when possible
- **Validation errors:** Show both what and why — e.g., "Case number '12345' is invalid: must be exactly 8 digits"
- Error formatting and coloring at Claude's discretion

### Retry behavior
- **Retry scope:** Automatic retries for:
  - Network timeouts (connection, read timeouts)
  - 5xx server errors (transient API issues)
  - Rate limiting (429 responses)
  - Failed downloads (partial/corrupted transfers)
- **Strategy:** Respect Retry-After header when present, fallback to exponential backoff
- **Max attempts:** Configurable via flag or config (allow users to set --max-retries)
- **Visibility:** Debug mode only — silent retries by default, show retry details with --debug flag
- Default max retries: 3 (as specified in roadmap), but configurable

### Exit codes
- **Granularity:** Multiple exit codes for different failure types (useful for scripting)
- **Specific codes for:**
  - Authentication failures (missing token, expired credentials, permission denied)
  - Network/API errors (connection failures, timeouts, API unavailable)
  - Validation errors (invalid input, bad case number, missing args)
  - File operation errors (permission denied, disk full, file not found)
- **Convention:** Claude's discretion — pick most appropriate standard (BSD/Linux vs custom)
- **Documentation:** Document exit codes in README/man page, not in --help output
- **Retry exhaustion:** Claude decides whether to exit with original error code or special retry-exhausted code

### Recovery options
- **Partial downloads:** Claude decides whether to keep/resume or delete/restart based on API reliability
- **Batch operations:** Continue on error — download all files that can succeed, report failures at end
- **Force flag:** Claude decides, but must support batch/non-interactive mode (warnings can't block automated use)
- **Manual recovery:** Always suggest fix — provide immediate actionable guidance like "Try: mc auth login"

### Claude's Discretion
- Error formatting/coloring strategy (adapt to terminal capabilities)
- Exit code numbering convention (standard vs custom)
- Partial file handling (resume vs restart)
- Force flag implementation (must not break batch mode)
- Retry exhaustion exit code behavior

</decisions>

<specifics>
## Specific Ideas

- Batch mode requirement: Tool must be scriptable/automatable — warnings shouldn't block execution
- Error messages should be immediately actionable, not require doc lookup for common issues
- Exit codes serve scripting use cases — different failure types need distinct codes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-error-handling---robustness*
*Context gathered: 2026-01-22*
