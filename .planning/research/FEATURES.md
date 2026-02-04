# Feature Research: Window Tracking Systems

**Domain:** Terminal window tracking and session deduplication
**Researched:** 2026-02-04
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Window ID registry | Core capability - cannot track windows without ID storage | MEDIUM | SQLite-based persistence. tmux/screen model: track sessions by unique identifier |
| Lookup by case number | Primary use case - find window for a specific case | LOW | Registry key: case_number → window_id mapping |
| Create if not exists | Standard pattern - create new window only when needed | LOW | tmux: `has-session` check before create. kubectl: context auto-creation |
| Focus existing window | Core deduplication behavior - activate instead of create | MEDIUM | Platform-specific APIs (AppleScript for macOS, wmctrl for Linux) |
| Stale entry cleanup | Registry hygiene - remove entries for closed windows | MEDIUM | docker-compose: `--remove-orphans`. tmux-resurrect: periodic validation |
| Persist across restarts | Users expect registry to survive process restarts | LOW | File-based or database storage (already using SQLite) |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Automatic cleanup on startup | No manual intervention needed for stale entries | LOW | Validation check on startup: query all IDs, remove non-existent |
| Manual reconciliation command | Power users can fix registry corruption | LOW | `mc container reconcile` rebuilds registry from actual windows |
| Grace period before cleanup | Avoid premature deletion of temporarily hidden windows | MEDIUM | docker-compose model: only clean after threshold (e.g., 24h) |
| Cross-desktop/space tracking | macOS: track which Space window is on for better focus | HIGH | Requires Mission Control integration. Future enhancement |
| Window metadata storage | Store creation time, last access time for debugging | LOW | Extended registry schema: timestamps, platform info |
| Audit log of operations | Track create/focus/cleanup events for troubleshooting | LOW | Append-only log table alongside registry |
| Health check command | `mc window status` shows registry state and inconsistencies | LOW | Diagnostic tool: list windows, show orphans, validate IDs |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Title-based search as primary | Familiar pattern from tmux/screen | iTerm2 overwrites session name on command execution; fragile across terminals | Use ID-based lookup with title as fallback for migration |
| Pre-execution window search | Seems like it would prevent duplicates | Race conditions, timing-dependent, fails if command runs quickly | Store ID at creation time, not search before execution |
| Real-time window monitoring | "Know immediately when window closes" | Polling overhead, complexity, battery drain on macOS | Lazy cleanup on next access + periodic batch cleanup |
| Shared registry across users | Multi-user machines might share cases | File permissions complexity, concurrent access issues, security | Per-user registry (existing pattern with ~/mc/state) |
| Window content/state restoration | tmux-resurrect model: save pane contents | Very complex, fragile across terminal types, limited value for container exec sessions | Just restore window with new exec session |
| Automatic window creation | "Just create window when I run the command" | Violates explicit user intent; surprises users | Require explicit `mc case XXXXX` command |

## Feature Dependencies

```
[Window ID Capture]
    └──requires──> [Platform-specific Terminal API]
                       └──requires──> [AppleScript/wmctrl/etc]

[Focus Existing Window] ──requires──> [Window ID Registry Lookup]
                                          └──requires──> [SQLite Storage]

[Stale Entry Cleanup] ──enhances──> [Window ID Registry]
                          └──requires──> [Window Existence Check API]

[Manual Reconciliation] ──repairs──> [Window ID Registry]

[Grace Period Cleanup] ──conflicts──> [Immediate Cleanup]
    (Choose one cleanup strategy, not both)

[Audit Log] ──enhances──> [Window ID Registry]
    (Optional, independent feature)
```

### Dependency Notes

- **Window ID Capture requires Platform API:** Cannot store IDs without terminal-specific method to retrieve them (iTerm2: AppleScript `id of window`, Linux: `wmctrl -l`)
- **Focus requires Registry Lookup:** Cannot focus without knowing which window ID to target
- **Cleanup requires Existence Check:** Must query terminal to verify window still exists before removing registry entry
- **Grace Period conflicts with Immediate Cleanup:** Mutually exclusive strategies - either clean immediately on detection or wait for grace period

## MVP Definition

### Launch With (v2.0.2)

Minimum viable product — what's needed to validate the concept.

- [ ] **Window ID Registry** — Core storage mechanism (SQLite table in existing state DB)
- [ ] **Capture window ID on creation** — Store ID when terminal window launches
- [ ] **Lookup by case number** — Registry query: `SELECT window_id FROM registry WHERE case_number = ?`
- [ ] **Focus existing window if found** — Use ID-based focus instead of title search
- [ ] **Create new window if not found** — Fallback to creation when registry lookup fails
- [ ] **Basic stale entry cleanup** — Remove entries for non-existent windows on startup

