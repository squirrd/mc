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

    return True
