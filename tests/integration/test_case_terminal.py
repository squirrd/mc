"""Integration test for case terminal command.

Tests the end-to-end terminal attachment workflow with real components.
Skipped unless Podman and Salesforce are available.
"""

import os
import re
import subprocess
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


def _macos_pac_proxy_configured() -> bool:
    """Check if macOS has a PAC-based proxy configured.

    Returns:
        bool: True if running on macOS and scutil --proxy shows ProxyAutoConfigURLString
    """
    import platform
    if platform.system() != "Darwin":
        return False
    try:
        r = subprocess.run(["scutil", "--proxy"], capture_output=True, text=True, timeout=3)
        return "ProxyAutoConfigURLString" in r.stdout
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


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured"
)
def test_terminal_title_format_regression(mocker, tmp_path):
    """Regression test for UAT 5.1 - Terminal window title format.

    Bug discovered: 2026-02-04
    Platform: macOS (reproduced)
    Severity: Minor - Cosmetic issue affecting usability

    Problem:
    Terminal window title shows incorrect format. Instead of showing case metadata,
    the title displays a pod/container reference like "@38d5d5580c057c/case".

    Expected title format (updated requirement):
    {case}:{customer}:{description}:/{vm-path}
    Example: "04347611:IBM Corpora Limited:Server Down Critical Pr:/case"

    Old UAT expected format (no longer desired):
    {case} - {customer} - {description}
    Example: "04347611 - IBM Corpora Limited - Server Down Critical Pr"

    Actual (before fix):
    "@38d5d5580c057c/case" (container hostname/pod reference)

    Root cause:
    The build_window_title() function in src/mc/terminal/attach.py:66-93 exists and
    generates the correct format, but the title may not be properly set in the
    terminal window, or the format needs updating to match new requirements.

    Steps to reproduce:
    1. Run: mc case 04347611
    2. Observe terminal window title
    3. See pod reference instead of case metadata

    This test verifies:
    1. Title is generated in correct format
    2. Title includes case number, customer, description, and vm path
    3. Title is properly passed to terminal launcher

    UAT Test: 5.1 Initial Terminal Launch
    Fixed in: TBD (test currently validates title generation)
    """
    # Setup: Create temporary directories for isolated test environment
    test_base_dir = tmp_path / "mc"
    test_state_dir = test_base_dir / "state"
    test_state_dir.mkdir(parents=True)
    test_config_dir = test_base_dir / "config"
    test_config_dir.mkdir(parents=True)

    db_path = test_state_dir / "containers.db"

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

    # Setup real components
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # Mock TTY check (pytest doesn't run in TTY)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Mock terminal launcher to capture what title is passed
    mock_launcher = mocker.MagicMock()
    mocker.patch("mc.terminal.attach.get_launcher", return_value=mock_launcher)

    # Initialize real Podman client
    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    # Use real case number
    test_case_number = "04347611"
    container_name = f"mc-{test_case_number}"

    # Pre-cleanup: Remove any existing container
    try:
        existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        print(f"Removing pre-existing container {container_name}...")
        existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing_container.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    container = None
    try:
        # Execute: Attach terminal (triggers title generation)
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        # Verify terminal launcher was called
        mock_launcher.launch.assert_called_once()

        # Extract the launch options that were passed
        call_args = mock_launcher.launch.call_args
        launch_options = call_args[0][0]

        print(f"\nActual title passed to launcher: {launch_options.title}")

        # Parse the title to verify format
        # Expected format: {case}:{customer}:{description}:/{vm-path}
        # Example: "04347611:IBM Corpora Limited:Server Down Critical Pr:/case"

        # CRITICAL ASSERTIONS
        # 1. Title must contain the case number
        assert test_case_number in launch_options.title, (
            f"Title must contain case number {test_case_number}\n"
            f"Actual title: {launch_options.title}"
        )

        # 2. Title must contain customer name (from API)
        # We don't assert exact customer name since it comes from API
        # but we verify it's not a pod reference like "@38d5d5580c057c"
        assert not launch_options.title.startswith("@"), (
            f"Title should not start with '@' (pod reference)\n"
            f"Actual title: {launch_options.title}\n"
            f"Expected format: {{case}}:{{customer}}:{{description}}:/{{vm-path}}"
        )

        # 3. Title should use colon separators (new format requirement)
        # If title still uses " - " separators, that's the bug we're tracking
        if " - " in launch_options.title and ":" not in launch_options.title:
            pytest.fail(
                f"✗ BUG FOUND: Title uses old format with ' - ' separators\n"
                f"Actual: {launch_options.title}\n"
                f"Expected format: {{case}}:{{customer}}:{{description}}:/{{vm-path}}\n"
                f"Example: 04347611:IBM Corpora Limited:Server Down Critical Pr:/case\n"
                f"Fix needed in: src/mc/terminal/attach.py build_window_title()"
            )

        # 4. Title should include vm-path (:/case or similar)
        if ":/case" not in launch_options.title and "/case" not in launch_options.title:
            pytest.fail(
                f"✗ BUG FOUND: Title missing vm-path component\n"
                f"Actual: {launch_options.title}\n"
                f"Expected to include: ':/case' or '/case'\n"
                f"Fix needed in: src/mc/terminal/attach.py build_window_title()"
            )

        # 5. Verify title has colons (new separator format)
        colon_count = launch_options.title.count(":")
        if colon_count < 3:  # Should have at least 3 colons (case:customer:description:/path)
            pytest.fail(
                f"✗ BUG FOUND: Title missing colon separators (found {colon_count}, expected >= 3)\n"
                f"Actual: {launch_options.title}\n"
                f"Expected format: {{case}}:{{customer}}:{{description}}:/{{vm-path}}\n"
                f"Fix needed in: src/mc/terminal/attach.py build_window_title()"
            )

        print("✓ Test PASSED: Terminal title format is correct")
        print(f"✓ Title: {launch_options.title}")

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