### Add After Validation (v2.1.x)

Features to add once core is working.

- [ ] **Manual reconciliation command** — Trigger: Users report registry corruption (add `mc window reconcile`)
- [ ] **Health check command** — Trigger: Support requests about window state (add `mc window status`)
- [ ] **Window metadata timestamps** — Trigger: Need to debug "when was this window created?" questions
- [ ] **Grace period for cleanup** — Trigger: Users complain about windows being forgotten too quickly

### Future Consideration (v2.2+)

Features to defer until product-market fit is established.

- [ ] **Audit log** — Why defer: Adds complexity, low immediate value, storage overhead
- [ ] **Cross-desktop tracking (macOS Spaces)** — Why defer: High complexity, requires Mission Control APIs, limited demand
- [ ] **Window content restoration** — Why defer: Very complex, fragile, unclear value proposition

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Window ID registry | HIGH | MEDIUM | P1 |
| Capture ID on creation | HIGH | LOW | P1 |
| Lookup by case number | HIGH | LOW | P1 |
| Focus existing window | HIGH | MEDIUM | P1 |
| Basic cleanup on startup | HIGH | LOW | P1 |
| Manual reconciliation | MEDIUM | LOW | P2 |
| Health check command | MEDIUM | LOW | P2 |
| Grace period cleanup | MEDIUM | MEDIUM | P2 |
| Window metadata timestamps | LOW | LOW | P2 |
| Audit log | LOW | MEDIUM | P3 |
| Cross-desktop tracking | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for launch (v2.0.2)
- P2: Should have, add when possible (v2.1.x)
- P3: Nice to have, future consideration (v2.2+)

## Ecosystem Pattern Analysis

### tmux Session Management Model

**Pattern:** `has-session` check before create
```bash
if ! tmux has-session -t "$session_name"; then
    tmux new-session -s "$session_name"
else
    tmux attach -t "$session_name"
fi
```

**Key insights:**
- Session lookup by unique name (not title matching)
- Create-if-not-exists is idempotent operation
- Explicit attach vs create commands (MC combines these)

**Application to MC:**
```python
window_id = registry.lookup(case_number)
if window_id and window_exists(window_id):
    focus_window(window_id)
else:
    create_terminal_window(case_number)
```

### kubectl Context Switching Model

**Pattern:** Context stored in config, switching changes active context
```bash
kubectl config use-context production
kubectl config current-context  # Returns: production
```

**Key insights:**
- Global registry (kubeconfig file) tracks all contexts
- Active context persists across commands
- No duplicate prevention needed (contexts are definitions, not processes)

**Application to MC:**
- Registry is similar to kubeconfig (persistent mapping)
- Window ID is like context name (unique identifier)
- Difference: MC windows are processes, kubectl contexts are config

### docker-compose Orphan Cleanup Model

**Pattern:** `--remove-orphans` flag cleans stale containers
```bash
docker-compose down --remove-orphans
```

**Key insights:**
- Orphan detection: containers not in current compose file
- Explicit cleanup (not automatic)
- Users control when cleanup happens

**Application to MC:**
- Stale entries = windows in registry but not in terminal app
- Cleanup strategy options:
  1. Automatic on startup (recommended)
  2. Manual via `mc window cleanup` command
  3. Automatic + manual reconcile command

### tmux-resurrect Recovery Model

**Pattern:** Session restoration from saved state
```bash
# Sessions saved to ~/.tmux/resurrect/last
# Restore with: prefix + Ctrl-r
```

**Key insights:**
- Crash recovery: validate saved state on restore
- Symlink points to latest good state
- Corrupted state: user manually fixes symlink

**Application to MC:**
- Registry corruption recovery options:
  1. Rebuild from scratch (scan all terminal windows)
  2. Discard corrupted entries (conservative)
  3. User-initiated reconcile command (recommended)

## User Workflow Analysis

### Happy Path: First Terminal Launch

```
1. User runs: `mc case 12345678`
2. MC checks registry: `registry.lookup("12345678")` → None
3. MC creates terminal window
4. MC captures window ID via AppleScript
5. MC stores: `registry.store("12345678", window_id)`
6. Terminal opens with podman exec session
```

**Features used:** Registry lookup, window creation, ID capture, registry storage

### Happy Path: Focus Existing Terminal

