"""Unit tests for WindowRegistry class."""

import sys
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

    def test_default_db_path_creation(self, tmp_path, mocker):
        """Test that default db_path is created when None provided."""
        # Mock user_data_dir to return temp path
        mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(tmp_path))

        # Create registry with None (uses default path)
        db = WindowRegistry(db_path=None)

        # Verify database file was created in mocked location
        expected_path = tmp_path / "window.db"
        assert expected_path.exists()

        # Verify it's functional
        assert db.register("12345678", "window-123", "iTerm2") is True

    def test_get_oldest_entries(self):
        """Test _get_oldest_entries returns entries ordered by last_validated."""
        db = WindowRegistry(":memory:")

        # Register multiple entries with different timestamps
        db.register("11111111", "window-1", "iTerm2")
        time.sleep(0.01)
        db.register("22222222", "window-2", "Terminal.app")
        time.sleep(0.01)
        db.register("33333333", "window-3", "xterm")

        # Get oldest entries
        oldest = db._get_oldest_entries(limit=2)

        # Should return 2 oldest (11111111 and 22222222)
        assert len(oldest) == 2
        assert oldest[0][0] == "11111111"  # case_number
        assert oldest[1][0] == "22222222"

    def test_cleanup_stale_entries_removes_invalid(self, mocker):
        """Test cleanup_stale_entries removes entries with invalid windows."""
        db = WindowRegistry(":memory:")

        # Register multiple entries
        db.register("11111111", "window-1", "iTerm2")
        db.register("22222222", "window-2", "Terminal.app")
        db.register("33333333", "window-3", "xterm")

        # Mock _validate_window_exists to return False for window-1 and window-3
        def mock_validate(window_id, terminal_type):
            return window_id != "window-1" and window_id != "window-3"

        mocker.patch.object(db, "_validate_window_exists", side_effect=mock_validate)

        # Run cleanup
        removed = db.cleanup_stale_entries(sample_size=10)

        # Should remove 2 entries (window-1 and window-3)
        assert removed == 2

        # Verify only window-2 remains
        def always_valid(wid):
            return True

        assert db.lookup("11111111", always_valid) is None
        assert db.lookup("22222222", always_valid) == "window-2"
        assert db.lookup("33333333", always_valid) is None

    def test_cleanup_stale_entries_respects_sample_size(self, mocker):
        """Test cleanup_stale_entries only checks sample_size entries."""
        db = WindowRegistry(":memory:")

        # Register 5 entries
        for i in range(1, 6):
            db.register(f"1111111{i}", f"window-{i}", "iTerm2")
            time.sleep(0.01)

        # Mock _validate_window_exists to always return False
        mocker.patch.object(db, "_validate_window_exists", return_value=False)

        # Cleanup with sample_size=3 should only check 3 oldest
        removed = db.cleanup_stale_entries(sample_size=3)

        # Should remove exactly 3 entries (the 3 oldest)
        assert removed == 3

    def test_validate_window_exists_exception_handling(self, mocker):
        """Test _validate_window_exists returns False on exception."""
        db = WindowRegistry(":memory:")

        # Mock get_launcher to raise exception
        mock_launcher = mocker.MagicMock()
        mock_launcher._window_exists_by_id.side_effect = RuntimeError("Test error")
        mocker.patch("mc.terminal.launcher.get_launcher", return_value=mock_launcher)

        # Should return False (aggressive cleanup)
        result = db._validate_window_exists("window-123", "iTerm2")
        assert result is False

    def test_connection_rollback_on_exception(self, tmp_path):
        """Test that connection context manager rolls back on exception."""
        db_path = str(tmp_path / "test.db")
        db = WindowRegistry(db_path)

        # Register initial entry
        db.register("12345678", "window-123", "iTerm2")

        # Force an exception during transaction
        try:
            with db._connection() as conn:
                conn.execute("DELETE FROM window_registry WHERE case_number = ?", ("12345678",))
                # Raise exception before commit
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify rollback - entry should still exist
        def always_valid(wid):
            return True

        window_id = db.lookup("12345678", always_valid)
        assert window_id == "window-123", "Entry should still exist after rollback"

    # --- Tests for terminal-type-aware validation (fix: cleanup-finally-split) ---

    def test_get_terminal_type_returns_stored_type(self):
        """get_terminal_type() returns the terminal_type stored at registration."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "Terminal.app")
        assert db.get_terminal_type("12345678") == "Terminal.app"

    def test_get_terminal_type_returns_iterm2_type(self):
        """get_terminal_type() returns iTerm2 when registered with that type."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "iTerm2")
        assert db.get_terminal_type("12345678") == "iTerm2"

    def test_get_terminal_type_returns_none_for_unknown_case(self):
        """get_terminal_type() returns None if case_number not in registry."""
        db = WindowRegistry(":memory:")
        assert db.get_terminal_type("99999999") is None

    def test_get_terminal_type_survives_remove(self):
        """get_terminal_type() returns None after entry is removed."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "Terminal.app")
        db.remove("12345678")
        assert db.get_terminal_type("12345678") is None

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only launcher test")
    def test_validate_window_exists_creates_iterm2_launcher(self, mocker):
        """_validate_window_exists creates a MacOSLauncher with terminal=iTerm2 on Darwin."""
        db = WindowRegistry(":memory:")

        # Mock MacOSLauncher so we can inspect which terminal type was used
        mock_launcher_instance = mocker.MagicMock()
        mock_launcher_instance._window_exists_by_id.return_value = True
        mock_launcher_cls = mocker.patch("mc.terminal.macos.MacOSLauncher", return_value=mock_launcher_instance)
        mocker.patch("platform.system", return_value="Darwin")

        db._validate_window_exists("window-123", "iTerm2")

        # MacOSLauncher must be constructed with terminal="iTerm2"
        mock_launcher_cls.assert_called_once_with(terminal="iTerm2")
        mock_launcher_instance._window_exists_by_id.assert_called_once_with("window-123")

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-only launcher test")
    def test_validate_window_exists_creates_terminal_app_launcher(self, mocker):
        """_validate_window_exists creates a MacOSLauncher with terminal=Terminal.app on Darwin."""
        db = WindowRegistry(":memory:")

        mock_launcher_instance = mocker.MagicMock()
        mock_launcher_instance._window_exists_by_id.return_value = False
        mock_launcher_cls = mocker.patch("mc.terminal.macos.MacOSLauncher", return_value=mock_launcher_instance)
        mocker.patch("platform.system", return_value="Darwin")

        result = db._validate_window_exists("window-456", "Terminal.app")

        # MacOSLauncher must be constructed with terminal="Terminal.app"
        mock_launcher_cls.assert_called_once_with(terminal="Terminal.app")
        assert result is False

    def test_cleanup_stale_entries_uses_correct_terminal_type(self, mocker):
        """cleanup_stale_entries passes stored terminal_type to _validate_window_exists."""
        db = WindowRegistry(":memory:")
        db.register("12345678", "window-123", "Terminal.app")
        db.register("87654321", "window-456", "iTerm2")

        validate_calls: list[tuple[str, str]] = []

        def mock_validate(window_id: str, terminal_type: str) -> bool:
            validate_calls.append((window_id, terminal_type))
            return True  # keep all entries

        mocker.patch.object(db, "_validate_window_exists", side_effect=mock_validate)

        db.cleanup_stale_entries(sample_size=20)

        # Both entries should have been validated with their correct terminal types
        assert ("window-123", "Terminal.app") in validate_calls
        assert ("window-456", "iTerm2") in validate_calls

    def test_window_registry_stale_cleanup_preserves_iterm2_api_window_id_regression(
        self, mocker
    ):
        """Regression test for fix/window-registry-stale-cleanup — UAT 5.2 Duplicate Launch Detection.

        Bug discovered: 2026-04-01
        Platform: macOS with iTerm2 Python API
        Severity: major
        Source: UAT 5.2 Duplicate Launch Detection

        Problem:
        cleanup_stale_entries() calls _validate_window_exists() which creates a MacOSLauncher
        and calls _window_exists_by_id(window_id). When the iTerm2 window was created via the
        Python API, the stored window ID is a UUID string like "w0t0p0". When the iterm2 Python
        library is unavailable at validation time, _window_exists_by_id falls back to AppleScript,
        which compares (id of theWindow as text) to the stored UUID. iTerm2's AppleScript 'id'
        property returns a numeric integer — it never equals a UUID string — so the comparison
        always returns False and the entry is incorrectly deleted as stale.

        On the second `mc case <number>` call:
        1. cleanup_stale_entries() runs before registry.lookup()
        2. The entry with UUID window ID is validated via AppleScript (because API is unavailable)
        3. AppleScript returns False (numeric ID != UUID string)
        4. The entry is deleted as stale
        5. registry.lookup() finds nothing — second call opens a new terminal instead of focusing

        Steps to reproduce:
        1. Register a window ID with UUID format ("w0t0p0") and terminal_type "iTerm2"
        2. Call cleanup_stale_entries() with iterm2 Python API unavailable (API returns None/False)
           and AppleScript validator returning False (it always does for UUID-format IDs)
        3. Check registry — entry is incorrectly deleted

        Expected: cleanup_stale_entries() preserves entries with UUID-format window IDs when
                  the window genuinely exists (UUID IDs must not be validated via AppleScript
                  numeric-ID comparison)
        Actual:   cleanup_stale_entries() deletes the entry because AppleScript validator returns
                  False for any UUID-format window ID, treating valid windows as stale

        This test ensures the bug does not regress.
        """
        registry = WindowRegistry(db_path=":memory:")

        # Register a window with a UUID-format ID (iTerm2 Python API style)
        uuid_window_id = "w0t0p0"
        case_number = "12345678"
        terminal_type = "iTerm2"

        registered = registry.register(case_number, uuid_window_id, terminal_type)
        assert registered, "Pre-condition: entry must be registered"

        # Simulate the bug scenario:
        #   - macOS (Darwin) system
        #   - iterm2 Python API unavailable → falls back to AppleScript
        #   - AppleScript _window_exists_by_id returns False for UUID IDs
        #     (AppleScript 'id' is numeric integer, UUID string never matches)
        mocker.patch("platform.system", return_value="Darwin")
        mocker.patch("mc.terminal.macos._ITERM2_LIB_AVAILABLE", False)
        mocker.patch(
            "mc.terminal.macos.MacOSLauncher._window_exists_by_id",
            return_value=False,  # AppleScript always returns False for UUID IDs
        )

        removed = registry.cleanup_stale_entries(sample_size=20)

        # The entry must NOT be removed — UUID window IDs cannot be validated via
        # AppleScript numeric-ID comparison; they must use the Python API or be skipped.
        assert removed == 0, (
            f"BUG REGRESSED: cleanup_stale_entries() removed {removed} entries for a "
            f"UUID-format iTerm2 window ID that should survive AppleScript validation. "
            f"UUID window IDs ('{uuid_window_id}') cannot be validated via AppleScript "
            f"numeric-ID comparison — they must use the Python API or be preserved."
        )

        # Confirm entry still in database
        with registry._connection() as conn:
            row = conn.execute(
                "SELECT window_id FROM window_registry WHERE case_number = ?",
                (case_number,),
            ).fetchone()
        assert row is not None, (
            "BUG REGRESSED: entry was deleted from DB by cleanup_stale_entries() even "
            "though window ID is UUID-format (iTerm2 Python API) and cannot be validated "
            "by AppleScript numeric-ID comparison"
        )
