"""Integration test for case terminal command.

Tests the end-to-end terminal attachment workflow with real components.
Skipped unless Podman and Salesforce are available.
"""

import os
import sys
import tempfile
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
from mc.integrations.salesforce_api import SalesforceAPIClient
from mc.terminal.attach import attach_terminal


def _podman_available() -> bool:
    """Check if Podman is available and accessible.

    Returns:
        bool: True if Podman can be reached, False otherwise
    """
    try:
        client = PodmanClient()
        return client.ping()
    except Exception:
        return False


def _salesforce_configured() -> bool:
    """Check if Salesforce credentials are configured.

    Returns:
        bool: True if credentials present in config, False otherwise
    """
    try:
        config = ConfigManager()
        if not config.exists():
            return False

        cfg = config.load()
        sf_config = cfg.get("salesforce", {})

        return all([
            sf_config.get("username"),
            sf_config.get("password"),
            sf_config.get("security_token"),
        ])
    except Exception:
        return False


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _salesforce_configured(),
    reason="Salesforce credentials not configured"
)
def test_case_terminal_end_to_end(mocker):
    """End-to-end test: terminal attachment workflow.

    Tests the entire stack:
    - Salesforce API integration (case metadata fetch)
    - Container auto-creation if missing
    - Bashrc generation with case metadata
    - Terminal launcher invocation

    Note: This test mocks the terminal launcher to avoid actually
    launching windows, but exercises all other real components.
    """
    # Setup temporary database and workspace
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        workspace_path = os.path.join(tmpdir, "workspace")
        os.makedirs(workspace_path)

        # Initialize real components
        config = ConfigManager()
        cfg = config.load()

        sf_config = cfg.get("salesforce", {})
        salesforce_client = SalesforceAPIClient(
            username=sf_config["username"],
            password=sf_config["password"],
            security_token=sf_config["security_token"],
        )

        podman_client = PodmanClient()
        state_db = StateDatabase(db_path)
        container_manager = ContainerManager(podman_client, state_db)

        # Mock terminal launcher to avoid actually launching windows
        mock_launcher = mocker.MagicMock()
        mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

        # Mock TTY check (tests run in non-TTY environments)
        mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

        # Override config base_directory for test
        mocker.patch.object(config, "load", return_value={"base_directory": tmpdir})

        # Use test case number that won't conflict
        test_case_number = "99999999"
        container_name = f"mc-{test_case_number}"

        container = None
        try:
            # Execute terminal attachment workflow
            attach_terminal(
                case_number=test_case_number,
                config_manager=config,
                salesforce_client=salesforce_client,
                container_manager=container_manager,
            )

            # Verify terminal launcher was called
            mock_launcher.launch.assert_called_once()

            # Verify launch options
            call_args = mock_launcher.launch.call_args
            launch_options = call_args[0][0]

            # Verify window title format
            assert test_case_number in launch_options.title
            assert " - " in launch_options.title  # Format: "case - customer - description"

            # Verify podman exec command
            command = launch_options.command
            assert "podman exec -it" in command
            assert container_name in command
            assert "/bin/bash" in command
            assert "BASH_ENV=" in command  # Custom bashrc injection
            assert f"PS1=[MC-{test_case_number}]" in command  # Custom prompt

            # Verify container was created (attach_terminal auto-creates if missing)
            # Get container from Podman
            try:
                container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]

                # Verify container is running
                assert container.status in ("running", "configured"), (
                    f"Expected running/configured, got {container.status}"
                )

                # Verify container labels
                assert "mc.managed" in container.labels
                assert container.labels["mc.case_number"] == test_case_number

            except Exception as e:
                pytest.fail(f"Container not found or invalid: {e}")

            # Verify state database updated
            metadata = state_db.get_container(test_case_number)
            assert metadata is not None, "Container not in state database"
            assert metadata.case_number == test_case_number
            assert metadata.workspace_path is not None

        finally:
            # Cleanup: stop and remove container
            if container:
                try:
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass  # Ignore cleanup errors

            # Try cleanup by name if container object not available
            try:
                cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
                cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
                cleanup_container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass  # Container already cleaned up


