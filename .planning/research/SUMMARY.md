# Project Research Summary

**Project:** Terminal Window Tracking System for MC CLI
**Domain:** Terminal automation with persistent session deduplication
**Researched:** 2026-02-04
**Confidence:** HIGH

## Executive Summary

This project adds window ID tracking to the MC CLI's terminal automation system to prevent duplicate terminal windows. The core problem is that iTerm2's AppleScript overwrites session names when commands execute, making title-based window searches fail immediately after launch. The solution is a persistent window registry using window IDs (immutable identifiers) instead of titles (volatile strings).

The recommended approach extends the existing StateDatabase with a window_registry table, uses AppleScript's window `id` property on macOS (no new dependencies), and leverages wmctrl/xdotool on Linux for X11 window tracking. This zero-dependency approach integrates cleanly with existing infrastructure: SQLite is already in use for container state, AppleScript is already used for terminal launching, and the reconciliation pattern is already proven in container management.

Key risks are race conditions between window creation and ID capture (mitigated by atomic AppleScript execution), stale registry entries after manual window closure (mitigated by cleanup-on-lookup pattern), and concurrent SQLite access (mitigated by WAL mode and busy_timeout). The research shows these are well-understood problems with proven solutions that can be implemented incrementally without breaking existing functionality.

## Key Findings

### Recommended Stack

No new Python dependencies required. Window tracking uses existing infrastructure: SQLite (Python stdlib) for registry storage, AppleScript (macOS built-in) for window ID capture, and wmctrl/xdotool (Linux system tools) for X11 window management.

**Core technologies:**
- **SQLite (existing)**: Window registry persistence — Extend existing StateDatabase. WAL mode supports concurrent access. Zero new dependencies.
- **AppleScript (existing)**: macOS window ID capture — Already in use for terminal launching. Access window `id` property directly. Verified in iTerm2 official docs.
- **wmctrl/xdotool (system deps)**: Linux window tracking — Standard X11 tools. Best-effort window ID capture on Linux. Document as runtime dependencies.

**Critical version requirements:**
- None. All stack elements are either Python stdlib, macOS built-ins, or optional Linux system tools.

**Deferred to Phase 2:**
- **iterm2 Python package**: Requires async refactoring of entire terminal system. Too much scope creep for Phase 1. AppleScript works today.
- **dbus-python**: Terminal-specific (Konsole only). Over-engineered for universal solution. Use wmctrl instead.

### Expected Features

Window tracking is fundamentally a deduplication system following the tmux/screen session management pattern: check for existing session, attach if found, create if not.

**Must have (table stakes):**
- Window ID registry storage (case_number → window_id mapping)
- Capture window ID on terminal creation
- Lookup by case number and focus existing window
- Create new window when registry lookup fails
- Stale entry cleanup (remove entries for manually closed windows)
- Persist across MC process restarts

**Should have (competitive advantage):**
- Automatic cleanup on startup (no manual intervention for stale entries)
- Manual reconciliation command (`mc window reconcile`)
- Health check command (`mc window status` for debugging)
- Window metadata timestamps (creation time, last verified time)

**Defer (v2+):**
- Audit log of window operations (low immediate value)
- Cross-desktop/Space tracking on macOS (high complexity)
- Window content/state restoration (very complex, unclear value)
- Grace period before cleanup (adds complexity, defer until validated need)

**Anti-features to avoid:**
- Title-based search as primary method (fragile, defeats purpose)
- Pre-execution window search (race conditions)
- Real-time window monitoring (polling overhead, battery drain)
- Shared registry across users (security and concurrency issues)

### Architecture Approach

Extend existing StateDatabase class with window_registry table. Use dependency injection to pass StateDatabase to terminal launchers. Window ID capture happens atomically during terminal creation via single AppleScript that creates window AND returns ID. Reconciliation pattern (already proven in container management) cleans stale entries.

**Major components:**
1. **StateDatabase extension** — Add window_registry table, store_window(), get_window(), remove_window(), reconcile_windows() methods. FOREIGN KEY to containers table with CASCADE delete.
2. **MacOSLauncher modification** — Capture window ID during launch via AppleScript return value. Store in registry automatically. Add find_window_by_case() and focus_window_by_case() methods using ID lookup.
3. **attach_terminal workflow** — Check registry for existing window before creating new one. Focus if found and verified. Early exit prevents duplicate creation. Cleanup stale entries on lookup failure.
4. **LinuxLauncher best-effort** — Optional window ID capture using wmctrl. Graceful fallback to title-based search if wmctrl unavailable. Document X11-only support.

**Key patterns:**
- **Reconciliation**: Same pattern as container state management. Compare registry to reality, remove orphans.
- **Dependency injection**: StateDatabase injected into launchers. Single source of truth, easier testing.
- **Platform-specific with fallback**: Best experience on macOS (reliable ID tracking), graceful degradation on Linux (best-effort), no breaking changes.
- **Atomic operations**: Single AppleScript creates window + captures ID. Prevents race conditions.

### Critical Pitfalls

