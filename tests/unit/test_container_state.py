"""Unit tests for container state management."""

import sqlite3
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from mc.container.models import ContainerMetadata
from mc.container.state import StateDatabase


class TestStateDatabaseInit:
    """Tests for StateDatabase initialization."""

    def test_init_with_custom_path(self, tmp_path):
        """Test initialization with custom database path."""
        db_path = tmp_path / "test.db"
        db = StateDatabase(str(db_path))

        assert db.db_path == str(db_path)
        assert db_path.exists()

    def test_init_with_default_path(self, mocker, tmp_path):
        """Test initialization with default platform path."""
        # Use real temp directory to avoid database file creation issues
        mock_dir = str(tmp_path / "fake_data_dir")
        mocker.patch("mc.container.state.user_data_dir", return_value=mock_dir)

        db = StateDatabase()

        assert db.db_path == f"{mock_dir}/containers.db"

    def test_init_memory_database(self):
        """Test initialization with in-memory database."""
        db = StateDatabase(":memory:")

        assert db.db_path == ":memory:"
        assert db._memory_conn is not None

    def test_wal_mode_enabled(self, tmp_path):
        """Test that WAL mode is properly enabled."""
        db_path = tmp_path / "test.db"
        db = StateDatabase(str(db_path))

        # Query journal mode
        conn = sqlite3.connect(str(db_path))
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        assert mode.lower() == "wal"

    def test_schema_created(self, tmp_path):
        """Test that schema is created on initialization."""
        db_path = tmp_path / "test.db"
        db = StateDatabase(str(db_path))

        # Check table exists
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='containers'"
        )
        tables = cursor.fetchall()
        conn.close()

        assert len(tables) == 1
        assert tables[0][0] == "containers"

    def test_indices_created(self, tmp_path):
        """Test that indices are created on initialization."""
        db_path = tmp_path / "test.db"
        db = StateDatabase(str(db_path))

        # Check indices exist
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='containers'"
        )
        indices = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "idx_container_id" in indices
        assert "idx_created_at" in indices


class TestCRUDOperations:
    """Tests for CRUD operations."""

    def test_add_container(self, tmp_path):
        """Test adding a container to state."""
        db = StateDatabase(str(tmp_path / "test.db"))

        db.add_container("12345678", "abc123", "/path/to/workspace")

        result = db.get_container("12345678")
        assert result is not None
        assert result.case_number == "12345678"
        assert result.container_id == "abc123"
        assert result.workspace_path == "/path/to/workspace"

    def test_add_container_duplicate_case_number(self, tmp_path):
        """Test that adding duplicate case_number raises IntegrityError."""
        db = StateDatabase(str(tmp_path / "test.db"))

        db.add_container("12345678", "abc123", "/path/to/workspace")

        with pytest.raises(sqlite3.IntegrityError):
            db.add_container("12345678", "different_id", "/different/path")

    def test_add_container_sets_timestamps(self, tmp_path):
        """Test that add_container sets created_at and updated_at."""
        db = StateDatabase(str(tmp_path / "test.db"))

        before = int(time.time())
        db.add_container("12345678", "abc123", "/path/to/workspace")
        after = int(time.time())

        result = db.get_container("12345678")
        assert result is not None
        assert before <= result.created_at <= after
        assert before <= result.updated_at <= after
        assert result.created_at == result.updated_at

    def test_get_container_exists(self, tmp_path):
        """Test getting an existing container."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("12345678", "abc123", "/path/to/workspace")

        result = db.get_container("12345678")

        assert result is not None
        assert isinstance(result, ContainerMetadata)
        assert result.case_number == "12345678"

    def test_get_container_not_exists(self, tmp_path):
        """Test getting a non-existent container returns None."""
        db = StateDatabase(str(tmp_path / "test.db"))

        result = db.get_container("99999999")

        assert result is None

    def test_list_all_empty(self, tmp_path):
        """Test listing all containers when database is empty."""
        db = StateDatabase(str(tmp_path / "test.db"))

        results = db.list_all()

        assert results == []

    def test_list_all_multiple(self, tmp_path):
        """Test listing all containers with multiple entries."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # Add containers with slight time delay to test ordering
        db.add_container("11111111", "id1", "/path1")
        time.sleep(0.01)
        db.add_container("22222222", "id2", "/path2")
        time.sleep(0.01)
        db.add_container("33333333", "id3", "/path3")

        results = db.list_all()

        assert len(results) == 3
        # Should be ordered by created_at DESC (newest first)
        assert results[0].case_number == "33333333"
        assert results[1].case_number == "22222222"
        assert results[2].case_number == "11111111"

    def test_delete_container_exists(self, tmp_path):
        """Test deleting an existing container."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("12345678", "abc123", "/path/to/workspace")

        db.delete_container("12345678")

        result = db.get_container("12345678")
        assert result is None

    def test_delete_container_not_exists(self, tmp_path):
        """Test deleting a non-existent container (should not raise error)."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # Should not raise exception
        db.delete_container("99999999")

    def test_update_container_single_field(self, tmp_path, mocker):
        """Test updating a single field."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # Mock time to have predictable timestamps
        mock_time = mocker.patch("mc.container.state.time.time")
        mock_time.return_value = 1000.0

        db.add_container("12345678", "abc123", "/path/to/workspace")
        original = db.get_container("12345678")

        # Advance time for update
        mock_time.return_value = 2000.0
        db.update_container("12345678", container_id="new_id")

        updated = db.get_container("12345678")
        assert updated is not None
        assert updated.container_id == "new_id"
        assert updated.workspace_path == "/path/to/workspace"
        assert updated.updated_at > original.updated_at
        assert updated.created_at == original.created_at

    def test_update_container_multiple_fields(self, tmp_path):
        """Test updating multiple fields."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("12345678", "abc123", "/path/to/workspace")

        db.update_container(
            "12345678", container_id="new_id", workspace_path="/new/path"
        )

        updated = db.get_container("12345678")
        assert updated is not None
        assert updated.container_id == "new_id"
        assert updated.workspace_path == "/new/path"

    def test_update_container_no_fields(self, tmp_path):
        """Test updating with no fields raises ValueError."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("12345678", "abc123", "/path/to/workspace")

        with pytest.raises(ValueError, match="No fields provided to update"):
            db.update_container("12345678")


class TestReconciliation:
    """Tests for state reconciliation."""

    def test_reconcile_no_orphans(self, tmp_path):
        """Test reconciliation when all state matches Podman."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("11111111", "id1", "/path1")
        db.add_container("22222222", "id2", "/path2")

        # All containers still exist in Podman
        podman_ids = {"id1", "id2"}
        db.reconcile(podman_ids)

        # Both containers should still be in state
        assert db.get_container("11111111") is not None
        assert db.get_container("22222222") is not None

    def test_reconcile_removes_orphans(self, tmp_path):
        """Test reconciliation removes orphaned state."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("11111111", "id1", "/path1")
        db.add_container("22222222", "id2", "/path2")
        db.add_container("33333333", "id3", "/path3")

        # Only id1 and id3 exist in Podman (id2 was externally deleted)
        podman_ids = {"id1", "id3"}
        db.reconcile(podman_ids)

        # id2's container should be removed from state
        assert db.get_container("11111111") is not None
        assert db.get_container("22222222") is None
        assert db.get_container("33333333") is not None

    def test_reconcile_removes_all(self, tmp_path):
        """Test reconciliation when all containers deleted externally."""
        db = StateDatabase(str(tmp_path / "test.db"))
        db.add_container("11111111", "id1", "/path1")
        db.add_container("22222222", "id2", "/path2")

        # No containers exist in Podman
        podman_ids = set()
        db.reconcile(podman_ids)

        # All containers should be removed
        assert db.get_container("11111111") is None
        assert db.get_container("22222222") is None
        assert db.list_all() == []

    def test_reconcile_empty_state(self, tmp_path):
        """Test reconciliation with empty state database."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # Should not raise exception
        db.reconcile({"id1", "id2"})

        assert db.list_all() == []


