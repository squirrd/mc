# Phase 17: Registry Cleanup & Maintenance - Research

**Researched:** 2026-02-08
**Domain:** SQLite database maintenance, stale entry detection, self-healing registries
**Confidence:** HIGH

## Summary

This phase builds on the existing window registry (Phase 15) and macOS window tracking (Phase 16) to implement self-healing cleanup that prevents stale entry accumulation. The research identifies that the project already has established patterns for registry reconciliation in `StateDatabase.reconcile()`, which validates Podman containers against external state. This same pattern can be applied to window registry cleanup.

The standard approach is **incremental, sampling-based cleanup** triggered at explicit points (startup, before operations) rather than background processes. The system validates window existence via platform-specific APIs (AppleScript on macOS, wmctrl on Linux) and immediately deletes stale entries without soft deletes or undo mechanisms.

**Primary recommendation:** Implement cleanup as a method on `WindowRegistry` class following the existing `StateDatabase.reconcile()` pattern, with sampling of oldest entries (by `last_validated` timestamp) to balance cleanup thoroughness with performance. Trigger cleanup automatically before terminal launch operations and expose manual reconcile command for troubleshooting.

## Standard Stack

The project already has all required dependencies - no new libraries needed.

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | Built-in | Database operations | Python standard library, already used in WindowRegistry and StateDatabase |
| platformdirs | Existing | Cross-platform paths | Already used for database location |
| subprocess | Built-in | AppleScript/wmctrl execution | Platform API interaction |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| logging | Built-in | Structured logging | Cleanup event tracking (project already has JSONFormatter and SensitiveDataFilter) |
| argparse | Built-in | CLI commands | Manual reconcile command parsing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Incremental cleanup | Full table scan | Full scan validates all entries but scales poorly (O(n) on every operation) |
| Sampling oldest | Sampling random | Random sampling misses chronically stale entries, oldest-first catches legitimately closed windows |
| Immediate delete | Soft delete/archive | Soft delete adds complexity for no benefit (window IDs have no historical value) |

**Installation:**
No new dependencies required - all libraries already in project.

## Architecture Patterns

### Recommended Method Structure
```python
# Add to WindowRegistry class in src/mc/terminal/registry.py

def cleanup_stale_entries(self, sample_size: int = 20) -> int:
    """Clean up stale window entries by validating oldest entries.

    Samples oldest entries by last_validated timestamp and validates
    window existence via platform API. Immediately deletes invalid entries.

    Args:
        sample_size: Number of oldest entries to validate (default: 20)

    Returns:
        Number of stale entries removed
    """

def get_oldest_entries(self, limit: int = 20) -> list[tuple[str, str, str]]:
    """Get oldest registry entries for validation.

    Returns entries with oldest last_validated timestamps, indicating
    windows that haven't been accessed recently and may be stale.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of (case_number, window_id, terminal_type) tuples
    """
```

### Pattern 1: Reconciliation-Based Cleanup
**What:** Validate external state (window existence) against internal state (registry), delete mismatches
**When to use:** When registry depends on external resources that can change independently
**Example:**
```python
# Source: Existing pattern from src/mc/container/state.py reconcile()
def cleanup_stale_entries(self, sample_size: int = 20) -> int:
    """Clean up stale window entries by validating oldest entries."""
    removed_count = 0

    with self._connection() as conn:
        # Get oldest entries for validation
        oldest = self._get_oldest_entries(limit=sample_size)

        for case_number, window_id, terminal_type in oldest:
            # Validate window still exists via platform API
            if not self._validate_window_exists(window_id, terminal_type):
                # Immediately delete stale entry
                conn.execute(
                    "DELETE FROM window_registry WHERE case_number = ?",
                    (case_number,)
                )
                removed_count += 1

    return removed_count
```

