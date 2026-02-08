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

        self._setup_wal_mode()
        self._ensure_schema()

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
