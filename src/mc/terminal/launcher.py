"""Terminal launcher interface and platform detection."""

import platform
from dataclasses import dataclass
from typing import Protocol


@dataclass
class LaunchOptions:
    """Options for launching a terminal window.

    Attributes:
        title: Window title
        command: Command to execute in the terminal
        auto_focus: Whether to bring window to foreground
    """

    title: str
    command: str
    auto_focus: bool = True


class TerminalLauncher(Protocol):
    """Protocol for platform-specific terminal launchers."""

    def launch(self, options: LaunchOptions) -> None:
        """Launch a new terminal window with the given options.

        Args:
            options: Launch configuration

        Raises:
            RuntimeError: If terminal launch fails
            FileNotFoundError: If terminal binary not found
        """
        ...


def get_launcher(platform_override: str | None = None) -> TerminalLauncher:
    """Get platform-appropriate terminal launcher.

    Args:
        platform_override: Override platform detection (for testing)

    Returns:
        Platform-specific terminal launcher instance

    Raises:
        NotImplementedError: If platform is not supported
    """
    system = platform_override or platform.system()

    if system == "Darwin":
        from mc.terminal.macos import MacOSLauncher

        return MacOSLauncher()
    elif system == "Linux":
        from mc.terminal.linux import LinuxLauncher

        return LinuxLauncher()
    else:
        raise NotImplementedError(
            f"Terminal launching not supported on {system}. "
            f"Supported platforms: macOS (Darwin), Linux"
        )
