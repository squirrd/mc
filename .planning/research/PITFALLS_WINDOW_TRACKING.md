# Pitfalls Research: Window/Session Tracking in Terminal Automation

**Domain:** Terminal window/session tracking systems
**Researched:** 2026-02-04
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Window Title Volatility (iTerm2 AppleScript)

**What goes wrong:**
Window titles/session names get completely overwritten when commands execute, making title-based window search fail immediately after launch. You create a window with title "CASE:12345:Customer:Description", but within milliseconds of running a command, the title becomes "podman (exec)" or "bash (bash)", making the original title completely inaccessible.

**Why it happens:**
iTerm2's AppleScript `name` property is mutable and volatile. When a command runs, iTerm2 automatically replaces the name with command information. No AppleScript-accessible property stores the "original" or "custom" name, and the search happens AFTER command execution starts, when the title is already replaced.

**How to avoid:**
- Use window ID tracking instead of title-based search
- Capture window/tab IDs at creation time and store in registry
- Search by immutable ID rather than mutable title property
- Never rely on AppleScript session name for window identification after command execution

**Warning signs:**
- find_window_by_title() returns False even though window exists
- Title searches work when window is idle but fail during command execution
- Multiple windows accumulate for the same case/session
- Test passes with blocking subprocess.run() but fails with non-blocking Popen()

**Phase to address:**
Phase 1: Registry Foundation - Implement window ID registry before any title-based search functionality

---

### Pitfall 2: Race Condition Between Window Creation and ID Capture

**What goes wrong:**
Window creation is asynchronous via Popen(), but ID capture happens synchronously. The AppleScript to capture window ID may execute before iTerm2 finishes creating the window, resulting in capturing the wrong window ID (previous window) or no ID at all. This causes the registry to map the wrong window to a case number.

**Why it happens:**
Terminal launch uses non-blocking subprocess.Popen() to return control to user immediately (UX requirement), but window creation in iTerm2 takes 100-500ms. AppleScript "return id of current window" executes immediately, before the new window is fully initialized, so "current window" may still be the previously-focused window.

**How to avoid:**
- Use single AppleScript that creates window AND returns ID atomically
- Don't split creation and ID capture into separate subprocess calls
- Add short delay (0.1-0.2s) within AppleScript before capturing ID
- Verify captured ID doesn't match any existing registry entry (sanity check)
- Return window ID from launch() function for immediate storage

**Warning signs:**
- Registry associates wrong window with case number
- Focusing case A brings up terminal for case B
- Same window ID appears for multiple different cases
- ID capture works inconsistently (timing-dependent failures)
- Test failures appear ~30% of the time (classic race condition symptom)

**Phase to address:**
Phase 1: Registry Foundation - Atomic window creation + ID capture in single AppleScript

---

### Pitfall 3: Stale Registry Entries After Manual Window Closure

**What goes wrong:**
User manually closes terminal window (Cmd+W, quit iTerm2, crash), but registry still contains the window ID. Next time they run `mc case 12345`, the code finds the ID in registry, checks if window exists, gets False, but then creates a NEW window with a NEW ID without updating the registry. The old stale ID remains in the registry forever, cluttering the database.

**Why it happens:**
Window closure is an external event outside the application's control. macOS doesn't provide callbacks when iTerm2 windows close. The registry is a local cache that assumes windows exist, but has no automatic invalidation mechanism when reality changes.

**How to avoid:**
- Implement cleanup-on-lookup pattern: when window ID lookup fails, immediately remove stale entry
- Run periodic registry reconciliation (startup, hourly, or on-demand command)
- Store creation timestamp with each entry, expire after configurable TTL (e.g., 7 days)
- Provide `mc window reconcile` command to rebuild registry from reality
- Log cleanup actions for debugging (INFO level: "Removed stale entry for case 12345")

