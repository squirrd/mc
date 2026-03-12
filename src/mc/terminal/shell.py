"""Custom bashrc generation for container shells.

This module generates custom bash configuration to inject into containers
via BASH_ENV environment variable, providing welcome banners, custom prompts,
and helper functions.
"""

import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Any, Optional

from platformdirs import user_data_dir

from mc.terminal.banner import generate_banner


def detect_macos_proxy() -> Optional[str]:
    """Detect macOS system proxy via scutil --proxy.

    On macOS with a PAC-based corporate proxy, HTTPS_PROXY env var is often
    empty even though Go binaries on the host auto-detect the proxy via
    CFNetworkCopySystemProxySettings. This function bridges that gap for the
    Linux container which only reads env vars.

    Returns:
        Proxy URL string (e.g. "http://proxy.corp.example.com:8080"), or None
        if not on macOS, no proxy configured, or detection fails.
    """
    if platform.system() != "Darwin":
        return None
    try:
        r = subprocess.run(["scutil", "--proxy"], capture_output=True, text=True, timeout=3)
        output = r.stdout

        # Direct HTTPS proxy configured?
        if "HTTPSProxy" in output and "HTTPSPort" in output:
            host_match = re.search(r"HTTPSProxy\s*:\s*(\S+)", output)
            port_match = re.search(r"HTTPSPort\s*:\s*(\d+)", output)
            if host_match and port_match:
                return f"http://{host_match.group(1)}:{port_match.group(1)}"

        # PAC URL configured? Fetch the PAC file and parse out the first PROXY directive.
        pac_match = re.search(r"ProxyAutoConfigURLString\s*:\s*(\S+)", output)
        if not pac_match:
            return None
        pac_url = pac_match.group(1)

        curl_result = subprocess.run(
            ["curl", "--silent", "--max-time", "5", pac_url],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # PAC files contain lines like: return "PROXY host:port; DIRECT"
        proxy_match = re.search(r'return\s+"PROXY\s+([^:;"]+):(\d+)', curl_result.stdout)
        if proxy_match:
            return f"http://{proxy_match.group(1)}:{proxy_match.group(2)}"
    except Exception:
        pass
    return None


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
    
    # Read optional proxy from host environment; fall back to macOS system detection
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy is None and platform.system() == "Darwin":
        https_proxy = detect_macos_proxy()

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

    # Conditionally propagate proxy from host environment or macOS system proxy
    if https_proxy is not None:
        bashrc_lines += [
            "# Proxy configuration (from host environment or macOS system proxy)",
            f"export HTTPS_PROXY='{https_proxy}'",
            f"export HTTP_PROXY='{https_proxy}'",
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
