# Phase 15: Window Registry Foundation - Research

**Researched:** 2026-02-08
**Domain:** SQLite-based persistent storage with concurrent access
**Confidence:** HIGH

## Summary

This phase implements a window registry using SQLite with Write-Ahead Logging (WAL) mode to store mappings between case numbers and terminal window IDs. The registry enables duplicate terminal prevention by tracking which windows belong to which cases across multiple mc process invocations.

The standard approach leverages Python's built-in sqlite3 module (version 3.50.4 available in Python 3.13.7) with WAL mode for concurrent reads and single-writer coordination. The codebase already uses this pattern successfully in `src/mc/container/state.py` (StateDatabase), providing a proven reference implementation. Key architectural decisions include separate database file (window.db), lazy validation of window existence on lookup, and auto-commit transactions for simplicity.

**Primary recommendation:** Follow the established StateDatabase pattern with WAL mode, auto-commit transactions, and context manager-based connection handling. Use tenacity (already a dependency) for retry logic on database locks.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| sqlite3 | 3.50.4 (bundled) | Persistent storage with concurrent access | Built-in to Python, zero dependencies, proven for local persistence |
| platformdirs | >=4.0.0 | Platform-specific data directory paths | Already in use, follows XDG standards on Linux, native conventions on macOS |
| tenacity | >=8.3.0 | Retry logic with exponential backoff | Already a dependency, handles database lock retries gracefully |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=9.0.0 | Unit testing with fixtures | Testing database operations with :memory: databases |
| pytest-mock | >=3.15.0 | Mocking for timestamp control | Testing time-dependent behavior |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| SQLite file | JSON file | JSON simpler but no concurrent access protection, requires manual locking |
| Separate window.db | Extend state.db | User decision: separate file chosen for clean separation of concerns |
| sqlite3 module | SQLAlchemy ORM | ORM adds dependency, overkill for simple CRUD operations |

**Installation:**
```bash
# No new dependencies required - all libraries already in pyproject.toml
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── terminal/
│   ├── macos.py              # Window ID validation via AppleScript
│   └── registry.py           # NEW: WindowRegistry class
└── container/
    └── state.py              # Reference: StateDatabase pattern
```

### Pattern 1: StateDatabase Class Structure
**What:** Class-based database wrapper with context manager for connections
**When to use:** Any SQLite-backed storage needing concurrent access
**Example:**
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/container/state.py
class WindowRegistry:
    """Manage window ID mappings in SQLite database with WAL mode."""

    def __init__(self, db_path: str | None = None):
        """Initialize window registry.

        Args:
            db_path: Path to SQLite database file. If None, uses platform-appropriate
                     default location (~/.local/share/mc/window.db on Linux,
                     ~/Library/Application Support/mc/window.db on macOS).
        """
        if db_path is None:
            data_dir = user_data_dir("mc", "redhat")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "window.db")

        self.db_path = db_path
        self._memory_conn: sqlite3.Connection | None = None

        # For :memory: databases, keep persistent connection
        if db_path == ":memory:":
            self._memory_conn = sqlite3.connect(
                db_path, check_same_thread=False, timeout=30.0
            )
            self._memory_conn.row_factory = sqlite3.Row

        self._setup_wal_mode()
        self._ensure_schema()
```

### Pattern 2: WAL Mode Configuration
**What:** Write-Ahead Logging for concurrent access
**When to use:** Always for file-based SQLite databases with multiple processes
**Example:**
```python
# Source: Official SQLite PRAGMA documentation
def _setup_wal_mode(self) -> None:
    """Enable WAL mode for better read/write concurrency."""
    with self._connection() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")  # Best balance for WAL mode
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second timeout
        conn.execute("PRAGMA cache_size=-64000")   # 64MB cache
