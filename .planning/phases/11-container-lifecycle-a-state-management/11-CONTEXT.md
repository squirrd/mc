# Phase 11: Container Lifecycle & State Management - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Orchestrate container creation, listing, stopping, deletion with SQLite-based state tracking and reconciliation. This is the orchestration layer that integrates Podman (Phase 9) with Salesforce case metadata (Phase 10) to provide isolated per-case workspaces.

</domain>

<decisions>
## Implementation Decisions

### Command Interface
- Primary command: `mc 12345678` (bare case number) creates container and attaches terminal (Phase 12)
- Alias `mc 12345678` to either `mc container create 12345678` or `mc create 12345678` (Claude decides which)
- Error handling: Concise by default, `--verbose` flag for full details (stack traces, Podman output)
- Lifecycle commands:
  - `mc container list` - show all case containers with status and metadata
  - `mc container stop <case>` - stop running container gracefully
  - `mc container delete/rm <case>` - delete container (workspace always preserved)

### State Visibility
- List output shows: case number, status (running/stopped), customer name, severity, case owner, created timestamp, uptime
- Format: ASCII table with columns (easy visual scanning)
- Empty state: Friendly message "No containers found. Create one with: mc 12345678"
- No filtering/sorting - keep simple, developers can pipe to grep if needed

### Lifecycle Behavior
- Stopped containers: Auto-restart with notification ("Restarting container for case 12345678...")
- Workspace preservation: `mc container delete` NEVER deletes workspace (container-only operation)
- Container persistence: Containers survive system reboots
- Graceful stop timeout: Claude decides based on typical workloads

### State Reconciliation
- External deletions (podman rm): Periodic sync on every mc command detects and cleans orphaned metadata
- External creations (podman run): Ignore - MC only tracks containers it created
- Sync frequency: Reconcile state at start of each mc operation (no background process)
- State recovery: Claude decides safest approach if SQLite database corrupted/deleted

### Claude's Discretion
- Choose between `mc container create` vs `mc create` as the canonical form
- Determine graceful stop timeout (likely 10 seconds, standard Docker/Podman default)
- Design state recovery strategy (rebuild from Podman vs fresh start)
- SQLite schema design for state tracking
- Container naming convention (label strategy for identifying mc-managed containers)
- Exact table formatting for `mc container list`

</decisions>

<specifics>
## Specific Ideas

- "Auto-restart should feel seamless - developer shouldn't have to think about whether container is stopped"
- Workspace preservation is critical - "I never want to accidentally lose case work"
- Simple command interface - "Just `mc 12345678` and I'm working on the case"

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 11-container-lifecycle-a-state-management*
*Context gathered: 2026-01-26*