@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available"
)
@pytest.mark.skipif(
    not _redhat_api_configured(),
    reason="Red Hat API credentials not configured"
)
def test_duplicate_terminal_prevention_regression(mocker, tmp_path):
    """Regression test for UAT 5.2 - Duplicate Launch Detection.

    Bug discovered: 2026-02-04
    Platform: macOS with iTerm2 (reproduced)
    Severity: Major - Affects usability, creates terminal clutter
    Fixed in: Phases 15-18 (Window ID-based tracking)

    Problem:
    Running `mc case 04347611` multiple times incorrectly allows multiple
    terminal windows to be spun up instead of focusing the existing window.

    Expected behavior (fixed in phases 15-18):
    1. First call: Creates new terminal window, captures window ID, registers in WindowRegistry
    2. Second call: Finds existing window via WindowRegistry, focuses by ID, shows message
       "Focused existing terminal for case 04347611"
    3. No new terminal window created on second call

    Solution:
    Window ID-based tracking replaces title-based search (which was unreliable in iTerm2).
    - Phase 15: WindowRegistry with window ID storage
    - Phase 16: macOS window ID capture and focus_window_by_id()
    - Phase 18: Linux X11 support

    This test verifies (using REAL iTerm2 integration):
    1. First attach_terminal creates a new window (real iTerm2 window)
    2. Window ID is captured and stored in WindowRegistry
    3. Second attach_terminal finds existing window via WindowRegistry lookup
    4. Second attach_terminal does NOT create new window (verified by window count)
    5. "Focused existing terminal" message shown on second call

    IMPORTANT - NO MOCKING:
    This is a TRUE integration test. It uses:
    - Real Podman client and containers
    - Real Red Hat API calls
    - Real iTerm2 AppleScript execution (launches actual windows!)
    - Real MacOSLauncher with real window ID tracking
    - Real WindowRegistry with isolated database

    We only mock TTY detection (pytest limitation). Everything else is REAL.

    UAT Test: 5.2 Duplicate Launch Detection
    Fixed in: Phases 15-18 (2026-02-07)
    """
    import platform
    import time

    # This test requires macOS with iTerm2
    if platform.system() != "Darwin":
        pytest.skip("Test requires macOS")

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

    # Setup REAL components (NO MOCKING except TTY)
    config_manager = ConfigManager()
    config_manager._config_path = config_path

    from mc.integrations.redhat_api import RedHatAPIClient
    from mc.utils.auth import get_access_token

    access_token = get_access_token(minimal_config["api"]["rh_api_offline_token"])
    api_client = RedHatAPIClient(access_token)

    # ONLY mock TTY check (pytest limitation - tests don't run in TTY)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Mock user_data_dir for WindowRegistry to use isolated test database
    mocker.patch("mc.terminal.registry.user_data_dir", return_value=str(test_state_dir))

    # Initialize REAL Podman client, state database, container manager
    podman_client = PodmanClient()
    state_db = StateDatabase(str(db_path))
    container_manager = ContainerManager(podman_client, state_db)

    # Use REAL launcher - no mocking!
    from mc.terminal.launcher import get_launcher
    launcher = get_launcher()

    print(f"\nUsing REAL launcher: {type(launcher).__name__}")
    print(f"Terminal type: {launcher.terminal if hasattr(launcher, 'terminal') else 'unknown'}")

    # Use real case number
    test_case_number = "04347611"
    container_name = f"mc-{test_case_number}"

    # Build expected window title (same logic as attach.py)
    from mc.terminal.attach import build_window_title

    # Get case metadata to build title
    from mc.utils.cache import get_case_metadata
    case_details, account_details, _ = get_case_metadata(test_case_number, api_client)
    customer_name = account_details.get("name", "Unknown")
    description = case_details.get("summary", "")

    expected_title = build_window_title(test_case_number, customer_name, description)
    print(f"Expected window title: {expected_title}")

    # Pre-cleanup: Remove any existing container and registry entries
    try:
        existing_container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        print(f"Removing pre-existing container {container_name}...")
        existing_container.stop(timeout=2)  # type: ignore[no-untyped-call]
        existing_container.remove()  # type: ignore[no-untyped-call]
    except Exception:
        pass

    # Clean up any existing registry entry for this case
    from mc.terminal.registry import WindowRegistry
    registry = WindowRegistry(str(registry_db_path))
    registry.remove(test_case_number)

    container = None
    terminal_windows_created = []

    try:
        # FIRST CALL: Attach terminal for the first time
        print("\n=== FIRST CALL: mc case 04347611 ===")
        print("This will launch a REAL iTerm2 window!")

        # Count windows before (if we can)
        from mc.terminal.macos import MacOSLauncher
        windows_before_first = None
        if isinstance(launcher, MacOSLauncher):
            # Try to count iTerm2 windows
            try:
                import subprocess
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "iTerm" to count windows'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    windows_before_first = int(result.stdout.strip())
                    print(f"iTerm2 windows before first call: {windows_before_first}")
            except Exception as e:
                print(f"Could not count windows: {e}")

        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        # Give iTerm2 time to create the window and register it
        time.sleep(2)

        # Count windows after first call
        windows_after_first = None
        if isinstance(launcher, MacOSLauncher):
            try:
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "iTerm" to count windows'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    windows_after_first = int(result.stdout.strip())
                    print(f"iTerm2 windows after first call: {windows_after_first}")
            except Exception:
                pass

        # Verify window was created
        print(f"\n✓ First call completed - iTerm2 window should be open")

        # Verify window ID was registered in WindowRegistry
        if isinstance(launcher, MacOSLauncher):
            def always_valid(window_id):
                return True

            window_id = registry.lookup(test_case_number, always_valid)
            print(f"\nWindowRegistry lookup for case {test_case_number}: {window_id}")

            if not window_id:
                # Window ID should be registered after first call
                pytest.fail(
                    f"✗ BUG FOUND: Window ID not registered in WindowRegistry!\n"
                    f"First call should capture window ID and store in registry.\n"
                    f"Registry path: {registry_db_path}\n"
                    f"Fix needed in: src/mc/terminal/attach.py window registration logic"
                )

        # SECOND CALL: Attach terminal again (should focus existing, not create new)
        print("\n=== SECOND CALL: mc case 04347611 ===")
        print("This should FOCUS existing window, NOT create a new one")

        # Capture stdout to check for "Focused" message
        import io
        import sys
        captured_output = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_output

        try:
            attach_terminal(
                case_number=test_case_number,
                config_manager=config_manager,
                api_client=api_client,
                container_manager=container_manager,
            )
        finally:
            sys.stdout = old_stdout

        output = captured_output.getvalue()
        print(f"\nCaptured output from second call:\n{output}")

        # Give time for any window creation/focus
        time.sleep(1)

        # Count windows after second call
        windows_after_second = None
        if isinstance(launcher, MacOSLauncher):
            try:
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "iTerm" to count windows'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    windows_after_second = int(result.stdout.strip())
                    print(f"iTerm2 windows after second call: {windows_after_second}")
            except Exception:
                pass

        # CRITICAL ASSERTIONS for duplicate prevention

        # 1. "Focused existing terminal" message should be shown
        if "Focused existing terminal" not in output:
            pytest.fail(
                f"✗ BUG FOUND: No 'Focused existing terminal' message shown\n"
                f"Captured output: {output}\n"
                f"Expected: 'Focused existing terminal for case {test_case_number}'\n"
                f"This means WindowRegistry lookup or focus_window_by_id failed.\n"
                f"Check: 1) WindowRegistry lookup, 2) Window ID validation, 3) focus_window_by_id\n"
                f"Fix needed in: src/mc/terminal/attach.py or src/mc/terminal/macos.py"
            )

        # 2. Window count should not increase (no new window created)
        if windows_before_first is not None and windows_after_first is not None and windows_after_second is not None:
            windows_created_on_first = windows_after_first - windows_before_first
            windows_created_on_second = windows_after_second - windows_after_first

            print(f"\nWindow count analysis:")
            print(f"  Before first call: {windows_before_first}")
            print(f"  After first call:  {windows_after_first} (+{windows_created_on_first})")
            print(f"  After second call: {windows_after_second} (+{windows_created_on_second})")

            if windows_created_on_second > 0:
                pytest.fail(
                    f"✗ BUG FOUND: Second call created {windows_created_on_second} new window(s)!\n"
                    f"Expected: 0 new windows (should focus existing via WindowRegistry)\n"
                    f"Actual: {windows_created_on_second} new window(s)\n"
                    f"Duplicate window created - WindowRegistry lookup/focus failed.\n"
                    f"Fix needed in: src/mc/terminal/attach.py window ID tracking logic"
                )

        print("\n✓ Test PASSED: Duplicate prevention working correctly")
        print(f"✓ First call: Created window")
        print(f"✓ Second call: Found existing window and focused it")
        print(f"✓ No duplicate window created")
        print(f"✓ User message shown: 'Focused existing terminal for case {test_case_number}'")

        print("\n⚠️  MANUAL CLEANUP REQUIRED:")
        print(f"Please manually close the iTerm2 window titled:")
        print(f"  '{expected_title}'")

        # Get container for cleanup
        try:
            container = podman_client.client.containers.get(container_name)  # type: ignore[union-attr]
        except Exception:
            pass

    finally:
        # Cleanup: Remove test container
        if container:
            try:
                print(f"\nCleaning up container {container_name}...")
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


