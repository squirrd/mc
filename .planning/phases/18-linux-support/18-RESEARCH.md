# Phase 18: Linux Support - Research

**Researched:** 2026-02-08
**Domain:** Linux X11 window management with wmctrl/xdotool
**Confidence:** MEDIUM

## Summary

This phase extends Phase 16's macOS window tracking to Linux X11 environments, implementing cross-platform duplicate terminal prevention. The standard approach uses wmctrl for window focusing via EWMH/NetWM X11 protocols, with X11/Wayland detection via environment variables ($DISPLAY, $WAYLAND_DISPLAY) and explicit Wayland non-support. Key challenges include gnome-terminal's server-client architecture complicating window ID tracking, konsole's WINDOWID environment variable being more reliable, and the need for distro-specific installation instructions.

The research reveals wmctrl as the more reliable choice over xdotool for window focusing by ID (xdotool better for search/matching, wmctrl better for ID-based operations). Critical insight: gnome-terminal uses a shared gnome-terminal-server process that makes window ID capture timing-sensitive, while konsole provides WINDOWID environment variable directly. User decisions constrain implementation to gnome-terminal and konsole only (no xfce4-terminal despite existing codebase support), with strict validation requiring these terminals be installed at startup.

**Primary recommendation:** Use wmctrl for window focusing by ID with EWMH/NetWM protocols. Detect X11 vs Wayland via $DISPLAY/$WAYLAND_DISPLAY environment variables. Capture window IDs using $WINDOWID environment variable for konsole, and xdotool/xprop for gnome-terminal fallback. Implement strict tool validation at startup with distro-detected installation instructions.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| subprocess | Built-in | Execute wmctrl, xdotool, xprop commands | Standard Python approach for external commands |
| wmctrl | 1.07 (stable) | Window focusing via EWMH/NetWM X11 protocols | Standard X11 window management tool, EWMH-compliant |
| os.environ | Built-in | Access $DISPLAY, $WAYLAND_DISPLAY, $WINDOWID, $XDG_CURRENT_DESKTOP | Standard environment variable access |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| xdotool | 3.x | Window search and verification | Fallback for window ID capture if $WINDOWID unavailable |
| xprop | X11 built-in | Window property inspection (_NET_ACTIVE_WINDOW) | Debugging and window validation |
| WindowRegistry | Phase 15 | Window ID storage and validation | Already implemented for cross-platform tracking |
| LinuxLauncher | Phase 12/15 | Terminal launching | Existing abstraction, needs window operation methods |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| wmctrl | xdotool | xdotool better for window search/matching, but wmctrl more reliable for ID-based focusing |
| wmctrl + xdotool | Direct X11 lib (python-xlib) | Python bindings add dependency, no reliability benefit, more complex |
| $WINDOWID env var | xwininfo interactive | xwininfo requires user click (not scriptable), $WINDOWID is direct |
| $DISPLAY check | Platform check only | Wayland uses XWayland with $DISPLAY set, need explicit Wayland detection |

**Installation:**
```bash
# Debian/Ubuntu
sudo apt install wmctrl

# Fedora/RHEL 8+
sudo dnf install wmctrl

# Older RHEL/CentOS 7
sudo yum install wmctrl
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── terminal/
│   ├── linux.py              # Enhanced with X11 detection, focus_window_by_id(), _capture_window_id()
│   ├── registry.py           # Already implemented in Phase 15 (no changes)
│   └── launcher.py           # Protocol definition (no changes)
└── cli/
    └── commands/
        └── case.py           # Already enhanced in Phase 16 (minor platform check adjustment)
```

### Pattern 1: X11 vs Wayland Detection at Startup
**What:** Check environment variables once at startup, cache result for session
**When to use:** LinuxLauncher.__init__() to determine if window focusing available
**Example:**
```python
# Source: freedesktop.org standards + user context decisions
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
```

