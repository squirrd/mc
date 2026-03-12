# Phase 32: Update Notifications - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Display a non-intrusive update-available banner at CLI startup when a newer MC version exists. Banner is suppressed after first display each calendar day and shows a modified message when a version pin is active. The banner check never blocks CLI execution beyond a 1-2s timeout. Version pinning commands and the update mechanism itself are Phase 31/30 scope.

</domain>

<decisions>
## Implementation Decisions

### Banner content & style
- Rich Panel (bordered box) — not a single line
- Title: "MC Update Available" (branded)
- Content: current version -> latest version (e.g. `v2.0.4 -> v2.0.5`)
- Upgrade command in banner: `mc-update upgrade` (NOT `uv tool upgrade mc`)
- Color scheme: yellow/amber
- Blank line above and below the panel to visually separate from command output
- No release notes hint or URL

### Suppression behavior
- Calendar day (midnight local time) reset — not rolling 24h window
- Only interactive TTY invocations count as "shown" — piped/non-interactive runs do not trigger suppression
- Suppression state stored in `config.toml [version]` section (consistent with ETag/pin data)
- Stored value: ISO timestamp of last display (date derived from it for calendar-day comparison)
- No force-show bypass flag needed
- On network failure: show a Rich styled warning (yellow/amber, consistent with banner style), write suppression timestamp anyway (retry next calendar day)
- No special reset on successful upgrade — normal check logic handles it (no newer version = no banner)

### Banner placement & targeting
- Banner appears BEFORE command output
- Shown on every subcommand invocation (any `mc` command)
- Exception: `mc --version` suppresses the banner (must remain clean/parseable)
- Fresh data required (not cached) — wait up to 1-2s for check result before running command
- Timeout behavior: if check doesn't complete within 1-2s, print a brief "Update check timed out" note on stderr and run the command
- Timeout duration: hardcoded (not configurable)

### Pin interaction
- When pinned AND newer version exists: show a modified banner (same once-per-day suppression rules apply)
- Modified banner content: `v2.0.5 available (pinned at v2.0.4)` + `Run: mc-update unpin to upgrade`
- When pinned and no newer version: check runs in background, no output
- Pin does NOT fully suppress — it changes the banner message

### Claude's Discretion
- Exact Rich Panel dimensions and border style
- How the 1-2s blocking wait is implemented (threading.Event, future, etc.)
- Exact wording of the timeout note and network failure warning
- Where in `cli/main.py` the check is hooked in

</decisions>

<specifics>
## Specific Ideas

- The banner upgrade command must use `mc-update upgrade` — the Phase 30 helper — not raw `uv tool upgrade mc`
- The pin banner must explicitly tell the user HOW to unpin: `mc-update unpin`
- The timeout note should be brief, on stderr — not alarming, just transparent

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 32-update-notifications*
*Context gathered: 2026-03-12*