# ---------------------------------------------------------------------------
# Regression tests — container OCM env setup (fix/container-ocm-env-setup)
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_container_ocm_env_setup_https_proxy_in_bashrc_regression() -> None:
    """Regression test for fix/container-ocm-env-setup — HTTPS_PROXY missing from bashrc.

    Bug discovered: 2026-03-08
    Platform: macOS / Linux
    Severity: major
    Source: prod usage

    Problem:
        When `mc case <number>` creates a new terminal, the case bashrc
        (injected via BASH_ENV) did not contain HTTPS_PROXY.  Users had to
        manually copy-paste the proxy env var into every new container session
        to use OCM through the corporate proxy.

    Root cause:
        generate_bashrc() in terminal/shell.py never read or propagated
        HTTPS_PROXY from the host environment.

    Test approach:
        Calls generate_bashrc() with HTTPS_PROXY set in the host environment
        and asserts the resulting script contains the export line.
        No Podman or network access required.

    This test will fail until the bug is fixed, then pass automatically.
    """
    import os
    from unittest.mock import patch

    from mc.terminal.shell import generate_bashrc

    case_number = "12345678"
    metadata = {
        "case_number": case_number,
        "customer_name": "Test Corp",
        "description": "Server down",
    }
    proxy_value = "http://squid.corp.redhat.com:3128"

    with patch.dict(os.environ, {"HTTPS_PROXY": proxy_value}):
        bashrc = generate_bashrc(case_number, metadata)

    assert f"export HTTPS_PROXY='{proxy_value}'" in bashrc, (
        f"bashrc must propagate host HTTPS_PROXY into the container shell.\n"
        f"Expected: export HTTPS_PROXY='{proxy_value}'\n"
        f"Bashrc produced:\n{bashrc}"
    )