### Pattern 2: Desktop Environment Detection for Terminal Preference
**What:** Use $XDG_CURRENT_DESKTOP to prefer native terminal (konsole on KDE, gnome-terminal on GNOME)
**When to use:** Terminal detection when both konsole and gnome-terminal installed
**Example:**
```python
# Source: freedesktop.org XDG standards + user context decisions
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
```

### Pattern 3: Startup Validation with Distro-Detected Installation Instructions
**What:** Validate wmctrl available at startup, provide distro-specific install commands if missing
**When to use:** LinuxLauncher.__init__() when display_server == "x11"
**Example:**
```python
# Source: User context decisions + package manager research
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
            if "version_id=\"7" in os_release:
                return "rhel7"
            else:
                return "rhel8+"
        elif "centos" in os_release:
            if "version_id=\"7" in os_release:
                return "centos7"
            else:
                return "centos8+"
    except Exception:
        pass

    return "unknown"
```

### Pattern 4: Window ID Capture via $WINDOWID Environment Variable
**What:** Capture window ID from $WINDOWID environment variable set by terminal
**When to use:** After terminal launch, konsole and most terminals (NOT gnome-terminal)
**Example:**
```python
# Source: Terminal emulator standards + WebSearch research
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

    try:
        # Get active window ID using xdotool
        result = subprocess.run(
            ["xdotool", "getactivewindow"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Convert decimal to hex format for consistency
            window_id = int(result.stdout.strip())
            return f"0x{window_id:08x}"
    except Exception:
        pass

    return None
```

### Pattern 5: Window Validation by ID
**What:** Check if window with specific ID still exists using wmctrl -l
**When to use:** WindowRegistry.lookup() validator callback
**Example:**
```python
# Source: wmctrl man page + community patterns
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
            timeout=5
        )
        # wmctrl -l output format: "0x0400000a  0 hostname Window Title"
        # First column is window ID in hex
        return window_id.lower() in result.stdout.lower()
    except Exception:
        return False
```

### Pattern 6: Window Focusing by ID with Desktop Switching
**What:** Use wmctrl -i -a to focus window by ID, switching desktops/workspaces if needed
**When to use:** Primary window focusing mechanism for Linux X11
**Example:**
```python
# Source: wmctrl man page + community patterns
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
            timeout=5
        )
        # wmctrl returns 0 on success, non-zero on failure
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False
```

### Pattern 7: Graceful Wayland Fallback
**What:** Detect Wayland, provide clear error message, no silent fallbacks
**When to use:** Startup detection when WAYLAND_DISPLAY is set
**Example:**
```python
# Source: User context decisions
def __init__(self, terminal: Literal["gnome-terminal", "konsole"] | None = None):
    """Initialize Linux launcher.

    Raises:
        RuntimeError: If on Wayland (X11-only support per Phase 18)
    """
    self.display_server = self._detect_display_server()

    # Strict Wayland check - fail with clear error
    if self.display_server == "wayland":
        raise RuntimeError(
            "Window tracking not supported on Wayland. "
            "Phase 18 supports X11 only. Switch to X11 session or disable window tracking."
        )

    # Validate terminal and wmctrl if on X11
    if self.display_server == "x11":
        self.terminal = terminal or self._detect_terminal()
        self._validate_wmctrl_available()
    else:
        # Unknown display server - allow terminal launch but no window tracking
        self.terminal = terminal or self._detect_terminal()
```

