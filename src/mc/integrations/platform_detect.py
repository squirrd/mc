"""Platform detection and Podman availability checking."""

import json
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional


def detect_platform() -> str:
    """
    Detect platform type.

    Returns:
        str: Platform type - 'macos', 'linux', or 'unsupported'
    """
    system = platform.system()
    if system == 'Darwin':
        return 'macos'
    elif system == 'Linux':
        return 'linux'
    else:
        return 'unsupported'


def is_podman_machine_running() -> bool:
    """
    Check if Podman machine is running (macOS only).

    Returns:
        bool: True if a Podman machine is running, False otherwise
    """
    try:
        result = subprocess.run(
            ['podman', 'machine', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        machines = json.loads(result.stdout)

        # Check if any machine is running
        for machine in machines:
            if machine.get('Running', False):
                return True
        return False
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return False


def ensure_podman_ready(platform_type: str) -> None:
    """
    Ensure Podman is ready for operations.

    Args:
        platform_type: Platform type from detect_platform()

    Raises:
        RuntimeError: If Podman is not available or user declines to start machine
    """
    if platform_type == 'macos':
        if not is_podman_machine_running():
            # Prompt user to start machine
            response = input("Podman machine is stopped. Start it? [y/n] ")
            if response.lower() == 'y':
                subprocess.run(['podman', 'machine', 'start'], check=True)
            else:
                raise RuntimeError("Podman machine must be running")
    elif platform_type == 'linux':
        # Linux native - just verify Podman is installed
        try:
            subprocess.run(
                ['podman', '--version'],
                capture_output=True,
                check=True
            )
        except FileNotFoundError:
            raise RuntimeError(
                "Podman is not installed. Install with: "
                "dnf install podman (RHEL/Fedora) or apt install podman (Ubuntu/Debian)"
            )
        except subprocess.CalledProcessError:
            raise RuntimeError(
                "Podman is not installed. Install with: "
                "dnf install podman (RHEL/Fedora) or apt install podman (Ubuntu/Debian)"
            )
    else:
        raise RuntimeError(
            f"Unsupported platform: {platform_type}. "
            "MC requires macOS or Linux. See docs for workarounds."
        )


def get_podman_machine_uri() -> Optional[str]:
    """
    Get Podman machine SSH URI from connections config (macOS).

    Returns:
        Optional[str]: SSH URI for default Podman machine, or None if not found
    """
    try:
        connections_file = Path.home() / '.config' / 'containers' / 'podman-connections.json'
        if not connections_file.exists():
            return None

        import json
        with open(connections_file) as f:
            data = json.load(f)

        # Get default connection name
        default_name = data.get('Connection', {}).get('Default')
        if not default_name:
            return None

        # Get URI for default connection
        connections = data.get('Connection', {}).get('Connections', {})
        default_conn = connections.get(default_name, {})
        uri = default_conn.get('URI')

        # Ensure string type (defensive)
        if uri and isinstance(uri, bytes):
            uri = uri.decode('utf-8')

        return uri
    except (json.JSONDecodeError, KeyError, OSError):
        return None


def get_socket_path(platform_type: str) -> Optional[str]:
    """
    Get Podman socket path for current platform.

    Args:
        platform_type: Platform type from detect_platform()

    Returns:
        Optional[str]: Socket path or full URI (SSH on macOS), or None for auto-detection
    """
    # Check CONTAINER_HOST environment variable first
    container_host = os.getenv('CONTAINER_HOST')
    if container_host:
        # Ensure string type (decode if bytes somehow present)
        if isinstance(container_host, bytes):
            container_host = container_host.decode('utf-8')

        # Parse unix:// URI
        if container_host.startswith('unix://'):
            return container_host[7:]  # Remove 'unix://' prefix
        return container_host

    if platform_type == 'linux':
        # Rootless Linux: /run/user/{uid}/podman/podman.sock
        xdg_runtime_dir = os.getenv('XDG_RUNTIME_DIR')
        if xdg_runtime_dir:
            socket_path = Path(xdg_runtime_dir) / 'podman' / 'podman.sock'
        else:
            # Fallback: construct from UID
            uid = os.getuid()
            socket_path = Path(f'/run/user/{uid}/podman/podman.sock')

        if socket_path.exists():
            return str(socket_path)

        # Check rootful socket as last resort
        rootful_socket = Path('/run/podman/podman.sock')
        if rootful_socket.exists():
            return str(rootful_socket)

        # Return default rootless path even if it doesn't exist yet
        # (socket might be created on first Podman operation)
        return str(socket_path)

    elif platform_type == 'macos':
        # macOS: Use local Podman machine API socket
        # This works around podman-py 5.7.0 bug where base_url=None fails with empty bytes
        # The socket is created by Podman machine and proxies to the VM
        machine_socket = Path.home() / '.local' / 'share' / 'containers' / 'podman' / 'machine' / 'podman.sock'

        if machine_socket.exists():
            return str(machine_socket)

        # Fallback: try to read from podman connections (less reliable)
        # Note: SSH URIs don't work without explicit identity file configuration
        return None

    else:
        raise ValueError(f"Unsupported platform: {platform_type}")


def check_podman_version(warn_threshold: int = 3, fail_threshold: int = 7) -> dict[str, Optional[int] | str]:
    """
    Check Podman version compatibility.

    Args:
        warn_threshold: Warn if version is this many behind (default: 3)
        fail_threshold: Fail if version is this many behind (default: 7)

    Returns:
        dict: Version info with keys: version, major, minor, action, message
            action is one of: 'ok', 'warn', 'fail'
    """
    try:
        result = subprocess.run(
            ['podman', '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse "podman version 5.2.1" or "podman version 5.2.1-dev"
        match = re.search(r'(\d+)\.(\d+)', result.stdout)
        if not match:
            return {
                'version': None,
                'major': None,
                'minor': None,
                'action': 'fail',
                'message': f"Could not parse version from: {result.stdout}"
            }

        major = int(match.group(1))
        minor = int(match.group(2))

        # Expected version (from container build time)
        expected_major = 5
        expected_minor = 0

        # Calculate version difference (using minor version granularity)
        version_diff = (expected_major - major) * 10 + (expected_minor - minor)

        if version_diff >= fail_threshold:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'fail',
                'message': f"Podman {major}.{minor} is too old (7+ versions behind). Update required."
            }
        elif version_diff >= warn_threshold:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'warn',
                'message': f"Podman {major}.{minor} is 3+ versions behind. Consider updating."
            }
        else:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'ok',
                'message': f"Podman {major}.{minor} is compatible."
            }

    except FileNotFoundError:
        return {
            'version': None,
            'major': None,
            'minor': None,
            'action': 'fail',
            'message': "Podman is not installed or not in PATH."
        }
    except subprocess.CalledProcessError:
        return {
            'version': None,
            'major': None,
            'minor': None,
            'action': 'fail',
            'message': "Podman is not installed or not in PATH."
        }
