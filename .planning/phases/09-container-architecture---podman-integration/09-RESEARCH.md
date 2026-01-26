# Phase 9: Container Architecture & Podman Integration - Research

**Researched:** 2026-01-26
**Domain:** Rootless Podman integration with platform detection and UID/GID mapping
**Confidence:** HIGH

## Summary

This phase establishes the foundation for Podman integration: connecting to the Podman socket, detecting platform differences (macOS Podman machine vs Linux native), and configuring rootless containers with correct UID/GID mapping for workspace volume mounts. The research confirms that podman-py 5.7.0+ is the standard library for Python-based Podman integration, --userns=keep-id is the recommended approach for rootless UID mapping, and the :U volume suffix provides automatic ownership correction but requires careful use due to host filesystem modifications.

**Primary recommendation:** Use podman-py 5.7.0+ for Podman API access, always apply --userns=keep-id for rootless containers, and implement lazy platform detection with macOS Podman machine auto-start prompting.

**Key findings:**
- Socket path detection follows standard pattern: `/run/user/$UID/podman/podman.sock` (Linux rootless) or Podman machine socket path (macOS)
- The --userns=keep-id flag preserves host UID/GID inside container, preventing permission issues with volume mounts
- The :U volume suffix recursively chowns mounted volumes but modifies host filesystem (use with caution)
- Podman 5.0+ defaults to pasta networking with known inter-container communication limitations
- macOS requires Podman machine VM; use `podman machine list --format json` to check status before operations

## Standard Stack

The established libraries/tools for Podman integration in Python:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| podman-py | 5.7.0+ | Python bindings for Podman RESTful API | Official library from containers/podman-py. Provides Docker-compatible API surface. Active development with quarterly releases. Supports both rootless and rootful modes. Type hints included as of 5.7.0. |
| Podman | 5.0+ | Container runtime (system dependency) | Required system installation. Rootless mode eliminates daemon security risks. Native on RHEL/Fedora. Available via brew on macOS for development. Pasta networking default since 5.0. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| platform (stdlib) | N/A | OS detection | Use `platform.system()` to detect 'Darwin' (macOS) vs 'Linux'. Returns consistent string values for cross-platform detection. |
| subprocess (stdlib) | N/A | Podman machine management | Check Podman installation (`podman --version`), manage Podman machine on macOS (`podman machine list`, `podman machine start`). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| podman-py | subprocess + podman CLI | Direct CLI calls simpler for basic operations but lose type safety, structured error handling, and object-oriented API. Podman-py recommended for maintainability. |
| podman-py | docker-py | Docker-py works if you use Docker runtime, but Podman is standard on RHEL/Fedora (target environment), rootless by default (70% lower attack surface), and daemonless (4x faster startup). |
| Platform detection on first use | Detection at module import | Lazy detection avoids import-time overhead and allows testing without Podman installed. Only detect when Podman operations are actually needed. |

**Installation:**
```bash
# Python library
pip install podman>=5.7.0

# System dependency
# macOS:
brew install podman
podman machine init
podman machine start

# Fedora/RHEL:
dnf install podman

# Ubuntu/Debian:
apt install podman
```

## Architecture Patterns

### Recommended Integration Structure
```
src/mc/integrations/
├── podman.py              # PodmanClient wrapper class
│   ├── __init__()         # Lazy socket connection
│   ├── ping()             # Verify connectivity
│   └── get_version()      # Version compatibility check
├── platform_detect.py     # Platform detection module
│   ├── detect_platform()  # Returns 'macos' | 'linux' | 'unsupported'
│   ├── get_socket_path()  # Platform-specific socket path
│   └── ensure_podman_ready()  # Auto-start macOS machine if needed
```

### Pattern 1: Lazy Socket Connection
**What:** Defer Podman socket connection until first API call, not at module import or class instantiation.

**When to use:** When you want fast CLI startup and graceful handling of environments without Podman.

**Example:**
```python
# Source: Based on podman-py patterns and lazy initialization best practices
import podman
from typing import Optional

class PodmanClient:
    """Wrapper for Podman operations with lazy connection."""

    def __init__(self, socket_path: Optional[str] = None):
        self._socket_path = socket_path
        self._client: Optional[podman.PodmanClient] = None

    @property
    def client(self) -> podman.PodmanClient:
        """Get Podman client, connecting on first access."""
        if self._client is None:
            if self._socket_path:
                uri = f"unix://{self._socket_path}"
            else:
                # Auto-detect socket path
                uri = None  # podman-py uses default

            try:
                self._client = podman.PodmanClient(base_url=uri)
            except Exception as e:
                raise ConnectionError(
                    f"Cannot connect to Podman socket at {self._socket_path or 'default path'}. "
                    f"Ensure Podman is installed and running: {e}"
                )

        return self._client

    def ping(self) -> bool:
        """Verify Podman connection."""
        try:
            return self.client.ping()
        except Exception:
            return False
```

