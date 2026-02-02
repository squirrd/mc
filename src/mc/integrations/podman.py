"""Podman client wrapper with lazy connection and retry logic."""

import time
from typing import Any, Callable, Dict, Optional, TypeVar

import podman

from mc.integrations.platform_detect import (
    detect_platform,
    ensure_podman_ready,
    get_socket_path,
)

T = TypeVar('T')


def retry_podman_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> T:
    """
    Retry Podman operation with exponential backoff.

    Args:
        operation: Callable that performs the Podman operation
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)

    Returns:
        Result of the operation

    Raises:
        ConnectionError: If all retry attempts fail
        TimeoutError: If all retry attempts time out
    """
    last_exception: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            return operation()
        except (ConnectionError, TimeoutError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(
                    f"Podman operation failed (attempt {attempt + 1}/{max_retries}), "
                    f"retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                # Last attempt failed
                raise last_exception

    # Should not reach here, but for type safety
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error: no exception but operation failed")


class PodmanClient:
    """Wrapper for Podman operations with lazy connection and retry logic."""

    def __init__(self, socket_path: Optional[str] = None, timeout: int = 120):
        """
        Initialize Podman client wrapper.

        Connection is deferred until first API access (lazy connection pattern).
        This enables fast CLI startup and graceful handling of environments where
        Podman isn't needed for the current operation.

        Args:
            socket_path: Optional explicit socket path. If None, auto-detects based
                        on platform (macOS vs Linux) and user mode (rootless vs rootful).
            timeout: API timeout in seconds (default: 120). Increase for slow operations
                    like image pulls.
        """
        # Defensive: ensure socket_path is string, not bytes
        if socket_path and isinstance(socket_path, bytes):
            socket_path = socket_path.decode('utf-8')

        self._socket_path = socket_path
        self._timeout = timeout
        self._client: Optional[podman.PodmanClient] = None
        self._platform_type: Optional[str] = None

    @property
    def client(self) -> podman.PodmanClient:
        """
        Get Podman client, connecting on first access (lazy connection).

        This property implements lazy initialization - the Podman socket connection
        is not established until this property is first accessed. This defers
        platform detection, machine startup prompts (macOS), and socket connection
        until actually needed.

        Connection establishment is wrapped in retry logic to handle transient
        errors transparently (e.g., socket temporarily unavailable, machine starting).

        Returns:
            podman.PodmanClient: Connected Podman client

        Raises:
            ConnectionError: If unable to connect after retries, with platform-specific
                           remediation steps (machine start for macOS, install for Linux)
            RuntimeError: If platform is unsupported or Podman is not ready
        """
        # Return cached client if already connected
        if self._client is not None:
            return self._client

        # Detect platform and ensure Podman is ready
        try:
            self._platform_type = detect_platform()
            ensure_podman_ready(self._platform_type)

            # Get socket path based on platform
            socket_path: Optional[str]
            if self._socket_path:
                socket_path = self._socket_path
            else:
                socket_path = get_socket_path(self._platform_type)

            # Defensive: ensure socket_path is string, not bytes
            if socket_path and isinstance(socket_path, bytes):
                socket_path = socket_path.decode('utf-8')

            # Construct URI
            uri: Optional[str]
            if socket_path:
                uri = f"unix://{socket_path}"
            else:
                uri = None

            # Defensive: ensure URI is string, not bytes
            if uri and isinstance(uri, bytes):
                uri = uri.decode('utf-8')

            # Connect with retry logic
            def _connect() -> podman.PodmanClient:
                """Inner function to wrap connection in retry logic."""
                # On macOS with Podman machine, pass base_url=None (let it auto-detect)
                # On Linux, pass the socket path URI
                if uri is not None:
                    return podman.PodmanClient(base_url=uri, timeout=self._timeout)
                else:
                    return podman.PodmanClient(base_url=None, timeout=self._timeout)

            # Use retry_podman_operation to handle transient errors
            self._client = retry_podman_operation(_connect)

        except (ConnectionError, TimeoutError) as e:
            # Connection failed after retries - provide helpful error message
            socket_info = f" at {self._socket_path or socket_path or 'default path'}" if (self._socket_path or socket_path) else ""

            if self._platform_type == 'macos':
                remediation = "Run 'podman machine start' to start the Podman machine."
            elif self._platform_type == 'linux':
                remediation = "Install Podman: dnf install podman (RHEL/Fedora) or apt install podman (Ubuntu/Debian)"
            else:
                remediation = "Ensure Podman is installed and running."

            raise ConnectionError(
                f"Cannot connect to Podman socket{socket_info}. "
                f"Error: {e}. "
                f"{remediation}"
            ) from e
        except RuntimeError as e:
            # Platform detection or readiness check failed
            raise

        return self._client

    def ping(self) -> bool:
        """
        Verify Podman connection.

        Returns:
            bool: True if connected and responsive, False otherwise
        """
        try:
            return self.client.ping()
        except Exception:
            return False

    def get_version(self) -> Dict[str, Any]:
        """
        Get Podman version information.

        Returns:
            dict: Version information including API version, Podman version, OS, etc.
        """
        return self.client.version()  # type: ignore[no-any-return, no-untyped-call]

    def close(self) -> None:
        """Close Podman connection if open."""
        if self._client is not None:
            self._client.close()  # type: ignore[no-untyped-call]
            self._client = None

    def __enter__(self) -> 'PodmanClient':
        """Context manager entry - return self for use in with statement."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[Any]
    ) -> None:
        """Context manager exit - close connection."""
        self.close()
