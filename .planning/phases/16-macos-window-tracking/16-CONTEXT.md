# Phase 16: macOS Window Tracking - Context

**Gathered:** 2026-02-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Duplicate terminal prevention on macOS. When user runs `mc case XXXXX` twice, the system must focus the existing terminal window instead of creating a new one. This phase delivers: window existence validation, reliable window focusing across Spaces, stale entry detection, and clear user feedback when focusing vs creating.

</domain>

<decisions>
## Implementation Decisions

### Window focusing behavior
- **Space switching:** Yes, switch macOS Spaces to bring window to foreground - user wants to see the window immediately
- **Minimized windows:** Un-minimize from Dock and focus - treat same as background window
- **App activation:** Yes, activate terminal application (make it frontmost) - ready to type immediately
- **Focus failure:** Ask user what to do with detailed prompt showing error reason and asking whether to create new terminal

### User feedback messages
- **Focus success message:** Claude's discretion - choose appropriate verbosity
- **Create success message:** Claude's discretion - choose appropriate verbosity
- **Verbose mode:** Claude's discretion - decide whether to add --verbose flag for debugging
- **Error prompt format:** Detailed with context - show error reason: "Window focus failed: [error]. Create new terminal instead? (y/n): "

### Stale window handling
- **Stale entry detection:** Notify then create - show message "Previous window closed, creating new one" then proceed
- **Validation timing:** Always validate first - check window exists before every focus attempt (catches stale entries immediately)
- **Opportunistic cleanup:** Yes, cleanup related entries - when finding one stale entry, scan and clean other potentially stale entries
- **Race condition handling:** Retry validation once - if focus fails after validation, re-validate once then create new window

### Terminal app priorities
- **Default preference:** iTerm2 preferred - use iTerm2 when available, fall back to Terminal.app
- **Per-case tracking:** Yes, track per case - store which terminal app created each window, always focus the right app's window
- **App unavailable:** Ask user what to do - prompt: "Previous window was in iTerm2 (not installed). Create in Terminal.app instead? (y/n)"
- **Override flag:** No override needed - preference and per-case tracking is sufficient

### Claude's Discretion
- Exact message verbosity and formatting for success cases
- Whether to implement --verbose flag for debugging
- Window validation AppleScript implementation details
- Error message formatting specifics

</decisions>

<specifics>
## Specific Ideas

No specific requirements - open to standard macOS window management approaches using AppleScript.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 16-macos-window-tracking*
*Context gathered: 2026-02-07*
