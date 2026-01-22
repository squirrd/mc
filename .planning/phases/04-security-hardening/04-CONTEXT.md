# Phase 4: Security Hardening - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Implement production-ready security measures for the MC CLI tool. This includes token validation and caching, SSL certificate verification, input validation, and safe handling of large file downloads. Authentication mechanisms and core API functionality already exist - this phase hardens them against common security issues.

</domain>

<decisions>
## Implementation Decisions

### Token validation & caching
- **Expiration checking**: Check with 5-minute buffer before expiration, proactively refresh
- **Storage location**: File-based cache at `~/.mc/token` with proper permissions (0600)
- **Refresh failure handling**: Retry auth flow automatically - attempt to get new token using credentials
- **Manual invalidation**: Not supported - fully automatic token management
- **Token protection**: File permissions only (0600) - no encryption layer
- **Logging**: Log events only (got/refreshed/expired) without token content
- **Multi-user support**: Single user only - one cached token per system
- **Default TTL**: 1 hour if API doesn't provide expiry information

### SSL verification failures
- **Failure handling**: Warn and require explicit flag (`--insecure-host`) to bypass
- **Warning content**: Detailed - include reason for failure (expired, self-signed, wrong host) plus hostname
- **Flag scope**: Per-endpoint - specify which hosts to trust individually for granular control
- **Custom CA bundles**: Support both config file (`~/.mc/config`) and environment variables (REQUESTS_CA_BUNDLE)

### Input validation rules
- **Case number format**: Exact format only - must be exactly 8 digits, reject all other formats
- **Validation failure response**: Error immediately before API call with fast feedback
- **Other input validation**: Claude's discretion - determine what other inputs need validation based on security/UX needs
- **Error message format**: User-friendly with examples - "Case number must be 8 digits. Example: 12345678"

### Large file warnings
- **Size threshold**: Configurable (default 3GB) - allow users to customize via config
- **Warning intrusiveness**: Flag to suppress (default warn) - show warning by default but `--yes` or `--force` skips for scripting
- **Warning information**: Display all of:
  - Filename being downloaded
  - File size in human-readable format
  - Disk space check (verify sufficient space)
  - Estimated download time based on connection speed
- **Automation handling**: Claude's discretion - tool is primarily CLI on host but needs batch mode support for container use

### Claude's Discretion
- Which other inputs beyond case numbers need validation (file paths, attachment IDs, etc.)
- Exact mechanism for detecting batch/automation mode (TTY detection vs env var vs both)
- Implementation details of token refresh retry logic
- Specific error codes and exit statuses for different failure types

</decisions>

<specifics>
## Specific Ideas

- Tool should work both interactively (on host CLI) and in batch mode (container automation)
- Security is important but should not block legitimate use cases - always provide escape hatches with explicit flags
- Token management should be transparent - users shouldn't think about it unless something goes wrong

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 04-security-hardening*
*Context gathered: 2026-01-22*
