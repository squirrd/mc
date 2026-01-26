"""Linux terminal launchers (gnome-terminal, konsole, xfce4-terminal)."""

import shutil
import subprocess
from typing import Literal

from mc.terminal.launcher import LaunchOptions


class LinuxLauncher:
    """Linux terminal launcher supporting multiple terminal emulators."""

    def __init__(
        self,
        terminal: Literal[
            "gnome-terminal", "konsole", "xfce4-terminal"
        ] | None = None,
    ) -> None:
        """Initialize Linux launcher.

        Args:
            terminal: Specific terminal to use, or None for auto-detection
        """
        self.terminal = terminal or self._detect_terminal()

    def _detect_terminal(
        self,
    ) -> Literal["gnome-terminal", "konsole", "xfce4-terminal"]:
        """Detect available terminal emulator.

        Returns:
            Available terminal binary name

        Raises:
            RuntimeError: If no supported terminal found

        Priority: gnome-terminal > konsole > xfce4-terminal
        """
        terminals = ["gnome-terminal", "konsole", "xfce4-terminal"]
        for term in terminals:
            if shutil.which(term):
                return term  # type: ignore[return-value]

        raise RuntimeError(
            "No supported terminal emulator found. "
            f"Install one of: {', '.join(terminals)}"
        )

    def _build_gnome_terminal_args(self, options: LaunchOptions) -> list[str]:
        """Build command-line arguments for gnome-terminal.

        Args:
            options: Launch configuration

        Returns:
            Command-line arguments list
        """
        return [
            "gnome-terminal",
            f"--title={options.title}",
            "--",
            "bash",
            "-c",
            options.command,
        ]

    def _build_konsole_args(self, options: LaunchOptions) -> list[str]:
        """Build command-line arguments for konsole.

        Args:
            options: Launch configuration

        Returns:
            Command-line arguments list

        Note: konsole doesn't support --title flag directly.
        Title is set via ANSI escape sequences in the shell.
        """
        # Set title via escape sequence in command
        title_escape = f'\\033]0;{options.title}\\007'
        command_with_title = f'printf "{title_escape}"; {options.command}'

        return [
            "konsole",
            "--noclose",
            "-e",
            "bash",
            "-c",
            command_with_title,
        ]

    def _build_xfce4_terminal_args(self, options: LaunchOptions) -> list[str]:
        """Build command-line arguments for xfce4-terminal.

        Args:
            options: Launch configuration

        Returns:
            Command-line arguments list
        """
        return [
            "xfce4-terminal",
            f"--title={options.title}",
            "--command",
            f"bash -c '{options.command}'",
        ]

    def launch(self, options: LaunchOptions) -> None:
        """Launch a new terminal window.

        Args:
            options: Launch configuration

        Raises:
            FileNotFoundError: If terminal binary not found
            RuntimeError: If terminal launch fails
        """
        # Verify terminal binary exists
        if not shutil.which(self.terminal):
            raise FileNotFoundError(
                f"{self.terminal} not found. Install {self.terminal} to use this launcher."
            )

        # Build appropriate command-line arguments
        if self.terminal == "gnome-terminal":
            args = self._build_gnome_terminal_args(options)
        elif self.terminal == "konsole":
            args = self._build_konsole_args(options)
        elif self.terminal == "xfce4-terminal":
            args = self._build_xfce4_terminal_args(options)
        else:
            raise RuntimeError(f"Unsupported terminal: {self.terminal}")

        # Launch terminal (non-blocking)
        try:
            process = subprocess.Popen(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Don't wait for completion - return to prompt immediately
            # Background cleanup to prevent zombie processes
            def cleanup() -> None:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

            import threading

            threading.Thread(target=cleanup, daemon=True).start()

        except Exception as e:
            raise RuntimeError(f"Failed to launch {self.terminal}: {e}") from e