### Pattern 2: Sampling Oldest Entries
**What:** Query by `ORDER BY last_validated ASC LIMIT N` to prioritize oldest entries
**When to use:** When full table scan is prohibitively expensive but cleanup must be thorough
**Example:**
```python
# Source: SQLite best practices for time-based cleanup
def _get_oldest_entries(self, limit: int = 20) -> list[tuple[str, str, str]]:
    """Get oldest registry entries by last_validated timestamp."""
    with self._connection() as conn:
        rows = conn.execute(
            """
            SELECT case_number, window_id, terminal_type
            FROM window_registry
            ORDER BY last_validated ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [(row["case_number"], row["window_id"], row["terminal_type"])
                for row in rows]
```

### Pattern 3: Platform-Specific Validation
**What:** Use existing `_window_exists_by_id()` methods from Phase 16 for validation
**When to use:** Window existence check - already implemented in MacOSLauncher and will be in LinuxLauncher
**Example:**
```python
# Source: src/mc/terminal/macos.py _window_exists_by_id()
def _validate_window_exists(self, window_id: str, terminal_type: str) -> bool:
    """Validate window exists via platform launcher."""
    from mc.terminal.launcher import get_launcher

    try:
        launcher = get_launcher()
        # Use existing window validation from Phase 16
        return launcher._window_exists_by_id(window_id)
    except Exception:
        # If validation fails (API error, permissions), treat as stale
        # Aggressive cleanup - better to remove questionable entries
        return False
```

### Pattern 4: CLI Command Structure
**What:** Follow existing container command pattern for reconcile command
**When to use:** Manual troubleshooting and detailed reporting
**Example:**
```python
# Source: src/mc/cli/commands/container.py pattern
def reconcile(args: argparse.Namespace) -> None:
    """Reconcile window registry with actual terminal windows.

    Validates all window entries and removes stale entries for windows
    that were manually closed outside MC's control.
    """
    # Initialize registry (using consolidated ~/mc/state/window.db path)
    state_dir = os.path.join(os.path.expanduser("~"), "mc", "state")
    os.makedirs(state_dir, exist_ok=True)
    db_path = os.path.join(state_dir, "window.db")

    registry = WindowRegistry(db_path)

    # Run full reconciliation (larger sample or full scan)
    removed = registry.cleanup_stale_entries(sample_size=100)

    # Detailed reporting for manual command
    print(f"Window Registry Reconciliation Complete")
    print(f"  Entries validated: {sample_size}")
    print(f"  Stale entries removed: {removed}")
    print(f"  Registry location: {db_path}")
```

### Anti-Patterns to Avoid

- **Background periodic cleanup:** Adds complexity (threading, scheduling) with minimal benefit. Context decision: "No background/periodic cleanup - only explicit triggers"
- **Soft delete/archive:** Unnecessarily complex for window IDs that have no historical value. Context decision: "Delete stale entries immediately (no soft delete, no archive, no undo)"
- **Full table scan on every operation:** O(n) scaling makes startup slow as registry grows. Context decision: "Sample oldest entries during cleanup (oldest 20 per run)"
- **Blocking on validation failures:** API errors shouldn't stop cleanup workflow. Context decision: "If window existence check fails (API error, permission denied), remove the entry (aggressive cleanup)"

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Window existence validation | Custom window enumeration | Existing `_window_exists_by_id()` from Phase 16 | Already implemented for iTerm2 and Terminal.app in MacOSLauncher |
| Database connection management | Manual connection pooling | Existing `_connection()` context manager | Already handles WAL mode, transactions, rollback correctly |
| Reconciliation pattern | New cleanup architecture | Follow `StateDatabase.reconcile()` pattern | Proven pattern already in codebase for container cleanup |
| Structured logging | Print statements only | Existing `logging.getLogger(__name__)` infrastructure | Project has JSONFormatter, SensitiveDataFilter, debug mode support |
| CLI command structure | Custom argument parsing | Follow `src/mc/cli/commands/container.py` pattern | Consistent with `mc container create/list/stop/delete` commands |

**Key insight:** The project already solved all core architectural patterns in Phases 11 (container state reconciliation), 15 (window registry), and 16 (window validation). This phase is compositional - combining existing patterns rather than inventing new ones.

## Common Pitfalls