### Pattern 2: Platform Detection with Podman Machine Auto-Start
**What:** Detect macOS vs Linux, check if Podman machine is running on macOS, and prompt to start if needed.

**When to use:** When operations require Podman to be available and you want graceful handling of macOS VM.

**Example:**
```python
# Source: Based on podman machine list command and platform detection patterns
import platform
import subprocess
import json

def detect_platform() -> str:
    """Detect platform: 'macos', 'linux', or 'unsupported'."""
    system = platform.system()
    if system == 'Darwin':
        return 'macos'
    elif system == 'Linux':
        return 'linux'
    else:
        return 'unsupported'

def is_podman_machine_running() -> bool:
    """Check if Podman machine is running (macOS only)."""
    try:
        result = subprocess.run(
            ['podman', 'machine', 'list', '--format', 'json'],
            capture_output=True,
            text=True,
            check=True
        )
        machines = json.loads(result.stdout)

        # Check if any machine is running
        for machine in machines:
            if machine.get('Running', False):
                return True
        return False
    except (subprocess.CalledProcessError, json.JSONDecodeError, FileNotFoundError):
        return False

def ensure_podman_ready(platform_type: str) -> None:
    """Ensure Podman is ready for operations."""
    if platform_type == 'macos':
        if not is_podman_machine_running():
            # Prompt user to start machine
            response = input("Podman machine is stopped. Start it? [y/n] ")
            if response.lower() == 'y':
                subprocess.run(['podman', 'machine', 'start'], check=True)
            else:
                raise RuntimeError("Podman machine must be running")
    elif platform_type == 'linux':
        # Linux native - just verify Podman is installed
        try:
            subprocess.run(
                ['podman', '--version'],
                capture_output=True,
                check=True
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError(
                "Podman is not installed. Install with: "
                "dnf install podman (RHEL/Fedora) or apt install podman (Ubuntu/Debian)"
            )
    else:
        raise RuntimeError(
            f"Unsupported platform: {platform_type}. "
            "MC requires macOS or Linux. See docs for workarounds."
        )
```

### Pattern 3: Socket Path Detection
**What:** Determine correct Podman socket path based on platform and rootless/rootful mode.

**When to use:** When you need to explicitly specify socket path for podman-py connection.

**Example:**
```python
# Source: Official Podman documentation socket paths
import os
from pathlib import Path

def get_socket_path(platform_type: str) -> str:
    """Get Podman socket path for current platform."""
    if platform_type == 'linux':
        # Rootless Linux: /run/user/$UID/podman/podman.sock
        uid = os.getuid()
        socket_path = f"/run/user/{uid}/podman/podman.sock"

        if not Path(socket_path).exists():
            # Fallback: check if rootful socket exists
            rootful_path = "/run/podman/podman.sock"
            if Path(rootful_path).exists():
                socket_path = rootful_path

        return socket_path

    elif platform_type == 'macos':
        # macOS: Socket in Podman machine directory
        # podman-py will auto-detect from machine config
        # Return None to use default detection
        return None

    else:
        raise ValueError(f"Unsupported platform: {platform_type}")
```

### Pattern 4: UID/GID Mapping with --userns=keep-id
**What:** Always use --userns=keep-id flag for rootless containers to preserve host UID/GID inside container.

**When to use:** Every time you create a rootless container that mounts host volumes (workspace directories).

**Example:**
```python
# Source: Podman rootless tutorial and podman-py container creation patterns
# https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md

def create_container(self, image: str, name: str, workspace_path: str) -> str:
    """Create rootless container with correct UID/GID mapping."""
    # Hard-coded --userns=keep-id for all rootless containers
    # This ensures host user's UID/GID are preserved inside container
    userns_mode = "keep-id"

    # Volume mount with workspace
    volumes = {
        workspace_path: {
            "bind": "/workspace",
            "mode": "rw"
        }
    }

    try:
        container = self.client.containers.create(
            image=image,
            name=name,
            userns_mode=userns_mode,  # Critical for UID/GID mapping
            volumes=volumes,
            detach=True,
            tty=True,
            stdin_open=True
        )
        container.start()
        return container.id
    except podman.errors.ImageNotFound:
        raise ImageNotFoundError(f"Image not found: {image}. Run: podman pull {image}")
    except Exception as e:
        raise ContainerCreationError(f"Failed to create container: {e}")
```

