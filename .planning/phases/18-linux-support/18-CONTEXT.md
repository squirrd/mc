# Phase 18: Linux Support - Context

**Gathered:** 2026-02-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Cross-platform window tracking with graceful fallback for Linux X11 systems. Extends Phase 16's macOS window tracking to Linux environments, handling X11/Wayland detection, terminal compatibility (gnome-terminal, konsole), and wmctrl/xdotool integration. Wayland support is explicitly out of scope.

</domain>

<decisions>
## Implementation Decisions

### Platform Detection Strategy
- Detect X11 vs Wayland using `$DISPLAY` and `$WAYLAND_DISPLAY` environment variables
- When wmctrl or xdotool missing on X11: **Fail with error message** (strict approach — forces tool installation before proceeding)
- Detection happens **once at startup**, cached for session (assumes environment doesn't change during execution)
- Claude's discretion: Choose between wmctrl or xdotool based on reliability research (user said "you decide")

### Fallback Behavior
- When running on Wayland: Claude decides appropriate balance of user awareness and functionality
- If wmctrl fails to focus existing window: **Clean stale entry from registry and create new terminal** (self-healing approach)
- **Always try focusing on each operation** — no caching of "focusing unavailable" state (handles edge cases like mid-session tool installation)
- When fallback creates new terminal: **Always track in registry** (consistent tracking regardless of whether focusing worked)

### Terminal Compatibility Scope
- **Official support: gnome-terminal and konsole only** (focused approach — test thoroughly against these two)
- When unsupported terminal detected (xterm, alacritty, etc.): **Fail with error listing supported terminals** (strict — forces user to switch)
- **Validate supported terminal installed on startup** using `which gnome-terminal` (proactive — fail fast with clear error)
- When both konsole and gnome-terminal installed: **Detect desktop environment via `$XDG_CURRENT_DESKTOP`, prefer native terminal** (konsole on KDE, gnome-terminal on GNOME)

### User Feedback & Documentation
- Success message format: **"Focused existing terminal for case XXXXX"** (simple, states what happened)
- Error message for missing wmctrl: **Full installation instructions with distro detection** ("Install: sudo apt install wmctrl (Debian/Ubuntu) or sudo dnf install wmctrl (Fedora/RHEL)")
- **No 'mc doctor' diagnostic command** — rely on runtime errors to guide user (simpler, less maintenance)
- Claude's discretion: Documentation structure for X11 limitation (user said "you decide")

### Claude's Discretion
- Choice between wmctrl vs xdotool when both available (research which is more reliable)
- Wayland fallback behavior (warning vs silent vs error)
- Documentation structure for presenting X11 limitation clearly

</decisions>

<specifics>
## Specific Ideas

- Detection should use standard Linux environment variables (`$DISPLAY`, `$WAYLAND_DISPLAY`, `$XDG_CURRENT_DESKTOP`)
- Error messages should be immediately actionable — include exact install commands with distro detection
- Strict validation philosophy: fail fast with clear errors rather than silent fallbacks that create confusion

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-linux-support*
*Context gathered: 2026-02-07*
