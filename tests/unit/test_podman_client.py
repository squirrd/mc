"""Unit tests for Podman client wrapper."""

import time
from unittest.mock import MagicMock, Mock, patch, call

import pytest

from mc.integrations.podman import PodmanClient, retry_podman_operation


class TestPodmanClientInit:
    """Tests for PodmanClient initialization."""

    def test_init_no_args(self):
        """Test instantiation with no arguments."""
        client = PodmanClient()
        assert client._socket_path is None
        assert client._timeout == 120
        assert client._client is None
        assert client._platform_type is None

    def test_init_custom_socket(self):
        """Test instantiation with custom socket path."""
        socket_path = "/custom/path/podman.sock"
        client = PodmanClient(socket_path=socket_path)
        assert client._socket_path == socket_path
        assert client._timeout == 120

    def test_init_custom_timeout(self):
        """Test instantiation with custom timeout."""
        client = PodmanClient(timeout=60)
        assert client._socket_path is None
        assert client._timeout == 60

    def test_init_all_custom(self):
        """Test instantiation with all custom parameters."""
        socket_path = "/custom/path/podman.sock"
        timeout = 90
        client = PodmanClient(socket_path=socket_path, timeout=timeout)
        assert client._socket_path == socket_path
        assert client._timeout == timeout