### Pattern 5: Version Compatibility Checking
**What:** Check Podman version and warn/fail based on sliding window compatibility strategy.

**When to use:** During platform detection, before critical operations.

**Example:**
```python
# Source: Version compatibility pattern from context decisions
import re
import subprocess

def check_podman_version(warn_threshold: int = 3, fail_threshold: int = 7) -> dict:
    """
    Check Podman version compatibility.

    Args:
        warn_threshold: Warn if version is this many behind (default: 3)
        fail_threshold: Fail if version is this many behind (default: 7)

    Returns:
        dict with 'version', 'major', 'minor', 'action' keys
    """
    try:
        result = subprocess.run(
            ['podman', '--version'],
            capture_output=True,
            text=True,
            check=True
        )
        # Parse "podman version 5.2.1"
        match = re.search(r'(\d+)\.(\d+)', result.stdout)
        if not match:
            raise ValueError(f"Could not parse version from: {result.stdout}")

        major = int(match.group(1))
        minor = int(match.group(2))

        # Expected version (from container build time)
        expected_major = 5
        expected_minor = 0

        # Calculate version difference
        version_diff = (expected_major - major) * 10 + (expected_minor - minor)

        if version_diff >= fail_threshold:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'fail',
                'message': f"Podman {major}.{minor} is too old (7+ versions behind). Update required."
            }
        elif version_diff >= warn_threshold:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'warn',
                'message': f"Podman {major}.{minor} is 3+ versions behind. Consider updating."
            }
        else:
            return {
                'version': f"{major}.{minor}",
                'major': major,
                'minor': minor,
                'action': 'ok',
                'message': f"Podman {major}.{minor} is compatible."
            }

    except (subprocess.CalledProcessError, FileNotFoundError):
        return {
            'version': None,
            'major': None,
            'minor': None,
            'action': 'fail',
            'message': "Podman is not installed or not in PATH."
        }
```

### Anti-Patterns to Avoid

- **Connecting to Podman at module import time:** Causes import failures when Podman isn't installed, slows down CLI startup, prevents testing without Podman. Use lazy connection instead.
- **Assuming rootful Podman on Linux:** Many users run rootless Podman by default (more secure). Always support rootless mode, detect based on socket path.
- **Using default container user without --userns=keep-id:** Files created in mounted volumes will have unexpected UIDs (100000+). Always use --userns=keep-id for rootless containers.
- **Not checking Podman machine status on macOS:** Attempting operations when machine is stopped results in cryptic connection errors. Check machine status before operations.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Podman API communication | Custom HTTP client for Podman socket | podman-py library | Handles connection lifecycle, error mapping, object serialization, API versioning. Reinventing this adds 500+ lines of boilerplate. |
| Socket path detection | Hard-code socket paths | Environment variables (XDG_RUNTIME_DIR) + standard paths | Podman respects XDG standards. Hard-coded paths break in non-standard setups, rootful mode, or future Podman versions. |
| Platform detection | Parse uname output | platform.system() stdlib | Standard library handles edge cases (BSD variants, WSL, etc.). Parsing uname is fragile and non-portable. |
| Podman machine status checking | Parse podman ps output | `podman machine list --format json` | JSON format is stable API. Parsing human-readable output breaks with locale changes or format updates. |
| UID/GID mapping in containers | Manual chown after container creation | --userns=keep-id + :U volume suffix | Podman's built-in mechanisms are kernel-backed, atomic, and handle edge cases (SELinux contexts, nested directories). Manual chown misses permission edge cases. |

**Key insight:** Podman's Python library and CLI flags are battle-tested across millions of containers. Custom solutions miss edge cases (SELinux contexts, cgroup v1/v2 differences, pasta vs slirp4netns networking variants).

## Common Pitfalls

