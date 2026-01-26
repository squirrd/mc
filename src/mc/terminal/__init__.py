"""Terminal customization for containerized environments.

This module provides shell customization for MC containers, including
custom bashrc generation with welcome banners and helper functions.
"""

from mc.terminal.banner import format_field, generate_banner
from mc.terminal.shell import generate_bashrc, get_bashrc_path, write_bashrc

__all__ = [
    "format_field",
    "generate_banner",
    "generate_bashrc",
    "get_bashrc_path",
    "write_bashrc",
]
