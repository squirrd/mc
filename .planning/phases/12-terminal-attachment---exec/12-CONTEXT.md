# Phase 12: Terminal Attachment & Exec - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Auto-open terminal windows to containerized workspaces when developers access a case. When a developer runs `mc case 12345678` (or shorthand `mc 12345678`), a new terminal window launches and attaches to that case's container, providing immediate access to the isolated workspace. Scope includes terminal detection, window management, shell initialization, and graceful error handling across macOS and Linux platforms.

</domain>

<decisions>
## Implementation Decisions

### Terminal Launcher Behavior
- Original shell returns to prompt immediately after launching terminal (non-blocking)
- New terminal window auto-focuses (brings to front)
- Window title format: `12345678 - CustomerName - Concatenated Description`
- Terminal window closes immediately when user exits container shell
- Terminal window uses default size/geometry (not configurable)

### Re-attachment Handling
- If case container already has attached terminal, show error: "Terminal already attached to case 12345678"
- No support for multiple terminals to same container
- Error message is brief (just the error, no additional help text)

### Shell Welcome Banner
- Display on container entry:
  - Case Description
  - Case Long Description
  - Case Summary
  - Case Next Steps
- All metadata from Salesforce (case description, long description, summary, next steps, comments)
- Comments stored as metadata but NOT displayed in banner
- No help hints or tips (just case metadata)

### Shell Configuration
- Custom MC bashrc injected into container
- Shell prompt prefixed with `[MC-12345678]` to indicate containerized environment
- Helper commands/aliases at Claude's discretion (choose style based on avoiding conflicts)

### Platform Detection & Fallbacks

**macOS terminals supported:**
- iTerm2
- Terminal.app

**Linux terminals supported:**
- gnome-terminal
- Claude chooses additional defaults for RHEL and Fedora desktops

**Detection priority:**
1. User config preference (per-platform configuration)
2. Auto-detection fallback

**Fallback behavior:**
- If preferred terminal unavailable: warn user, then try next available terminal
- First-use validation: test terminal launch on first use to verify it works
- If NO supported terminals found: error with install instructions

### Command Invocation Patterns

**Primary commands:**
- `mc case <number>` — full form
- `mc <number>` — shorthand alias

**Automation/scripting:**
- Claude's discretion on whether to suppress terminal launch for non-TTY environments

**Auto-creation:**
- If container doesn't exist: auto-create then attach (seamless)
- Show brief message during creation: "Creating container..." (no spinner)

**Auto-start:**
- If container stopped: always auto-start transparently when accessed

**Case number format:**
- Require full 8-digit case numbers (no partial matching)

**Offline handling:**
- If Salesforce API unavailable during creation: error and block creation (don't create without metadata)

**No features:**
- No dry-run mode
- No shell tab completion for case numbers
- No inline exec mode (always launch terminal)

### Error Handling & User Feedback

**Terminal launch failures:**
- Brief error with fix hint (e.g., "Terminal launch failed. Run: mc --check-terminal")

**Podman failures:**
- Show both raw Podman error AND MC's interpretation/suggestion

**Already-attached error:**
- Just show error message ("Terminal already attached to case 12345678")
- No additional help about finding window or forcing new terminal

**Error logging:**
- Always log errors to MC log file for debugging
- Persistent logging regardless of debug flags

### Claude's Discretion
- Helper command/alias naming style (choose to avoid conflicts)
- Whether to test terminal launch capability (validation approach)
- Automation handling (suppressing terminal launch for non-TTY environments)
- Additional Linux terminal emulators for RHEL/Fedora desktops

</decisions>

<specifics>
## Specific Ideas

- Window title must include full case metadata: `12345678 - CustomerName - Concatenated Description`
- Welcome banner should feel informative but not cluttered — just the essential case context
- Shell prompt `[MC-12345678]` makes it obvious you're in a container
- "Brief with fix hint" error style keeps output concise but actionable

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-terminal-attachment---exec*
*Context gathered: 2026-01-26*
