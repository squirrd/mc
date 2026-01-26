"""Configuration data models and schema."""

from typing import Dict, Any


def get_default_config() -> Dict[str, Any]:
    """Get default configuration values.

    Returns:
        Default configuration dictionary
    """
    return {
        "base_directory": "~/mc",
        "api": {
            "offline_token": ""
        },
        "podman": {
            "timeout": 120,
            "retry_attempts": 3,
            "socket_path": None
        }
    }


def validate_config(config: Dict[str, Any]) -> bool:
    """Validate configuration structure.

    Args:
        config: Configuration dictionary to validate

    Returns:
        True if valid, False otherwise
    """
    if not isinstance(config, dict):
        return False

    if "base_directory" not in config:
        return False

    if "api" not in config or not isinstance(config["api"], dict):
        return False

    if "offline_token" not in config["api"]:
        return False

    # Podman config is optional, but if present must have valid structure
    if "podman" in config:
        if not isinstance(config["podman"], dict):
            return False

        # Validate podman config fields if present
        podman_config = config["podman"]
        if "timeout" in podman_config and not isinstance(podman_config["timeout"], int):
            return False
        if "retry_attempts" in podman_config and not isinstance(podman_config["retry_attempts"], int):
            return False
        if "socket_path" in podman_config and podman_config["socket_path"] is not None:
            if not isinstance(podman_config["socket_path"], str):
                return False

    return True
