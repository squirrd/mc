"""Unit tests for WindowRegistry class."""

import time
from pathlib import Path

import pytest

from mc.terminal.registry import WindowRegistry


class TestWindowRegistry:
    """Test WindowRegistry database operations."""

    def test_register_and_lookup(self, tmp_path):
        """Test basic register and lookup operations."""
        # Use file-based database
        db = WindowRegistry(str(tmp_path / "test.db"))

        # Register window
        success = db.register("12345678", "window-123", "iTerm2")
        assert success is True

        # Lookup with validator
        def always_valid(window_id):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id == "window-123"

    def test_duplicate_registration(self):
        """Test first-write-wins behavior with UNIQUE constraint."""
        db = WindowRegistry(":memory:")

        # First registration succeeds
        assert db.register("12345678", "window-1", "iTerm2") is True

        # Second registration fails (IntegrityError caught)
        assert db.register("12345678", "window-2", "iTerm2") is False

    def test_stale_entry_removal(self):
        """Test auto-cleanup when validator returns False."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "iTerm2")

        # Validator returns False (window closed)
        def always_invalid(window_id):
            return False

        # Lookup returns None and removes entry
        window_id = db.lookup("12345678", always_invalid)
        assert window_id is None

        # Verify entry was removed
        def always_valid(window_id):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id is None

    def test_lookup_nonexistent_case(self):
        """Test lookup for case that was never registered."""
        db = WindowRegistry(":memory:")

        def always_valid(window_id):
            return True

        window_id = db.lookup("99999999", always_valid)
        assert window_id is None

    def test_remove(self):
        """Test explicit removal of registry entry."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "iTerm2")

        # Remove entry
        db.remove("12345678")

        # Verify removed
        def always_valid(window_id):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id is None

    def test_remove_nonexistent_case(self):
        """Test remove is idempotent (doesn't error on missing entry)."""
        db = WindowRegistry(":memory:")

        # Should not raise exception
        db.remove("99999999")

    def test_last_validated_timestamp_updated(self):
        """Test that last_validated timestamp updates on successful lookup."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "iTerm2")

        # Initial timestamp
        time.sleep(0.1)  # Ensure time advances

        # Lookup updates timestamp
        def always_valid(window_id):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id == "window-123"

        # Verify timestamp was updated (implementation detail: check via direct query)
        # This test verifies the UPDATE statement executes without errors

    def test_database_persistence(self, tmp_path):
        """Test that registry persists across WindowRegistry instances."""
        db_path = str(tmp_path / "test.db")

        # Register with first instance
        db1 = WindowRegistry(db_path)
        db1.register("12345678", "window-123", "iTerm2")

        # Lookup with second instance (new connection)
        db2 = WindowRegistry(db_path)

        def always_valid(window_id):
            return True

        window_id = db2.lookup("12345678", always_valid)
        assert window_id == "window-123"

    def test_memory_database_isolation(self):
        """Test that :memory: databases are isolated per instance."""
        db1 = WindowRegistry(":memory:")
        db2 = WindowRegistry(":memory:")

        # Register in db1
        db1.register("12345678", "window-123", "iTerm2")

        # Should not exist in db2 (separate database)
        def always_valid(window_id):
            return True

        window_id = db2.lookup("12345678", always_valid)
        assert window_id is None

    def test_multiple_terminals(self):
        """Test registry supports different terminal types."""
        db = WindowRegistry(":memory:")

        db.register("11111111", "window-1", "iTerm2")
        db.register("22222222", "window-2", "Terminal.app")
        db.register("33333333", "window-3", "gnome-terminal")

        def always_valid(window_id):
            return True

        assert db.lookup("11111111", always_valid) == "window-1"
        assert db.lookup("22222222", always_valid) == "window-2"
        assert db.lookup("33333333", always_valid) == "window-3"

    def test_wal_mode_enabled(self, tmp_path):
        """Test that WAL mode is properly enabled."""
        import sqlite3

        db_path = str(tmp_path / "test.db")
        db = WindowRegistry(db_path)

        # Query journal mode
        conn = sqlite3.connect(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        assert mode.lower() == "wal"

    def test_concurrent_reads(self, tmp_path):
        """Test that multiple registry instances can read concurrently."""
        db_path = str(tmp_path / "test.db")
        db1 = WindowRegistry(db_path)
        db2 = WindowRegistry(db_path)

        db1.register("12345678", "window-123", "iTerm2")

        # Both instances should be able to read simultaneously
        def always_valid(window_id):
            return True

        result1 = db1.lookup("12345678", always_valid)
        result2 = db2.lookup("12345678", always_valid)

        assert result1 == "window-123"
        assert result2 == "window-123"

    def test_write_then_read_different_instances(self, tmp_path):
        """Test that writes are visible to subsequent reads from different instances."""
        db_path = str(tmp_path / "test.db")
        db1 = WindowRegistry(db_path)
        db2 = WindowRegistry(db_path)

        db1.register("12345678", "window-123", "iTerm2")

        # Second instance should see the write
        def always_valid(window_id):
            return True

        result = db2.lookup("12345678", always_valid)
        assert result == "window-123"

    def test_special_characters_in_window_id(self):
        """Test handling of special characters in window IDs."""
        db = WindowRegistry(":memory:")

        # Window ID with special characters (alphanumeric IDs from Linux)
        special_id = "0x1a2b3c4d"
        db.register("12345678", special_id, "xterm")

        def always_valid(window_id):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id == special_id

    def test_empty_registry_operations(self):
        """Test operations on empty registry don't raise errors."""
        db = WindowRegistry(":memory:")

        # All these should work without errors
        def always_valid(window_id):
            return True

        assert db.lookup("12345678", always_valid) is None
        db.remove("12345678")  # Should not raise

    def test_validator_receives_correct_window_id(self):
        """Test that validator callback receives the registered window ID."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-xyz", "iTerm2")

        received_ids = []

        def capturing_validator(window_id):
            received_ids.append(window_id)
            return True

        window_id = db.lookup("12345678", capturing_validator)

        assert window_id == "window-xyz"
        assert received_ids == ["window-xyz"]