### Pattern 8: Stale Entry Self-Healing with New Terminal Creation
**What:** When focus fails on existing window ID, remove stale entry and create new terminal
**When to use:** After focus_window_by_id() returns False
**Example:**
```python
# Source: User context decisions + Phase 16 patterns
def focus_or_create_window(case_number: str, launcher: LinuxLauncher, registry: WindowRegistry) -> None:
    """Focus existing window or create new one with self-healing.

    User decision: If focus fails, clean stale entry and create new terminal.
    No user prompting on Linux - automatic self-healing.
    """
    # Look up window ID with validation
    window_id = registry.lookup(case_number, launcher._window_exists_by_id)

    if window_id:
        # Attempt to focus
        try:
            success = launcher.focus_window_by_id(window_id)
            if success:
                print(f"Focused existing terminal for case {case_number}")
                return
            else:
                # Focus failed - self-healing approach
                # registry.lookup already removed stale entry via validator
                print(f"Previous window unavailable, creating new terminal")
        except Exception as e:
            # wmctrl error - log but continue to create new
            print(f"Window focus failed: {e}. Creating new terminal")

    # No existing window or focus failed - create new
    # ... (existing terminal creation logic)

    # Register new window ID
    window_id = launcher._capture_window_id()
    if window_id:
        registry.register(case_number, window_id, launcher.terminal)
```

### Anti-Patterns to Avoid
- **Not checking display server before wmctrl operations:** wmctrl fails silently on Wayland with XWayland, detect and error early
- **Using xdotool for ID-based focusing:** xdotool good for search, wmctrl more reliable for focus by ID
- **Not handling gnome-terminal server architecture:** gnome-terminal-server owns all windows, $WINDOWID not set in parent process
- **Capturing window ID without delay:** Terminal window creation takes time, immediate capture gets wrong window
- **Not validating terminal installation at startup:** Better to fail fast with install instructions than fail silently at runtime
- **Silent Wayland fallback:** Users need clear feedback that Wayland unsupported, not silent degradation

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| X11 window focusing | Custom X11 protocol code | wmctrl with -i -a flags | EWMH/NetWM standard, handles workspace switching, works across WMs |
| Window existence check | Parse X11 events | wmctrl -l pipe check | Lists all windows reliably, standard output format |
| Display server detection | Parse ps/systemctl | $DISPLAY and $WAYLAND_DISPLAY env vars | Standard freedesktop.org approach, reliable |
| Desktop environment detection | Parse config files | $XDG_CURRENT_DESKTOP env var | XDG standard, set by all modern DEs |
| Distro detection | Parse /proc/version | /etc/os-release file | systemd standard since ~2012, all modern distros |
| Window ID validation | Phase 15's WindowRegistry class | Already handles concurrency, validation, cleanup |
| Terminal launching | Phase 12/15's LinuxLauncher | Already handles gnome-terminal, konsole, xfce4-terminal |

**Key insight:** Linux window management complexity handled by wmctrl implementing EWMH/NetWM standards. Don't implement X11 protocols directly - use standard tools that work across window managers (GNOME, KDE, XFCE, i3, etc.).

## Common Pitfalls

### Pitfall 1: Assuming $DISPLAY Means X11
**What goes wrong:** XWayland sets $DISPLAY even on Wayland, wmctrl operations fail
**Why it happens:** XWayland provides X11 compatibility layer with $DISPLAY set for X11 apps
**How to avoid:** Check $WAYLAND_DISPLAY first - if set, it's Wayland regardless of $DISPLAY
**Warning signs:** wmctrl commands silently fail or return no windows on GNOME/KDE Wayland sessions

### Pitfall 2: Capturing Window ID Too Soon After Launch
**What goes wrong:** Wrong window ID captured (parent shell, previous window, etc.)
**Why it happens:** Terminal window creation is asynchronous, takes time to fully initialize
**How to avoid:** Add 0.5-1.0 second delay after launch before capturing window ID (matches Phase 16)
**Warning signs:** Window IDs that never validate, focusing wrong windows

### Pitfall 3: gnome-terminal Server-Client Model Confusion
**What goes wrong:** $WINDOWID not available, window ID capture fails
**Why it happens:** gnome-terminal-server owns windows, gnome-terminal binary just pokes server
**How to avoid:** Use xdotool getactivewindow after launch delay, not $WINDOWID env var
**Warning signs:** Window ID capture always fails on gnome-terminal but works on konsole

