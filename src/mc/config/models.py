"""Configuration data models and schema."""

from typing import Any


def get_default_config() -> dict[str, Any]:
    """Get default configuration values.

    Returns:
        Default configuration dictionary
    """
    return {
        "base_directory": "~/mc",
        "api": {
            "rh_api_offline_token": ""
        },
        "salesforce": {
            "username": "",
            "password": "",
            "security_token": ""
        },
        "podman": {
            "timeout": 120,
            "retry_attempts": 3,
            "socket_path": ""
        },
        "version": {
            "pinned_mc": "latest",
            "last_check": None
        }
    }


def validate_config(config: dict[str, Any]) -> bool:
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

    # Support both rh_api_offline_token (new) and offline_token (deprecated)
    if "rh_api_offline_token" not in config["api"] and "offline_token" not in config["api"]:
        return False

    # Salesforce config is required
    if "salesforce" not in config or not isinstance(config["salesforce"], dict):
        return False

    # Validate required Salesforce fields
    required_sf_fields = ["username", "password", "security_token"]
    for field in required_sf_fields:
        if field not in config["salesforce"]:
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
        if "socket_path" in podman_config:
            # socket_path can be empty string (auto-detect) or a path
            if not isinstance(podman_config["socket_path"], str):
                return False

    # Version config is optional (backward compatibility), but if present must have valid structure
    if "version" in config:
        if not isinstance(config["version"], dict):
            return False

        # Validate version config fields if present
        version_config = config["version"]
        if "pinned_mc" in version_config:
            if not isinstance(version_config["pinned_mc"], str):
                return False
        if "last_check" in version_config:
            # last_check must be float or None
            if version_config["last_check"] is not None and not isinstance(version_config["last_check"], (float, int)):
                return False

    return True
