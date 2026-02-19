# Phase 28: Version Check Infrastructure - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Non-blocking GitHub API integration that checks for MC CLI updates. System checks GitHub releases API, respects hourly throttle, caches version data with timestamps, uses PEP 440 version comparison, and handles network failures gracefully. Users are informed about available updates but installation happens separately (v2.0.5).

</domain>

<decisions>
## Implementation Decisions

### Check timing & triggers
- Auto-check at command startup (non-blocking, async execution)
- System-wide hourly throttle: no check if less than 1 hour since last check
- Non-blocking execution: command runs immediately, version check happens in background
- Weekly release cadence means updates are not urgent

### User notifications
- Single-line message to stderr when update available
- Message format: "mc v2.0.6 available. Update: uvx --reinstall mc-cli@latest"
- Show once per day maximum (not every command run)
- Track last notification timestamp separately from last check timestamp

### Failure handling
- Silent failure for network/API errors (no user-facing warnings)
- Log all failures to mc log file with error details and timestamp
- Rate limit (403) extends throttle window to 24 hours instead of 1 hour
- Manual override command: `mc version --update` bypasses throttle and forces immediate check

### Cache strategy
- Store latest_version + timestamp in TOML config file ([version] section)
- Cache location: ~/.config/mc/config.toml (centralized with existing config)
- Hourly throttle only - no separate max-age expiry
- Auto-detect version changes: if current version != cached current version, invalidate cache and re-check

### Claude's Discretion
- GitHub API endpoint selection (releases API vs tags API)
- Exact async implementation (threading vs asyncio)
- PEP 440 version comparison library usage (packaging library recommended)
- ETag conditional request implementation (optional optimization)
- Structured logging format for version check events

</decisions>

<specifics>
## Specific Ideas

- Phase 28 focuses on **checking** for updates only - auto-update installation is v2.0.5 scope
- Updates come out weekly, not urgent for users to get immediately
- Manual command flag is `--update` not `--check` or `--force`
- Last notification timestamp must be separate from last check timestamp to support "once per day" display logic

</specifics>

<deferred>
## Deferred Ideas

- Auto-update with user notification - v2.0.5 MC Auto-Update milestone
- Download orchestration and installation safety - v2.0.5
- Rollback mechanisms - v2.0.5
- Container version checking - v2.0.6 Container Management milestone

</deferred>

---

*Phase: 28-version-check-infrastructure*
*Context gathered: 2026-02-19*