### Pitfall 4: Not Validating wmctrl Installation
**What goes wrong:** Silent failures at runtime when user tries to focus window
**Why it happens:** Assuming wmctrl available, no startup check
**How to avoid:** Validate shutil.which("wmctrl") in __init__, raise RuntimeError with install instructions if missing
**Warning signs:** Window focusing never works, no clear error message to user

### Pitfall 5: Using Decimal vs Hex Window IDs Inconsistently
**What goes wrong:** Window ID lookups fail because format mismatch
**Why it happens:** wmctrl uses hex (0x0400000a), xdotool returns decimal (67108874), mixing formats
**How to avoid:** Standardize on hex format with 0x prefix, convert as needed
**Warning signs:** _window_exists_by_id returns False for valid windows

### Pitfall 6: Not Handling Workspace/Desktop Switching
**What goes wrong:** Window exists but focus fails because it's on different workspace
**Why it happens:** Using wrong wmctrl flags (-R vs -a), not understanding desktop switching
**How to avoid:** Use -a flag (switches to desktop, raises, focuses), not just raise
**Warning signs:** Focus works on same workspace, fails on different workspace

### Pitfall 7: Assuming All Terminals Set $WINDOWID
**What goes wrong:** Window ID capture fails for some terminals
**Why it happens:** Only some terminals (konsole, xterm, urxvt) set $WINDOWID, gnome-terminal doesn't
**How to avoid:** Use xdotool getactivewindow fallback, don't rely solely on $WINDOWID
**Warning signs:** Works on konsole, fails on gnome-terminal

### Pitfall 8: Not Testing Focus Across Window Managers
**What goes wrong:** wmctrl works on GNOME/KDE, fails on tiling WMs (i3, awesome, etc.)
**Why it happens:** Tiling WMs may not fully support EWMH _NET_ACTIVE_WINDOW
**How to avoid:** Document X11 support as "best effort on EWMH-compliant WMs", test on i3/awesome
**Warning signs:** User reports focus fails on i3 but works on GNOME

## Code Examples

Verified patterns from research and existing codebase:

### LinuxLauncher Enhancement (Complete Implementation)
```python
# Source: Pattern synthesis from research + existing linux.py structure
import os
import shutil
import subprocess
import time
from typing import Literal

from mc.terminal.launcher import LaunchOptions


class LinuxLauncher:
    """Linux terminal launcher with X11 window tracking support."""

    def __init__(
        self,
        terminal: Literal["gnome-terminal", "konsole"] | None = None,
    ) -> None:
        """Initialize Linux launcher with X11/Wayland detection.

        Args:
            terminal: Specific terminal to use, or None for auto-detection

        Raises:
            RuntimeError: If on Wayland or if required tools missing
        """
        # Detect display server
        self.display_server = self._detect_display_server()

        # Strict Wayland check
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
        """Detect X11 vs Wayland display server."""
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        elif os.environ.get("DISPLAY"):
            return "x11"
        else:
            return "unknown"

    def _detect_terminal(self) -> Literal["gnome-terminal", "konsole"]:
        """Detect available terminal emulator with desktop preference."""
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").upper()

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

        raise RuntimeError(
            "No supported terminal emulator found. "
            "Install gnome-terminal or konsole to use window tracking."
        )

    def _detect_distro(self) -> str:
        """Detect Linux distribution for installation instructions."""
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
        """Validate wmctrl installed, raise error with install instructions if not."""
        if shutil.which("wmctrl"):
            return

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

    def _capture_window_id(self) -> str | None:
        """Capture window ID after terminal creation.

        Returns:
            Window ID as hexadecimal string (0x...), or None if capture fails
        """
        # Wait for window to fully create
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
                # Convert decimal to hex format
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
            return window_id.lower() in result.stdout.lower()
        except Exception:
            return False

    def focus_window_by_id(self, window_id: str) -> bool:
        """Focus window by ID, handling workspace switching.

        Args:
            window_id: Window ID to focus (hex format: 0x...)

        Returns:
            True if focus succeeded, False otherwise
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
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False
        except Exception:
            return False

    # ... (existing launch() methods unchanged)
```

