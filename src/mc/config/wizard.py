"""Interactive configuration wizard."""

from pathlib import Path
from typing import Dict, Any


def run_setup_wizard() -> Dict[str, Any]:
    """Run interactive configuration wizard.

    Returns:
        Configuration dictionary from user input
    """
    print("MC Configuration Setup")
    print("=" * 50)
    print()

    # Prompt for base directory with default
    default_base = str(Path.home() / "mc")
    base_dir_input = input(f"Base directory [{default_base}]: ").strip()
    if not base_dir_input:
        base_dir = default_base
    else:
        base_dir = base_dir_input

    # Prompt for offline token (required)
    print()
    while True:
        offline_token = input("Red Hat API offline token: ").strip()
        if offline_token:
            break
        print("ERROR: Offline token is required")

    print()
    print("Configuration saved successfully!")

    return {
        "base_directory": base_dir,
        "api": {
            "offline_token": offline_token
        }
    }