```

### Pattern 3: Context Manager for Connections
**What:** Auto-commit on success, rollback on exception, close connection
**When to use:** Every database operation
**Example:**
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/container/state.py
@contextmanager
def _connection(self) -> Iterator[sqlite3.Connection]:
    """Context manager for database connections.

    Automatically commits on success, rolls back on exception.
    """
    # For :memory: databases, use persistent connection
    if self._memory_conn is not None:
        try:
            yield self._memory_conn
            self._memory_conn.commit()
        except Exception:
            self._memory_conn.rollback()
            raise
        return

    # For file-based databases, create new connection
    conn = sqlite3.connect(self.db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### Pattern 4: Schema with UNIQUE Constraint for Concurrency Control
**What:** Database enforces one window per case via UNIQUE constraint
**When to use:** Preventing race conditions in concurrent registrations
**Example:**
```python
def _ensure_schema(self) -> None:
    """Create window_registry table if it doesn't exist."""
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
```

### Pattern 5: Lazy Validation with Auto-Cleanup
**What:** Validate window existence on lookup, auto-remove stale entries
**When to use:** Detecting when users manually close windows
**Example:**
```python
def lookup(self, case_number: str, validator: Callable[[str], bool]) -> str | None:
    """Get window ID by case number, auto-validates and removes if stale.

    Args:
        case_number: Salesforce case number
        validator: Callback to check if window still exists

    Returns:
        Window ID if found and valid, None otherwise
    """
    with self._connection() as conn:
        row = conn.execute(
            "SELECT window_id, last_validated FROM window_registry WHERE case_number = ?",
            (case_number,)
        ).fetchone()

        if not row:
            return None

        window_id = row["window_id"]

        # Validate window still exists
        if not validator(window_id):
            # Auto-remove stale entry
            conn.execute("DELETE FROM window_registry WHERE case_number = ?", (case_number,))
            return None

        # Update validation timestamp
        conn.execute(
            "UPDATE window_registry SET last_validated = ? WHERE case_number = ?",
            (int(time.time()), case_number)
        )

        return window_id
```

### Pattern 6: First-Write-Wins via IntegrityError Handling
**What:** Handle UNIQUE constraint violations when concurrent processes register same case
**When to use:** Multiple mc processes might create window for same case simultaneously
**Example:**
```python
def register(self, case_number: str, window_id: str, terminal_type: str) -> bool:
    """Register window ID for case number.

    Args:
        case_number: Salesforce case number
        window_id: Terminal window ID
        terminal_type: Terminal application name

    Returns:
        True if registered, False if already registered by another process
    """
    try:
        with self._connection() as conn:
            now = int(time.time())
            conn.execute(
                """
                INSERT INTO window_registry (case_number, window_id, created_at, terminal_type, last_validated)
                VALUES (?, ?, ?, ?, ?)
                """,
                (case_number, window_id, now, terminal_type, now)
            )
        return True
    except sqlite3.IntegrityError:
        # Another process already registered this case - first write wins
        return False
```

### Pattern 7: Retry with Tenacity for Database Locks
**What:** Exponential backoff retry for OperationalError (database locked)
**When to use:** Operations that might hit concurrent write contention
**Example:**
```python
# Source: Tenacity documentation
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    retry=retry_if_exception_type(sqlite3.OperationalError),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
def register(self, case_number: str, window_id: str, terminal_type: str) -> bool:
    """Register with retry on database lock."""
    # Implementation here
```

### Pattern 8: AppleScript Window ID Retrieval and Validation
**What:** Capture window ID on creation, validate existence by ID
**When to use:** macOS terminal automation (iTerm2, Terminal.app)
**Example:**
```applescript
-- Capture window ID on creation (iTerm2)
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        set name to "CASE:Customer:Description:/path"
        write text "podman exec ..."
    end tell
    -- Return window ID for storage
    return id of current window
end tell

-- Validate window exists by ID (iTerm2)
tell application "iTerm"
    try
        -- Attempt to access window properties
        set windowExists to false
        repeat with theWindow in windows
            if id of theWindow is TARGET_ID then
                set windowExists to true
                exit repeat
            end if
        end repeat
        return windowExists
    on error
        return false
    end try
