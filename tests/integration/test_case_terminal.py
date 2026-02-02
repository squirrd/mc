"""Integration test for case terminal command.

Tests the end-to-end terminal attachment workflow with real components.
Skipped unless Podman and Salesforce are available.
"""

import os
import tempfile

import pytest

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
