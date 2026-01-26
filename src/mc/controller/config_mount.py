"""Configuration mount helper for container credential distribution.

Provides helpers for mounting host configuration files into containers,
enabling containers to access Red Hat API and Salesforce credentials
without duplicating configuration.
"""

from pathlib import Path
from mc.exceptions import ConfigError


def get_config_mount_spec(config_path: Path) -> dict[str, str]:
    """Generate Podman mount spec for read-only config access.

    Creates a mount specification that allows containers to read the host
    configuration file containing API credentials and Salesforce credentials.
    The mount is read-only to prevent containers from modifying the host config.

    Args:
        config_path: Path to host configuration file

    Returns:
        dict: Mount specification with keys:
            - source: Host config file path (absolute)
            - target: Container config file path (/root/.mc/config.toml)
            - options: Mount options ("ro" for read-only)

    Raises:
        ConfigError: If config file does not exist

    Example:
        >>> config_path = Path("~/.mc/config.toml").expanduser()
        >>> spec = get_config_mount_spec(config_path)
        >>> spec
        {
            "source": "/home/user/.mc/config.toml",
            "target": "/root/.mc/config.toml",
            "options": "ro"
        }
    """
    if not config_path.exists():
        raise ConfigError(f"Config file not found: {config_path}")

    return {
        "source": str(config_path.resolve()),
        "target": "/root/.mc/config.toml",
        "options": "ro"  # Read-only - containers can read but not modify
    }
