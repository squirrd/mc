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

### Cache Behavior (Activity-Aware)
- **Active terminal**: 5-10 minute TTL while terminal has shell keystroke activity
- **Inactive terminal**: Pause cache updates after 30 minutes of inactivity
- **Background auto-refresh**: Automatically refresh cache during active periods
- **Refresh failure handling**: Notify user immediately if background refresh fails (network error, API down)
- **Cache storage location**: Claude decides between host filesystem (~/.mc/cache) or SQLite state database

### Token Management
- **Distribution approach**: Claude decides optimal method to make tokens available to containers
- **Refresh strategy**: Claude determines proactive vs reactive refresh timing
- **Storage location**: Claude chooses secure storage (host cache, SQLite, env vars)
- **Refresh failure UX**: Graceful degradation - allow cached/offline operations, warn about auth issues

### Case Resolution & Workspace Paths
- **Path structure**: Same as v1.0 - {base_dir}/{account_name}/{case_number}-{summary}
- **Path formatting**: Reuse existing shorten_and_format() function
- **Missing metadata**: Fail with clear error if required fields (account name, summary) are missing
- **Metadata changes**: Container workspace path pinned at creation time (no auto-updates)
- **Workspace creation timing**: Lazy creation - workspace created when first accessed, not during container creation
- **Query operations**: No standalone query commands - metadata only fetched during container operations

### Claude's Discretion
- API client controller/agent split architecture
- Cache storage location (filesystem vs SQLite)
- Token distribution mechanism
- Token refresh timing (proactive vs reactive)
- Activity detection implementation details for cache TTL
- Background refresh notification mechanism

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

None - discussion stayed within phase scope

</deferred>

---

*Phase: 10-salesforce-integration-&-case-resolution*
*Context gathered: 2026-01-26*
