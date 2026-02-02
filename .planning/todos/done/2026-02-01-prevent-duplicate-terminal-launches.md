---
created: 2026-02-01T12:35
title: Prevent duplicate terminal launches and focus existing terminals
area: containers
files:
  - src/mc/terminal/attach.py
  - src/mc/container/manager.py
---

## Problem

Running `mc <case>` (e.g., `mc 04363692`) always launches a new terminal window, even if a terminal is already attached to that container.

This creates duplicate terminals for the same case, which:
- Clutters the user's workspace
- Creates confusion about which terminal is the "active" one
- Wastes resources

Expected behavior:
1. Detect if a terminal is already running for the case
2. Display message: "Terminal already running for case 04363692"
3. Bring the existing terminal to the front (focus it)

## Solution

Track terminal sessions in container state (likely in SQLite database):
- Store terminal PID, window ID, or application-specific identifier when launching
- Check if terminal process is still running before launching new one
- Use platform-specific commands to bring terminal to front:
  - macOS iTerm2: AppleScript to activate specific window
  - macOS Terminal.app: Similar AppleScript approach
  - Linux: wmctrl or xdotool to focus terminal window

Alternative: Use terminal metadata (window title matching case ID) to find and focus existing terminals.