def _redhat_api_configured() -> bool:
    """Check if Red Hat API credentials are configured.

    Returns:
        bool: True if offline token present in config, False otherwise
    """
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
def test_fresh_install_missing_config_base_directory_regression(mocker, tmp_path):
    """Regression test for UAT 1.1 - Fresh install with missing config file.

    Bug discovered: 2026-02-02
    Platform: macOS (reproduced), likely affects Linux too
    Severity: Critical - Blocks core functionality on fresh install

    Problem:
    On a fresh install with no existing config file at ~/mc/config/config.toml,
    running `mc case <number>` fails with confusing error:
    "Failed to create container for case 04347611. Podman error: 'base_directory'"

    Root cause:
    - Line 165 in src/mc/terminal/attach.py uses:
      base_dir = config_manager.load()["base_directory"]
    - This raises FileNotFoundError when config doesn't exist
    - Error is caught generically and shows misleading "Podman error: 'base_directory'"
    - Should use config_manager.get("base_directory", default) instead

    Steps to reproduce:
    1. Remove all MC config directories (fresh install state)
    2. Run: mc case 04347611
    3. Code attempts to load config["base_directory"] but config doesn't exist
    4. Error: "Podman error: 'base_directory'"

    Expected: Container created successfully using default ~/mc base directory
    Actual (before fix): Confusing KeyError/'base_directory' error

    This test ensures fresh installs work without requiring config file to exist.

    UAT Test: 1.1 Fresh Install - Lazy Initialization
    Fixed in: TBD (test currently reproduces the bug)
    """
    # Setup: Create temporary directories for isolated test environment
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)
    test_config_dir = test_base_dir / "config"
    test_config_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"

    # Create a config file with ONLY API credentials (simulates fresh install after wizard)
    # Intentionally OMIT base_directory to test the bug scenario
    from mc.config.manager import ConfigManager as RealConfigManager
    real_config = RealConfigManager()
    real_cfg = real_config.load()

    # Create minimal config with just API token (like after running mc config wizard)
    minimal_config = {
        "api": {
            "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
        }
        # NOTE: NO base_directory key - this triggers the bug!
    }

    fake_config_path = test_config_dir / "config.toml"

    import tomli_w
    with open(fake_config_path, "wb") as f:
        tomli_w.dump(minimal_config, f)

    # Setup real components - only override config path for isolation
    config_manager = ConfigManager()
    config_manager._config_path = fake_config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    # Get access token from offline token (real API call)
    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Mock TTY check (pytest doesn't run in TTY)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Initialize real Podman client and state database
    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    # Use real case number from Red Hat (04347611 from UAT test)
    test_case_number = "04347611"
    container_name = f"mc-{test_case_number}"

    container = None
    try:
        # Execute: Attempt terminal attachment with NO base_directory in config
        # This should either:
        # 1. FAIL with "Podman error: 'base_directory'" (reproduces bug)
        # 2. SUCCEED by using default ~/mc (bug is fixed)

        # NOTE: This will launch a REAL terminal window!
        # The test is meant to be a full integration test.
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        # Assert: If we get here, bug is FIXED
        print("✓ Test PASSED: Fresh install works without base_directory in config")

        # Verify container was created successfully
        import time
        time.sleep(2)  # Give container time to start

        try:
            container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            assert container.status in ("running", "configured"), (
                f"Expected running/configured, got {container.status}"
            )
        except Exception as e:
            pytest.fail(f"Container should exist but doesn't: {e}")

        # Verify state database has the container
        metadata = state_db.get_container(test_case_number)
        assert metadata is not None, "Container should be in state database"
        assert metadata.case_number == test_case_number

        # Verify workspace was created using default base directory
        # (Should fall back to expanding user home)
        assert metadata.workspace_path is not None
        print(f"✓ Workspace created at: {metadata.workspace_path}")

    except RuntimeError as e:
        # If we get RuntimeError, check if it's the bug we're testing for
        error_msg = str(e)

        # The bug manifests as: "Podman error: 'base_directory'"
        # This is because config_manager.load()["base_directory"] raises KeyError
        # which is caught and shown as the key name 'base_directory'
        if "'base_directory'" in error_msg or "base_directory" in error_msg:
            pytest.fail(
                f"✗ BUG REPRODUCED: Fresh install fails with missing config error.\n"
                f"Error: {error_msg}\n"
                f"Expected: Should use default ~/mc base directory when config missing.\n"
                f"Fix: Use config_manager.get('base_directory', default) instead of .load()[]"
            )
        else:
            # Some other error - re-raise for investigation
            raise

    finally:
        # Cleanup: Remove test container if created
        if container:
            try:
                print(f"Cleaning up container {container_name}...")
                container.stop(timeout=2)  # type: ignore[no-untyped-call]
                container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass

        # Cleanup by name if container object not available
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
def test_fresh_install_no_old_directories_created_regression(mocker, tmp_path):
    """Regression test for UAT 1.1 - No directories created in old platformdirs locations.

    Bug discovered: 2026-02-04
    Platform: macOS (reproduced), likely affects Linux too
    Severity: Minor - Creates directories in wrong locations

    Problem:
    During fresh install, when running `mc case <number>`, directories are being
    created in OLD platform-specific locations instead of consolidated ~/mc/:
    - macOS: ~/Library/Application Support/mc/bashrc
    - Linux: ~/.local/share/mc/bashrc or ~/.config/mc

    Root cause:
    src/mc/terminal/shell.py:84 uses platformdirs.user_data_dir("mc", "redhat")
    which creates directories in platform-specific locations. Should use the new
    consolidated ~/mc/config/ structure instead.

    Steps to reproduce:
    1. Clean slate - remove/backup all MC directories
    2. Run: mc case 04347611
    3. Check directory creation

    Expected:
    - Directories ONLY created under ~/mc/
    - NO directories in ~/.mc
    - NO directories in ~/Library/Application Support/mc/ (macOS)
    - NO directories in ~/.config/mc or ~/.local/share/mc (Linux)

    Actual (before fix):
    - ~/Library/Application Support/mc/bashrc created (macOS)
    - ~/.local/share/mc/bashrc created (Linux)

    This test ensures fresh installs only create directories in consolidated ~/mc/ location.

    UAT Test: 1.1 Fresh Install - Lazy Initialization
    Fixed in: 2026-02-04 (shell.py updated to use consolidated directory structure)
    """
    import platform
    import shutil
    from datetime import datetime

    # Detect platform for old directory paths
    is_macos = platform.system() == "Darwin"
    is_linux = platform.system() == "Linux"

    # Define old directory paths that should NOT be created
    old_dirs_to_check = []
    old_dirs_backup_info = []

    if is_macos:
        old_dirs_to_check.extend([
            Path.home() / ".mc",
            Path.home() / "Library" / "Application Support" / "mc",
        ])
    elif is_linux:
        old_dirs_to_check.extend([
            Path.home() / ".mc",
            Path.home() / ".config" / "mc",
            Path.home() / ".local" / "share" / "mc",
        ])

    # Backup existing directories (move them with timestamp)
    timestamp = datetime.now().strftime("%y%m%d-%H%M")
    for old_dir in old_dirs_to_check:
        if old_dir.exists():
            backup_dir = old_dir.parent / f"{old_dir.name}.{timestamp}"
            print(f"Backing up {old_dir} to {backup_dir}")
            shutil.move(str(old_dir), str(backup_dir))
            old_dirs_backup_info.append((old_dir, backup_dir))

    # Also backup ~/mc if it exists (for complete fresh install test)
    mc_home_dir = Path.home() / "mc"
    mc_backup_dir = None
    if mc_home_dir.exists():
        mc_backup_dir = Path.home() / f"mc.{timestamp}"
        print(f"Backing up {mc_home_dir} to {mc_backup_dir}")
        shutil.move(str(mc_home_dir), str(mc_backup_dir))

    try:
        # Verify clean slate - no old directories exist
        for old_dir in old_dirs_to_check:
            assert not old_dir.exists(), f"Old directory should not exist after backup: {old_dir}"
        assert not mc_home_dir.exists(), f"~/mc should not exist after backup: {mc_home_dir}"

        # Setup: Create minimal config with API credentials in NEW location
        # This simulates a fresh install after running config wizard
        config_dir = Path.home() / "mc" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_path = config_dir / "config.toml"

        # Get real credentials for Red Hat API
        from mc.config.manager import ConfigManager as RealConfigManager
        real_config = RealConfigManager()

        # Find the backed up config or load from current location
        if mc_backup_dir and (mc_backup_dir / "config" / "config.toml").exists():
            real_cfg = tomllib.load(open(mc_backup_dir / "config" / "config.toml", "rb"))
        else:
            real_cfg = real_config.load()

        # Create minimal config
        minimal_config = {
            "api": {
                "rh_api_offline_token": real_cfg["api"]["rh_api_offline_token"]
            },
            "base_directory": str(Path.home() / "mc")
        }

        import tomli_w
        with open(config_path, "wb") as f:
            tomli_w.dump(minimal_config, f)

        # Setup real components
        config_manager = ConfigManager()
        config_manager._config_path = config_path

        from mc.integrations.redhat_api import RedHatAPIClient
        from mc.utils.auth import get_access_token

        access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
        api_client = RedHatAPIClient(access_token)

        # Mock TTY check (pytest doesn't run in TTY)
        mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

        # Mock terminal launcher to avoid actually launching windows
        mock_launcher = mocker.MagicMock()
        mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

        # Initialize real Podman client
        podman_client = PodmanClient()

        # Use real state database in new location
        state_dir = Path.home() / "mc" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state_db = StateDatabase(str(state_dir / "containers.db"))

        container_manager = ContainerManager(podman_client, state_db)

        # Use real case number
        test_case_number = "04347611"
        container_name = f"mc-{test_case_number}"

        # Pre-cleanup: Remove any existing container with this name
        try:
            existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            print(f"Removing pre-existing container {container_name}...")
            existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
            existing_container.remove()  # type: ignore[no-untyped-call]
        except Exception:
            pass  # No pre-existing container

        container = None
        try:
            # Execute: Create container (triggers bashrc generation)
            attach_terminal(
                case_number=test_case_number,
                config_manager=config_manager,
                api_client=api_client,
                container_manager=container_manager,
            )

            # Give system time to create any directories
            import time
            time.sleep(1)

            # CRITICAL ASSERTIONS: Verify NO old directories were created
            for old_dir in old_dirs_to_check:
                if old_dir.exists():
                    # Bug reproduced! Old directory was created
                    dir_contents = list(old_dir.rglob("*"))
                    pytest.fail(
                        f"✗ BUG REPRODUCED: Old directory created during fresh install!\n"
                        f"Directory: {old_dir}\n"
                        f"Contents: {dir_contents}\n"
                        f"Expected: No directories in old platformdirs locations\n"
                        f"Fix: Update src/mc/terminal/shell.py to use ~/mc/config/ instead of platformdirs"
                    )

            # Verify directories WERE created in new consolidated location
            assert mc_home_dir.exists(), "~/mc should be created"
            assert config_dir.exists(), "~/mc/config should exist"
            assert state_dir.exists(), "~/mc/state should exist"

            # Verify bashrc was created in NEW location (not old platformdirs location)
            bashrc_new_location = Path.home() / "mc" / "config" / "bashrc"
            if not bashrc_new_location.exists():
                # If bashrc isn't in new location, that's also a problem
                # (means it might be in old location or not created at all)
                pytest.fail(
                    f"✗ Bashrc directory not found in new location: {bashrc_new_location}\n"
                    f"Expected: ~/mc/config/bashrc/\n"
                    f"This suggests bashrc is being created in old platformdirs location."
                )

            # Success! Bug is fixed
            print("✓ Test PASSED: Fresh install creates directories ONLY in ~/mc/")
            print(f"✓ Verified no directories in old locations: {old_dirs_to_check}")
            print(f"✓ Verified bashrc in new location: {bashrc_new_location}")

            # Get container for cleanup
            try:
                container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
            except Exception:
                pass

        finally:
            # Cleanup: Remove test container
            if container:
                try:
                    print(f"Cleaning up container {container_name}...")
                    container.stop(timeout=2)  # type: ignore[no-untyped-call]
                    container.remove()  # type: ignore[no-untyped-call]
                except Exception:
                    pass

            # Cleanup by name if container object not available
            try:
                cleanup_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
                cleanup_container.stop(timeout=2)  # type: ignore[no-untyped-call]
                cleanup_container.remove()  # type: ignore[no-untyped-call]
            except Exception:
                pass

    finally:
        # Restore backed up directories
        print("\nRestoring backed up directories...")

        # Remove test directories in ~/mc
        if mc_home_dir.exists():
            print(f"Removing test directory: {mc_home_dir}")
            shutil.rmtree(mc_home_dir, ignore_errors=True)

        # Restore ~/mc backup
        if mc_backup_dir and mc_backup_dir.exists():
            print(f"Restoring {mc_backup_dir} to {mc_home_dir}")
            shutil.move(str(mc_backup_dir), str(mc_home_dir))

        # Restore old directories
        for old_dir, backup_dir in old_dirs_backup_info:
            if backup_dir.exists():
                print(f"Restoring {backup_dir} to {old_dir}")
                shutil.move(str(backup_dir), str(old_dir))

        print("Restore complete.")
