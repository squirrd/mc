# Phase 36: OCM Token Background Monitor - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a host-side daemon thread that monitors OCM refresh token expiry every 30 minutes and notifies the user + triggers re-login when expiry is within 60 minutes. Runs on host only (not inside containers). Scheduled token rotation and agent-mode monitoring are out of scope.

</domain>

<decisions>
## Implementation Decisions

### Warning message format
- Single-line Rich colored output (not a panel/box) — consistent with mc's lightweight notification style
- Content: time remaining + action taken, e.g. `⚠ OCM token expires in 45 min — re-logging in...`
- Warning appears at startup only — printed before the mc command runs, never mid-command
- stdout vs stderr: Claude's discretion (keep stdout clean for scripts if possible)

### Re-login behavior
- `ocm login` output is streamed/visible to the user — not suppressed
- If re-login fails: print a brief failure warning so the user knows to re-login manually
- If re-login succeeds: stay quiet — no confirmation message
- Retry policy: attempt once only, no retry on failure

### Token-not-found message
- Printed every mc invocation when `ocm.json` is absent (not suppressed after first occurrence)
- Content: location + action hint — `ℹ OCM config not found at ~/.config/ocm/ocm.json — run 'ocm login' to set up`
- Same visual style as the warning (single-line Rich colored line)
- Printed at startup, before command output

### Monitor deduplication
- Deduplicate across processes using a PID lock file
- Lock file location: `~/mc/state/ocm-monitor.pid`
- If lock file exists and PID is alive: skip starting another monitor
- If lock file is stale (PID is dead): auto-clean the lock file and start a new monitor

### Claude's Discretion
- Whether warning/info messages go to stdout or stderr
- Exact Rich color/style (yellow for warning, blue/cyan for info is reasonable)
- Internal thread naming and daemon thread setup details
- Lock file write/read implementation details

</decisions>

<specifics>
## Specific Ideas

- Lock file under `~/mc/state/` (not `/tmp`) — consistent with existing state directory (containers.db lives there)
- The warning line mirrors the existing update notification banner pattern but as a single line, not a panel

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 36-ocm-token-monitor*
*Context gathered: 2026-03-20*