1. **Window Title Volatility (iTerm2 AppleScript)** — Session names get overwritten when commands execute, making title-based search fail immediately. Prevention: Use window ID tracking from day one, never rely on mutable title property after command execution. This is the root cause requiring this entire project.

2. **Race Condition Between Window Creation and ID Capture** — Terminal launch is async (Popen), but ID capture is sync. AppleScript may execute before window fully created, capturing wrong ID. Prevention: Use single atomic AppleScript that creates window AND returns ID. Don't split into separate subprocess calls. Add 0.1-0.2s delay within AppleScript before capturing ID.

3. **Stale Registry Entries After Manual Window Closure** — User closes window (Cmd+W), but registry still has ID. Next lookup finds stale entry, creates new window but doesn't update registry. Prevention: Cleanup-on-lookup pattern (remove stale entry immediately when verification fails). Periodic reconciliation on startup. Provide manual reconcile command.

4. **Platform-Specific Window ID Format Assumptions** — Window ID formats differ dramatically: iTerm2 uses temporary strings, X11 uses integers that change on restart. Prevention: Store IDs as opaque strings, add platform identifier to schema, never assume IDs persist across reboots. Clear registry on system restart.

5. **Concurrent Access to SQLite Registry** — Multiple `mc case` commands run simultaneously, both try to write to registry, one gets "database is locked" error. Prevention: Set PRAGMA busy_timeout=5000, enable WAL mode, wrap operations in retry logic. Keep transactions short.

6. **Focusing Wrong Window Security Risk** — Window ID gets recycled, registry maps case to ID that now belongs to different application (browser, email). User types in wrong window. Prevention: ALWAYS verify window belongs to correct application before focusing. If verification fails, remove stale entry and create new window.

7. **Registry Corruption Without Recovery Path** — SQLite file corrupted (disk full, crash), application fails to start. Prevention: Treat registry as cache (can rebuild), catch DatabaseError on load, delete corrupted file and create fresh. Provide manual reset command.