### Pitfall 1: Validating All Entries on Every Operation
**What goes wrong:** `SELECT * FROM window_registry` followed by validation of every entry causes O(n) performance degradation
**Why it happens:** Desire for "perfect" accuracy leads to over-validation
**How to avoid:** Sample oldest entries (by `last_validated` timestamp) to bound cleanup time regardless of registry size
**Warning signs:** Startup delay increasing linearly with registry size, cleanup taking >1 second

### Pitfall 2: Blocking Terminal Launch on Cleanup Failures
**What goes wrong:** If AppleScript/wmctrl API fails (permissions, window manager crash), entire `mc case` command fails
**Why it happens:** Not handling validation exceptions gracefully
**How to avoid:** Wrap validation in try/except, treat exceptions as "stale" (aggressive cleanup), log warning but continue
**Warning signs:** User reports "mc case hangs" or "permission denied blocks terminal launch"

### Pitfall 3: Race Condition During Window Closure
**What goes wrong:** Window closes between validation check and focus attempt, causing false "window exists" result
**Why it happens:** Non-atomic check-then-act pattern
**How to avoid:** Already handled in Phase 16-02: "Prompt user on focus failure after validation (handles race condition where window closes between validation and focus)". Cleanup similarly: accept that validation snapshot may be stale by milliseconds
**Warning signs:** Occasional focus failures even after "window found" validation passes

### Pitfall 4: Not Indexing last_validated Column
**What goes wrong:** `ORDER BY last_validated ASC LIMIT 20` becomes slow table scan without index
**Why it happens:** Schema doesn't include index on sort column
**How to avoid:** Add `CREATE INDEX IF NOT EXISTS idx_last_validated ON window_registry(last_validated)` in schema setup
**Warning signs:** EXPLAIN QUERY PLAN shows "SCAN TABLE" instead of "SEARCH TABLE USING INDEX"

### Pitfall 5: Silent Cleanup with No User Visibility
**What goes wrong:** Users confused when registry doesn't find windows they thought should exist
**Why it happens:** Cleanup runs silently without feedback
**How to avoid:** Context decision already addresses this: "Show count only if entries removed ('Cleaned up N stale window entries'), silent if nothing cleaned" for automatic cleanup, detailed report for manual reconcile
**Warning signs:** User bug reports "mc can't find my window" with no obvious cause

### Pitfall 6: Database Locks During Cleanup
**What goes wrong:** Long-running cleanup holds exclusive write lock, blocking concurrent terminal launches
**Why it happens:** Large batch DELETE in single transaction
**How to avoid:** Delete incrementally (commit after each stale entry) OR use small sample size to bound transaction time. WAL mode (already enabled) allows concurrent reads during cleanup
**Warning signs:** "Database is locked" errors, terminal launch hangs during cleanup

## Code Examples

Verified patterns from codebase analysis:

### Cleanup Method Integration
```python
# Source: Composite of WindowRegistry pattern and StateDatabase reconcile pattern
# Location: Add to src/mc/terminal/registry.py WindowRegistry class

def cleanup_stale_entries(self, sample_size: int = 20) -> int:
    """Clean up stale window entries by validating oldest entries.

    Samples oldest entries by last_validated timestamp and validates
    window existence via platform API. Immediately deletes invalid entries.
    Incremental deletion (commit per entry) avoids long-running locks.

    Args:
        sample_size: Number of oldest entries to validate (default: 20)

    Returns:
        Number of stale entries removed
    """
    import logging
    logger = logging.getLogger(__name__)

    removed_count = 0
    oldest_entries = self._get_oldest_entries(limit=sample_size)

    for case_number, window_id, terminal_type in oldest_entries:
        # Validate window existence (platform-specific)
        if not self._validate_window_exists(window_id, terminal_type):
            # Delete stale entry immediately (incremental commit)
            self.remove(case_number)
            removed_count += 1
            logger.info(f"Removed stale window registry entry for case {case_number}")

    return removed_count

def _get_oldest_entries(self, limit: int = 20) -> list[tuple[str, str, str]]:
    """Get oldest registry entries by last_validated timestamp.

    Returns entries with oldest last_validated timestamps, indicating
    windows that haven't been accessed recently and may be stale.

    Args:
        limit: Maximum number of entries to return

    Returns:
        List of (case_number, window_id, terminal_type) tuples ordered
        by last_validated ascending (oldest first)
    """
    with self._connection() as conn:
        rows = conn.execute(
            """
            SELECT case_number, window_id, terminal_type
            FROM window_registry
            ORDER BY last_validated ASC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [
            (row["case_number"], row["window_id"], row["terminal_type"])
            for row in rows
        ]

def _validate_window_exists(self, window_id: str, terminal_type: str) -> bool:
    """Validate window exists via platform-specific launcher.

    Args:
        window_id: Window ID to validate
        terminal_type: Terminal type (iTerm2, Terminal.app, etc.)

    Returns:
        True if window exists, False if stale or validation fails
    """
    from mc.terminal.launcher import get_launcher

    try:
        launcher = get_launcher()
        # Use existing _window_exists_by_id from Phase 16
        return launcher._window_exists_by_id(window_id)
    except Exception:
        # Aggressive cleanup: treat validation errors as stale
        # Better to remove questionable entries than accumulate crud
        return False
```

