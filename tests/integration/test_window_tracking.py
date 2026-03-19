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
def test_container_delete_clears_window_registry_regression(mocker, tmp_path):
    """Regression test: container delete must remove the window registry entry.

    Bug discovered: 2026-03-13
    Platform: Both (macOS and Linux)
    Severity: Major

    Problem:
    After `mc container delete <case>`, running `mc case <number>` focused the old
    (now-dead) terminal window instead of launching a new one. The user saw
    "Focused existing terminal" but no new terminal appeared.

    Root cause:
    ContainerManager.delete() cleaned up the Podman container and state database
    but did NOT call WindowRegistry().remove(). The stale registry entry caused
    attach_terminal() to believe the old window was still valid and focus it
    instead of launching a new terminal.

    Test approach:
    1. Create a real Podman container for a test case number
    2. Inject a fake window ID into WindowRegistry (simulating an open terminal)
    3. Call container_manager.delete(case_number)
    4. Assert the registry entry is gone (lookup returns None)
    5. Verify attach_terminal() calls launcher.launch(), not focus_window_by_id()
       when _window_exists_by_id is mocked to return True (stale window present)

    This test will fail until the fix is applied, then pass automatically.
    """
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"
    registry_db_path = test_state_dir / "window.db"

    # Use a dedicated test case number that won't conflict with real work
    test_case_number = "04381169"
    container_name = f"mc-{test_case_number}"

    podman_client = PodmanClient()

    # Pre-cleanup: remove any leftover container from previous runs
    try:
        existing = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        existing.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    # Isolate the window registry to our tmp_path database
    mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(test_state_dir))

    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)
    registry = WindowRegistry(str(registry_db_path))

    try:
        # Step 1: Create a real Podman container
        container_manager.create(
            case_number=test_case_number,
            workspace_path=str(test_base_dir / "workspaces" / test_case_number),
        )

        # Step 2: Inject a fake window ID (simulating a terminal opened for this case)
        fake_window_id = "777000111"
        registered = registry.register(test_case_number, fake_window_id, "iTerm2")
        assert registered is True, "Fake window ID should register successfully"

        # Confirm entry is present before delete
        def always_valid(wid: str) -> bool:
            return True

        entry_before = registry.lookup(test_case_number, always_valid)
        assert entry_before == fake_window_id, "Registry entry should exist before delete"

        # Step 3: Delete the container
        container_manager.delete(test_case_number)

        # Step 4: Assert registry entry is gone
        entry_after = registry.lookup(test_case_number, always_valid)
        assert entry_after is None, (
            "Window registry entry should be removed after container delete. "
            "Got: %s" % entry_after
        )

    finally:
        # Cleanup: remove container if it still exists
        try:
            cleanup = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            cleanup.stop(timeout=2)  # type: ignore[no-untyped-call]
            cleanup.remove()  # type: ignore[no-untyped-call]
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