class TestPodmanClientLazyConnection:
    """Tests for lazy connection behavior."""

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_lazy_connection_on_first_access(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test that connection is established on first .client access."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        assert client._client is None

        # First access triggers connection
        result = client.client
        assert result is mock_client_instance
        mock_detect.assert_called_once()
        mock_ensure.assert_called_once_with('linux')
        mock_get_socket.assert_called_once_with('linux')
        mock_podman_client.assert_called_once_with(
            base_url='unix:///run/user/1000/podman/podman.sock',
            timeout=120
        )

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_lazy_connection_cached(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test that client is cached after first access."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()

        # Access client twice
        result1 = client.client
        result2 = client.client

        # Should return same instance
        assert result1 is result2
        # PodmanClient should only be instantiated once
        assert mock_podman_client.call_count == 1

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_connection_failure(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test that connection failures raise helpful error."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_podman_client.side_effect = ConnectionError("Connection refused")

        client = PodmanClient()

        with pytest.raises(ConnectionError) as exc_info:
            _ = client.client

        error_msg = str(exc_info.value)
        assert "Cannot connect to Podman socket" in error_msg
        assert "/run/user/1000/podman/podman.sock" in error_msg
        assert "dnf install podman" in error_msg  # Linux remediation


class TestPodmanClientMethods:
    """Tests for PodmanClient methods."""

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_ping_success(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test ping returns True on success."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        mock_client_instance = MagicMock()
        mock_client_instance.ping.return_value = True
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        assert client.ping() is True

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_ping_failure(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test ping returns False on exception."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        mock_client_instance = MagicMock()
        mock_client_instance.ping.side_effect = Exception("Connection error")
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        assert client.ping() is False

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_get_version(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test get_version returns version dict."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        version_info = {"Version": "5.2.1", "ApiVersion": "1.40"}
        mock_client_instance = MagicMock()
        mock_client_instance.version.return_value = version_info
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        result = client.get_version()
        assert result == version_info

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_close(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test close method closes client and sets to None."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        # Access client to create connection
        _ = client.client
        assert client._client is not None

        # Close connection
        client.close()
        assert client._client is None
        mock_client_instance.close.assert_called_once()

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_context_manager(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test context manager creates and closes client."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        with PodmanClient() as client:
            # Access client inside context
            _ = client.client
            assert client._client is not None

        # Client should be closed after exiting context
        assert client._client is None
        mock_client_instance.close.assert_called_once()


class TestRetryLogic:
    """Tests for retry_podman_operation function."""

    def test_retry_success_first_attempt(self):
        """Test operation succeeds on first attempt (no retries)."""
        operation = Mock(return_value="success")
        result = retry_podman_operation(operation)
        assert result == "success"
        operation.assert_called_once()

    def test_retry_success_after_failures(self):
        """Test operation succeeds after transient failures."""
        operation = Mock(side_effect=[
            ConnectionError("Failed 1"),
            ConnectionError("Failed 2"),
            "success"
        ])

        with patch('time.sleep'):  # Mock sleep to speed up test
            result = retry_podman_operation(operation)

        assert result == "success"
        assert operation.call_count == 3

    def test_retry_exhausted(self):
        """Test all retries exhausted raises final exception."""
        operation = Mock(side_effect=ConnectionError("Permanent failure"))

        with patch('time.sleep'):  # Mock sleep to speed up test
            with pytest.raises(ConnectionError) as exc_info:
                retry_podman_operation(operation)

        assert "Permanent failure" in str(exc_info.value)
        assert operation.call_count == 3

    def test_retry_timeout_error(self):
        """Test retries on TimeoutError."""
        operation = Mock(side_effect=[
            TimeoutError("Timed out 1"),
            TimeoutError("Timed out 2"),
            "success"
        ])

        with patch('time.sleep'):
            result = retry_podman_operation(operation)

        assert result == "success"
        assert operation.call_count == 3

    def test_retry_exponential_backoff(self):
        """Test exponential backoff delays."""
        operation = Mock(side_effect=[
            ConnectionError("Failed 1"),
            ConnectionError("Failed 2"),
            "success"
        ])

        with patch('time.sleep') as mock_sleep:
            retry_podman_operation(operation, base_delay=2.0)

        # Should have 2 sleep calls (first and second retry)
        assert mock_sleep.call_count == 2
        # First retry: 2.0 * 2^0 = 2.0
        # Second retry: 2.0 * 2^1 = 4.0
        mock_sleep.assert_has_calls([call(2.0), call(4.0)])

    def test_retry_not_triggered_on_other_exceptions(self):
        """Test that non-transient exceptions are not retried."""
        operation = Mock(side_effect=ValueError("Invalid value"))

        with pytest.raises(ValueError):
            retry_podman_operation(operation)

        # Should fail immediately without retries
        operation.assert_called_once()


class TestPlatformIntegration:
    """Tests for platform-specific integration."""

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_macos_platform_integration(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test macOS platform detection and socket path."""
        mock_detect.return_value = 'macos'
        mock_get_socket.return_value = None  # macOS uses auto-detection
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        _ = client.client

        mock_detect.assert_called_once()
        mock_ensure.assert_called_once_with('macos')
        mock_get_socket.assert_called_once_with('macos')
        # Should connect with None (auto-detect)
        mock_podman_client.assert_called_once_with(base_url=None, timeout=120)

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_linux_platform_integration(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test Linux platform detection and socket path."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        _ = client.client

        mock_detect.assert_called_once()
        mock_ensure.assert_called_once_with('linux')
        mock_get_socket.assert_called_once_with('linux')
        mock_podman_client.assert_called_once_with(
            base_url='unix:///run/user/1000/podman/podman.sock',
            timeout=120
        )


class TestRetryIntegration:
    """Tests verifying retry integration in client property."""

    @patch('mc.integrations.podman.retry_podman_operation')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_client_property_uses_retry(
        self, mock_detect, mock_ensure, mock_get_socket, mock_retry
    ):
        """Test that client property integrates retry_podman_operation."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_client_instance = MagicMock()
        # Mock retry to return a client instance
        mock_retry.return_value = mock_client_instance

        client = PodmanClient()
        result = client.client

        # Verify retry_podman_operation was called
        mock_retry.assert_called_once()
        # Result should be what retry returned
        assert result is mock_client_instance

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_connection_error_includes_remediation_macos(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test macOS connection error includes machine start remediation."""
        mock_detect.return_value = 'macos'
        mock_get_socket.return_value = None
        mock_podman_client.side_effect = ConnectionError("Connection refused")

        client = PodmanClient()

        with pytest.raises(ConnectionError) as exc_info:
            _ = client.client

        error_msg = str(exc_info.value)
        assert "Cannot connect to Podman socket" in error_msg
        assert "podman machine start" in error_msg

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_connection_error_includes_remediation_linux(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test Linux connection error includes install remediation."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = '/run/user/1000/podman/podman.sock'
        mock_podman_client.side_effect = ConnectionError("Connection refused")

        client = PodmanClient()

        with pytest.raises(ConnectionError) as exc_info:
            _ = client.client

        error_msg = str(exc_info.value)
        assert "Cannot connect to Podman socket" in error_msg
        assert "dnf install podman" in error_msg

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_retry_not_triggered_on_success(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test retry completes on first attempt if connection succeeds."""
        mock_detect.return_value = 'linux'
        mock_get_socket.return_value = None
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        client = PodmanClient()
        _ = client.client

        # Should be called exactly once (no retries)
        mock_podman_client.assert_called_once()

    @patch('mc.integrations.podman.podman.PodmanClient')
    @patch('mc.integrations.podman.get_socket_path')
    @patch('mc.integrations.podman.ensure_podman_ready')
    @patch('mc.integrations.podman.detect_platform')
    def test_explicit_socket_path_used(
        self, mock_detect, mock_ensure, mock_get_socket, mock_podman_client
    ):
        """Test that explicit socket path overrides auto-detection."""
        mock_detect.return_value = 'linux'
        mock_client_instance = MagicMock()
        mock_podman_client.return_value = mock_client_instance

        custom_socket = '/custom/podman.sock'
        client = PodmanClient(socket_path=custom_socket)
        _ = client.client

        # Should not call get_socket_path when explicit path provided
        mock_get_socket.assert_not_called()
        # Should use explicit socket path
        mock_podman_client.assert_called_once_with(
            base_url=f'unix://{custom_socket}',
            timeout=120
        )