**Warning signs:**
- Registry database grows indefinitely
- Most registry entries fail existence check
- Window focus failures with "Window not found, creating new..." message
- User reports: "I closed all terminals but registry still has 50 entries"
- Database file size > 1MB for typical usage (should be <100KB)

**Phase to address:**
Phase 2: Cleanup & Reconciliation - After basic tracking works, add robustness

---

### Pitfall 4: Platform-Specific Window ID Format Assumptions

**What goes wrong:**
Code assumes window IDs are stable integers (like X11 window IDs), but window ID format differs dramatically across platforms. iTerm2 AppleScript IDs are temporary strings, macOS CGWindowID are uint32_t but recycled after reboot, X11 window IDs are 32-bit integers that change across X server restarts, and Wayland compositors use compositor-specific handles with no global namespace.

**Why it happens:**
Developer writes implementation on one platform (macOS), assumes window ID behavior, then deploys to Linux or different macOS configuration. Each platform's window system has different ID semantics: lifetime, scope, uniqueness guarantees, and reuse policies.

**How to avoid:**
- Never assume window ID persists across process/system restarts
- Store registry as in-memory or session-scoped (don't persist to disk long-term)
- Platform-specific ID extraction: iTerm2 uses "id of window", X11 uses xdotool getwindowfocus
- Treat window IDs as opaque strings in registry, not integers
- Add platform identifier to registry schema (prevents cross-platform pollution)
- Clear registry on major system events (OS upgrade, display server restart)

**Warning signs:**
- Window focus works on macOS but not Linux (or vice versa)
- Registry entries from before reboot cause failures
- Window ID "12345" exists but window doesn't (ID was recycled)
- Different terminal emulators on same platform have different ID formats
- Test passes in CI (fresh environment) but fails on developer machine (stale registry)

**Phase to address:**
Phase 1: Registry Foundation - Design schema to be platform-agnostic from day one

---

### Pitfall 5: Concurrent Access to SQLite Registry

**What goes wrong:**
Two `mc case` commands run simultaneously in different shells. Both try to write to window_registry.db at the same time. SQLite returns "database is locked" error, causing one command to fail with exception. User sees "Error: unable to store window ID" and duplicate windows are created.

**Why it happens:**
SQLite's default locking is EXCLUSIVE for writes - only one writer at a time. The BEGIN command doesn't acquire locks immediately; a RESERVED lock is acquired on first INSERT/UPDATE. If both processes reach INSERT at nearly the same time, one gets RESERVED lock, the other gets "database is locked". Default busy_timeout is 0ms, so immediate failure.

**How to avoid:**
- Set PRAGMA busy_timeout=5000 (wait up to 5 seconds for lock)
- Use WAL mode (PRAGMA journal_mode=WAL) for concurrent reads during writes
- Wrap all database operations in try/except with retry logic (3 attempts, exponential backoff)
- Keep transactions SHORT - insert/update then commit immediately
- Don't hold database connection open across network calls or user input
- Use connection pooling with proper timeout configuration

**Warning signs:**
- "sqlite3.OperationalError: database is locked" in logs
- Intermittent failures when multiple terminals launched quickly
- Works fine when launching terminals slowly, fails under load
- Test passes in serial execution, fails in parallel execution
- Long-running transactions (check with PRAGMA busy_timeout check)

**Phase to address:**
Phase 1: Registry Foundation - Configure SQLite correctly from initial implementation

---

### Pitfall 6: Registry Corruption Without Recovery Path

**What goes wrong:**
SQLite database file becomes corrupted (disk full during write, system crash, file system corruption). Next time user runs `mc case`, application crashes with "sqlite3.DatabaseError: database disk image is malformed". User cannot launch ANY terminal windows because registry init fails on startup.

**Why it happens:**
SQLite files are vulnerable to corruption from hardware failures, OS crashes during write, disk full, and file system issues. Application treats registry as critical dependency - if registry fails to load, application refuses to start. No fallback mechanism exists.

**How to avoid:**
- Treat registry as cache, not source of truth (can always rebuild)
- Catch DatabaseError on registry load, log warning, DELETE corrupted file, create fresh
- Implement graceful degradation: if registry unavailable, fall back to title search (slower but functional)
- Use SQLite's built-in corruption detection: PRAGMA integrity_check on startup
- Keep registry file size small (auto-cleanup) to minimize corruption impact
- Provide manual recovery command: `mc window reset-registry`

**Warning signs:**
- Application crashes on startup with database corruption error
- Registry file grows very large (>10MB) suggesting no cleanup
- Frequent "PRAGMA integrity_check" failures in logs
- User reports: "I had to delete ~/.mc/state/window_registry.db to make mc work again"
- Corrupted SQLite files in crash reports or error tracking

**Phase to address:**
Phase 2: Cleanup & Reconciliation - Add corruption detection and recovery

---

### Pitfall 7: Focusing Wrong Window Causes Security Risk

**What goes wrong:**
Registry associates case 12345 with window ID W1. User closes that window. Another application (Terminal.app, browser) creates new window that happens to reuse ID W1. User runs `mc case 12345`, code finds W1 in registry, focuses window... but it's now the WRONG window (browser, email, etc.). User types sensitive commands thinking they're in the MC terminal, but they're typing in an email or Slack window.

**Why it happens:**
Window IDs are finite and get recycled. On macOS, CGWindowID is uint32_t (4 billion values), but in practice window managers reuse IDs after windows close. No verification that window ID still belongs to iTerm2 or contains the expected content. Focus operation succeeds even when target window is completely different application.

**How to avoid:**
- ALWAYS verify window application before focusing: check "application name is 'iTerm'"
- Verify window title contains expected case number (belt-and-suspenders approach)
- If verification fails, remove stale entry and create NEW window (safe fallback)
- Log verification failures at WARNING level for security audit
- Never focus window without validation in security-sensitive contexts
- Provide user confirmation for focus operation: "Focusing case 12345 terminal (Y/n)?"

**Warning signs:**
- User reports: "MC focused my browser instead of terminal"
- Window focus succeeds but user sees wrong application content
- Security incident: password typed into chat application
- Window ID exists but belongs to different application (iTerm2 -> Terminal.app)
- Focus operation succeeds silently even when target window is unrelated

**Phase to address:**
Phase 1: Registry Foundation - Include application validation in find_window_by_id() from start

---

### Pitfall 8: X11 vs Wayland Incompatibility

**What goes wrong:**
Window tracking code works perfectly on X11 (Ubuntu 20.04, CentOS 8) using xdotool or wmctrl for window ID lookup. Deploy to modern Ubuntu 22.04+ with Wayland, and all window tracking fails. No window IDs are captured, search always returns False, duplicate windows everywhere. Tools like xdotool don't work on Wayland due to security model.

**Why it happens:**
X11 allows any application to enumerate all windows and get their IDs via Xlib. Wayland's security model prevents applications from accessing other applications' windows. Each application only knows about its own windows. No global window ID namespace exists. Tools like xdotool require X11 protocol, fail on Wayland (or work only via XWayland emulation with limitations).

**How to avoid:**
- Detect display server on startup: check $WAYLAND_DISPLAY vs $DISPLAY
- Platform-specific implementations: X11Tracker vs WaylandTracker
- On Wayland, use compositor-specific APIs (KDE: kwin-script, GNOME: shell extensions)
- Consider fallback: if window tracking unavailable, disable duplicate prevention with warning
- Document Linux compatibility: "Window tracking requires X11 or compositor extensions"
- Test on both X11 and Wayland in CI (multi-platform test matrix)

**Warning signs:**
- Window tracking works on developer machine (X11) but not production (Wayland)
- xdotool or wmctrl commands fail with "cannot open display"
- User environment has $WAYLAND_DISPLAY but code assumes X11
- GitHub issues: "Doesn't work on Ubuntu 22.04 / Fedora 35"
- Window ID capture returns empty string on Linux but works on macOS

**Phase to address:**
Phase 3: Cross-Platform Support - After macOS implementation proven, add Linux support

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Store window IDs in plain JSON file | Simple, no SQL dependency | Race conditions, corruption, no transactions | Never (SQLite is stdlib) |
| Skip window existence verification before focus | Faster focus operation | Security risk: focus wrong window | Never (verification is cheap) |
| Use title-based search as fallback | Better UX if ID tracking fails | Inconsistent behavior, race conditions | Only as emergency fallback |
| Persist registry across system reboots | User convenience (remembers windows) | Window ID reuse bugs, stale entries | Never (IDs not stable across reboots) |
| Global cleanup cron job (delete old entries) | Automatic maintenance | Deletes valid long-running sessions | Only with very long TTL (30+ days) |
| Assume window IDs are integers | Simpler database schema | Platform incompatibility (iTerm2 uses strings) | Never (use TEXT column) |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| iTerm2 AppleScript | Trust session name property during command execution | Use window ID, never rely on mutable properties |
| SQLite locking | Default settings (no busy_timeout, no WAL) | Set busy_timeout=5000, use WAL mode |
| Subprocess.Popen | Assume window exists immediately after Popen returns | Wait for creation or use atomic create+capture script |
| macOS CGWindowID | Assume ID is stable across app/system restarts | Treat as session-scoped, expire on restart |
| X11 window IDs | Use xdotool/wmctrl without checking for Wayland | Detect display server, use platform-appropriate API |
| Terminal.app | Assume same AppleScript API as iTerm2 | Different property names (custom title vs name) |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full window iteration for every search | Slow focus operation (2-5 seconds) | Use registry lookup (O(1) vs O(n)) | >10 terminal windows open |
| No registry cleanup | Database grows to 100MB+ | Periodic cleanup, TTL-based expiration | After 6 months of daily use |
| Synchronous AppleScript per window | UI freezes during search | Batch operations, timeout limits | >5 windows per search |
| Hold SQLite connection across commands | Lock contention, blocking | Open connection, query, close immediately | Concurrent usage |
| Store full window screenshots in registry | 10MB+ database, slow queries | Store only IDs and metadata | >50 registry entries |
| Linear scan of all iTerm2 windows | O(n*m) complexity (windows * tabs) | Registry index lookup | >20 total windows across all apps |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Window ID Tracking:** Often missing existence verification — verify window still exists AND belongs to correct application before focusing
- [ ] **Registry Storage:** Often missing corruption recovery — add PRAGMA integrity_check and rebuild-on-corruption fallback
- [ ] **Stale Entry Cleanup:** Often missing cleanup-on-lookup — don't just run periodic cleanup, also clean during normal operations
- [ ] **Concurrent Access:** Often missing busy_timeout and WAL mode — verify PRAGMA settings in tests
- [ ] **Platform Compatibility:** Often missing Wayland support — test on both X11 and Wayland, document limitations
- [ ] **Error Handling:** Often missing graceful degradation — if registry fails, fall back to functional (slower) mode
- [ ] **Security Validation:** Often missing application verification — confirm window belongs to expected terminal application
- [ ] **Race Condition Testing:** Often missing concurrent launch tests — test simultaneous `mc case` calls from multiple shells

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Corrupt SQLite registry | LOW | Delete ~/.mc/state/window_registry.db, restart application (registry rebuilds empty) |
| Stale registry entries | LOW | Run `mc window reconcile` to verify all IDs and remove invalid entries |
| Wrong window focused | MEDIUM | Add application verification to find_window_by_id(), deploy hotfix |
| Window ID recycling security issue | HIGH | Invalidate all registry entries, force recreation, add app verification |
| X11/Wayland incompatibility | MEDIUM | Detect display server, disable window tracking on unsupported platforms with warning |
| Concurrent access deadlock | LOW | Increase busy_timeout to 10s, enable WAL mode, restart |
| Race condition in ID capture | MEDIUM | Refactor to atomic AppleScript, add verification loop with timeout |
| Registry growing unbounded | LOW | Run cleanup with short TTL (7 days), then set up automated cleanup |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Window Title Volatility | Phase 1: Registry Foundation | Test finds window by ID after command execution |
| Race Condition (ID Capture) | Phase 1: Registry Foundation | Concurrent launch test (10 windows in 1 second) |
| Stale Registry Entries | Phase 2: Cleanup & Reconciliation | Close window, verify registry cleanup, test reconcile command |
| Platform-Specific ID Format | Phase 1: Registry Foundation | Cross-platform test suite (macOS + Linux CI) |
| Concurrent SQLite Access | Phase 1: Registry Foundation | Parallel access test (5 simultaneous writes) |
| Registry Corruption | Phase 2: Cleanup & Reconciliation | Corrupt database file, verify graceful recovery |
| Focusing Wrong Window | Phase 1: Registry Foundation | Mock window ID reuse, verify application validation |
| X11 vs Wayland | Phase 3: Cross-Platform Support | Test on Ubuntu 22.04 (Wayland) and 20.04 (X11) |

## Sources

**Web Research:**
- [iTerm2 AppleScript Documentation](https://iterm2.com/documentation-scripting.html) - Official AppleScript reference (MEDIUM confidence)
- [SQLite File Locking](https://sqlite.org/lockingv3.html) - Concurrent access patterns (HIGH confidence)
- [SQLite Corruption Recovery](https://sqlite.org/recovery.html) - Official recovery documentation (HIGH confidence)
- [Wayland vs X11 2026 Comparison](https://dev.to/rosgluk/wayland-vs-x11-2026-comparison-5cok) - Window ID tracking differences (MEDIUM confidence)
- [Focus Stealing Security Risks](https://en.wikipedia.org/wiki/Focus_stealing) - User input security concerns (HIGH confidence)
- [AppleScript Race Conditions Discussion](https://discussions.apple.com/thread/8414962) - Window creation timing issues (MEDIUM confidence)
- [Orphaned Process Cleanup Patterns](https://github.com/steveyegge/gastown/issues/29) - Defense-in-depth cleanup strategy (HIGH confidence)
- [Session Registry Cleanup Patterns](https://docs.connectwise.com/ScreenConnect_Documentation/Supported_extensions/Productivity/Stale_Session_Cleanup) - Stale session handling (MEDIUM confidence)
- [Microsoft Terminal Focus Issues](https://github.com/microsoft/terminal/issues/15786) - Terminal focus stealing examples (MEDIUM confidence)
- [SQLite Concurrency 2025](https://tenthousandmeters.com/blog/sqlite-concurrent-writes-and-database-is-locked-errors/) - Practical SQLite locking guide (HIGH confidence)

**Codebase Investigation:**
- `.planning/INTEGRATION_TEST_FIX_REPORT.md` - Real-world iTerm2 AppleScript limitations discovered through testing (HIGH confidence)
- `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md` - Proposed solutions with detailed analysis (HIGH confidence)
- `src/mc/terminal/macos.py` - Current implementation showing title-based search (HIGH confidence)
- `src/mc/terminal/linux.py` - Linux launcher showing lack of window tracking (HIGH confidence)

**Key Insights:**
- iTerm2 session name volatility is verified through actual experimentation (10+ AppleScript tests)
- Window ID recycling security risk is theoretical but documented in focus stealing literature
- SQLite concurrency patterns are from official documentation and best practices
- X11/Wayland incompatibility is verified from 2025-2026 Linux ecosystem research
- Race conditions confirmed through real integration test failures

---
*Pitfalls research for: Window/Session Tracking in Terminal Automation*
*Researched: 2026-02-04*
*Confidence: HIGH (based on real bug analysis, official documentation, and ecosystem research)*