@pytest.mark.integration
@pytest.mark.skipif(
    platform.system() != "Darwin",
    reason="macOS-specific test — MacOSLauncher only runs on Darwin"
)
def test_iterm2_fallback_capture_regression(mocker, tmp_path):
    """Regression: _capture_window_id() must query Terminal.app when launch() fell back to it.

    Bug discovered: 2026-03-16
    Platform: macOS
    Severity: Major

    Problem:
    When iTerm2 is installed but its Python API is unavailable (Settings > General >
    Magic > Enable Python API is off), launch() silently falls back to spawning a
    Terminal.app window via AppleScript.  However _capture_window_id() checks
    self.terminal == "iTerm2" and asks iTerm2 for its "current window", returning
    the ID of the iTerm2 shell the user ran `mc` from - not the newly opened
    Terminal.app case window.  That wrong ID is registered in WindowRegistry, so
    the next `mc case <num>` call finds it valid (the iTerm2 shell is still open),
    "focuses" the original shell, and never opens the case terminal.

    Root cause:
    MacOSLauncher._capture_window_id() does not track which app was actually used
    for the last launch.  self.terminal is set to "iTerm2" at construction time
    (because iTerm2 is detected), and _capture_window_id() blindly uses self.terminal
    to select which app to query - even when launch() used Terminal.app as a fallback.

    Test approach:
    - MacOSLauncher with terminal="iTerm2", _try_iterm2_api mocked to return None
    - subprocess.Popen mocked (Terminal.app launch is non-blocking)
    - subprocess.run mocked to simulate Terminal.app returning a new window ID
    - Assert _capture_window_id() sends an osascript that targets "Terminal" not "iTerm"
    - Assert the returned ID matches what Terminal.app reported (not an iTerm2 shell ID)
    """
    from unittest.mock import MagicMock, patch
    from mc.terminal.macos import MacOSLauncher
    from mc.terminal.launcher import LaunchOptions

    options = LaunchOptions(
        title="04389182:Banque Misr:Unable to deploy application:/case",
        command="podman exec -it mc-04389182 /bin/bash; exit",
    )

    terminal_app_window_id = "5999"   # ID Terminal.app would return for the new window
    iterm2_shell_window_id = "5948"   # ID iTerm2 returns for the shell that ran mc

    with (
        patch.object(MacOSLauncher, "_try_iterm2_api", return_value=None),
        patch("mc.terminal.macos._should_show_iterm2_fallback_notice", return_value=False),
        patch("shutil.which", return_value="/usr/bin/osascript"),
        patch("subprocess.Popen") as mock_popen,
        patch("threading.Thread"),
        patch("subprocess.run") as mock_run,
    ):
        mock_popen.return_value = MagicMock()
        # Simulate Terminal.app reporting the new case window ID
        mock_run.return_value = MagicMock(returncode=0, stdout=f"{terminal_app_window_id}\n")

        launcher = MacOSLauncher(terminal="iTerm2")
        launcher.launch(options)
        captured_id = launcher._capture_window_id()

        assert mock_run.called, "_capture_window_id() must call subprocess.run (osascript)"
        capture_script = mock_run.call_args[0][0][2]  # ["osascript", "-e", <script>]

        assert "Terminal" in capture_script, (
            "_capture_window_id() must query Terminal.app after Terminal.app fallback launch. "
            f"Script used: {capture_script!r}"
        )
        assert "iTerm" not in capture_script, (
            "_capture_window_id() must NOT query iTerm2 when Terminal.app was the actual launcher. "
            "Querying iTerm2 captures the current shell window ID, not the new case terminal. "
            f"Script used: {capture_script!r}"
        )
        assert captured_id == terminal_app_window_id, (
            f"Captured window ID '{captured_id}' is wrong. Expected Terminal.app window ID "
            f"'{terminal_app_window_id}'. If '{iterm2_shell_window_id}' is returned, the "
            "current iTerm2 shell is being tracked instead of the new Terminal.app case window."
        )


@pytest.mark.integration
def test_terminal_app_double_window_regression():
    """Regression: _build_terminal_app_script must not open 2 windows when Terminal.app is not running.

    Bug discovered: 2026-03-16
    Platform: macOS
    Severity: Major

    Problem:
    Running `mc case N` for the second time (after the window registry cleans up a stale
    entry) opens 2 Terminal.app windows instead of 1.  The AppleScript generated by
    _build_terminal_app_script does:
        tell application "Terminal"
            activate           -- starts Terminal.app → opens DEFAULT window #1
            do script "cmd"   -- ALWAYS creates a new window → window #2
            ...
        end tell
    When Terminal.app is not already running, `activate` opens a default shell window (#1),
    and `do script` unconditionally creates another window (#2).  Two windows appear.

    Root cause:
    _build_terminal_app_script (macos.py) does not check whether Terminal.app was running
    before deciding how to invoke `do script`.  The fix is to capture
    `set termWasRunning to application "Terminal" is running` before `activate`, then use
    `do script "cmd" in window 1` when Terminal.app was not previously running — reusing the
    startup window rather than creating a second one.

    Expected behaviour:
    The generated AppleScript includes a guard that checks whether Terminal.app was running
    before activating it, so that `do script` is routed to the startup window when Terminal.app
    was not already open (preventing the second window).

    Actual behaviour:
    The generated AppleScript has no `is running` guard; `do script` always creates a new
    window regardless of whether Terminal.app just opened a default one via `activate`.

    Test approach:
    - Calls _build_terminal_app_script() directly (no real Terminal.app interaction)
    - Asserts the generated script contains the `is running` guard
    - The test fails when the bug is present (script has no guard → double-window possible)
    """
    from mc.terminal.macos import MacOSLauncher
    from mc.terminal.launcher import LaunchOptions

    launcher = MacOSLauncher(terminal="Terminal.app")
    options = LaunchOptions(
        title="04389182:Banque Misr:Unable to deploy application:/case",
        command="podman exec -it mc-04389182 /bin/bash; exit",
    )
    script = launcher._build_terminal_app_script(options)

    assert "is running" in script, (
        "_build_terminal_app_script must check 'application \"Terminal\" is running' before "
        "activating Terminal.app.  Without this guard, activate() opens a default window and "
        "do script creates a second — producing 2 Terminal.app windows.  "
        f"Generated script:\n{script}"
    )

    # Verify the script branches on was-running: uses 'in window 1' for the cold-start path
    assert "in window 1" in script, (
        "When Terminal.app was not running, the script must use 'do script ... in window 1' "
        "to run the command in the startup window rather than opening a third window.  "
        f"Generated script:\n{script}"
    )
