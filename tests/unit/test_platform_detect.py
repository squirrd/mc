"""Unit tests for platform detection module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mc.integrations.platform_detect import (
    check_podman_version,
    detect_platform,
    ensure_podman_ready,
    get_socket_path,
    is_podman_machine_running,
)


class TestDetectPlatform:
    """Tests for detect_platform()."""

    def test_detect_platform_macos(self, mocker):
        """Test detection of macOS platform."""
        mocker.patch('platform.system', return_value='Darwin')
        assert detect_platform() == 'macos'

    def test_detect_platform_linux(self, mocker):
        """Test detection of Linux platform."""
        mocker.patch('platform.system', return_value='Linux')
        assert detect_platform() == 'linux'

    def test_detect_platform_unsupported(self, mocker):
        """Test detection of unsupported platform."""
        mocker.patch('platform.system', return_value='Windows')
        assert detect_platform() == 'unsupported'


class TestIsPodmanMachineRunning:
    """Tests for is_podman_machine_running()."""

    def test_is_podman_machine_running_true(self, mocker):
        """Test when Podman machine is running."""
        mock_result = MagicMock()
        mock_result.stdout = '[{"Name": "podman-machine-default", "Running": true}]'
        mocker.patch('subprocess.run', return_value=mock_result)

        assert is_podman_machine_running() is True

    def test_is_podman_machine_running_false(self, mocker):
        """Test when Podman machine is stopped."""
        mock_result = MagicMock()
        mock_result.stdout = '[{"Name": "podman-machine-default", "Running": false}]'
        mocker.patch('subprocess.run', return_value=mock_result)

        assert is_podman_machine_running() is False

    def test_is_podman_machine_running_multiple_machines(self, mocker):
        """Test with multiple machines where one is running."""
        mock_result = MagicMock()
        mock_result.stdout = '[{"Name": "machine1", "Running": false}, {"Name": "machine2", "Running": true}]'
        mocker.patch('subprocess.run', return_value=mock_result)

        assert is_podman_machine_running() is True

    def test_is_podman_machine_running_error(self, mocker):
        """Test when subprocess raises CalledProcessError."""
        mocker.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'podman'))

        assert is_podman_machine_running() is False

    def test_is_podman_machine_running_json_error(self, mocker):
        """Test when JSON parsing fails."""
        mock_result = MagicMock()
        mock_result.stdout = 'invalid json'
        mocker.patch('subprocess.run', return_value=mock_result)

        assert is_podman_machine_running() is False

    def test_is_podman_machine_running_not_found(self, mocker):
        """Test when podman command is not found."""
        mocker.patch('subprocess.run', side_effect=FileNotFoundError)

        assert is_podman_machine_running() is False


class TestEnsurePodmanReady:
    """Tests for ensure_podman_ready()."""

    def test_ensure_podman_ready_macos_running(self, mocker):
        """Test macOS when machine is already running."""
        mocker.patch(
            'mc.integrations.platform_detect.is_podman_machine_running',
            return_value=True
        )
        mock_run = mocker.patch('subprocess.run')

        ensure_podman_ready('macos')

        # Should not call machine start
        mock_run.assert_not_called()

    def test_ensure_podman_ready_macos_start_yes(self, mocker):
        """Test macOS when user accepts to start machine."""
        mocker.patch(
            'mc.integrations.platform_detect.is_podman_machine_running',
            return_value=False
        )
        mocker.patch('builtins.input', return_value='y')
        mock_run = mocker.patch('subprocess.run')

        ensure_podman_ready('macos')

        # Should call machine start
        mock_run.assert_called_once_with(['podman', 'machine', 'start'], check=True)

    def test_ensure_podman_ready_macos_start_no(self, mocker):
        """Test macOS when user declines to start machine."""
        mocker.patch(
            'mc.integrations.platform_detect.is_podman_machine_running',
            return_value=False
        )
        mocker.patch('builtins.input', return_value='n')

        with pytest.raises(RuntimeError, match="Podman machine must be running"):
            ensure_podman_ready('macos')

    def test_ensure_podman_ready_linux_success(self, mocker):
        """Test Linux when Podman is installed."""
        mock_run = mocker.patch('subprocess.run')

        ensure_podman_ready('linux')

        mock_run.assert_called_once_with(
            ['podman', '--version'],
            capture_output=True,
            check=True
        )

    def test_ensure_podman_ready_linux_not_installed(self, mocker):
        """Test Linux when Podman is not installed."""
        mocker.patch('subprocess.run', side_effect=FileNotFoundError)

        with pytest.raises(RuntimeError, match="Podman is not installed"):
            ensure_podman_ready('linux')

    def test_ensure_podman_ready_linux_called_process_error(self, mocker):
        """Test Linux when podman command fails."""
        mocker.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'podman'))

        with pytest.raises(RuntimeError, match="Podman is not installed"):
            ensure_podman_ready('linux')

    def test_ensure_podman_ready_unsupported(self):
        """Test unsupported platform."""
        with pytest.raises(RuntimeError, match="Unsupported platform: unsupported"):
            ensure_podman_ready('unsupported')


class TestGetSocketPath:
    """Tests for get_socket_path()."""

    def test_get_socket_path_env_override(self, mocker):
        """Test with CONTAINER_HOST environment variable set."""
        mocker.patch.dict('os.environ', {'CONTAINER_HOST': 'unix:///custom/path/podman.sock'})

        result = get_socket_path('linux')

        assert result == '/custom/path/podman.sock'

    def test_get_socket_path_env_override_no_prefix(self, mocker):
        """Test with CONTAINER_HOST without unix:// prefix."""
        mocker.patch.dict('os.environ', {'CONTAINER_HOST': '/custom/path/podman.sock'})

        result = get_socket_path('linux')

        assert result == '/custom/path/podman.sock'

    def test_get_socket_path_linux_rootless(self, mocker):
        """Test Linux rootless socket path."""
        mocker.patch.dict('os.environ', {'XDG_RUNTIME_DIR': '/run/user/1000'}, clear=True)
        mock_path = mocker.patch('pathlib.Path.exists', return_value=True)

        result = get_socket_path('linux')

        assert result == '/run/user/1000/podman/podman.sock'

    def test_get_socket_path_linux_rootless_no_xdg(self, mocker):
        """Test Linux rootless without XDG_RUNTIME_DIR."""
        mocker.patch.dict('os.environ', {}, clear=True)
        mocker.patch('os.getuid', return_value=1000)
        mocker.patch('pathlib.Path.exists', return_value=True)

        result = get_socket_path('linux')

        assert result == '/run/user/1000/podman/podman.sock'

    def test_get_socket_path_linux_rootful_fallback(self, mocker):
        """Test Linux fallback to rootful socket."""
        mocker.patch.dict('os.environ', {}, clear=True)
        mocker.patch('os.getuid', return_value=1000)

        # Mock Path.exists to return False for rootless, True for rootful
        def exists_side_effect(self):
            return str(self) == '/run/podman/podman.sock'

        mocker.patch('pathlib.Path.exists', exists_side_effect)

        result = get_socket_path('linux')

        assert result == '/run/podman/podman.sock'

    def test_get_socket_path_linux_no_socket_exists(self, mocker):
        """Test Linux when no socket exists yet."""
        mocker.patch.dict('os.environ', {'XDG_RUNTIME_DIR': '/run/user/1000'}, clear=True)
        mocker.patch('pathlib.Path.exists', return_value=False)

        result = get_socket_path('linux')

        # Should return default rootless path even if it doesn't exist
        assert result == '/run/user/1000/podman/podman.sock'

    def test_get_socket_path_macos(self):
        """Test macOS returns machine socket path if it exists, else None."""
        result = get_socket_path('macos')

        # Should return machine socket path if it exists, else None
        if result is not None:
            assert 'podman/machine/podman.sock' in result
        # If None, that's also valid (socket doesn't exist yet)

    def test_get_socket_path_unsupported(self):
        """Test unsupported platform raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported platform"):
            get_socket_path('unsupported')


class TestCheckPodmanVersion:
    """Tests for check_podman_version()."""

    def test_check_podman_version_ok(self, mocker):
        """Test compatible Podman version."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 5.2.1'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['version'] == '5.2'
        assert result['major'] == 5
        assert result['minor'] == 2
        assert result['action'] == 'ok'

    def test_check_podman_version_warn(self, mocker):
        """Test version 3 behind triggers warning."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 4.7.0'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['version'] == '4.7'
        assert result['action'] == 'warn'
        assert '3+ versions behind' in result['message']

    def test_check_podman_version_fail(self, mocker):
        """Test version 7+ behind triggers failure."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 4.2.0'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['version'] == '4.2'
        assert result['action'] == 'fail'
        assert '7+ versions behind' in result['message']

    def test_check_podman_version_newer(self, mocker):
        """Test newer version is compatible."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 6.0.0'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['version'] == '6.0'
        assert result['action'] == 'ok'

    def test_check_podman_version_not_installed(self, mocker):
        """Test when Podman is not installed."""
        mocker.patch('subprocess.run', side_effect=FileNotFoundError)

        result = check_podman_version()

        assert result['version'] is None
        assert result['action'] == 'fail'
        assert 'not installed' in result['message']

    def test_check_podman_version_called_process_error(self, mocker):
        """Test when podman command fails."""
        mocker.patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, 'podman'))

        result = check_podman_version()

        assert result['version'] is None
        assert result['action'] == 'fail'

    def test_check_podman_version_parse_error(self, mocker):
        """Test when version cannot be parsed."""
        mock_result = MagicMock()
        mock_result.stdout = 'invalid version output'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['action'] == 'fail'
        assert 'Could not parse version' in result['message']

    def test_check_podman_version_with_dev_suffix(self, mocker):
        """Test parsing version with -dev suffix."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 5.3.0-dev'
        mocker.patch('subprocess.run', return_value=mock_result)

        result = check_podman_version()

        assert result['version'] == '5.3'
        assert result['major'] == 5
        assert result['minor'] == 3
        assert result['action'] == 'ok'

    def test_check_podman_version_custom_thresholds(self, mocker):
        """Test custom warn and fail thresholds."""
        mock_result = MagicMock()
        mock_result.stdout = 'podman version 4.8.0'
        mocker.patch('subprocess.run', return_value=mock_result)

        # With default thresholds (warn=3, fail=7), 4.8 should be OK
        result = check_podman_version(warn_threshold=2, fail_threshold=5)

        assert result['version'] == '4.8'
        assert result['action'] == 'warn'