@pytest.mark.integration
def test_container_ocm_env_setup_https_proxy_absent_when_unset_regression() -> None:
    """Regression — HTTPS_PROXY must not appear in bashrc when host env is unset.

    Ensures the fix is conditional (reads from host env) and does not
    hardcode the proxy value.

    Bug discovered: 2026-03-08
    """
    import os
    from unittest.mock import patch

    from mc.terminal.shell import generate_bashrc

    metadata = {"case_number": "12345678"}
    env_without_proxy = {k: v for k, v in os.environ.items() if k != "HTTPS_PROXY"}

    with patch.dict(os.environ, env_without_proxy, clear=True):
        bashrc = generate_bashrc("12345678", metadata)

    assert "HTTPS_PROXY" not in bashrc, (
        "bashrc must not contain HTTPS_PROXY when host env var is absent"
    )


@pytest.mark.integration
def test_container_ocm_env_setup_ocm_config_mounted_regression(tmp_path: Path) -> None:
    """Regression test for fix/container-ocm-env-setup — OCM config not mounted.

    Bug discovered: 2026-03-08
    Platform: macOS / Linux
    Severity: major
    Source: prod usage

    Problem:
        ContainerManager.create() did not mount the host OCM config file
        (~/.config/ocm/ocm.json or ~/Library/Application Support/ocm/ocm.json)
        into the container.  Users had to manually copy-paste OCM credentials
        (JWT tokens) into every new container session.

    Root cause:
        The volumes dict passed to podman containers.create() only contained
        the workspace mount.  No OCM config volume was added.

    Test approach:
        - Creates a fake OCM config file in tmp_path
        - Patches get_ocm_config_path() to return that temp path
        - Calls ContainerManager.create() with mocked Podman
        - Asserts the volumes dict includes a read-only mount at
          /root/.config/ocm/ocm.json pointing at the host config file
        No real Podman required.

    This test will fail until the bug is fixed, then pass automatically.
    """
    from unittest.mock import MagicMock, Mock, patch

    from mc.container.manager import ContainerManager
    from mc.container.state import StateDatabase
    from mc.integrations.podman import PodmanClient

    # Create a fake OCM config that exists on disk
    fake_ocm = tmp_path / "ocm.json"
    fake_ocm.write_text('{"access_token": "fake-jwt"}')

    podman_client = Mock(spec=PodmanClient)
    state_db = Mock(spec=StateDatabase)
    podman_client.client.containers.list.return_value = []
    state_db.get_container.return_value = None
    mock_image = MagicMock()
    podman_client.client.images.get.return_value = mock_image
    mock_container = MagicMock()
    mock_container.id = "abc123"
    podman_client.client.containers.create.return_value = mock_container

    manager = ContainerManager(podman_client, state_db)

    with patch("mc.container.manager.os.makedirs"), \
         patch("mc.container.manager.get_ocm_config_path", return_value=fake_ocm):
        manager.create("12345678", "/path/to/workspace", "TestCustomer")

    create_call = podman_client.client.containers.create.call_args
    volumes = create_call.kwargs["volumes"]

    expected_target = "/home/mcuser/.config/ocm/ocm.json"
    ocm_mounts = [
        (src, spec) for src, spec in volumes.items()
        if isinstance(spec, dict) and spec.get("bind") == expected_target
    ]

    assert ocm_mounts, (
        f"ContainerManager.create() must mount the host OCM config at "
        f"'{expected_target}' inside the container.\n"
        f"Actual volumes passed to containers.create(): {volumes}\n"
        f"Bug: OCM config volume is missing or mounted at wrong path."
    )
    _src, spec = ocm_mounts[0]
    assert spec["mode"] == "ro", (
        f"OCM config mount must be read-only (mode='ro'), got mode='{spec['mode']}'"
    )