### Pitfall 1: UID/GID Mapping Confusion in Volume Mounts
**What goes wrong:** Container creates files in workspace with unexpected UIDs (e.g., UID 100025 instead of user's UID 1000), causing permission denied errors when host user accesses files.

**Why it happens:** Rootless Podman maps container root (UID 0) to host user's UID, but other container UIDs map to subuids from `/etc/subuid`. If container process runs as UID 26, it appears as UID 100025 on host. Developers assume container UID 0 = host UID 0.

**How to avoid:**
- **Always use --userns=keep-id** for rootless containers (hard-coded, not optional)
- Apply :U suffix to volume mounts conditionally (research findings suggest conditional use based on mount type)
- Test file creation from both container and host before finalizing
- Document which user runs inside container (root vs non-root)

**Warning signs:**
- `ls -la` shows high UIDs (100000+) on workspace files
- Permission denied when accessing container-created files
- Files owned by "nobody" or unmapped UIDs
- chown fails inside container

### Pitfall 2: :U Volume Suffix Modifies Host Filesystem
**What goes wrong:** Using :U suffix on volume mounts recursively changes ownership of host files, potentially breaking other processes or users that access the same directory.

**Why it happens:** The :U suffix tells Podman to "recursively change the owner and group of the source volume based on the UID and GID within the container." This modifies the actual host filesystem, not just container's view. Documentation warns: "use with caution since this modifies the host filesystem."

**How to avoid:**
- **Conditional :U application:** Consider using :U only when necessary (bind mounts of user-owned directories, not system directories)
- Validate ownership before applying :U (check if files already have correct ownership)
- Document side effects in user-facing messages ("This will change file ownership in your workspace")
- Consider alternative: podman unshare chown (changes ownership in user namespace without affecting host)

**Warning signs:**
- Other applications can't access files after container creation
- Permission issues in shared directories (multi-user systems)
- Build artifacts owned by unexpected UIDs
- Git shows all files as modified (ownership changed)

### Pitfall 3: macOS Podman Machine Not Running
**What goes wrong:** Attempting Podman operations on macOS when machine is stopped results in "Connection refused" errors without clear indication that machine needs starting.

**Why it happens:** macOS doesn't have native container support (no Linux kernel). Podman runs containers in a VM ("Podman machine"). If machine is stopped, socket doesn't exist. Error messages from podman-py are generic connection failures.

**How to avoid:**
- **Check machine status before operations:** Use `podman machine list --format json` to verify "Running": true
- **Prompt user to start machine:** Implement interactive prompt with clear message
- **Auto-start with confirmation:** Don't silently start (resource usage), ask first
- **Clear error messages:** Map "Connection refused" to "Podman machine is not running. Start with: podman machine start"

**Warning signs:**
- ConnectionError: Connection refused on macOS
- Socket path doesn't exist
- Works after reboot but stops working later
- `podman ps` fails with connection error

### Pitfall 4: Rootless vs Rootful Socket Path Confusion
**What goes wrong:** Code connects to wrong Podman socket (rootful when expecting rootless or vice versa), shows wrong containers, can't access images.

**Why it happens:** Rootless and rootful Podman use different sockets with separate storage. Default socket is `/run/user/$UID/podman/podman.sock` (rootless) vs `/run/podman/podman.sock` (rootful). Podman-py auto-detection may choose wrong socket if both exist.

**How to avoid:**
- **Explicitly detect rootless mode:** Check if socket exists at `/run/user/$UID/podman/podman.sock`
- **Environment variable override:** Respect CONTAINER_HOST if set
- **Document assumption:** State clearly that MC assumes rootless Podman
- **Validate on connection:** After connecting, verify you're seeing expected state (or empty state for new setup)

**Warning signs:**
- Containers created but `mc list` shows nothing
- Images pulled but Podman can't find them
- Permission denied on operations that should work rootless
- Different results from `podman ps` vs MC's container listing

### Pitfall 5: Podman API Timeout on First Connection
**What goes wrong:** First API call after Podman service starts takes >30 seconds, causing timeout errors. Subsequent calls are fast.

**Why it happens:** Podman service (when using socket activation) may need to start up on first connection. Image pulls or first container creation trigger indexing. User-configured timeout is too short for cold starts.

**How to avoid:**
- **Configurable timeout:** Add `podman.timeout` to config file (default 120 seconds)
- **Retry with exponential backoff:** Auto-retry failed API calls up to 3 times (per decision context)
- **Longer timeout for image operations:** Use higher timeout for pulls/builds than for list/inspect
- **Warn on slow operations:** Log "Podman service starting..." if operation takes >5 seconds

**Warning signs:**
- First operation times out, second succeeds
- Timeout errors after machine start/restart
- Works fine on warm system, fails on cold boot
- Error: "Read timeout" or "Connection timeout"

### Pitfall 6: Port Binding Restrictions Below 1024
**What goes wrong:** Rootless containers cannot bind to privileged ports (<1024), causing failures when trying to map ports like 80, 443, or 22.

**Why it happens:** Linux kernel restricts port binding below 1024 to root user (CAP_NET_BIND_SERVICE capability). Rootless Podman runs as unprivileged user, can't bind privileged ports.

**How to avoid:**
- **Document limitation:** Clearly state that rootless mode can't bind ports <1024
- **Suggest alternatives:** Use higher ports (8080 instead of 80), configure sysctl `net.ipv4.ip_unprivileged_port_start`
- **Detect and provide helpful error:** Map "Permission denied" on port binding to specific message about rootless limitation
- **For MC's use case:** Phase 9 doesn't involve port binding (that's container lifecycle in later phases), but document for future phases

**Warning signs:**
- Error: "Permission denied" when binding port
- Port binding works in Docker but not Podman
- Rootful Podman works, rootless fails
- Port mapping silently ignored

## Code Examples

Verified patterns from official sources:

### Podman-py Basic Connection
```python
# Source: https://podman-py.readthedocs.io/en/latest/
import podman

# Context manager pattern (recommended for resource cleanup)
with podman.PodmanClient() as client:
    # Verify connection
    if client.ping():
        print("Connected to Podman")

        # Get version info
        version = client.version()
        print(f"Podman version: {version['Version']}")
```

### Socket Path Auto-Detection
```python
# Source: Podman documentation - socket paths
# https://docs.podman.io/en/latest/markdown/podman-system-service.1.html
import os
from pathlib import Path

def get_default_socket_path() -> str:
    """Get default Podman socket path for rootless mode."""
    # Check environment variable first
    container_host = os.getenv('CONTAINER_HOST')
    if container_host:
        # Parse unix:// URI
        if container_host.startswith('unix://'):
            return container_host[7:]  # Remove 'unix://' prefix
        return container_host

    # Standard rootless socket path
    xdg_runtime_dir = os.getenv('XDG_RUNTIME_DIR')
    if xdg_runtime_dir:
        socket_path = Path(xdg_runtime_dir) / 'podman' / 'podman.sock'
    else:
        # Fallback: construct from UID
        uid = os.getuid()
        socket_path = Path(f'/run/user/{uid}/podman/podman.sock')

    if socket_path.exists():
        return str(socket_path)

    # Check rootful socket as last resort
    rootful_socket = Path('/run/podman/podman.sock')
    if rootful_socket.exists():
        return str(rootful_socket)

    raise FileNotFoundError("No Podman socket found")
```

### Container Creation with --userns=keep-id
```python
# Source: Podman rootless tutorial
# https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md
import podman

def create_workspace_container(
    client: podman.PodmanClient,
    image: str,
    name: str,
    workspace_path: str
) -> str:
    """Create container with workspace mount and correct UID/GID mapping."""

    # Volume mount configuration
    volumes = {
        workspace_path: {
            'bind': '/workspace',
            'mode': 'rw'
        }
    }

    # Create container with --userns=keep-id equivalent
    container = client.containers.create(
        image=image,
        name=name,
        userns_mode='keep-id',  # Preserve host UID/GID
        volumes=volumes,
        detach=True,
        tty=True,
        stdin_open=True
    )

    container.start()
    return container.id
```

### Retry Pattern for Transient Errors
```python
# Source: Retry pattern based on decision context (3 retries, exponential backoff)
import time
from typing import Callable, TypeVar

T = TypeVar('T')

def retry_podman_operation(
    operation: Callable[[], T],
    max_retries: int = 3,
    base_delay: float = 1.0
) -> T:
    """Retry Podman operation with exponential backoff."""
    last_exception = None

    for attempt in range(max_retries):
        try:
            return operation()
        except (ConnectionError, TimeoutError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                print(f"Podman operation failed (attempt {attempt + 1}/{max_retries}), "
                      f"retrying in {delay}s...")
                time.sleep(delay)
            else:
                # Last attempt failed
                raise last_exception

    # Should not reach here, but for type safety
    raise last_exception
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| slirp4netns networking | pasta networking | Podman 5.0 (2024) | Pasta is faster (no NAT overhead) but breaks inter-container communication on single-NIC systems. MC doesn't need inter-container networking (isolated case containers). |
| BoltDB for state | SQLite for state | Podman 4.8 (deprecated), removal in 6.0 (mid-2026) | SQLite is industry standard, better tooling, actively maintained. Use SQLite from start to match Podman's direction. |
| AppleScript for iTerm2 | iterm2 Python library | iTerm2 3.x+ | Python API is more reliable, testable, and less injection-prone than string concatenation in AppleScript. |
| Socket activation required | Socket activation optional | Podman 4.0+ | Podman API can work without systemd socket activation (direct socket creation). Simplifies setup for CLI tools. |

**Deprecated/outdated:**
- **gnome-terminal -e flag:** Deprecated in GNOME Terminal 3.x, use `--` double-dash syntax instead
- **docker-py for Podman:** While Podman is Docker-compatible, podman-py is the native library with Podman-specific features (rootless support, pasta networking awareness)
- **Hard-coded socket paths:** Podman respects XDG_RUNTIME_DIR and CONTAINER_HOST environment variables; hard-coding paths breaks in non-standard setups

## Open Questions

Things that couldn't be fully resolved:

1. **:U volume suffix application strategy**
   - What we know: :U recursively chowns host filesystem, required for some permission scenarios, documented warning about host modification
   - What's unclear: Optimal strategy - always apply, conditional on mount type, or conditional on ownership validation
   - Recommendation: Implement conditional application (check ownership first, only apply :U if mismatch detected), allow user override via config flag. Mark as Claude's discretion for planning phase.

2. **UID validation after container start**
   - What we know: --userns=keep-id should preserve UID/GID, :U suffix modifies ownership
   - What's unclear: Whether to validate actual UID inside container matches host, or trust --userns=keep-id
   - Recommendation: Trust --userns=keep-id initially (avoid extra API calls), add validation only if users report permission issues. Mark as Claude's discretion for planning phase.

3. **Rootless vs rootful detection heuristic reliability**
   - What we know: Socket path indicates mode (/run/user/$UID = rootless, /run/podman = rootful)
   - What's unclear: Edge cases where both sockets exist or socket path doesn't indicate mode definitively
   - Recommendation: Use socket path heuristic as primary method, assume rootless by default (safer, more common). Mark as Claude's discretion for planning phase.

## Sources

### Primary (HIGH confidence)
- [Podman-py Documentation](https://podman-py.readthedocs.io/en/latest/) - Official Python bindings documentation
- [Podman Run Documentation](https://docs.podman.io/en/latest/markdown/podman-run.1.html) - --userns=keep-id and :U suffix documentation
- [Podman Rootless Tutorial](https://github.com/containers/podman/blob/main/docs/tutorials/rootless_tutorial.md) - Official rootless setup guide
- [Podman System Service Documentation](https://docs.podman.io/en/latest/markdown/podman-system-service.1.html) - Socket paths and service configuration
- [Podman Machine List Documentation](https://docs.podman.io/en/latest/markdown/podman-machine-list.1.html) - macOS machine status checking
- [Python platform module](https://docs.python.org/3/library/platform.html) - Standard library platform detection

### Secondary (MEDIUM confidence)
- [Using volumes with rootless podman, explained - Tutorial Works](https://www.tutorialworks.com/podman-rootless-volumes/) - Practical volume mount examples
- [Understanding rootless Podman's user namespace modes - Red Hat](https://www.redhat.com/en/blog/rootless-podman-user-namespace-modes) - UID/GID mapping deep dive
- [Podman rootless(7) - Arch manual pages](https://man.archlinux.org/man/extra/podman/podman-rootless.7.en) - Rootless limitations and constraints
- [Podman Networking Documentation - eriksjolund/podman-networking-docs](https://github.com/eriksjolund/podman-networking-docs) - Pasta vs slirp4netns networking

### Tertiary (LOW confidence - WebSearch only, marked for validation)
- [Podman machine macOS auto-start discussions](https://github.com/podman-desktop/podman-desktop/issues/225) - Auto-start feature request context
- [Podman-py connection issues](https://github.com/containers/podman-py/issues/188) - Historical socket connection problems
- [Red Hat Customer Portal - rootless port binding](https://access.redhat.com/solutions/7044059) - Port <1024 limitation details

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - podman-py is official library, Podman 5.0+ is well-documented
- Architecture: HIGH - Patterns verified from official Podman documentation and podman-py examples
- Pitfalls: HIGH - UID/GID mapping, :U suffix, and macOS machine issues verified from official docs and community reports

**Research date:** 2026-01-26
**Valid until:** ~60 days (Podman has quarterly releases but foundational patterns are stable)

**Notes for planner:**
- Phase 9 scope is foundation only: connection, platform detection, UID/GID setup
- Container lifecycle operations (create, list, stop, delete) are Phase 11
- Salesforce integration is Phase 10
- Terminal automation is Phase 12
- This research focuses exclusively on Podman integration foundation
