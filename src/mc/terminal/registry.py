"""SQLite-based window ID registry for terminal tracking."""

import os
import sqlite3
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from platformdirs import user_data_dir


class WindowRegistry:
    """Manage terminal window ID mappings in SQLite database with WAL mode.

    Provides registration and lookup of terminal window IDs by case number,
    with lazy validation and auto-cleanup of stale entries.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize window registry.

        Args:
            db_path: Path to SQLite database file. If None, uses platform-appropriate
                     default location (~/.local/share/mc/window.db on Linux,
                     ~/Library/Application Support/mc/window.db on macOS).
                     Special value ":memory:" creates in-memory database for testing.
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

        # Try to initialize database with corruption recovery
        try:
            self._setup_wal_mode()
            self._ensure_schema()
        except sqlite3.DatabaseError:
            # Database corrupted - delete and recreate (graceful recovery)
            # Only for file-based databases (not :memory:)
            if db_path != ":memory:" and os.path.exists(db_path):
                import logging
                logger = logging.getLogger(__name__)
                logger.warning("Window registry database corrupted, recreating: %s", db_path)

                # Remove corrupted database file and WAL/SHM files
                try:
                    os.remove(db_path)
                    if os.path.exists(f"{db_path}-wal"):
                        os.remove(f"{db_path}-wal")
                    if os.path.exists(f"{db_path}-shm"):
                        os.remove(f"{db_path}-shm")
                except OSError:
                    pass  # Best effort cleanup

                # Retry initialization with fresh database
                self._setup_wal_mode()
                self._ensure_schema()
            else:
                # :memory: database or file doesn't exist - re-raise
                raise

    def _setup_wal_mode(self) -> None:
        """Enable WAL mode for better read/write concurrency.

        WAL mode allows multiple concurrent readers and one writer,
        preventing "database is locked" errors.

        Configuration:
        - journal_mode=WAL: Write-Ahead Logging for concurrent access
        - synchronous=NORMAL: Best balance for WAL mode (survives app crashes)
        - busy_timeout=30000: 30-second timeout for lock acquisition
        - cache_size=-64000: 64MB page cache (negative = KB, positive = pages)
        """
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA cache_size=-64000")

    def _ensure_schema(self) -> None:
        """Create window_registry table and indices if they don't exist.

        Schema:
        - case_number: Primary key, unique identifier for the case
        - window_id: Terminal window identifier (macOS numeric, Linux alphanumeric)
        - created_at: Unix timestamp when entry was first registered
        - terminal_type: Type of terminal (iTerm2, Terminal.app, xterm, etc.)
        - last_validated: Unix timestamp when window existence was last validated
        """
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
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_last_validated ON window_registry(last_validated)"
            )

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for database connections.

        Automatically commits on success, rolls back on exception,
        and always closes connection (except for :memory: databases).

        Yields:
            SQLite connection with Row factory enabled
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

    def register(self, case_number: str, window_id: str, terminal_type: str) -> bool:
        """Register a window ID for a case number.

        Uses first-write-wins behavior via UNIQUE constraint on case_number.
        If case_number already registered, returns False without modification.

        Args:
            case_number: Salesforce case number
            window_id: Terminal window identifier
            terminal_type: Type of terminal (iTerm2, Terminal.app, etc.)

        Returns:
            True if registration successful, False if case_number already registered
        """
        try:
            with self._connection() as conn:
                now = int(time.time())
                conn.execute(
                    """
                    INSERT INTO window_registry (case_number, window_id, created_at, terminal_type, last_validated)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (case_number, window_id, now, terminal_type, now),
                )
                return True
        except sqlite3.IntegrityError:
            # UNIQUE constraint violation - case_number already registered
            return False

    def lookup(self, case_number: str, validator: Callable[[str], bool]) -> str | None:
        """Look up window ID for a case number with lazy validation.

        Validates that window still exists using provided validator callback.
        Auto-removes stale entries if validation fails (self-healing registry).

        Args:
            case_number: Salesforce case number
            validator: Callback that returns True if window_id still exists

        Returns:
            window_id if found and valid, None if not found or validation failed
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT window_id
                FROM window_registry
                WHERE case_number = ?
                """,
                (case_number,),
            ).fetchone()

            if row is None:
                return None

            window_id = row["window_id"]

            # Lazy validation - check if window still exists
            if not validator(window_id):
                # Auto-cleanup: remove stale entry
                conn.execute(
                    "DELETE FROM window_registry WHERE case_number = ?",
                    (case_number,),
                )
                return None

            # Update last_validated timestamp
            conn.execute(
                """
                UPDATE window_registry
                SET last_validated = ?
                WHERE case_number = ?
                """,
                (int(time.time()), case_number),
            )

            return window_id

    def remove(self, case_number: str) -> None:
        """Remove a window ID registration.

        Idempotent operation - no error if case_number not found.

        Args:
            case_number: Salesforce case number
        """
        with self._connection() as conn:
            conn.execute(
                "DELETE FROM window_registry WHERE case_number = ?",
                (case_number,),
            )

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
                logger.info("Removed stale window registry entry for case %s", case_number)

        return removed_count
