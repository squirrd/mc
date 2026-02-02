---
created: 2026-02-01T21:56
title: Auto-close terminal when shell exits
area: containers
files:
  - src/mc/terminal/attach.py
  - src/mc/terminal/macos.py
  - src/mc/terminal/linux.py
---

## Problem

After running `mc 04363692` to launch a terminal attached to a container, if the user exits the shell inside the terminal (via `exit` or Ctrl+D), the terminal window remains open showing the shell prompt or just a blank screen.

**Expected behavior:**
When the container shell exits, the terminal window should automatically close, providing a clean user experience.

**Current behavior:**
- User runs `mc 04363692`
- Terminal launches and attaches to container
- User types `exit` or presses Ctrl+D
- Shell exits but terminal window stays open
- User must manually close the terminal window

**Benefits of auto-close:**
- Cleaner UX - no orphaned terminal windows
- Consistent with typical terminal behavior (many terminals close on exit by default)
- Reduces manual cleanup for users working with multiple containers

## Solution

Configure terminals to close automatically when the shell command exits. Implementation varies by platform:

**macOS iTerm2:**
```applescript
-- In src/mc/terminal/macos.py iTerm2 launcher
tell application "iTerm"
    create window with default profile
    tell current session of current window
        write text "podman exec -it <container> /bin/bash"
        -- Add custom profile setting or use default behavior
        -- iTerm2: Preferences > Profiles > Session > "When session ends: Close"
    end tell
end tell
```

Note: iTerm2 behavior can be controlled via profile settings. May need to:
1. Create a temporary profile with auto-close enabled
2. Use that profile for MC container sessions
3. Or rely on user's default profile settings

**macOS Terminal.app:**
```applescript
-- In src/mc/terminal/macos.py Terminal.app launcher
tell application "Terminal"
    do script "podman exec -it <container> /bin/bash ; exit"
    -- The '; exit' ensures Terminal closes when command completes
end tell
```

Alternatively, set Terminal preferences programmatically:
```bash
# Set Terminal to close window when shell exits cleanly
defaults write com.apple.Terminal "Shell Exit Action" -int 1
```

**Linux (gnome-terminal, konsole):**
```bash
# gnome-terminal
gnome-terminal -- bash -c "podman exec -it <container> /bin/bash; exit"

# konsole
konsole --hold=never -e bash -c "podman exec -it <container> /bin/bash"
# --hold=never closes window when command exits (exit code 0)
# Default behavior may already do this
```

**Implementation strategy:**

1. **Update terminal launchers** in platform-specific modules:
   - `src/mc/terminal/macos.py` - iTerm2 and Terminal.app
   - `src/mc/terminal/linux.py` - gnome-terminal and konsole

2. **Test exit scenarios:**
   - Normal exit via `exit` command
   - Ctrl+D (EOF)
   - Container stops/crashes
   - Shell crashes (non-zero exit)

3. **Configuration option:**
   Consider adding `auto_close_terminal` config option for users who prefer keeping terminals open:
   ```toml
   [terminal]
   auto_close_on_exit = true  # default: true
   ```

4. **Edge cases:**
   - Distinguish between clean exit (code 0) vs error exit
   - Some users may want terminal to stay open on errors for debugging
   - Consider "close on clean exit only" behavior

**Testing:**
- Launch container with `mc <case>`
- Run `exit` in container shell → terminal should close
- Launch container, run failing command, exit → verify behavior
- Test on macOS (iTerm2, Terminal.app) and Linux (gnome-terminal, konsole)