```
1. User runs: `mc case 12345678` (second time)
2. MC checks registry: `registry.lookup("12345678")` → "window-abc-123"
3. MC verifies window exists: `window_exists("window-abc-123")` → True
4. MC focuses window via AppleScript
5. No duplicate terminal created
```

**Features used:** Registry lookup, window existence check, focus operation

### Edge Case: User Manually Closed Window

```
1. User closes terminal window manually (Cmd+W)
2. Registry still has entry: "12345678" → "window-abc-123"
3. User runs: `mc case 12345678`
4. MC checks registry: `registry.lookup("12345678")` → "window-abc-123"
5. MC verifies window exists: `window_exists("window-abc-123")` → False
6. MC removes stale entry: `registry.remove("12345678")`
7. MC creates new terminal window
8. MC stores new window ID
```

**Features used:** Registry lookup, stale detection, cleanup, create new, store new

### Edge Case: Registry Corruption

```
1. Registry file corrupted/deleted
2. User runs: `mc case 12345678`
3. MC attempts registry.lookup() → DatabaseError
4. MC logs error, falls back to create mode
5. User sees warning: "Window registry unavailable, creating new window"
6. Terminal created successfully
7. User runs: `mc container reconcile` to rebuild registry
```

**Features used:** Error handling, fallback behavior, manual reconciliation

### Edge Case: Stale Entries Accumulate

```
1. User creates terminals for 10 cases
2. User manually closes 5 windows
3. Registry has 10 entries, 5 are stale
4. MC startup: runs automatic cleanup
5. Cleanup scans all 10 entries
6. Cleanup removes 5 stale entries
7. Registry now has 5 valid entries
```

**Features used:** Startup cleanup, bulk validation, stale removal

## Platform Considerations

### macOS (iTerm2/Terminal.app)

**ID Capture Method:**
```applescript
tell application "iTerm"
    return id of current window  # Returns: "window id 12345"
end tell
```

**Window Existence Check:**
```applescript
tell application "iTerm"
    repeat with w in windows
        if id of w is "window id 12345" then return true
    end repeat
    return false
end tell
```

**Focus Method:**
```applescript
tell application "iTerm"
    repeat with w in windows
        if id of w is TARGET_ID then
            select w
            activate
            return
        end if
    end repeat
end tell
```

### Linux (gnome-terminal/konsole)

**ID Capture Method:**
```bash
wmctrl -l  # Lists windows with IDs
# Format: 0x03400006  0 hostname Terminal - case:12345678
# Parse window ID from first column
```

**Window Existence Check:**
```bash
wmctrl -l | grep "^$WINDOW_ID " > /dev/null
echo $?  # 0 = exists, 1 = not found
```

**Focus Method:**
```bash
wmctrl -i -a $WINDOW_ID  # -i = treat as numeric ID, -a = activate
```

## Testing Strategy

### Unit Tests

```python
def test_registry_store_and_lookup():
    """Verify basic registry operations"""
    registry = WindowRegistry()
    registry.store("12345678", "window-abc-123")
    assert registry.lookup("12345678") == "window-abc-123"

def test_registry_remove_stale():
    """Verify stale entry removal"""
    registry = WindowRegistry()
    registry.store("12345678", "stale-window")
    registry.remove("12345678")
    assert registry.lookup("12345678") is None

def test_registry_cleanup_validates_existence():
    """Verify cleanup checks window existence before removal"""
    registry = WindowRegistry()
    registry.store("12345678", "valid-window")
    registry.store("99999999", "invalid-window")

    # Mock window_exists to return False for invalid-window
    cleanup_count = registry.cleanup(window_checker)

    assert cleanup_count == 1  # Removed 1 stale entry
    assert registry.lookup("12345678") == "valid-window"
    assert registry.lookup("99999999") is None
```

### Integration Tests

```python
def test_duplicate_terminal_prevention():
    """Regression test for UAT 5.2"""
    # First call: create window
    result1 = attach_terminal("12345678", ...)
    assert result1.window_created is True
    window_id = registry.lookup("12345678")
    assert window_id is not None

    # Second call: focus existing
    result2 = attach_terminal("12345678", ...)
    assert result2.window_created is False
    assert result2.window_focused is True
    assert registry.lookup("12345678") == window_id  # Same window

def test_manual_close_creates_new_window():
    """Verify handling of manually closed windows"""
    # Create window
    attach_terminal("12345678", ...)
    window_id = registry.lookup("12345678")

    # Simulate manual close (remove from terminal app)
    terminal.close_window(window_id)

    # Next attach should detect stale entry and create new
    attach_terminal("12345678", ...)
    new_window_id = registry.lookup("12345678")
    assert new_window_id != window_id  # Different window created
```

