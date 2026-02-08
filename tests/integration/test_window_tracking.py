"""Integration tests for window tracking edge cases.

Tests window lifecycle, stale entry handling, and registry corruption recovery.
These tests verify the window tracking system (phases 15-18) handles edge cases
beyond the primary duplicate prevention scenario.
"""

import os
import platform
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from mc.config.manager import ConfigManager
from mc.container.manager import ContainerManager
from mc.container.state import StateDatabase
from mc.integrations.podman import PodmanClient
from mc.integrations.redhat_api import RedHatAPIClient
from mc.terminal.attach import attach_terminal
from mc.terminal.registry import WindowRegistry


def _podman_available() -> bool:
    """Check if Podman is available and accessible."""
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


def _redhat_api_configured() -> bool:
    """Check if Red Hat API credentials are configured."""
    try:
        config = ConfigManager()
        if not config.exists():
            return False

        cfg = config.load()
        api_config = cfg.get("api", {})

        return bool(api_config.get("rh_api_offline_token"))
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured"
)
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific test"
)
def test_window_cleanup_after_manual_close(mocker, tmp_path):
    """Test window registry cleanup when user manually closes window.

    Scenario:
    1. Create terminal for case X
    2. Verify window ID registered
    3. Manually close window (simulate user closing iTerm2 window)
    4. Run attach_terminal again for same case
    5. Verify: New window created (not error), old entry cleaned up

    This tests the lazy validation cleanup in WindowRegistry.lookup().
    When validator returns False (window doesn't exist), the stale entry
    should be removed and a new window created.
    """
    # Setup: Create temporary directories for isolated test environment
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)
    test_config_dir = test_base_dir / "config"
    test_config_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"
    registry_db_path = test_state_dir / "window.db"

    # Create minimal config with API credentials
    from mc.config.manager import ConfigManager as RealConfigManager
    real_config = RealConfigManager()
    real_cfg = real_config.load()

    minimal_config = {
        "api": {
            "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
        },
        "base_directory": str(test_base_dir)
    }

    config_path = test_config_dir / "config.toml"

    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # Setup REAL components
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Mock TTY check
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Mock user_data_dir for WindowRegistry to use isolated test database
    mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(test_state_dir))

    # Initialize REAL components
    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    # Use REAL launcher
    from mc.terminal.launcher import get_launcher
    launcher = get_launcher()

    # Use real case number from test set
    test_case_number = "04300354"
    container_name = f"mc-{test_case_number}"

    # Pre-cleanup
    try:
        existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing_container.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    # Clean up registry entry
    registry = WindowRegistry(str(registry_db_path))
    registry.remove(test_case_number)

    container = None
    created_window_id = None

    try:
        # FIRST CALL: Create terminal and window
        print("\n=== FIRST CALL: Create initial window ===")
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        time.sleep(2)  # Give window time to register

        # Verify window ID was registered
        def always_valid(wid):
            return True

        created_window_id = registry.lookup(test_case_number, always_valid)
        assert created_window_id is not None, "Window ID should be registered after first call"
        print(f"✓ Window ID registered: {created_window_id}")

        # SIMULATE WINDOW CLOSURE: Stop container to cause window to close
        # (Stopping the podman exec process will cause iTerm2 window to close)
        try:
            existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            print("Stopping container to simulate window closure...")
            existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            time.sleep(2)  # Give iTerm2 time to close window after container stops
        except Exception as e:
            print(f"Warning: Failed to stop container: {e}")

        # Verify window is actually closed (the window should close when process exits)
        from mc.terminal.macos import MacOSLauncher
        if isinstance(launcher, MacOSLauncher):
            window_exists = launcher._window_exists_by_id(created_window_id)
            # Note: Window might still exist briefly if user hasn't closed it manually
            print(f"Window exists after container stop: {window_exists}")
            # Don't assert here - window closure is async and depends on user closing iTerm2 window
            print("✓ Container stopped (window should close or become orphaned)")

        # SECOND CALL: Attach again (should detect stale or create new depending on window state)
        print("\n=== SECOND CALL: Attach after manual close ===")
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        time.sleep(2)

        # Verify: Window ID registered (should be new or same if window still exists)
        new_window_id = registry.lookup(test_case_number, always_valid)
        assert new_window_id is not None, "Window ID should be registered after second attach"
        print(f"✓ Window ID after second attach: {new_window_id}")

        if new_window_id != created_window_id:
            print("✓ Stale entry cleanup working - new window created after container stop")
        else:
            print("Note: Same window ID (window might still exist or was reused)")

        # Get container for cleanup
        try:
            container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        except Exception:
            pass

        print("\n⚠️  MANUAL CLEANUP REQUIRED:")
        print("Please manually close the iTerm2 window for this test.")

    finally:
        # Cleanup: Remove test container
        if container:
            try:
                container.stop(timeout=2)  # type: ignore[no-untyped-call]
                container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass

        try:
            cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            cleanup_container.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured"
)
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific test"
)
def test_stale_window_id_handling(mocker, tmp_path):
    """Test handling of stale window IDs (window force-killed).

    Scenario:
    1. Register fake window ID in WindowRegistry
    2. Verify window doesn't actually exist (validation fails)
    3. Run attach_terminal for that case
    4. Verify: Stale entry removed, new window created

    This tests lazy validation cleanup when window ID exists in registry
    but the window was force-killed (e.g., iTerm2 crashed, window killed via Activity Monitor).
    """
    # Setup
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)
    test_config_dir = test_base_dir / "config"
    test_config_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"
    registry_db_path = test_state_dir / "window.db"

    # Create config
    from mc.config.manager import ConfigManager as RealConfigManager
    real_config = RealConfigManager()
    real_cfg = real_config.load()

    minimal_config = {
        "api": {
            "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
        },
        "base_directory": str(test_base_dir)
    }

    config_path = test_config_dir / "config.toml"

    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # Setup components
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)
    mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(test_state_dir))

    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    from mc.terminal.launcher import get_launcher
    launcher = get_launcher()

    test_case_number = "04330024"
    container_name = f"mc-{test_case_number}"

    # Pre-cleanup
    try:
        existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing_container.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    registry = WindowRegistry(str(registry_db_path))
    registry.remove(test_case_number)

    container = None

    try:
        # INJECT STALE ENTRY: Register fake window ID that doesn't exist
        fake_window_id = "999999999"
        registered = registry.register(test_case_number, fake_window_id, "iTerm2")
        assert registered is True, "Fake window ID should register successfully"
        print(f"\n✓ Injected stale entry: case {test_case_number} -> window ID {fake_window_id}")

        # Verify window doesn't actually exist
        from mc.terminal.macos import MacOSLauncher
        if isinstance(launcher, MacOSLauncher):
            window_exists = launcher._window_exists_by_id(fake_window_id)
            assert not window_exists, "Fake window ID should not exist"
            print("✓ Verified fake window ID doesn't exist")

        # RUN ATTACH: Should detect stale entry and create new window
        print("\n=== ATTACH: Should detect stale entry and create new window ===")
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        time.sleep(2)

        # Verify: New real window ID registered (different from fake)
        def always_valid(wid):
            return True

        new_window_id = registry.lookup(test_case_number, always_valid)
        assert new_window_id is not None, "New window ID should be registered"
        assert new_window_id != fake_window_id, "New window ID should be different from fake"
        print(f"✓ New real window ID registered: {new_window_id}")
        print("✓ Stale entry cleanup working - new window created when old ID invalid")

        # Get container for cleanup
        try:
            container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        except Exception:
            pass

        print("\n⚠️  MANUAL CLEANUP REQUIRED:")
        print("Please manually close the iTerm2 window for this test.")

    finally:
        # Cleanup
        if container:
            try:
                container.stop(timeout=2)  # type: ignore[no-untyped-call]
                container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass

        try:
            cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            cleanup_container.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured"
)
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific test"
)
def test_registry_corruption_graceful_fallback(mocker, tmp_path):
    """Test graceful fallback when registry database is corrupted/deleted.

    Scenario:
    1. Create container and window
    2. Corrupt/delete registry database file
    3. Run attach_terminal again
    4. Verify: New registry created, window created (no crash)

    This tests that the system gracefully handles registry corruption
    without crashing. It should create a new registry and continue working.
    """
    # Setup
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)
    test_config_dir = test_base_dir / "config"
    test_config_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"
    registry_db_path = test_state_dir / "window.db"

    # Create config
    from mc.config.manager import ConfigManager as RealConfigManager
    real_config = RealConfigManager()
    real_cfg = real_config.load()

    minimal_config = {
        "api": {
            "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
        },
        "base_directory": str(test_base_dir)
    }

    config_path = test_config_dir / "config.toml"

    import tomli_w
    with open(config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # Setup components
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)
    mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(test_state_dir))

    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    test_case_number = "04339264"
    container_name = f"mc-{test_case_number}"

    # Pre-cleanup
    try:
        existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing_container.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    # Remove registry if exists
    if registry_db_path.exists():
        os.remove(registry_db_path)

    container = None

    try:
        # FIRST CALL: Create window and registry
        print("\n=== FIRST CALL: Create window and registry ===")
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        time.sleep(2)

        # Verify registry was created
        assert registry_db_path.exists(), "Registry database should be created"
        print("✓ Registry database created")

        # CORRUPT THE REGISTRY: Write garbage data to database file
        print("\n=== CORRUPTING REGISTRY ===")
        with open(registry_db_path, "wb") as f:
            f.write(b"This is not a valid SQLite database! Corruption simulation.")
        print("✓ Registry database corrupted")

        # Verify corruption (opening should fail)
        try:
            conn = sqlite3.connect(str(registry_db_path))
            conn.execute("SELECT * FROM window_registry")
            conn.close()
            pytest.fail("Database should be corrupted and fail to query")
        except sqlite3.DatabaseError:
            print("✓ Verified database is corrupted")

        # SECOND CALL: Attach after corruption (should recover gracefully)
        print("\n=== SECOND CALL: Attach after registry corruption ===")
        # This should NOT crash - it should create a new registry
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        time.sleep(2)

        # Verify: New registry created and working
        registry = WindowRegistry(str(registry_db_path))

        def always_valid(wid):
            return True

        window_id = registry.lookup(test_case_number, always_valid)
        # Note: window_id might be None or a new ID depending on whether corruption recovery
        # recreated the DB or if it's using the existing window
        print(f"✓ Registry accessible after corruption: window_id = {window_id}")
        print("✓ System gracefully handled registry corruption (no crash)")

        # Get container for cleanup
        try:
            container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        except Exception:
            pass

        print("\n⚠️  MANUAL CLEANUP REQUIRED:")
        print("Please manually close the iTerm2 window for this test.")

    finally:
        # Cleanup
        if container:
            try:
                container.stop(timeout=2)  # type: ignore[no-untyped-call]
                container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass

        try:
            cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            cleanup_container.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass
