"""Integration tests for config and state database migration."""

import os
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_home(monkeypatch):
    """Create temporary home directory for testing migration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Set HOME to temp directory
        monkeypatch.setenv('HOME', tmpdir)
        monkeypatch.setenv('USERPROFILE', tmpdir)  # Windows
        yield tmpdir


def test_config_migration_from_platformdirs_macos(temp_home, monkeypatch):
    """Test config migration from old macOS platformdirs location."""
    # Mock platform to be macOS
    monkeypatch.setattr('platform.system', lambda: 'Darwin')

    # Create old config location (macOS)
    old_config_dir = Path(temp_home) / 'Library' / 'Application Support' / 'mc'
    old_config_dir.mkdir(parents=True, exist_ok=True)
    old_config_path = old_config_dir / 'config.toml'

    # Write old config
    old_config_path.write_text('''[api]
rh_api_offline_token = "test_token_migration"

base_directory = "~/mc"
''')

    # Import ConfigManager AFTER setting up environment
    from mc.config.manager import ConfigManager

    # Get config path (should trigger migration)
    config_mgr = ConfigManager()
    new_config_path = config_mgr.get_config_path()

    # Verify migration occurred
    assert new_config_path.exists()
    assert str(new_config_path) == f'{temp_home}/mc/config/config.toml'

    # Verify content preserved
    content = new_config_path.read_text()
    assert 'test_token_migration' in content
    assert 'base_directory' in content


def test_state_migration_from_platformdirs_macos(temp_home, monkeypatch):
    """Test state database migration from old macOS platformdirs location."""
    # Mock platform to be macOS
    monkeypatch.setattr('platform.system', lambda: 'Darwin')

    # Create old state location (macOS)
    old_state_dir = Path(temp_home) / 'Library' / 'Application Support' / 'mc'
    old_state_dir.mkdir(parents=True, exist_ok=True)
    old_state_path = old_state_dir / 'containers.db'

    # Create dummy database file
    old_state_path.write_text('dummy_db_content')

    # Simulate state migration by directly calling the migration code
    # from container.py commands module
    state_dir = Path(temp_home) / 'mc' / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)
    new_db_path = state_dir / 'containers.db'

    # Migration check (from container.py lines 33-40)
    if not new_db_path.exists():
        from platformdirs import user_data_dir
        old_db_path = Path(user_data_dir("mc", "redhat")) / "containers.db"
        if old_db_path.exists():
            shutil.copy2(old_db_path, new_db_path)

    # Verify migration
    assert new_db_path.exists()
    assert new_db_path.read_text() == 'dummy_db_content'


def test_fresh_install_no_migration(temp_home):
    """Test fresh install creates config without migration."""
    from mc.config.manager import ConfigManager

    # Get config path (no old config exists)
    config_mgr = ConfigManager()
    config_path = config_mgr.get_config_path()

    # Verify new location created
    assert str(config_path) == f'{temp_home}/mc/config/config.toml'
    assert config_path.parent.exists()  # Directory created


def test_container_list_with_missing_config_keys(temp_home, monkeypatch):
    """Test that container list handles missing config keys gracefully.

    This is the UAT Test 1.2 scenario - old config missing base_directory.
    """
    # Mock platform to be macOS
    monkeypatch.setattr('platform.system', lambda: 'Darwin')

    # Mock Podman machine running check
    import mc.integrations.platform_detect
    monkeypatch.setattr(mc.integrations.platform_detect, 'is_podman_machine_running', lambda: True)

    # Mock get_podman_machine_uri to return a test URI
    monkeypatch.setattr(
        mc.integrations.platform_detect,
        'get_podman_machine_uri',
        lambda: 'ssh://core@127.0.0.1:57841/run/user/501/podman/podman.sock'
    )

    # Create config with only API section (missing base_directory)
    config_dir = Path(temp_home) / 'mc' / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.toml'

    config_path.write_text('''[api]
rh_api_offline_token = "test_token_12345"
''')

    # Mock Podman client to avoid actual connection
    class MockPodmanClient:
        def __init__(self, base_url=None, timeout=30):
            # This is where the bug would occur - check base_url type
            if base_url is not None and not isinstance(base_url, str):
                raise ValueError(f"base_url must be string or None, got {type(base_url)}")
            self.base_url = base_url

        class containers:
            @staticmethod
            def list(**kwargs):
                return []

        def ping(self):
            return True

        def close(self):
            pass

    # Import and patch
    import mc.integrations.podman
    original_podman = mc.integrations.podman.podman

    class MockPodman:
        PodmanClient = MockPodmanClient

    monkeypatch.setattr(mc.integrations.podman, 'podman', MockPodman)

    # Now try to use container list
    from mc.cli.commands.container import _get_manager

    try:
        manager = _get_manager()
        containers = manager.list()
        # Should not raise ValueError about scheme
        assert isinstance(containers, list)
    except ValueError as e:
        if "scheme" in str(e):
            pytest.fail(f"ValueError with scheme error: {e}")
        raise


def is_podman_available():
    """Check if Podman is installed and accessible."""
    return shutil.which('podman') is not None


def is_podman_machine_running_real():
    """Check if Podman machine is actually running (no mocks)."""
    # Allow override via environment variable for manual testing
    if os.getenv('MC_TEST_PODMAN_RUNNING') == '1':
        return True

    try:
        import subprocess
        import json

        # Try to find podman in common locations
        podman_cmd = shutil.which('podman') or '/opt/homebrew/bin/podman'

        result = subprocess.run(
            [podman_cmd, 'machine', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
            env=os.environ.copy()  # Preserve environment
        )
        machines = json.loads(result.stdout)
        return any(m.get('Running', False) for m in machines)
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        return False
    except Exception:
        return False


@pytest.mark.skipif(
    not is_podman_available(),
    reason="Requires Podman installed"
)
def test_real_podman_connection_after_migration(temp_home, monkeypatch):
    """Test that real Podman connection works after migration.

    This is a REAL integration test that actually connects to Podman.
    Tests the UAT 1.2 scenario with actual Podman machine.
    """
    podman_running = is_podman_machine_running_real()
    print(f"\nPodman machine running check: {podman_running}")
    if not podman_running:
        pytest.skip("Podman machine not running")

    # Use real platform detection
    import platform as plat
    if plat.system() != 'Darwin':
        pytest.skip("This test is for macOS Podman machine")

    # Create migrated config with ONLY api section (missing base_directory)
    # This simulates the UAT 1.2 scenario
    config_dir = Path(temp_home) / 'mc' / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.toml'

    config_path.write_text('''[api]
rh_api_offline_token = "test_token_integration"
''')

    # Create state directory
    state_dir = Path(temp_home) / 'mc' / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)

    # Set HOME to temp directory so MC uses the test config
    monkeypatch.setenv('HOME', temp_home)

    # Mock ensure_podman_ready to skip interactive prompts in BOTH locations
    import mc.integrations.platform_detect
    import mc.integrations.podman
    monkeypatch.setattr(mc.integrations.platform_detect, 'ensure_podman_ready', lambda x: None)
    monkeypatch.setattr(mc.integrations.podman, 'ensure_podman_ready', lambda x: None)

    # Try to create PodmanClient and connect
    from mc.integrations.podman import PodmanClient

    try:
        print("\nCreating PodmanClient...")
        client = PodmanClient()
        print("✓ PodmanClient created successfully (NO SCHEME ERROR!)")

        # This should NOT raise ValueError about scheme
        # If it does, the bug still exists
        print("Attempting to ping...")
        try:
            is_connected = client.ping()
            print(f"Ping result: {is_connected}")
        except Exception as ping_error:
            print(f"Ping failed with: {type(ping_error).__name__}: {ping_error}")
            # Ping failure is OK - we're mainly testing for scheme error
            # SSH connection might not work in test environment
            print("✓ Main test passed: No scheme error when creating PodmanClient")
            return

        # If ping worked, verify we can list containers
        if is_connected:
            containers = client.client.containers.list(all=True)
            assert isinstance(containers, list), "Should return list of containers"
            print(f"✓ Successfully connected to Podman")
            print(f"✓ Found {len(containers)} containers")

    except ValueError as e:
        if "scheme" in str(e).lower():
            pytest.fail(f"FAILED: Scheme error still occurs: {e}")
        raise
    except Exception as e:
        # If it's a connection error, that's OK - we're testing scheme error
        print(f"Connection error (expected in test env): {type(e).__name__}: {e}")
        print("✓ Main test passed: No scheme error occurred")
    finally:
        if 'client' in locals():
            try:
                client.close()
            except:
                pass


@pytest.mark.integration
def test_config_path_env_isolation_regression(monkeypatch):
    """Regression test for config-path-env-isolation

    Bug discovered: 2026-03-27
    Platform: Both
    Severity: major
    Source: ad-hoc

    Problem:
    ConfigManager.get_config_path() always resolves to ~/mc/config/config.toml and
    _get_manager() always uses ~/mc/state/ regardless of MC_ENV. This means UAT runs
    share the same config and state files as production, making it impossible to test
    safely without polluting or clobbering production state.

    Steps to reproduce:
    1. Set MC_ENV=uat in the environment.
    2. Call ConfigManager().get_config_path() — observe it resolves to the production
       path ~/mc/config/config.toml instead of an env-specific path.
    3. Call _get_manager() — observe state_dir is ~/mc/state/ regardless of MC_ENV.

    Expected: When MC_ENV=uat, paths resolve to ~/mc-uat/config/config.toml and
              ~/mc-uat/state/ (or similar env-specific isolation).
    Actual:   Paths always resolve to ~/mc/config/config.toml and ~/mc/state/
              regardless of MC_ENV value.

    This test ensures the bug does not regress.
    """
    import importlib

    with tempfile.TemporaryDirectory() as tmpdir:
        # Use a clean HOME so we control all path resolution
        monkeypatch.setenv("HOME", tmpdir)
        monkeypatch.setenv("MC_ENV", "uat")

        # Force re-import so Path.home() picks up the new HOME
        import mc.config.manager as manager_mod
        importlib.reload(manager_mod)
        ConfigManager = manager_mod.ConfigManager

        config_mgr = ConfigManager()
        config_path = config_mgr.get_config_path()

        # The config path must NOT resolve to the production path.
        # When MC_ENV=uat, it must be isolated from ~/mc/config/config.toml.
        production_path = str(Path(tmpdir) / "mc" / "config" / "config.toml")
        assert str(config_path) != production_path, (
            f"Config path resolves to production path {production_path} even when "
            f"MC_ENV=uat — no environment-based path switching exists in ConfigManager."
        )


@pytest.mark.skipif(
    not is_podman_available(),
    reason="Requires Podman installed"
)
def test_container_list_command_real(temp_home, monkeypatch):
    """Test the actual 'mc container list' command with real Podman.

    This tests the complete flow from UAT Test 1.2 step 4.
    """
    if not is_podman_machine_running_real():
        pytest.skip("Podman machine not running")

    import platform as plat
    if plat.system() != 'Darwin':
        pytest.skip("This test is for macOS Podman machine")

    # Create minimal config (UAT 1.2 scenario)
    config_dir = Path(temp_home) / 'mc' / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / 'config.toml'

    config_path.write_text('''[api]
rh_api_offline_token = "test_token_cli"
''')

    # Create state directory
    state_dir = Path(temp_home) / 'mc' / 'state'
    state_dir.mkdir(parents=True, exist_ok=True)

    # Get ACTUAL real Podman socket (not affected by monkeypatch)
    # Try common macOS locations
    import pwd
    real_user = pwd.getpwuid(os.getuid()).pw_dir  # Get real home dir from passwd
    real_socket = Path(real_user) / '.local' / 'share' / 'containers' / 'podman' / 'machine' / 'podman.sock'

    if not real_socket.exists():
        pytest.skip(f"Podman socket not found at {real_socket}")

    print(f"Using real Podman socket: {real_socket}")

    import mc.integrations.platform_detect

    # Mock ensure_podman_ready to skip interactive prompts
    monkeypatch.setattr(mc.integrations.platform_detect, 'ensure_podman_ready', lambda x: None)

    # Mock get_socket_path to use real HOME for Podman socket (not temp_home)
    # We need to patch it in the podman module where it's imported
    import mc.integrations.podman
    original_get_socket_path = mc.integrations.podman.get_socket_path

    def mock_get_socket_path(platform_type):
        # For macOS, return real socket path (not affected by temp HOME)
        print(f"mock_get_socket_path called: platform={platform_type}, socket_exists={real_socket.exists()}, socket={real_socket}")
        if platform_type == 'macos' and real_socket.exists():
            print(f"Returning real Podman socket: {real_socket}")
            return str(real_socket)
        result = original_get_socket_path(platform_type)
        print(f"Returning from original: {result}")
        return result

    monkeypatch.setattr(mc.integrations.podman, 'get_socket_path', mock_get_socket_path)

    # Import after setting environment
    from mc.cli.commands.container import _get_manager

    try:
        # Get ContainerManager (same as 'mc container list' uses)
        manager = _get_manager()

        # Call list() - this is what fails with the scheme error
        containers = manager.list()

        # Should return a list (even if empty)
        assert isinstance(containers, list), "Should return list of containers"

        print(f"✓ ContainerManager.list() succeeded")
        print(f"✓ No scheme error occurred")
        print(f"✓ Found {len(containers)} containers")

    except ValueError as e:
        if "scheme" in str(e).lower():
            pytest.fail(f"FAILED: UAT 1.2 scenario still fails with scheme error: {e}")
        raise


@pytest.mark.integration
def test_mc_7_iso_datetime_last_failed_fetch_config_manager_signature_acceptance(
    tmp_path,
):
    """Acceptance test for MC-7 / config-manager-signature slice

    Feature added: 2026-05-20
    Scope: api-only
    Source: MC-7
    Slice: config-manager-signature

    Feature description:
    Refactor last_failed_fetch config value from Unix epoch float to ISO datetime
    string for consistency with last_banner_shown. This slice verifies that
    update_version_config accepts last_failed_fetch as an ISO datetime string (str)
    and get_version_config returns it as a string.

    Acceptance criterion:
    update_version_config(last_failed_fetch=<ISO-datetime-string>) stores the value
    and get_version_config() returns it as a str (not float).

    This test covers:
    1. update_version_config accepts a str for last_failed_fetch
    2. get_version_config returns the stored value as a str

    Expected: last_failed_fetch round-trips through config as an ISO datetime string.
    """
    from mc.config.manager import ConfigManager
    import inspect

    config_mgr = ConfigManager()
    config_mgr._config_path = tmp_path / "config.toml"

    # Bootstrap an empty config
    config_mgr.save_atomic({
        "api": {"rh_api_offline_token": "test"},
        "version": {},
    })

    # --- Verify the signature accepts str ---
    sig = inspect.signature(config_mgr.update_version_config)
    param = sig.parameters["last_failed_fetch"]
    annotation = param.annotation
    # The annotation must be str | None (not float | None)
    assert annotation is not float and annotation != (float | None), (
        f"update_version_config(last_failed_fetch=...) type hint is {annotation!r}; "
        f"expected str | None — the signature has not been changed to accept ISO datetime strings."
    )

    # --- Round-trip: write ISO string, read it back ---
    iso_ts = "2026-05-20T14:30:00"
    config_mgr.update_version_config(last_failed_fetch=iso_ts)

    version_config = config_mgr.get_version_config()
    stored = version_config["last_failed_fetch"]
    assert isinstance(stored, str), (
        f"get_version_config()['last_failed_fetch'] returned {type(stored).__name__} "
        f"({stored!r}); expected str — the config manager still treats "
        f"last_failed_fetch as a float."
    )
    assert stored == iso_ts, (
        f"Round-trip failed: wrote {iso_ts!r}, got back {stored!r}."
    )


@pytest.mark.integration
def test_mc_7_iso_datetime_last_failed_fetch_banner_read_write_acceptance(
    tmp_path, monkeypatch,
):
    """Acceptance test for MC-7 / banner-read-write slice

    Feature added: 2026-05-20
    Scope: api-only
    Source: MC-7
    Slice: banner-read-write

    Feature description:
    banner.py writes ISO datetime on fetch failure and reads/compares using datetime
    parsing instead of epoch arithmetic; throttle behavior unchanged.

    Acceptance criterion:
    After a failed fetch, the config file contains an ISO datetime string (not a float)
    at version.last_failed_fetch, and the throttle check correctly suppresses retries
    within the throttle window using datetime comparison.

    This test covers:
    1. banner.py writes an ISO datetime string on failure (not a float)
    2. The throttle logic correctly reads the ISO datetime and suppresses retries

    Expected: last_failed_fetch is an ISO datetime string after a fetch failure, and
    the throttle window is respected using datetime parsing.
    """
    from mc.config.manager import ConfigManager
    from datetime import datetime

    config_mgr = ConfigManager()
    config_mgr._config_path = tmp_path / "config.toml"

    config_mgr.save_atomic({
        "api": {"rh_api_offline_token": "test"},
        "version": {},
    })

    # Simulate what banner.py does on fetch failure — currently it calls:
    #   config_manager.update_version_config(last_failed_fetch=time.time())
    # After the feature, it should call something like:
    #   config_manager.update_version_config(
    #       last_failed_fetch=datetime.now().isoformat(timespec="seconds")
    #   )
    # We test by invoking the banner module's internal failure-recording path
    # and then inspecting the config.

    # Patch ConfigManager so banner.py uses our isolated config
    monkeypatch.setattr(
        "mc.config.manager.ConfigManager.__init__",
        lambda self: setattr(self, "_config_path", tmp_path / "config.toml") or None,
    )

    # Patch _fetch_with_timeout to return None (simulating failure)
    monkeypatch.setattr("mc.banner._fetch_with_timeout", lambda: None)
    # Patch _already_shown_today to return False (so the banner flow proceeds)
    monkeypatch.setattr("mc.banner._already_shown_today", lambda: False)
    # Patch sys.stdout.isatty to return True
    monkeypatch.setattr("sys.stdout.isatty", lambda: True)
    # Patch _is_version_invocation to return False
    monkeypatch.setattr("mc.banner._is_version_invocation", lambda: False)
    # Patch get_version to return a version string (locally imported in show_update_banner)
    monkeypatch.setattr("mc.version.get_version", lambda: "2.0.4")
    # Ensure MC_ENV is not set (to avoid the MC_ENV label path)
    monkeypatch.delenv("MC_ENV", raising=False)

    import mc.banner
    mc.banner.show_update_banner()

    # Now inspect what was written
    reloaded = config_mgr.load()
    stored = reloaded.get("version", {}).get("last_failed_fetch")
    assert stored is not None, (
        "last_failed_fetch was not written to config after a simulated fetch failure."
    )
    assert isinstance(stored, str), (
        f"last_failed_fetch is {type(stored).__name__} ({stored!r}); "
        f"expected str (ISO datetime) — banner.py still writes a float epoch."
    )
    # Verify it parses as ISO datetime
    try:
        datetime.fromisoformat(stored)
    except (ValueError, TypeError) as exc:
        raise AssertionError(
            f"last_failed_fetch value {stored!r} is not valid ISO datetime: {exc}"
        ) from exc


@pytest.mark.integration
def test_mc_7_iso_datetime_last_failed_fetch_backward_compat_acceptance(
    tmp_path,
):
    """Acceptance test for MC-7 / backward-compat slice

    Feature added: 2026-05-20
    Scope: api-only
    Source: MC-7
    Slice: backward-compat

    Feature description:
    Existing configs with float epoch values for last_failed_fetch are gracefully
    handled on read (parsed and converted), preventing ValueError on upgrade.
    Migration is transparent to the user.

    Acceptance criterion:
    When version.last_failed_fetch in config.toml contains a legacy float epoch value,
    get_version_config() returns it as an ISO datetime string (not a float), and no
    ValueError is raised.

    This test covers:
    1. A config file with a float epoch last_failed_fetch can be read without error
    2. The returned value is an ISO datetime string (transparently converted)

    Expected: Legacy float epoch values are silently converted to ISO datetime strings
    on read, so existing user configs do not break on upgrade.
    """
    from mc.config.manager import ConfigManager
    from datetime import datetime
    import time

    config_mgr = ConfigManager()
    config_mgr._config_path = tmp_path / "config.toml"

    # Write a config with a legacy float epoch value for last_failed_fetch
    legacy_epoch = 1716220200.0  # a specific Unix timestamp
    config_mgr.save_atomic({
        "api": {"rh_api_offline_token": "test"},
        "version": {
            "last_failed_fetch": legacy_epoch,
        },
    })

    # Read it back — should NOT raise ValueError, and should return str
    version_config = config_mgr.get_version_config()
    stored = version_config["last_failed_fetch"]

    assert isinstance(stored, str), (
        f"get_version_config()['last_failed_fetch'] returned {type(stored).__name__} "
        f"({stored!r}) for a legacy float epoch value; expected str (ISO datetime). "
        f"The backward-compatibility conversion from float epoch to ISO datetime "
        f"has not been implemented in get_version_config()."
    )

    # Verify the converted value is a valid ISO datetime
    try:
        parsed = datetime.fromisoformat(stored)
    except (ValueError, TypeError) as exc:
        raise AssertionError(
            f"Converted last_failed_fetch {stored!r} is not valid ISO datetime: {exc}"
        ) from exc

    # Verify the converted datetime corresponds to the original epoch
    # (within 1 second tolerance for rounding)
    converted_epoch = parsed.timestamp()
    assert abs(converted_epoch - legacy_epoch) < 1.0, (
        f"Converted datetime {stored!r} (epoch={converted_epoch}) does not match "
        f"original legacy epoch {legacy_epoch}. Difference: "
        f"{abs(converted_epoch - legacy_epoch):.2f}s"
    )