### CLI Integration (Adjustment for Linux)
```python
# Source: Existing case.py patterns + Phase 16/18 requirements
from mc.terminal.launcher import get_launcher
from mc.terminal.registry import WindowRegistry
import platform


def case_command(case_number: str, base_dir: str, offline_token: str) -> None:
    """Open case terminal, focusing existing if present."""

    # Validate case number
    case_number = validate_case_number(case_number)

    # Window tracking on macOS and Linux X11
    if platform.system() in ["Darwin", "Linux"]:
        launcher = get_launcher()
        registry = WindowRegistry()

        # Check for existing window
        window_id = registry.lookup(case_number, launcher._window_exists_by_id)

        if window_id:
            # Try to focus existing window
            if hasattr(launcher, "focus_window_by_id"):
                success = launcher.focus_window_by_id(window_id)
                if success:
                    print(f"Focused existing terminal for case {case_number}")
                    return
                else:
                    # Self-healing - registry.lookup already removed stale entry
                    print("Previous window unavailable, creating new terminal")

    # Create new terminal window
    # ... (existing terminal creation logic)

    # Register window ID if on supported platform
    if platform.system() in ["Darwin", "Linux"]:
        window_id = launcher._capture_window_id()
        if window_id:
            registry.register(case_number, window_id, launcher.terminal)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Title-based window search | Window ID lookup | Phase 15 (v2.0.2) | Reliable tracking (titles volatile) |
| xdotool for all operations | wmctrl for focus, xdotool for search | Established practice | Tool specialization improves reliability |
| lsb_release command | /etc/os-release file | systemd era (~2012) | No extra package dependency |
| YUM package manager | DNF on Fedora/RHEL 8+ | Fedora 22, RHEL 8 (2019) | Faster dependency resolution |
| Wayland XWayland compatibility | Explicit Wayland non-support | Phase 18 (2026) | Clear user expectations vs silent failures |

**Deprecated/outdated:**
- **xdotool for ID-based focusing:** Still works but wmctrl more reliable for this specific use case
- **lsb_release command:** Extra package dependency, /etc/os-release is standard
- **yum on modern distros:** Still works via symlink but dnf is preferred on Fedora/RHEL 8+
- **Assuming X11 from $DISPLAY:** XWayland breaks this assumption, must check $WAYLAND_DISPLAY

## Open Questions

Things that couldn't be fully resolved:

1. **Tiling window manager compatibility**
   - What we know: wmctrl uses EWMH/NetWM standards, tiling WMs (i3, awesome, sway) have varying support
   - What's unclear: Which tiling WMs fully support _NET_ACTIVE_WINDOW and workspace switching
   - Recommendation: Document X11 support as "EWMH-compliant window managers", test on i3/awesome if possible

2. **gnome-terminal window ID capture reliability**
   - What we know: gnome-terminal-server owns windows, xdotool getactivewindow gets most recent
   - What's unclear: Race condition if user switches focus during 0.5s delay, or multiple terminals launch simultaneously
   - Recommendation: Use 0.5s delay (matches macOS), accept edge cases, rely on validation/cleanup

3. **xdotool dependency vs optional**
   - What we know: xdotool needed for window ID capture fallback, not for focusing (wmctrl handles)
   - What's unclear: Should xdotool be required or gracefully degrade if missing?
   - Recommendation: Start with xdotool required (add to wmctrl validation), can relax to optional in Phase 19 if needed

4. **Wayland future support approach**
   - What we know: Wayland has no standard window management protocol (compositor-specific)
   - What's unclear: Will there be a standard tool (wlrctl, etc.) or remain compositor-specific?
   - Recommendation: Phase 18 explicit non-support, defer Wayland to future phase when standards emerge

## Sources

### Primary (HIGH confidence)
- Existing codebase: `/Users/dsquirre/Repos/mc/src/mc/terminal/linux.py` - Terminal launching patterns
- Existing codebase: `/Users/dsquirre/Repos/mc/src/mc/terminal/macos.py` - Window tracking patterns from Phase 16
- Existing codebase: `/Users/dsquirre/Repos/mc/src/mc/terminal/registry.py` - Registry with validation (Phase 15)
- [wmctrl man page](https://linux.die.net/man/1/wmctrl) - Official wmctrl documentation
- [Root Window Properties | Extended Window Manager Hints](https://specifications.freedesktop.org/wm-spec/1.3/ar01s03.html) - EWMH/NetWM standards
- [Wayland - ArchWiki](https://wiki.archlinux.org/title/Wayland) - Wayland vs X11 detection
- [How to Find Linux Distribution Release Name and Version](https://www.ubuntumint.com/check-linux-version/) - /etc/os-release standard

### Secondary (MEDIUM confidence)
- [GNOME Terminal Server](https://eklitzke.org/gnome-terminal-server) - gnome-terminal architecture explanation
- [WINDOWID variable not being set (#17) · GNOME / gnome-terminal](https://gitlab.gnome.org/GNOME/gnome-terminal/-/issues/17) - gnome-terminal $WINDOWID limitation
- [Gnome-terminal window id cannot be found by xdotool nor wmctrl - GNOME Discourse](https://discourse.gnome.org/t/gnome-terminal-window-id-cannot-be-found-by-xdotool-nor-wmctrl/14835) - gnome-terminal window tracking challenges
- [How to Use the Command 'wmctrl' (with examples)](https://commandmasters.com/commands/wmctrl-linux/) - wmctrl usage patterns
- [xdotool Ubuntu Manpage](https://manpages.ubuntu.com/manpages/trusty/man1/xdotool.1.html) - xdotool documentation
- [How to Check If Wayland or Xorg Is Being Used](https://www.adamsdesk.com/posts/find-display-server-wayland-xorg/) - Display server detection
- [How to Determine if Your Linux OS is Running KDE or GNOME](https://codingtechroom.com/question/-detect-kde-gnome-linux-os) - XDG_CURRENT_DESKTOP usage

### Tertiary (LOW confidence)
- [Move window on Linux using Python, xdotool and wmctrl · GitHub](https://gist.github.com/wolkenarchitekt/be8b52952ce6df09fa8e127b0035050e) - Python subprocess examples
- [wmctrl vs xdotool reliability window focusing - Hackaday](https://hackaday.com/2017/09/21/linux-fu-x-command/) - Tool comparison (older article)
- [Package Management in Linux: APT, YUM, DNF, and Pacman](https://maelstromwebservices.com/blog/linux/pkg-management/) - Package manager overview
- WebSearch: X11 window focusing pitfalls - Community discussions, limited official documentation
- WebSearch: konsole WINDOWID variable - Scattered references across GitHub issues

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - wmctrl/subprocess are standard tools, patterns established
- Architecture: MEDIUM - Patterns synthesized from research + existing code, not all tested on Linux
- Pitfalls: MEDIUM - Identified from community discussions and Phase 16 macOS experience, some inferred
- gnome-terminal server model: MEDIUM - Documented in articles but timing behavior not fully tested
- Wayland detection: HIGH - Standard environment variables, well-documented

**Research date:** 2026-02-08
**Valid until:** 2026-03-08 (30 days - stable domain, X11 tools rarely change)
**Supported environments:** Linux X11 with EWMH-compliant window managers (GNOME, KDE, XFCE, etc.)
**Dependencies:** Phase 15 (WindowRegistry), Phase 16 (window tracking patterns), wmctrl 1.07, xdotool 3.x (optional)