### Manual Test Scenarios

1. **Basic duplicate prevention:**
   - Run `mc case 12345678` → Window opens
   - Run `mc case 12345678` → Window focused, no duplicate

2. **Stale entry handling:**
   - Run `mc case 12345678` → Window opens
   - Manually close window (Cmd+W)
   - Run `mc case 12345678` → New window opens

3. **Registry persistence:**
   - Run `mc case 12345678` → Window opens
   - Kill mc process completely
   - Run `mc case 12345678` → Same window focused (registry persisted)

4. **Cleanup on startup:**
   - Create 3 case windows
   - Manually close 2 windows
   - Restart mc (or run cleanup command)
   - Verify registry only has 1 entry

## Competitor Feature Analysis

| Feature | tmux | screen | kubectl | docker-compose | Our Approach |
|---------|------|--------|---------|----------------|--------------|
| Session registry | Named sessions | Named sessions | Context in kubeconfig | Container state DB | Case number → Window ID mapping |
| Duplicate prevention | `has-session` check | Session name uniqueness | N/A (config only) | Container name uniqueness | Registry lookup before create |
| Stale cleanup | Manual detach | Manual detach | N/A | `--remove-orphans` flag | Automatic on startup + manual reconcile |
| Focus/attach | `attach -t` command | `screen -r` command | N/A | N/A | Platform-specific focus API |
| Recovery | tmux-resurrect plugin | N/A | N/A | N/A | Manual reconcile command |
| Cross-platform | Yes (any terminal) | Yes (any terminal) | Yes (client-side) | Yes (Docker) | Per-platform adapters (macOS/Linux) |

**Key differentiators for MC:**
1. **Automatic cleanup** - tmux/screen require manual session management
2. **Transparent focus** - User doesn't need to know attach vs create
3. **Platform-aware** - Leverages native terminal APIs (AppleScript/wmctrl)
4. **Container integration** - Registry tied to container lifecycle (not just terminal)

## Sources

**Terminal Multiplexers:**
- [tmux: How to attach and reattach sessions](https://www.ditig.com/how-to-attach-tmux-session)
- [Tmux Cheat Sheet & Quick Reference](https://tmuxcheatsheet.com/)
- [How to use tmux in 2026](https://www.hostinger.com/tutorials/how-to-use-tmux)
- [Catch yourself before you duplicate session - DEV Community](https://dev.to/waylonwalker/catch-yourself-before-you-duplicate-session-5936)
- [GitHub - tmux-plugins/tmux-resurrect](https://github.com/tmux-plugins/tmux-resurrect)
- [Resurrecting tmux sessions after restart](https://peateasea.de/resurrecting-tmux-sessions-after-restart/)

**Container Lifecycle:**
- [Docker Compose Down --remove-orphans](https://dockerpros.com/wiki/docker-compose-down-remove-orphans/)
- [Using the Docker Compose Down Command Effectively](https://labex.io/tutorials/docker/using-the-docker-compose-down-command-effectively-400128)
- [Use lifecycle hooks | Docker Docs](https://docs.docker.com/compose/how-tos/lifecycle/)

**Context Management:**
- [Kubectl config set context Tutorial and Best Practices](https://refine.dev/blog/kubectl-config-set-context/)
- [The Best 3 Tools for Working with Many Kubernetes Contexts](https://home.robusta.dev/blog/switching-kubernets-context)
- [kubectl list contexts: Manage Kubernetes Clusters](https://www.plural.sh/blog/kubectl-list-contexts-guide/)

**Window Management:**
- [Another Window Session Manager - GNOME Shell Extensions](https://extensions.gnome.org/extension/4709/another-window-session-manager/)
- [linux-window-session-manager - GitHub](https://github.com/johannesjo/linux-window-session-manager)
- [AppleScript to Open a New iTerm Window and bring it to the front](https://gist.github.com/reyjrar/1769355)
- [iTerm2 Documentation - Hotkey](https://iterm2.com/documentation-hotkey.html)

**Registry/Session Management:**
- [FSLogix - StaleSessionCleanup - Microsoft Q&A](https://learn.microsoft.com/en-us/answers/questions/1093357/fslogix-stalesessioncleanup-disconnecting-active-v)
- [Registry troubleshooting for advanced users - Microsoft Learn](https://learn.microsoft.com/en-us/troubleshoot/windows-server/performance/registry-troubleshooting-advanced-users)

---
*Feature research for: MC Window Tracking System*
*Researched: 2026-02-04*
*Confidence: HIGH - All claims verified against multiple ecosystem sources*