@pytest.mark.integration
def test_ocm_config_mount_regression(tmp_path: Path) -> None:
    """Regression test for fix/ocm-config-mount — OCM config mounted at wrong path in container.

    Bug discovered: 2026-03-11
    Platform: macOS (Linux unaffected — same path on both sides)
    Severity: major
    Source: ad-hoc

    Problem:
        ContainerManager.create() mounts the host OCM config at /root/.config/ocm/ocm.json
        inside the container. However, the container runs as 'mcuser' (HOME=/home/mcuser),
        not root. mcuser cannot access /root/, so ocm sees no config at ~/.config/ocm/ocm.json
        (= /home/mcuser/.config/ocm/ocm.json) and fails with the misleading error:
        "please ensure you are logged into OCM by using the command 'ocm login --url $ENV'"

    Expected behaviour:
        The OCM config is mounted at /home/mcuser/.config/ocm/ocm.json so that the container
        user (mcuser) can read it and 'ocm backplane login <cluster-id>' succeeds.

    Actual behaviour:
        The OCM config is mounted at /root/.config/ocm/ocm.json. mcuser (uid=998) has no
        access to /root/, so ~/.config/ocm/ocm.json is effectively missing inside the container.

    Test approach:
        - Creates a fake OCM config file in tmp_path
        - Patches get_ocm_config_path() to return that temp path
        - Calls ContainerManager.create() with mocked Podman
        - Asserts the volumes dict includes a read-only mount at
          /home/mcuser/.config/ocm/ocm.json (the correct path for the container user)
        No real Podman required.

    This test will fail until the bug is fixed, then pass automatically.
    """
    from unittest.mock import MagicMock, Mock, patch

    from mc.container.manager import ContainerManager
    from mc.container.state import StateDatabase
    from mc.integrations.podman import PodmanClient

    # Create a fake OCM config that exists on disk
    fake_ocm = tmp_path / "ocm.json"
    fake_ocm.write_text('{"access_token": "fake-jwt"}')

    podman_client = Mock(spec=PodmanClient)
    state_db = Mock(spec=StateDatabase)
    podman_client.client.containers.list.return_value = []
    state_db.get_container.return_value = None
    mock_image = MagicMock()
    podman_client.client.images.get.return_value = mock_image
    mock_container = MagicMock()
    mock_container.id = "abc123"
    podman_client.client.containers.create.return_value = mock_container

    manager = ContainerManager(podman_client, state_db)

    with patch("mc.container.manager.os.makedirs"), \
         patch("mc.container.manager.get_ocm_config_path", return_value=fake_ocm):
        manager.create("12345678", "/path/to/workspace", "TestCustomer")

    create_call = podman_client.client.containers.create.call_args
    volumes = create_call.kwargs["volumes"]

    # The container user is 'mcuser' (HOME=/home/mcuser) — NOT root.
    # The mount target must reflect the container user's home directory.
    expected_target = "/home/mcuser/.config/ocm/ocm.json"
    ocm_mounts = [
        (src, spec) for src, spec in volumes.items()
        if isinstance(spec, dict) and spec.get("bind") == expected_target
    ]

    assert ocm_mounts, (
        f"ContainerManager.create() must mount the host OCM config at "
        f"'{expected_target}' inside the container (container user is mcuser, HOME=/home/mcuser).\n"
        f"Actual volumes passed to containers.create(): {volumes}\n"
        f"Bug: OCM config is mounted at /root/.config/ocm/ocm.json — mcuser cannot read /root/."
    )
    _src, spec = ocm_mounts[0]
    assert spec["mode"] == "ro", (
        f"OCM config mount must be read-only (mode='ro'), got mode='{spec['mode']}'"
    )