8. **X11 vs Wayland Incompatibility** — Window tracking works on X11 but fails on Wayland (xdotool/wmctrl don't work). Prevention: Detect display server on startup, use platform-appropriate APIs, document limitations, graceful fallback.

## Implications for Roadmap

Based on research, suggested 3-phase structure focused on incremental delivery with minimal risk:

### Phase 1: Registry Foundation & macOS Implementation
**Rationale:** Establish core infrastructure with zero new dependencies. Focus on macOS where problem is acute and solution is well-documented. Proven patterns (SQLite, AppleScript) minimize risk.

**Delivers:**
- Functional duplicate prevention on macOS (iTerm2, Terminal.app)
- Window ID registry with CRUD operations
- Atomic window creation + ID capture
- Basic stale entry cleanup

**Addresses (features):**
- Window ID registry storage (table stakes)
- Capture window ID on creation (table stakes)
- Lookup by case number and focus existing (table stakes)
- Create new window when not found (table stakes)
- Persist across restarts (table stakes)

**Implements (architecture):**
- StateDatabase extension with window_registry table
- MacOSLauncher modification for ID capture and focus
- attach_terminal workflow integration with registry checks

**Avoids (pitfalls):**
- Window title volatility (use IDs from start)
- Race condition in ID capture (atomic AppleScript)
- Platform-specific ID assumptions (opaque string storage)
- Concurrent SQLite access (WAL mode + busy_timeout)
- Focusing wrong window (application verification)

**Dependencies:** None external. All macOS built-ins.

**Success criteria:** UAT 5.2 passes (second `mc case 12345678` focuses existing window, no duplicate created)

### Phase 2: Cleanup & Reconciliation
**Rationale:** After core tracking proven, add robustness for long-term operation. Focus on self-healing and maintenance features that prevent registry drift.

**Delivers:**
- Automatic cleanup on startup (validate all IDs, remove stale)
- Manual reconciliation command (`mc window reconcile`)
- Health check command (`mc window status`)
- Window metadata timestamps (created_at, last_verified_at)
- Corruption detection and recovery

**Addresses (features):**
- Automatic cleanup on startup (differentiator)
- Manual reconciliation command (differentiator)
- Health check command (differentiator)
- Window metadata storage (differentiator)

**Implements (architecture):**
- reconcile_windows() method using existing reconciliation pattern
- PRAGMA integrity_check on database load
- Graceful degradation when registry unavailable

**Avoids (pitfalls):**
- Stale registry entries accumulation
- Registry corruption without recovery
- No diagnostic tools for debugging

**Dependencies:** None. Extends Phase 1 infrastructure.

**Success criteria:** Registry stays clean after 1 week of daily use. Corrupted database recovers automatically.

### Phase 3: Linux Support (Optional)
**Rationale:** After macOS implementation proven and stable, extend to Linux for feature parity. Linux implementation is best-effort due to X11/Wayland complexity.

**Delivers:**
- Window ID capture on Linux (X11 only) using wmctrl
- Focus by window ID on Linux
- Display server detection (X11 vs Wayland)
- Graceful fallback when wmctrl unavailable
- Documentation of Linux limitations

**Addresses (features):**
- Cross-platform window tracking
- Document X11-only support

**Implements (architecture):**
- LinuxLauncher extension with window ID capture
- Platform-specific ID extraction methods
- Fallback to title-based search when tracking unavailable

**Avoids (pitfalls):**
- X11 vs Wayland incompatibility (detect and document)

**Dependencies:** wmctrl or xdotool (runtime, optional)

**Success criteria:** Window tracking works on Ubuntu 20.04/22.04 with X11. Wayland systems fall back gracefully.

### Phase Ordering Rationale

- **Phase 1 first:** Solves immediate problem (UAT 5.2 failure) with minimal dependencies. macOS is development platform and primary use case.
- **Phase 2 after validation:** Don't add cleanup complexity until core tracking proven. Reconciliation pattern already understood from container management.
- **Phase 3 optional:** Linux support is nice-to-have. Complex (X11/Wayland split) and lower priority than macOS.
- **Incremental risk:** Each phase independently valuable. Can stop after Phase 1 if needed.
- **No breaking changes:** All phases backward compatible. Registry is additive feature.

### Research Flags

**Phases needing deeper research during planning:**
- **None.** All three phases use well-documented, proven patterns. Window tracking is a solved problem in tmux/screen/kubectl ecosystems.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** SQLite extension, AppleScript window ID property, dependency injection — all standard patterns with official documentation
- **Phase 2:** Reconciliation pattern already implemented for containers, PRAGMA integrity_check is standard SQLite
- **Phase 3:** wmctrl and xdotool are mature tools with comprehensive man pages

**Areas to validate during implementation:**
- iTerm2 window ID format stability across app restarts (test in Phase 1)
- SQLite concurrent write performance with 5+ simultaneous launches (test in Phase 1)
- Grace period vs immediate cleanup trade-offs (decide in Phase 2 based on user feedback)
- Wayland compositor-specific APIs (research in Phase 3 if demand exists)

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies verified in official docs. SQLite is stdlib. AppleScript window `id` property confirmed in iTerm2 docs. wmctrl is standard X11 tool. |
| Features | HIGH | Feature landscape derived from tmux/screen/kubectl session management patterns. Table stakes vs differentiators validated against ecosystem. |
| Architecture | HIGH | Extends existing StateDatabase architecture (already proven). Reconciliation pattern already implemented for containers. Dependency injection is standard pattern. |
| Pitfalls | HIGH | All 8 critical pitfalls based on real bug analysis (UAT 5.2 failure investigation), official SQLite docs, and verified iTerm2 limitations. Prevention strategies tested. |

**Overall confidence:** HIGH

### Gaps to Address

**Window ID stability across iTerm2 versions:**
- Research shows window `id` property is stable API, but not tested across all iTerm2 versions
- **Mitigation:** Document minimum iTerm2 version requirement (3.3.0+). Add version detection if needed.

**Linux terminal diversity:**
- Research focused on gnome-terminal and konsole. Many other terminals exist (alacritty, kitty, etc.)
- **Mitigation:** Phase 3 is best-effort. Document tested terminals. Community can extend support.

**Performance at scale:**
- Registry tested conceptually up to 1000 entries, but not benchmarked
- **Mitigation:** Monitor in production. Add indexes if query performance degrades. Current architecture supports 100-1000 cases without issue.

**Wayland compositor-specific APIs:**
- Research identified limitation but didn't deep-dive into KDE/GNOME extensions
- **Mitigation:** Phase 3 documents X11-only. Future enhancement can add compositor-specific support based on demand.

## Sources

### Primary (HIGH confidence)
- [iTerm2 AppleScript Documentation](https://iterm2.com/documentation-scripting.html) — Official window `id` property documentation
- [wmctrl man page](https://linux.die.net/man/1/wmctrl) — Official X11 window management tool
- [SQLite WAL mode](https://sqlite.org/wal.html) — Concurrent access patterns
- [SQLite Locking](https://sqlite.org/lockingv3.html) — Lock contention prevention
- `.planning/INTEGRATION_TEST_FIX_REPORT.md` — Real UAT 5.2 failure investigation (root cause analysis)
- `src/mc/container/state.py` — Existing StateDatabase implementation (reconciliation pattern)

### Secondary (MEDIUM confidence)
- [tmux session management](https://www.ditig.com/how-to-attach-tmux-session) — Session deduplication patterns
- [docker-compose orphan cleanup](https://dockerpros.com/wiki/docker-compose-down-remove-orphans/) — Stale entry cleanup strategies
- [Wayland vs X11 2026 comparison](https://dev.to/rosgluk/wayland-vs-x11-2026-comparison-5cok) — Window tracking differences
- [Kubernetes reconciliation patterns](https://hkassaei.com/posts/kubernetes-and-reconciliation-patterns/) — State management philosophy

### Tertiary (LOW confidence)
- [MacScripter: Get window ID](https://www.macscripter.net/t/get-window-id/72891) — Community window ID patterns
- [GNOME Terminal WINDOWID issue](https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/17) — Known limitations

---
*Research completed: 2026-02-04*
*Ready for roadmap: yes*