end tell
```

### Anti-Patterns to Avoid
- **BEGIN DEFERRED transactions in concurrent scenarios:** Causes "database locked" errors on upgrade to write transaction. Use auto-commit (isolation_level=None) instead.
- **Sharing sqlite3.Connection across threads/processes:** Connections are not thread-safe, leads to undefined behavior. Create connection per operation.
- **synchronous=FULL in WAL mode:** Overkill for this use case. NORMAL provides sufficient durability (survives app crashes, tolerates power loss).
- **Not handling IntegrityError on UNIQUE violations:** Expected in concurrent scenarios, must be caught and handled gracefully.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry with exponential backoff | Custom sleep loops | tenacity decorator | Handles edge cases (max retries, jitter), already a dependency |
| Platform-specific data directories | Manual os.path logic | platformdirs.user_data_dir() | Follows XDG standards, handles macOS/Linux/Windows correctly |
| Database connection lifecycle | Manual open/close/commit | Context manager pattern | Prevents leaked connections, ensures rollback on errors |
| Concurrent write coordination | File locking or semaphores | SQLite UNIQUE constraint + WAL mode | Database enforces atomicity, no race conditions |
| Timestamp generation | datetime.now() | int(time.time()) | Simpler, UTC by default, INTEGER type in SQLite |

**Key insight:** SQLite with WAL mode solves the entire concurrency problem. Don't layer additional locking mechanisms on top - let the database do its job.

## Common Pitfalls

### Pitfall 1: Not Enabling WAL Mode Before Creating Tables
**What goes wrong:** Database operates in DELETE journal mode, concurrent reads block writes
**Why it happens:** WAL mode must be set before schema creation, not after
**How to avoid:** Call `_setup_wal_mode()` before `_ensure_schema()` in `__init__`
**Warning signs:** "database is locked" errors even with proper timeouts

### Pitfall 2: Ignoring IntegrityError on Duplicate Registration
**What goes wrong:** Process crashes or logs errors when another process wins race
**Why it happens:** UNIQUE constraint violations are expected in concurrent scenarios
**How to avoid:** Catch sqlite3.IntegrityError, treat as "already registered" (success case)
**Warning signs:** Integration tests fail intermittently with IntegrityError

### Pitfall 3: Using synchronous=FULL in WAL Mode
**What goes wrong:** Unnecessary performance penalty (fsync on every transaction)
**Why it happens:** Copying default settings from non-WAL examples
**How to avoid:** Use synchronous=NORMAL for WAL mode (official SQLite recommendation)
**Warning signs:** Slow database operations (hundreds of ms instead of single-digit ms)

### Pitfall 4: Not Setting busy_timeout
**What goes wrong:** Immediate "database is locked" errors under concurrent load
**Why it happens:** Default timeout is 0 seconds (no retry)
**How to avoid:** Set `PRAGMA busy_timeout=30000` (30 seconds) in setup
**Warning signs:** OperationalError even with retry decorators

### Pitfall 5: Validating on Every Read Instead of Lazy Validation
**What goes wrong:** Performance degradation due to AppleScript calls on every lookup
**Why it happens:** Misunderstanding "validate on lookup" to mean "validate before every read"
**How to avoid:** Validate only in `lookup()` method, not in internal queries
**Warning signs:** Slow response times, AppleScript process spawns on every operation

### Pitfall 6: Assuming Window IDs Are Stable Across Restarts
**What goes wrong:** Stale entries remain after terminal app restart
**Why it happens:** iTerm2/Terminal.app assign new IDs after relaunch
**How to avoid:** Lazy validation detects and removes stale entries automatically
**Warning signs:** Registry has entries but windows don't exist

### Pitfall 7: Hardcoding Database Path
**What goes wrong:** Conflicts with existing installations, violates platform conventions
**Why it happens:** Skipping platformdirs abstraction for simplicity
**How to avoid:** Use `user_data_dir("mc", "redhat")` like StateDatabase
**Warning signs:** Database file in wrong location (~/mc/ instead of ~/.local/share/mc/)

### Pitfall 8: Not Handling :memory: Database Special Case
**What goes wrong:** Tests fail because connection closes between operations
**Why it happens:** :memory: databases don't persist across connection close/reopen
**How to avoid:** Maintain persistent connection for :memory:, new connections for files
**Warning signs:** Test data disappears after operation completes

## Code Examples

Verified patterns from official sources and existing codebase:

### Minimal CRUD Operations
```python
# Source: Existing StateDatabase pattern + user context decisions
class WindowRegistry:
    """Manage window ID mappings with concurrent access support."""

    def register(self, case_number: str, window_id: str, terminal_type: str) -> bool:
        """Register window ID for case (first-write-wins)."""
        try:
            with self._connection() as conn:
                now = int(time.time())
                conn.execute(
                    """
                    INSERT INTO window_registry
                    (case_number, window_id, created_at, terminal_type, last_validated)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (case_number, window_id, now, terminal_type, now)
                )
            return True
        except sqlite3.IntegrityError:
            return False  # Already registered by another process

    def lookup(self, case_number: str, validator: Callable[[str], bool]) -> str | None:
        """Get window ID, validate existence, auto-remove if stale."""
        with self._connection() as conn:
            row = conn.execute(
                "SELECT window_id FROM window_registry WHERE case_number = ?",
                (case_number,)
            ).fetchone()

            if not row:
                return None

            window_id = row["window_id"]

            # Validate and auto-remove if stale
            if not validator(window_id):
                conn.execute(
                    "DELETE FROM window_registry WHERE case_number = ?",
                    (case_number,)
                )
                return None

            # Update validation timestamp
            conn.execute(
                "UPDATE window_registry SET last_validated = ? WHERE case_number = ?",
                (int(time.time()), case_number)
            )

            return window_id

    def remove(self, case_number: str) -> None:
        """Explicitly remove registry entry."""
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM window_registry WHERE case_number = ?",
                (case_number,)
            )
```

### Testing Pattern with :memory: Database
```python
# Source: /Users/dsquirre/Repos/mc/tests/unit/test_container_state.py
def test_register_and_lookup(tmp_path):
    """Test basic registry operations."""
    db = WindowRegistry(str(tmp_path / "test.db"))

    # Register window
    success = db.register("12345678", "window-id-123", "iTerm2")
    assert success is True

    # Lookup with validator
    def validator(window_id):
        return True  # Simulate window exists

    window_id = db.lookup("12345678", validator)
    assert window_id == "window-id-123"

def test_duplicate_registration():
    """Test first-write-wins behavior."""
    db = WindowRegistry(":memory:")

    # First registration succeeds
    assert db.register("12345678", "window-1", "iTerm2") is True

    # Second registration fails (IntegrityError caught)
    assert db.register("12345678", "window-2", "iTerm2") is False

def test_stale_entry_removal(tmp_path):
    """Test auto-cleanup of stale entries."""
    db = WindowRegistry(str(tmp_path / "test.db"))
    db.register("12345678", "window-id-123", "iTerm2")

    # Validator returns False (window closed)
    def validator(window_id):
        return False

    # Lookup returns None and removes entry
    assert db.lookup("12345678", validator) is None

    # Entry is gone
    def always_true(window_id):
        return True

    assert db.lookup("12345678", always_true) is None
```

### AppleScript Window Validation
```python
# Source: iTerm2 documentation + existing macos.py patterns
def _window_exists_by_id(self, window_id: str) -> bool:
    """Check if window with ID still exists via AppleScript.

    Args:
        window_id: Window ID to validate

    Returns:
        True if window exists, False otherwise
    """
    if not shutil.which("osascript"):
        return False

    escaped_id = self._escape_applescript(window_id)

    if self.terminal == "iTerm2":
        script = f'''
tell application "iTerm"
    try
        repeat with theWindow in windows
            if (id of theWindow as text) is "{escaped_id}" then
                return true
            end if
        end repeat
        return false
    on error
        return false
    end try
end tell
'''
    else:  # Terminal.app
        script = f'''
tell application "Terminal"
    try
        repeat with theWindow in windows
            if (id of theWindow as text) is "{escaped_id}" then
                return true
            end if
        end repeat
        return false
    on error
        return false
    end try
end tell
'''

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == "true"
    except Exception:
        return False
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| BEGIN DEFERRED | Auto-commit (isolation_level=None) | WAL mode adoption | Eliminates lock upgrade failures |
| synchronous=FULL | synchronous=NORMAL in WAL | SQLite 3.7+ (2010) | 2-3x write performance, adequate durability |
| Manual retry loops | tenacity decorators | ~2020 (library maturity) | Cleaner code, better jitter handling |
| appdirs | platformdirs | 2021 (appdirs deprecated) | Active maintenance, better XDG support |

**Deprecated/outdated:**
- **appdirs library:** Replaced by platformdirs (still works but unmaintained)
- **DELETE journal mode:** WAL mode is superior for concurrent access (default in many modern tools)
- **Manual file locking for SQLite:** SQLite's internal locking is sufficient with WAL mode

## Open Questions

Things that couldn't be fully resolved:

1. **Window ID format/stability across iTerm2 versions**
   - What we know: iTerm2 exposes `id` property on window objects, designed for system commands
   - What's unclear: Whether ID format changed between major versions, ID reuse behavior
   - Recommendation: Test with multiple iTerm2 versions, store as TEXT to handle any format

2. **Terminal.app window ID behavior**
   - What we know: Terminal.app has `id` property per AppleScript standard
   - What's unclear: ID persistence across Terminal.app restarts, ID uniqueness guarantees
   - Recommendation: Lazy validation handles stale IDs, test manually with Terminal.app

3. **Optimal busy_timeout value**
   - What we know: Default 0s is too low, 30s is recommended for web apps, SQLite retries with exponential backoff
   - What's unclear: Ideal timeout for CLI tool with 1-5 concurrent processes
   - Recommendation: Start with 30s (follows existing StateDatabase), adjust if timeouts occur in integration tests

4. **WAL checkpoint behavior under concurrent load**
   - What we know: Auto-checkpoint at 1000 pages, PASSIVE mode by default, can be impeded by long readers
   - What's unclear: Whether registry workload (small transactions, frequent reads) will hit checkpoint issues
   - Recommendation: Monitor WAL file size in integration tests, force checkpoint if >1000 pages (unlikely)

## Sources

### Primary (HIGH confidence)
- [SQLite WAL Mode Official Documentation](https://sqlite.org/wal.html) - Concurrency model, limitations, performance
- [SQLite PRAGMA Settings](https://sqlite.org/pragma.html) - Recommended settings for WAL mode
- [Python sqlite3 Module](https://docs.python.org/3/library/sqlite3.html) - Version 3.50.4 in Python 3.13.7
- Existing codebase: `/Users/dsquirre/Repos/mc/src/mc/container/state.py` - Proven StateDatabase pattern
- Existing codebase: `/Users/dsquirre/Repos/mc/tests/unit/test_container_state.py` - Testing patterns
- [iTerm2 Scripting Documentation](https://iterm2.com/documentation-scripting.html) - Window ID property

### Secondary (MEDIUM confidence)
- [Charles Leifer - Going Fast with SQLite and Python](https://charlesleifer.com/blog/going-fast-with-sqlite-and-python/) - PRAGMA recommendations
- [Tenacity Documentation](https://tenacity.readthedocs.io/) - Retry patterns with exponential backoff
- [platformdirs PyPI](https://pypi.org/project/platformdirs/) - Platform-specific directory standards
- [SQLite Concurrency Best Practices](https://www.sqliteforum.com/p/handling-concurrency-in-sqlite-best) - Community patterns
- [Python SQLite Concurrent Writes Tutorial](https://www.pythontutorials.net/blog/concurrent-writing-with-sqlite3/) - Practical examples

### Tertiary (LOW confidence)
- WebSearch: AppleScript window ID behavior - Limited documentation, mostly community discussions
- WebSearch: Terminal.app window validation - No official Apple docs found, inferred from iTerm2 patterns

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified in existing codebase, sqlite3 version confirmed
- Architecture: HIGH - StateDatabase provides proven reference, patterns tested in production
- Pitfalls: MEDIUM - Identified from research + existing code, but not all experienced directly
- AppleScript window IDs: MEDIUM - Official iTerm2 docs confirm `id` property, Terminal.app behavior inferred

**Research date:** 2026-02-08
**Valid until:** 2026-03-08 (30 days - stable domain)
**Python version:** 3.13.7 (from pyproject.toml: >=3.11)
**SQLite version:** 3.50.4 (verified via python3 -c check)
**Key dependencies:** All required libraries already in pyproject.toml