def _find_running_mc_container() -> str | None:
    """Return the name of the first running mc-* container, or None."""
    try:
        result = subprocess.run(
            ["podman", "ps", "--filter", "name=mc-", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10,
        )
        names = [n.strip() for n in result.stdout.strip().splitlines() if n.strip()]
        return names[0] if names else None
    except Exception:
        return None


@pytest.mark.integration
@pytest.mark.skipif(
    not _podman_available(),
    reason="Podman not available",
)
@pytest.mark.skipif(
    not _macos_pac_proxy_configured(),
    reason="macOS PAC proxy not configured — proxy detection not applicable on this host",
)
def test_container_macos_proxy_detection_regression():
    """Regression: HTTPS_PROXY must reach an interactive container shell via --env, not BASH_ENV.

    Bug class: host→container boundary
    Bug discovered: 2026-03-11
    Severity: major

    Problem:
        ocm backplane login times out inside containers with:
          WARN[0000] proxy-url must be set explicitly in either config file or via the
                     environment HTTPS_PROXY
          ERRO[0030] cannot connect to Backplane API URL: context deadline exceeded

    Root cause (two-part):
        1. On macOS with a PAC-based corporate proxy, os.environ['HTTPS_PROXY'] is empty.
           Go binaries on macOS auto-detect the system proxy via CFNetworkCopySystemProxySettings,
           but the Linux container only reads env vars.
        2. BASH_ENV is only sourced by non-interactive shells. Interactive bash sessions
           launched via `podman exec -it` ignore BASH_ENV entirely. Even if the proxy is in
           the bashrc (which was fixed first), it never reaches the shell.

    Fix:
        build_exec_command() now detects the proxy (env var or macOS system) and passes it
        directly as --env flags to podman exec, guaranteeing it reaches the interactive shell.

    Test approach (host→container boundary — MUST use real podman exec):
        1. Detect the host proxy via detect_macos_proxy()
        2. Find a real running mc container
        3. Run `podman exec --env HTTPS_PROXY=<value> <container> bash -c 'echo $HTTPS_PROXY'`
        4. Assert the proxy value is printed — confirming the env var reaches the container

    This test cannot pass without a running container because the bug is at the
    host→container boundary. Testing the Python string returned by generate_bashrc()
    or build_exec_command() is insufficient — it does not prove the env var reaches
    the running container process.
    """
    from mc.terminal.shell import detect_macos_proxy
    from mc.terminal.attach import build_exec_command

    # Step 1: Detect the proxy on the host (same logic as the fix)
    https_proxy = os.environ.get("HTTPS_PROXY")
    if not https_proxy:
        https_proxy = detect_macos_proxy()

    assert https_proxy is not None, (
        "PAC proxy is configured (scutil --proxy shows ProxyAutoConfigURLString) "
        "but detect_macos_proxy() returned None. The detection logic is broken."
    )

    # Step 2: Find a running mc container to exec into
    container_name = _find_running_mc_container()
    if container_name is None:
        pytest.skip(
            "No running mc container found. Run 'mc case <number>' first to create one, "
            "then re-run this test."
        )

    # Step 3: Verify proxy IS accessible when passed via --env (end-to-end, no mocks)
    exec_result = subprocess.run(
        [
            "podman", "exec",
            "--env", f"HTTPS_PROXY={https_proxy}",
            "--env", f"HTTP_PROXY={https_proxy}",
            container_name,
            "bash", "-c", "echo $HTTPS_PROXY",
        ],
        capture_output=True, text=True, timeout=15,
    )
    assert exec_result.returncode == 0, (
        f"podman exec failed with exit code {exec_result.returncode}.\n"
        f"stderr: {exec_result.stderr}"
    )
    assert exec_result.stdout.strip() == https_proxy, (
        f"HTTPS_PROXY not accessible inside container when passed via --env.\n"
        f"Container: {container_name}\n"
        f"Expected: {https_proxy!r}\n"
        f"Got:      {exec_result.stdout.strip()!r}\n"
        f"Bug: proxy must be passed as --env to podman exec, not only via BASH_ENV.\n"
        f"BASH_ENV is ignored by interactive bash sessions."
    )

    # Step 4: Verify build_exec_command() generates a command that contains the proxy --env flags
    cmd = build_exec_command(container_name, "/tmp/test.bashrc", "12345678")
    assert f"HTTPS_PROXY={https_proxy}" in cmd, (
        f"build_exec_command() did not include HTTPS_PROXY in the podman exec command.\n"
        f"Command: {cmd}\n"
        f"Expected it to contain: HTTPS_PROXY={https_proxy}"
    )
    assert f"HTTP_PROXY={https_proxy}" in cmd, (
        f"build_exec_command() did not include HTTP_PROXY in the podman exec command.\n"
        f"Command: {cmd}"
    )