class TestConcurrency:
    """Tests for concurrent operations (WAL mode)."""

    def test_concurrent_reads(self, tmp_path):
        """Test that multiple reads can happen concurrently."""
        db_path = tmp_path / "test.db"
        db1 = StateDatabase(str(db_path))
        db2 = StateDatabase(str(db_path))

        db1.add_container("12345678", "abc123", "/path/to/workspace")

        # Both instances should be able to read simultaneously
        result1 = db1.get_container("12345678")
        result2 = db2.get_container("12345678")

        assert result1 is not None
        assert result2 is not None
        assert result1.container_id == result2.container_id

    def test_write_then_read(self, tmp_path):
        """Test that writes are visible to subsequent reads."""
        db_path = tmp_path / "test.db"
        db1 = StateDatabase(str(db_path))
        db2 = StateDatabase(str(db_path))

        db1.add_container("12345678", "abc123", "/path/to/workspace")

        # Second instance should see the write
        result = db2.get_container("12345678")
        assert result is not None
        assert result.container_id == "abc123"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_memory_database_persistence(self):
        """Test that :memory: database maintains state across operations."""
        db = StateDatabase(":memory:")

        db.add_container("12345678", "abc123", "/path/to/workspace")
        result = db.get_container("12345678")

        assert result is not None
        assert result.container_id == "abc123"

    def test_special_characters_in_paths(self, tmp_path):
        """Test handling of special characters in workspace paths."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # Workspace path with special characters
        special_path = "/path/with spaces/and'quotes/and\"doublequotes"
        db.add_container("12345678", "abc123", special_path)

        result = db.get_container("12345678")
        assert result is not None
        assert result.workspace_path == special_path

    def test_long_case_numbers(self, tmp_path):
        """Test handling of long case numbers."""
        db = StateDatabase(str(tmp_path / "test.db"))

        long_case = "1234567890" * 5  # 50 characters
        db.add_container(long_case, "abc123", "/path/to/workspace")

        result = db.get_container(long_case)
        assert result is not None
        assert result.case_number == long_case

    def test_empty_database_operations(self, tmp_path):
        """Test operations on empty database don't raise errors."""
        db = StateDatabase(str(tmp_path / "test.db"))

        # All these should work without errors
        assert db.get_container("12345678") is None
        assert db.list_all() == []
        db.delete_container("12345678")  # Should not raise
        db.reconcile(set())  # Should not raise
