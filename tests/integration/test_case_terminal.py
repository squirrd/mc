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

    Problem:
    Running `mc case 04347611` multiple times incorrectly allows multiple
    terminal windows to be spun up instead of focusing the existing window.

    Expected behavior:
    1. First call: Creates new terminal window
    2. Second call: Finds existing window, focuses it, shows message
       "Focused existing terminal for case 04347611"
    3. No new terminal window created on second call

    Actual behavior (before fix):
    1. First call: Creates new terminal window
    2. Second call: Creates ANOTHER new terminal window
    3. No "Focused" message shown
    4. Duplicate detection not working

    Root cause:
    The duplicate detection logic in src/mc/terminal/attach.py:241-257 exists
    but the find_window_by_title() method may not be finding the existing window.

    Possible issues:
    1. Window title search in iTerm2 AppleScript not matching
    2. Timing issue - window not fully created before second search
    3. Title escaping causing mismatch between set and search
    4. Session name vs window name mismatch in iTerm2

    Steps to reproduce:
    1. Run: mc case 04347611
    2. Run: mc case 04347611 (again)
    3. Observe: Two terminal windows exist instead of focusing first

    This test verifies:
    1. First attach_terminal creates a new window (launcher.launch called once)
    2. Second attach_terminal finds existing window (find_window_by_title returns True)
    3. Second attach_terminal does NOT create new window (launcher.launch not called again)
    4. "Focused existing terminal" message shown on second call

    UAT Test: 5.2 Duplicate Launch Detection
    Fixed in: TBD (test currently reproduces the bug)
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

    # Create mock launcher that simulates window creation and finding
    mock_launcher = mocker.MagicMock()

    # Track which titles have been "created" (simulates windows that exist)
    created_windows = []

    def mock_launch(options):
        """Simulate launching a window - add its title to created_windows."""
        created_windows.append(options.title)
        print(f"Mock: Created window with title: {options.title}")

    def mock_find(title):
        """Simulate finding a window - check if title in created_windows."""
        found = title in created_windows
        print(f"Mock: Searching for window with title: {title}")
        print(f"Mock: Created windows: {created_windows}")
        print(f"Mock: Found: {found}")
        return found

    def mock_focus(title):
        """Simulate focusing a window - return True if it exists."""
        can_focus = title in created_windows
        print(f"Mock: Attempting to focus window with title: {title}")
        print(f"Mock: Can focus: {can_focus}")
        return can_focus

    mock_launcher.launch.side_effect = mock_launch
    mock_launcher.find_window_by_title.side_effect = mock_find
    mock_launcher.focus_window_by_title.side_effect = mock_focus

    # Make launcher be a MacOSLauncher instance (for duplicate detection to run)
    from mc.terminal.macos import MacOSLauncher
    mock_launcher.__class__ = MacOSLauncher

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
        # FIRST CALL: Attach terminal for the first time
        print("\n=== FIRST CALL: mc case 04347611 ===")
        attach_terminal(
            case_number=test_case_number,
            config_manager=config_manager,
            api_client=api_client,
            container_manager=container_manager,
        )

        # Verify: launcher.launch was called once (new window created)
        assert mock_launcher.launch.call_count == 1, (
            f"First call should launch new window\n"
            f"Expected launch call count: 1\n"
            f"Actual: {mock_launcher.launch.call_count}"
        )

        # Get the title that was used for the first window
        first_call_args = mock_launcher.launch.call_args_list[0]
        first_window_title = first_call_args[0][0].title
        print(f"\n✓ First call created window with title: {first_window_title}")

        # SECOND CALL: Attach terminal again (should focus existing, not create new)
        print("\n=== SECOND CALL: mc case 04347611 ===")

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

        # CRITICAL ASSERTIONS for duplicate prevention

        # 1. find_window_by_title should have been called on second attach
        if mock_launcher.find_window_by_title.call_count == 0:
            pytest.fail(
                f"✗ BUG FOUND: find_window_by_title was never called!\n"
                f"Duplicate detection not running at all.\n"
                f"Check: Is launcher instance being detected as MacOSLauncher?\n"
                f"Launcher type: {type(mock_launcher)}\n"
                f"Fix needed in: src/mc/terminal/attach.py:246 isinstance check"
            )

        # 2. find_window_by_title should return True (window exists)
        # Get the result of the find call
        find_calls = [call for call in mock_launcher.find_window_by_title.call_args_list]
        if not find_calls:
            pytest.fail("✗ BUG: find_window_by_title was never called")

        # Check if find returned True (our mock tracks this)
        find_title = find_calls[-1][0][0]  # Title used in last find call
        window_was_found = find_title in created_windows

        if not window_was_found:
            pytest.fail(
                f"✗ BUG FOUND: find_window_by_title returned False when window exists\n"
                f"Searching for title: {find_title}\n"
                f"Created windows: {created_windows}\n"
                f"First window title: {first_window_title}\n"
                f"Title mismatch? {find_title != first_window_title}\n"
                f"Possible causes:\n"
                f"1. Title format changed between calls\n"
                f"2. Title escaping issues\n"
                f"3. Case metadata changed causing different title\n"
                f"Fix needed in: src/mc/terminal/macos.py find_window_by_title()"
            )

        # 3. launcher.launch should NOT be called a second time
        if mock_launcher.launch.call_count > 1:
            pytest.fail(
                f"✗ BUG FOUND: launcher.launch called {mock_launcher.launch.call_count} times!\n"
                f"Expected: 1 (create once, then focus)\n"
                f"Actual: {mock_launcher.launch.call_count}\n"
                f"Multiple terminals created instead of focusing existing one.\n"
                f"Fix needed in: src/mc/terminal/attach.py duplicate detection logic"
            )

        # 4. "Focused existing terminal" message should be shown
        if "Focused existing terminal" not in output:
            pytest.fail(
                f"✗ BUG FOUND: No 'Focused existing terminal' message shown\n"
                f"Captured output: {output}\n"
                f"Expected: 'Focused existing terminal for case {test_case_number}'\n"
                f"User should see feedback that window was focused, not recreated."
            )

        # 5. focus_window_by_title should have been called
        if mock_launcher.focus_window_by_title.call_count == 0:
            pytest.fail(
                f"✗ BUG FOUND: focus_window_by_title was never called\n"
                f"Window found but not focused.\n"
                f"Fix needed in: src/mc/terminal/attach.py:250 focus logic"
            )

        print("\n✓ Test PASSED: Duplicate prevention working correctly")
        print(f"✓ First call: Created window")
        print(f"✓ Second call: Found existing window and focused it")
        print(f"✓ No duplicate window created")
        print(f"✓ User message shown: 'Focused existing terminal for case {test_case_number}'")

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
