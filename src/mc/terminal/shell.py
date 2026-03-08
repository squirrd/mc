"""Custom bashrc generation for container shells.

This module generates custom bash configuration to inject into containers
via BASH_ENV environment variable, providing welcome banners, custom prompts,
and helper functions.
"""

import os
from pathlib import Path
from typing import Any

from platformdirs import user_data_dir

from mc.terminal.banner import generate_banner


def generate_bashrc(case_number: str, case_metadata: dict[str, Any]) -> str:
    """Generate custom bashrc content for container shell.

    Args:
        case_number: Case number (e.g., "12345678")
        case_metadata: Case metadata dictionary with fields:
            - case_number: str
            - customer_name: str (optional)
            - description: str (optional)
            - summary: str (optional)
            - next_steps: str (optional)

    Returns:
        Bashrc content as string
    """
    # Extract metadata with defaults
    customer = case_metadata.get("customer_name", "Unknown")
    description = case_metadata.get("description", "")
    
    # Generate welcome banner
    banner = generate_banner(case_metadata)
    
    # Read optional proxy from host environment
    https_proxy = os.environ.get("HTTPS_PROXY")

    # Build bashrc content
    bashrc_lines = [
        "# MC Custom Bashrc - Auto-generated",
        "",
        "# Set custom prompt with case number prefix",
        f"export PS1='[MC-{case_number}] \\w\\$ '",
        "",
        "# Export case metadata as environment variables",
        f"export MC_CASE_ID='{case_number}'",
        f"export MC_CUSTOMER='{customer}'",
        f"export MC_DESCRIPTION='{description}'",
        "",
    ]

    # Conditionally propagate HTTPS_PROXY from host environment
    if https_proxy is not None:
        bashrc_lines += [
            "# Proxy configuration from host environment",
            f"export HTTPS_PROXY='{https_proxy}'",
            "",
        ]

    bashrc_lines += [
        "# Helper aliases",
        "alias ll='ls -lah'",
        "alias case-info='echo \"Case: ${MC_CASE_ID}\"'",
        "",
        "# Helper function - show available MC commands",
        "mc-help() {",
        "    echo 'MC Container Environment'",
        "    echo '  exit         - Exit container and close terminal'",
        "    echo '  case-info    - Show current case information'",
        "    echo '  ll           - List files with details'",
        "    echo '  mc-help      - Show this help message'",
        "}",
        "",
        "# Display welcome banner on shell entry",
        f"cat << 'BANNER_EOF'",
        banner,
        "BANNER_EOF",
        "",
    ]
    
    return "\n".join(bashrc_lines)


def get_bashrc_path(case_number: str) -> str:
    """Get path where bashrc should be written.

    Args:
        case_number: Case number (e.g., "12345678")

    Returns:
        Absolute path to bashrc file (e.g., ~/mc/config/bashrc/mc-12345678.bashrc)
    """
    # Use consolidated directory structure: ~/mc/config/bashrc/
    # (instead of platform-specific platformdirs locations)
    bashrc_dir = Path.home() / "mc" / "config" / "bashrc"

    # Create directory if it doesn't exist
    bashrc_dir.mkdir(parents=True, exist_ok=True)

    # Return absolute path to case-specific bashrc
    return str(bashrc_dir / f"mc-{case_number}.bashrc")


def write_bashrc(case_number: str, case_metadata: dict[str, Any]) -> str:
    """Write custom bashrc to file for container shell.

    Args:
        case_number: Case number (e.g., "12345678")
        case_metadata: Case metadata dictionary

    Returns:
        Absolute path to written bashrc file
    """
    # Generate bashrc content
    content = generate_bashrc(case_number, case_metadata)
    
    # Get file path
    bashrc_path = get_bashrc_path(case_number)
    
    # Write to file
    with open(bashrc_path, "w") as f:
        f.write(content)
    
    # Set file permissions to 0o644 (readable by all, writable by owner)
    os.chmod(bashrc_path, 0o644)
    
    return bashrc_path