### Schema Update for Index
```python
# Source: SQLite indexing best practices
# Location: Update src/mc/terminal/registry.py _ensure_schema()

def _ensure_schema(self) -> None:
    """Create window_registry table and indices if they don't exist."""
    with self._connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS window_registry (
                case_number TEXT PRIMARY KEY,
                window_id TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                terminal_type TEXT,
                last_validated INTEGER
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_window_id ON window_registry(window_id)"
        )
        # NEW: Index for efficient ORDER BY last_validated queries
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_last_validated ON window_registry(last_validated)"
        )
```

### Automatic Cleanup Integration
```python
# Source: Pattern from ContainerManager._reconcile() before operations
# Location: src/mc/terminal/attach.py attach_terminal() function

def attach_terminal(
    case_number: str,
    config_manager: ConfigManager,
    api_client: RedHatAPIClient,
    container_manager: ContainerManager
) -> None:
    """Attach terminal to case container with auto-cleanup."""

    # NEW: Cleanup stale window registry entries before operation
    try:
        state_dir = os.path.join(os.path.expanduser("~"), "mc", "state")
        db_path = os.path.join(state_dir, "window.db")
        registry = WindowRegistry(db_path)

        removed = registry.cleanup_stale_entries(sample_size=20)
        if removed > 0:
            print(f"Cleaned up {removed} stale window entries")
    except Exception as e:
        # Non-fatal: cleanup failures shouldn't block terminal launch
        logger.warning(f"Window registry cleanup failed: {e}")

    # ... existing attach_terminal logic ...
```

