# Phase 17: Registry Cleanup & Maintenance - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Self-healing window registry that stays accurate over time by detecting and removing stale entries for manually closed windows. The registry foundation (Phase 15) and macOS window tracking (Phase 16) are already established. This phase ensures the registry doesn't accumulate stale entries as windows are manually closed by users.

</domain>

<decisions>
## Implementation Decisions

### Cleanup Triggers
- No background/periodic cleanup - only explicit triggers (startup, manual commands)
- User-initiated cleanup runs always silently without confirmation, regardless of number of entries found
- Cleanup timing strategy left to Claude's discretion (startup, before operations, or other)
- Command scope (windows only vs full reconciliation) left to Claude's discretion

### Stale Detection Logic
- Check window exists via platform API (AppleScript on macOS, wmctrl on Linux) to verify window ID validity
- Sample oldest entries during cleanup (oldest 20 per run) rather than validating entire registry
- If window existence check fails (API error, permission denied), remove the entry (aggressive cleanup)
- Handle duplicates by validating all instances and keeping only valid window IDs

### Reconciliation Strategy
- Delete stale entries immediately (no soft delete, no archive, no undo)
- No upper limit on registry size - grows indefinitely
- Ignore windows that exist but aren't in registry (don't auto-adopt orphaned windows)
- Run incrementally (best-effort) - delete each stale entry as found rather than transactional all-or-nothing

### User Visibility
- Automatic cleanup (startup, before operations): Show count only if entries removed ("Cleaned up N stale window entries"), silent if nothing cleaned
- Manual `mc container reconcile` command: Show detailed report (what checked, what removed, what kept)
- All cleanup actions logged at INFO level to structured logging system (visible in debug mode)
- On cleanup errors (can't connect to window manager, permissions): Warn and continue rather than blocking workflow

### Claude's Discretion
- Exact cleanup timing strategy (startup vs before-operation vs hybrid)
- Command naming and scope (`mc container reconcile` vs `mc window reconcile` vs unified command)
- Exact sample size for oldest-entry validation (currently suggested 20, but Claude can optimize)
- Error message formatting and warning text
- Detailed report format for manual reconcile command

</decisions>

<specifics>
## Specific Ideas

- Success criteria benchmark: "Registry stays accurate after 1 week of daily use (no accumulation of stale entries)"
- Integration test mentioned: `test_duplicate_terminal_prevention_regression` must pass - validates no duplicates created
- Platform APIs referenced: AppleScript window existence check on macOS, wmctrl on Linux
- Existing success criteria from ROADMAP.md:
  1. System detects and removes stale entries for manually closed windows
  2. Automatic cleanup on startup reconciles registry with actual windows
  3. Manual `mc container reconcile` command cleans orphaned entries
  4. Registry stays accurate after 1 week of daily use

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope. No new capabilities suggested.

</deferred>

---

*Phase: 17-registry-cleanup---maintenance*
*Context gathered: 2026-02-08*
