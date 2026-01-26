# Phase 10: Salesforce Integration & Case Resolution - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Query Red Hat Support Case API for case metadata (customer name, case summary, severity, status) and resolve case numbers to workspace paths for container mounting. This phase adapts the existing v1.0 API integration (mc/integrations/redhat_api.py, mc/utils/cache.py) to work in the v2.0 containerized architecture where containers need access to case data.

</domain>

<decisions>
## Implementation Decisions

### Existing Code Reuse
- **Reuse v1.0 Red Hat API client**: Existing mc/integrations/redhat_api.py handles API calls, error handling, retries
- **Reuse workspace path logic**: Existing WorkspaceManager and shorten_and_format() for path construction
- **Claude's discretion**: Determine optimal controller/agent split for API integration

### Cache Behavior (Fixed TTL)
- **TTL**: Fixed 5-minute cache TTL for case metadata
- **Background auto-refresh**: Automatically refresh cache every 4 minutes (before TTL expires)
- **Refresh failure handling**: Log errors but continue worker (don't block other cache refreshes)
- **Cache storage location**: SQLite database with WAL mode for concurrent access (~/.mc/cache/case_metadata.db)

### Token Management
- **Distribution approach**: Mount host config directory into containers read-only
- **Refresh strategy**: Proactive refresh 5 minutes before 2-hour token expiry
- **Storage location**: Host config file (~/.mc/config.toml) with secure permissions (0600)
- **Container access**: Read-only mount of config file, tokens refreshed by host process

### Case Resolution & Workspace Paths
- **Path structure**: Same as v1.0 - {base_dir}/{account_name}/{case_number}-{summary}
- **Path formatting**: Reuse existing shorten_and_format() function
- **Missing metadata**: Fail with clear error if required fields (account name, summary) are missing
- **Metadata changes**: Container workspace path pinned at creation time (no auto-updates)
- **Workspace creation timing**: Lazy creation - workspace created when first accessed, not during container creation
- **Query operations**: No standalone query commands - metadata only fetched during container operations

</decisions>

<specifics>
## Specific Ideas

- **Existing implementation reviewed**: mc/integrations/redhat_api.py already handles 404, rate limiting (429), timeouts, connection errors with proper retry logic and exponential backoff
- **Cache system in place**: mc/utils/cache.py provides 30-minute TTL caching with atomic writes and secure permissions (mode 0600)
- **Error handling patterns**: HTTPAPIError, APITimeoutError, APIConnectionError exceptions already defined and used consistently
- **Workspace structure**: {base_dir}/{account_name_formatted}/{case_number}-{summary_formatted} proven in v1.0

</specifics>

<deferred>
## Deferred Ideas

- **Activity-aware cache TTL**: Defer to future enhancement - start with fixed 5-minute TTL, add activity detection later if needed
- **Background refresh failure notifications**: Defer to future enhancement - start with error logging, add notifications later if needed
- **Cache corruption auto-recovery**: Defer to future enhancement - start with fail-fast on corruption, add recovery later if needed

</deferred>

---

*Phase: 10-salesforce-integration-&-case-resolution*
*Context gathered: 2026-01-26*
*Updated: 2026-01-26 (revised to fixed TTL approach)*
