"""SQLite-based state management for container metadata."""

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from platformdirs import user_data_dir

from mc.container.models import ContainerMetadata


class StateDatabase:
    """Manage container state in SQLite database with WAL mode.

    Provides CRUD operations for container metadata and reconciliation
    to detect external Podman operations.
    """

    def __init__(self, db_path: str | None = None):
        """Initialize state database.

        Args:
            db_path: Path to SQLite database file. If None, uses platform-appropriate
                     default location (~/.local/share/mc/containers.db on Linux,
                     ~/Library/Application Support/mc/containers.db on macOS).
        """
        if db_path is None:
            data_dir = user_data_dir("mc", "redhat")
            os.makedirs(data_dir, exist_ok=True)
            db_path = os.path.join(data_dir, "containers.db")

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
        """
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")

    def _ensure_schema(self) -> None:
        """Create containers table and indices if they don't exist."""
        with self._connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS containers (
                    case_number TEXT PRIMARY KEY,
                    container_id TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_container_id ON containers(container_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_created_at ON containers(created_at)"
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

    def add_container(
        self, case_number: str, container_id: str, workspace_path: str
    ) -> None:
        """Add container to state database.

        Args:
            case_number: Salesforce case number
            container_id: Podman container ID
            workspace_path: Host workspace directory path

        Raises:
            sqlite3.IntegrityError: If case_number already exists
        """
        with self._connection() as conn:
            now = int(time.time())
            conn.execute(
                """
                INSERT INTO containers (case_number, container_id, workspace_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (case_number, container_id, workspace_path, now, now),
            )

    def get_container(self, case_number: str) -> ContainerMetadata | None:
        """Get container metadata by case number.

        Args:
            case_number: Salesforce case number

        Returns:
            ContainerMetadata if found, None otherwise
        """
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT case_number, container_id, workspace_path, created_at, updated_at
                FROM containers
                WHERE case_number = ?
                """,
                (case_number,),
            ).fetchone()

            if row:
                return ContainerMetadata(
                    case_number=row["case_number"],
                    container_id=row["container_id"],
                    workspace_path=row["workspace_path"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None

    def list_all(self) -> list[ContainerMetadata]:
        """List all containers in state.

        Returns:
            List of ContainerMetadata ordered by created_at descending (newest first)
        """
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT case_number, container_id, workspace_path, created_at, updated_at
                FROM containers
                ORDER BY created_at DESC
                """
            ).fetchall()

            return [
                ContainerMetadata(
                    case_number=row["case_number"],
                    container_id=row["container_id"],
                    workspace_path=row["workspace_path"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in rows
            ]

    def delete_container(self, case_number: str) -> None:
        """Delete container from state.

        Args:
            case_number: Salesforce case number
        """
        with self._connection() as conn:
            conn.execute("DELETE FROM containers WHERE case_number = ?", (case_number,))

    def update_container(self, case_number: str, **kwargs: str | int) -> None:
        """Update container metadata.

        Args:
            case_number: Salesforce case number
            **kwargs: Fields to update (container_id, workspace_path, etc.)

        Raises:
            ValueError: If no fields provided to update
        """
        if not kwargs:
            raise ValueError("No fields provided to update")

        # Always update updated_at
        kwargs["updated_at"] = int(time.time())

        # Build UPDATE query dynamically
        fields = ", ".join(f"{field} = ?" for field in kwargs.keys())
        values = list(kwargs.values()) + [case_number]

        with self._connection() as conn:
            conn.execute(
                f"UPDATE containers SET {fields} WHERE case_number = ?",
                values,
            )

    def reconcile(self, podman_container_ids: set[str]) -> None:
        """Reconcile state with Podman reality.

        Deletes state entries for containers that no longer exist in Podman.
        This detects external deletions (e.g., user ran 'podman rm').

        Args:
            podman_container_ids: Set of container IDs currently in Podman
        """
        with self._connection() as conn:
            # Get all state containers
            rows = conn.execute(
                "SELECT case_number, container_id FROM containers"
            ).fetchall()

            # Delete orphaned state (container_id not in Podman)
            for row in rows:
                if row["container_id"] not in podman_container_ids:
                    conn.execute(
                        "DELETE FROM containers WHERE case_number = ?",
                        (row["case_number"],),
                    )
