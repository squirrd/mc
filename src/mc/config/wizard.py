"""Interactive configuration wizard."""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def run_setup_wizard() -> dict[str, Any]:
    """Run interactive configuration wizard.

    Returns:
        Configuration dictionary from user input
    """
    # Interactive prompts - keep as print for user interaction
    print("MC Configuration Setup")  # print OK
    print("=" * 50)  # print OK
    print()  # print OK

    # Prompt for base directory with default
    default_base = str(Path.home() / "mc")
    base_dir_input = input(f"Base directory [{default_base}]: ").strip()
    if not base_dir_input:
        base_dir = default_base
    else:
        base_dir = base_dir_input

    # Prompt for offline token (required)
    print()  # print OK
    while True:
        offline_token = input("Red Hat API offline token: ").strip()
        if offline_token:
            break
        print("ERROR: Offline token is required")  # print OK

    print()  # print OK
    logger.info("Configuration saved successfully")

    return {
        "base_directory": base_dir,
        "api": {
            "rh_api_offline_token": offline_token
        }
    }