### Manual Reconcile Command
```python
# Source: src/mc/cli/commands/container.py command pattern
# Location: New function in src/mc/cli/commands/container.py

def reconcile_windows(args: argparse.Namespace) -> None:
    """Reconcile window registry with actual terminal windows.

    Manual command for troubleshooting: validates window registry entries
    and removes stale entries for windows closed outside MC's control.

    Args:
        args: Parsed arguments (no additional args needed)
    """
    import os
    from mc.terminal.registry import WindowRegistry

    # Use consolidated state directory
    state_dir = os.path.join(os.path.expanduser("~"), "mc", "state")
    db_path = os.path.join(state_dir, "window.db")

    registry = WindowRegistry(db_path)

    # Larger sample for manual reconcile (or full scan if desired)
    sample_size = 100

    print(f"Window Registry Reconciliation")
    print(f"Database: {db_path}")
    print(f"Validating up to {sample_size} oldest entries...")
    print()

    removed = registry.cleanup_stale_entries(sample_size=sample_size)

    # Detailed report
    print(f"Reconciliation Complete")
    print(f"  Entries validated: {sample_size}")
    print(f"  Stale entries removed: {removed}")
    print(f"  Status: {'No cleanup needed' if removed == 0 else f'{removed} entries cleaned'}")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual cleanup commands only | Automatic cleanup on operation | Phase 17 (this phase) | Self-healing: users never manually reconcile unless troubleshooting |
| Full table scan validation | Sampling-based validation | Phase 17 (this phase) | O(1) cleanup time regardless of registry size |
| Print statements for logging | Structured logging with logger.info() | Phase 6 (Infrastructure Observability) | Debug visibility, JSON output support |
| platformdirs locations | Consolidated ~/mc/ directory | Phase 15+ migration | Single canonical location for all state |

**Current patterns (already established):**
- WAL mode for concurrent database access (Phase 15)
- First-write-wins duplicate prevention (Phase 15)
- Lazy validation with auto-cleanup on lookup (Phase 15)
- AppleScript window ID validation (Phase 16)
- Aggressive cleanup on validation failure (Phase 17 context decision)

**No deprecated patterns:** This phase builds on recent work (Phases 15-16 completed 2026-02-08), using current patterns.

## Open Questions

1. **Optimal sample size for cleanup**
   - What we know: Context suggests 20, but "Claude can optimize"
   - What's unclear: Tradeoff between cleanup thoroughness and operation latency
   - Recommendation: Start with 20 (balances cleanup and performance), make configurable if needed. Monitor cleanup effectiveness in 1-week test.

2. **Full scan option for manual reconcile**
   - What we know: Manual command should be more thorough than automatic
   - What's unclear: Should `mc container reconcile` validate ALL entries or use larger sample?
   - Recommendation: Use larger sample (100) for manual command. Full scan optional via flag `--full` if needed.

3. **Cleanup on startup vs before-operation**
   - What we know: Context says "Cleanup timing strategy left to Claude's discretion (startup, before operations, or other)"
   - What's unclear: Startup may not run frequently enough (user might never restart shell), before-operation adds latency to every `mc case` call
   - Recommendation: Before-operation cleanup (in attach_terminal) catches stale entries promptly. Startup cleanup unnecessary if before-operation is sufficient.

4. **Linux window validation implementation**
   - What we know: Phase 16 implemented macOS window validation, Linux wmctrl validation not yet implemented
   - What's unclear: Will LinuxLauncher have `_window_exists_by_id()` method?
   - Recommendation: Assume yes (Phase 16 pattern extends to Linux). If not implemented yet, cleanup gracefully skips validation on Linux or phase 17 adds it.

## Sources

### Primary (HIGH confidence)
- Codebase analysis:
  - src/mc/container/state.py reconcile() pattern (lines 223-245)
  - src/mc/terminal/registry.py WindowRegistry implementation (Phase 15)
  - src/mc/terminal/macos.py _window_exists_by_id() (Phase 16, lines 250-307)
  - src/mc/cli/commands/container.py command patterns
  - .planning/phases/17-registry-cleanup---maintenance/17-CONTEXT.md (user decisions)

### Secondary (MEDIUM confidence)
- [SQLite VACUUM](https://sqlite.org/lang_vacuum.html) - Database optimization best practices
- [Best Practices for Routine SQLite Maintenance](https://www.slingacademy.com/article/best-practices-for-routine-sqlite-maintenance/) - WAL mode, indexing, cleanup timing
- [SQLite Delete Query](https://sqldocs.org/sqlite-database/sqlite-delete-query) - DELETE performance with indexing

### Tertiary (LOW confidence)
- [What is Database Self-Healing?](https://www.dataopszone.com/what-is-database-self-healing/) - General pattern concepts (not SQLite-specific)
- [wmctrl man page](https://linux.die.net/man/1/wmctrl) - Linux window validation reference
- [AppleScript window existence discussion](https://www.macscripter.net/t/get-window-id/72891) - macOS window ID validation (community discussion, not official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All dependencies already in project, no new libraries needed
- Architecture: HIGH - Patterns proven in codebase (StateDatabase.reconcile, WindowRegistry, MacOSLauncher validation)
- Pitfalls: HIGH - Identified from SQLite best practices (indexing, WAL mode, batch size) and existing codebase patterns (aggressive cleanup on failure)

**Research date:** 2026-02-08
**Valid until:** 30 days (stable patterns - SQLite APIs and AppleScript window APIs change infrequently)
