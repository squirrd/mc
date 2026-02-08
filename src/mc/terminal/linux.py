"""Linux terminal launchers (gnome-terminal, konsole)."""

import os
import shutil
import subprocess
import time
from typing import Literal

from mc.terminal.launcher import LaunchOptions


class LinuxLauncher:
    """Linux terminal launcher supporting multiple terminal emulators."""

    def __init__(
        self,
        terminal: Literal["gnome-terminal", "konsole"] | None = None,
    ) -> None:
        """Initialize Linux launcher.

        Args:
            terminal: Specific terminal to use, or None for auto-detection

        Raises:
            RuntimeError: If on Wayland or if required tools missing
        """
        # Detect display server
        self.display_server = self._detect_display_server()

        # Strict Wayland check - fail with clear error
        if self.display_server == "wayland":
            raise RuntimeError(
                "Window tracking not supported on Wayland. "
                "Phase 18 supports X11 only. Switch to X11 session or disable window tracking."
            )

        # Detect and validate terminal
        self.terminal = terminal or self._detect_terminal()

        # Validate wmctrl available if on X11
        if self.display_server == "x11":
            self._validate_wmctrl_available()

    def _detect_display_server(self) -> Literal["x11", "wayland", "unknown"]:
        """Detect X11 vs Wayland display server.

        Returns:
            Display server type

        Detection logic:
        - WAYLAND_DISPLAY set -> Wayland
        - DISPLAY set but WAYLAND_DISPLAY not set -> X11
        - Neither set -> unknown
        """
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        elif os.environ.get("DISPLAY"):
            return "x11"
        else:
            return "unknown"

    def _detect_terminal(self) -> Literal["gnome-terminal", "konsole"]:
        """Detect available terminal emulator.

        Returns:
            Available terminal binary name

        Raises:
            RuntimeError: If no supported terminal found

        Priority: Desktop-native > availability order
        - KDE (XDG_CURRENT_DESKTOP=KDE): konsole > gnome-terminal
        - GNOME (XDG_CURRENT_DESKTOP=GNOME): gnome-terminal > konsole
        - Other: gnome-terminal > konsole (GNOME more common)
        """
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()

        # Check both terminals installed
        has_gnome = shutil.which("gnome-terminal")
        has_konsole = shutil.which("konsole")

        # Prefer desktop-native terminal
        if "KDE" in desktop and has_konsole:
            return "konsole"
        elif "GNOME" in desktop and has_gnome:
            return "gnome-terminal"

        # Fallback to availability
        if has_gnome:
            return "gnome-terminal"
        elif has_konsole:
            return "konsole"

        # Neither found - strict validation per user decision
        raise RuntimeError(
            "No supported terminal emulator found. "
            "Install gnome-terminal or konsole to use window tracking."
        )

    def _detect_distro(self) -> str:
        """Detect Linux distribution for installation instructions.

        Returns:
            Distribution identifier (debian, ubuntu, fedora, rhel8+, etc.)
        """
        # Read /etc/os-release (standard location since systemd)
        try:
            with open("/etc/os-release") as f:
                os_release = f.read().lower()

            if "ubuntu" in os_release:
                return "ubuntu"
            elif "debian" in os_release:
                return "debian"
            elif "fedora" in os_release:
                return "fedora"
            elif "rhel" in os_release or "red hat" in os_release:
                # Check version for dnf vs yum
                if 'version_id="7' in os_release:
                    return "rhel7"
                else:
                    return "rhel8+"
            elif "centos" in os_release:
                if 'version_id="7' in os_release:
                    return "centos7"
                else:
                    return "centos8+"
        except Exception:
            pass

        return "unknown"

    def _validate_wmctrl_available(self) -> None:
        """Validate wmctrl installed, raise error with install instructions if not.

        Raises:
            RuntimeError: If wmctrl not found, includes distro-specific install command
        """
        if shutil.which("wmctrl"):
            return  # Available, no action needed

        # Detect distro for installation instructions
        distro = self._detect_distro()

        if distro in ["debian", "ubuntu"]:
            install_cmd = "sudo apt install wmctrl"
        elif distro in ["fedora", "rhel8+", "centos8+"]:
            install_cmd = "sudo dnf install wmctrl"
        elif distro in ["rhel7", "centos7"]:
            install_cmd = "sudo yum install wmctrl"
        else:
            install_cmd = "Install wmctrl via your package manager"

        raise RuntimeError(
            f"wmctrl not found. Window focusing requires wmctrl on X11.\n"
            f"Install: {install_cmd}"
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

    def _capture_window_id(self) -> str | None:
        """Capture window ID after terminal creation.

        Returns:
            Window ID as hexadecimal string (0x...), or None if capture fails

        Approach:
        - konsole: Sets $WINDOWID environment variable (reliable)
        - gnome-terminal: Uses server-client model, no $WINDOWID (requires fallback)

        Note: This runs in the LAUNCHING process, not inside the new terminal.
        For konsole, we use xdotool to get the active window after launch.
        For gnome-terminal server model, window ID capture is timing-sensitive.
        """
        # Wait for window to fully create (matches Phase 16 0.5s delay)
        time.sleep(0.5)

        if not shutil.which("xdotool"):
            return None

        try:
            result = subprocess.run(
                ["xdotool", "getactivewindow"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Convert decimal to hex format for consistency
                window_id = int(result.stdout.strip())
                return f"0x{window_id:08x}"
        except Exception:
            pass

        return None

    def _window_exists_by_id(self, window_id: str) -> bool:
        """Validate if window with specific ID still exists.

        Args:
            window_id: Window ID to check (hex format: 0x...)

        Returns:
            True if window exists, False otherwise

        Uses wmctrl -l to list all windows, checks if window_id in output.
        """
        if not shutil.which("wmctrl"):
            return False

        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # wmctrl -l output format: "0x0400000a  0 hostname Window Title"
            # First column is window ID in hex
            return window_id.lower() in result.stdout.lower()
        except Exception:
            return False

    def focus_window_by_id(self, window_id: str) -> bool:
        """Focus window by ID, handling workspace switching.

        Args:
            window_id: Window ID to focus (hex format: 0x...)

        Returns:
            True if focus succeeded, False otherwise

        The -i flag interprets window argument as numeric ID.
        The -a flag activates window: switches to desktop, raises, and focuses.
        """
        if not shutil.which("wmctrl"):
            return False

        try:
            result = subprocess.run(
                ["wmctrl", "-i", "-a", window_id],
                capture_output=True,
                text=True,
                timeout=5,
            )
            # wmctrl returns 0 on success, non-zero on failure
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False
