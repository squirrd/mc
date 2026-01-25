# Architecture Research: Container Orchestrator CLI

**Domain:** Container orchestration CLI tool (host controller + container agent pattern)
**Researched:** 2026-01-26
**Confidence:** HIGH

## Standard Architecture

### System Overview

Container orchestrator CLIs follow a **host-controller + container-agent** pattern, where:
- **Host CLI** manages container lifecycle (create, list, stop, exec)
- **Container agent** runs inside containers (optional, for advanced features)
- **State persistence** tracks running containers and metadata
- **Integration layer** interfaces with container runtime (Podman, Docker)

```
┌────────────────────────────────────────────────────────────────┐
│                    Host CLI Layer (mc)                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  create  │  │   list   │  │   stop   │  │   exec   │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       └──────────────┴──────────────┴─────────────┘             │
├────────────────────────────────────────────────────────────────┤
│                 Controller Layer                                │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ Container        │  │ State            │                    │
│  │ Manager          │  │ Manager          │                    │
│  └────────┬─────────┘  └────────┬─────────┘                    │
│           │                      │                              │
├───────────┴──────────────────────┴──────────────────────────────┤
│                 Integration Layer                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │ Podman   │  │ Salesforce│ │ Terminal │  │ Image    │        │
│  │ API      │  │ Client    │  │ Launcher │  │ Builder  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │               │
├───────┴─────────────┴─────────────┴─────────────┴───────────────┤
│                 State Persistence Layer                         │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  SQLite DB (container metadata)                      │       │
│  │  - Running containers                                │       │
│  │  - Case → Container mapping                          │       │
│  │  - Created timestamps                                │       │
│  │  - Mount points                                      │       │
│  └──────────────────────────────────────────────────────┘       │
└────────────────────────────────────────────────────────────────┘
        │                    │                   │
        ↓                    ↓                   ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Podman     │    │  Salesforce │    │  Terminal   │
│  Runtime    │    │  API        │    │  Emulator   │
└─────────────┘    └─────────────┘    └─────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| Host CLI | User-facing commands, argument parsing, workflow orchestration | Click/Typer framework or argparse |
| Container Manager | Container lifecycle (create, start, stop, exec, remove) | Podman Python library (podman-py) |
| State Manager | Track container state, case→container mapping, metadata | SQLite database with simple schema |
| Salesforce Client | Fetch case metadata, cache API responses | requests library with file-based cache |
| Terminal Launcher | Open new terminal windows with container exec | Platform-specific commands (osascript for iTerm, gnome-terminal) |
| Image Builder | Build and publish container images | Podman build API or subprocess calls |

## Recommended MC v2.0 Architecture

### Architectural Decision: Shared Codebase vs Separate Components

**Recommendation:** **Shared codebase with runtime mode detection**

```python
# src/mc/cli/main.py
import os

def main():
    runtime_mode = os.getenv("MC_RUNTIME_MODE", "host")

    if runtime_mode == "container":
        # Container mode - limited commands, no container orchestration
        from mc.cli.commands.agent import agent_main
        agent_main()
    else:
        # Host mode - full CLI including container orchestration
        from mc.cli.commands.host import host_main
        host_main()
```

**Why shared codebase:**
- Reuse all existing v1.0 code (auth, API clients, workspace manager)
- Single version number, single deployment
- Container inherits all bug fixes and features automatically
- Simpler testing (one codebase, two modes)

**Why not separate binaries:**
- Code duplication for shared logic (auth, API, workspace)
- Version skew between host and container
- More complex release process

### MC v2.0 Component Separation

```
src/mc/
├── cli/
│   ├── main.py              # Entry point with mode detection
│   ├── commands/
│   │   ├── host.py          # Host-mode commands (NEW)
│   │   ├── agent.py         # Container-mode commands (NEW)
│   │   ├── case.py          # Existing commands (MODIFY for container awareness)
│   │   └── other.py         # Existing utility commands (KEEP)
├── controller/
│   ├── workspace.py         # Existing workspace manager (KEEP)
│   ├── container.py         # Container lifecycle manager (NEW)
│   └── state.py             # State persistence manager (NEW)
├── integrations/
│   ├── redhat_api.py        # Existing API client (KEEP)
│   ├── ldap.py              # Existing LDAP (KEEP)
│   ├── salesforce.py        # Salesforce API client (NEW)
│   ├── podman.py            # Podman API wrapper (NEW)
│   └── terminal.py          # Terminal launcher (NEW)
├── config/
│   ├── manager.py           # Existing config (EXTEND for Salesforce)
│   └── models.py            # Existing models (EXTEND)
└── [existing utils, etc.]
```

### New vs Modified Components

**NEW Components:**

1. **Container Manager** (`src/mc/controller/container.py`)
   - Create containers with case workspace mounts
   - List running containers
   - Stop/remove containers
   - Execute commands in containers

2. **State Manager** (`src/mc/controller/state.py`)
   - SQLite database for container metadata
   - Case → Container ID mapping
   - Container creation timestamps
   - Mount point tracking

3. **Salesforce Integration** (`src/mc/integrations/salesforce.py`)
   - Fetch case metadata (subject, owner, status)
   - Cache responses (30-minute TTL like existing cache)
   - Handle authentication (OAuth or session ID)

4. **Podman Integration** (`src/mc/integrations/podman.py`)
   - Wrapper around podman-py library
   - Handle connection (rootless vs rootful)
   - Image management (pull, build, tag, push)
   - Container operations with proper error handling

5. **Terminal Launcher** (`src/mc/integrations/terminal.py`)
   - Platform detection (macOS, Linux)
   - iTerm2 integration (macOS)
   - GNOME Terminal integration (Linux)
   - Fallback to xterm/default terminal
   - Execute `podman exec -it <container> /bin/bash`

**MODIFIED Components:**

1. **CLI Commands** (`src/mc/cli/commands/case.py`)
   - Add `--container` flag to existing commands
   - When in container, auto-detect and skip container creation
   - Existing commands work unchanged in non-container mode

2. **Config Manager** (`src/mc/config/manager.py`)
   - Add Salesforce credentials (username, password, security token)
   - Add container image configuration (registry, tag)
   - Add terminal emulator preference

3. **Workspace Manager** (`src/mc/controller/workspace.py`)
   - Add method to get container mount points
   - Support container-aware path resolution

**UNCHANGED Components:**
- All utils (auth, cache, downloads, file_ops, formatters, logging, validation)
- All existing integrations (redhat_api, ldap)
- Test infrastructure
- Exception hierarchy

## Architectural Patterns

### Pattern 1: State Persistence with SQLite

**What:** Use SQLite database to track container state and metadata

**When to use:** When you need queryable persistent state for container orchestration

**Trade-offs:**
- ✅ Lightweight, no separate database process
- ✅ ACID transactions for consistency
- ✅ Industry standard (Podman uses SQLite as of v4.8+)
- ❌ Single-writer limitation (not a problem for CLI use)

**Example:**
```python
# src/mc/controller/state.py
import sqlite3
from pathlib import Path
from typing import Optional

class StateManager:
    """Manages container state persistence."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS containers (
                case_number TEXT PRIMARY KEY,
                container_id TEXT NOT NULL,
                container_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    def register_container(self, case_number: str, container_id: str,
                          container_name: str, workspace_path: str):
        """Register a new container."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO containers
            (case_number, container_id, container_name, created_at, workspace_path, status)
            VALUES (?, ?, ?, datetime('now'), ?, 'running')
        """, (case_number, container_id, container_name, workspace_path))
        conn.commit()
        conn.close()

    def get_container(self, case_number: str) -> Optional[dict]:
        """Get container by case number."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM containers WHERE case_number = ?",
            (case_number,)
        )
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
```

### Pattern 2: Podman API Abstraction

**What:** Wrap podman-py library with domain-specific interface

**When to use:** When integrating with container runtime, isolate external dependency

**Trade-offs:**
- ✅ Easier to test (mock the wrapper, not podman-py)
- ✅ Cleaner error handling (convert podman exceptions to MC exceptions)
- ✅ Future flexibility (could swap Docker for Podman)
- ❌ Additional layer of abstraction

**Example:**
```python
# src/mc/integrations/podman.py
import logging
from typing import Optional
import podman

from mc.exceptions import ContainerError

logger = logging.getLogger(__name__)

class PodmanClient:
    """Wrapper for Podman operations."""

    def __init__(self):
        try:
            self.client = podman.PodmanClient()
        except Exception as e:
            raise ContainerError(
                "Failed to connect to Podman",
                f"Ensure Podman is installed and running: {e}"
            )

    def create_container(self, image: str, name: str,
                        volumes: dict[str, dict], **kwargs) -> str:
        """Create a container and return its ID."""
        try:
            container = self.client.containers.create(
                image=image,
                name=name,
                volumes=volumes,
                detach=True,
                tty=True,
                stdin_open=True,
                **kwargs
            )
            container.start()
            logger.info("Created container: %s (%s)", name, container.id[:12])
            return container.id
        except podman.errors.ImageNotFound:
            raise ContainerError(
                f"Container image not found: {image}",
                "Try: podman pull <image>"
            )
        except Exception as e:
            raise ContainerError(f"Failed to create container: {e}")

    def list_containers(self, all_containers: bool = False) -> list[dict]:
        """List containers."""
        try:
            containers = self.client.containers.list(all=all_containers)
            return [
                {
                    "id": c.id[:12],
                    "name": c.name,
                    "status": c.status,
                    "image": c.image.tags[0] if c.image.tags else c.image.id[:12]
                }
                for c in containers
            ]
        except Exception as e:
            raise ContainerError(f"Failed to list containers: {e}")
```

### Pattern 3: Salesforce API Caching

**What:** Cache Salesforce API responses with TTL, following existing cache pattern

**When to use:** External API with rate limits (same pattern as existing Red Hat API cache)

**Trade-offs:**
- ✅ Avoids rate limits (Salesforce: 100,000 daily API calls for Enterprise)
- ✅ Faster response time for repeated queries
- ✅ Consistent with existing MC cache strategy
- ❌ Stale data within TTL window (acceptable for case metadata)

**Example:**
```python
# src/mc/integrations/salesforce.py
import logging
from mc.utils.cache import FileCache

logger = logging.getLogger(__name__)

class SalesforceClient:
    """Salesforce API client with caching."""

    def __init__(self, cache_dir: Path, cache_ttl: int = 1800):
        self.cache = FileCache(cache_dir / "salesforce", ttl=cache_ttl)
        # Initialize Salesforce connection (simple_salesforce or requests)

    def get_case_metadata(self, case_number: str) -> dict:
        """Get case metadata with caching."""
        cache_key = f"case_{case_number}"

        # Try cache first
        cached = self.cache.get(cache_key)
        if cached:
            logger.debug("Using cached Salesforce data for case %s", case_number)
            return cached

        # Fetch from API
        logger.info("Fetching Salesforce metadata for case %s", case_number)
        try:
            # Query Salesforce API
            metadata = self._query_salesforce(case_number)

            # Cache the response
            self.cache.set(cache_key, metadata)
            return metadata
        except Exception as e:
            logger.error("Salesforce API error: %s", e)
            raise
```

### Pattern 4: Terminal Launcher Abstraction

**What:** Platform-specific terminal launching with fallback chain

**When to use:** Cross-platform CLI that needs to open new terminal windows

**Trade-offs:**
- ✅ Best experience on each platform (iTerm2 on macOS, GNOME Terminal on Linux)
- ✅ Graceful degradation to fallback terminals
- ✅ User-configurable preference
- ❌ Platform-specific code branches

**Example:**
```python
# src/mc/integrations/terminal.py
import platform
import subprocess
import shlex
from pathlib import Path
from mc.exceptions import TerminalError

class TerminalLauncher:
    """Cross-platform terminal launcher."""

    def __init__(self, preferred: str | None = None):
        self.platform = platform.system()
        self.preferred = preferred

    def launch(self, container_id: str, title: str):
        """Launch new terminal with container exec."""
        cmd = f"podman exec -it {container_id} /bin/bash"

        if self.platform == "Darwin":  # macOS
            self._launch_macos(cmd, title)
        elif self.platform == "Linux":
            self._launch_linux(cmd, title)
        else:
            raise TerminalError(f"Unsupported platform: {self.platform}")

    def _launch_macos(self, cmd: str, title: str):
        """Launch terminal on macOS."""
        # Try iTerm2 first (if preferred or detected)
        if self._has_iterm2():
            script = f'''
                tell application "iTerm"
                    create window with default profile
                    tell current session of current window
                        write text "{cmd}"
                        set name to "{title}"
                    end tell
                end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)
        else:
            # Fallback to Terminal.app
            script = f'''
                tell application "Terminal"
                    do script "{cmd}"
                    set custom title of front window to "{title}"
                end tell
            '''
            subprocess.run(["osascript", "-e", script], check=True)

    def _launch_linux(self, cmd: str, title: str):
        """Launch terminal on Linux."""
        # Try preferred terminal or detect available
        terminals = [
            ("gnome-terminal", ["gnome-terminal", "--", "bash", "-c", cmd]),
            ("konsole", ["konsole", "-e", cmd]),
            ("xterm", ["xterm", "-e", cmd])
        ]

        for term_name, term_cmd in terminals:
            if self._has_command(term_name):
                subprocess.Popen(term_cmd)
                return

        raise TerminalError("No supported terminal emulator found")

    def _has_iterm2(self) -> bool:
        """Check if iTerm2 is installed."""
        return Path("/Applications/iTerm.app").exists()

    def _has_command(self, cmd: str) -> bool:
        """Check if command exists in PATH."""
        return subprocess.run(
            ["which", cmd],
            capture_output=True
        ).returncode == 0
```

### Pattern 5: Runtime Mode Detection

**What:** Single codebase with host/container mode detection via environment variable

**When to use:** When host and container need different command sets but share core logic

**Trade-offs:**
- ✅ No code duplication
- ✅ Automatic feature parity
- ✅ Simpler deployment (one binary)
- ❌ Slightly more complex CLI routing

**Example:**
```python
# src/mc/cli/main.py
import os
import sys

def detect_runtime_mode() -> str:
    """Detect if running in host or container mode."""
    # Check environment variable (set in container image)
    if os.getenv("MC_RUNTIME_MODE") == "container":
        return "container"

    # Check if running inside container (multiple heuristics)
    if Path("/.dockerenv").exists() or Path("/run/.containerenv").exists():
        return "container"

    return "host"

def main():
    mode = detect_runtime_mode()

    if mode == "container":
        # Container mode - no container orchestration commands
        from mc.cli.commands.agent import build_agent_parser
        parser = build_agent_parser()
    else:
        # Host mode - full command set
        from mc.cli.commands.host import build_host_parser
        parser = build_host_parser()

    args = parser.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()
```

## Data Flow

### Container Creation Flow

```
User: mc create 12345678 --container
    ↓
CLI Parser (src/mc/cli/commands/host.py)
    ↓
Container Manager (src/mc/controller/container.py)
    ├─→ Check State Manager: Does container exist for case 12345678?
    │   └─→ Yes: Return existing container ID, skip creation
    │   └─→ No: Continue to creation
    ├─→ Salesforce Client: Fetch case metadata (subject, owner)
    │   └─→ Cache response (30 min TTL)
    ├─→ Red Hat API Client: Fetch case details (reuse v1.0 code)
    ├─→ Workspace Manager: Ensure workspace exists
    │   └─→ Create if needed (reuse v1.0 code)
    ├─→ Podman Client: Create container
    │   ├─→ Image: mc:latest (from local or pull from registry)
    │   ├─→ Name: mc-case-12345678
    │   ├─→ Mounts:
    │   │   - /home/user/cases/Account/12345678-Summary:/case (workspace)
    │   │   - /home/user/.config/mc:/root/.config/mc:ro (config)
    │   ├─→ Start container
    │   └─→ Return container ID
    ├─→ State Manager: Register container
    │   └─→ SQLite: INSERT (case_number, container_id, workspace_path, timestamp)
    └─→ Terminal Launcher: Open new terminal window
        └─→ Execute: podman exec -it mc-case-12345678 /bin/bash
```

### State Management Flow

```
State Manager (SQLite Database)
    ↓
┌─────────────────────────────────────────────┐
│ containers table                            │
├─────────────────────────────────────────────┤
│ case_number  | container_id  | created_at  │
│ workspace    | status        |             │
├─────────────────────────────────────────────┤
│ 12345678     | abc123def456  | 2026-01-26  │
│ /home/.../ws | running       | 10:30:00    │
└─────────────────────────────────────────────┘
    ↑
    │ (queries)
    │
Container Manager
    ├─→ register_container(case, id, workspace)
    ├─→ get_container(case_number) → container_id
    ├─→ list_containers() → [{case, id, status}, ...]
    └─→ remove_container(case_number)
```

### Key Data Flows

1. **Container creation:** CLI → Container Manager → Podman API → State Manager → Terminal Launcher
2. **Case workspace access:** CLI → State Manager (lookup) → Container Manager (exec) → Terminal Launcher
3. **Salesforce metadata:** Container Manager → Salesforce Client → Cache → API
4. **Container listing:** CLI → State Manager → Podman Client (validate) → Display

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Podman | Python library (podman-py) | RESTful API over Unix socket, rootless preferred |
| Salesforce | REST API with simple_salesforce or requests | OAuth or username/password/token auth, rate limits apply |
| Red Hat API | Existing integration (keep unchanged) | OAuth with offline token |
| LDAP | Existing integration (keep unchanged) | Subprocess call to ldapsearch |
| Terminal Emulator | Subprocess with platform detection | osascript (macOS), direct exec (Linux) |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI ↔ Container Manager | Direct function calls | Container Manager is domain controller |
| Container Manager ↔ State Manager | Direct function calls (SQLite queries) | State Manager owns DB connection |
| Container Manager ↔ Podman Client | Direct function calls (wrapper API) | Podman Client converts exceptions |
| Container Manager ↔ Salesforce Client | Direct function calls (cached) | Salesforce Client handles caching transparently |
| Host Mode ↔ Agent Mode | Environment variable detection | No direct communication, mode determined at startup |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 cases | Current design works perfectly, SQLite handles <1000 containers easily |
| 10-100 cases | No changes needed, consider container cleanup policy (auto-remove stopped containers after 7 days) |
| 100+ cases | Consider container pruning automation, disk space monitoring for workspace mounts |

### Scaling Priorities

1. **First bottleneck:** Disk space for container images and workspaces
   - **Fix:** Implement `mc prune` command to remove stopped containers and unused images
   - **Detection:** Monitor disk usage, warn when <10GB free

2. **Second bottleneck:** SQLite database size (unlikely for <10,000 containers)
   - **Fix:** Add cleanup task to archive old container records
   - **Detection:** Database file size >100MB

3. **Not a bottleneck:** Podman performance, Salesforce API rate limits, terminal launching

## Anti-Patterns

### Anti-Pattern 1: Running Podman Inside Container

**What people do:** Try to run `podman` commands from inside the MC container (nested containers)

**Why it's wrong:**
- Requires privileged container or complex socket mounting
- Security risk (container escape potential)
- Unnecessary complexity (host should manage containers)

**Do this instead:**
- Host CLI manages all container lifecycle
- Container CLI only runs case-management commands (no container orchestration)
- Use runtime mode detection to prevent container commands in container mode

### Anti-Pattern 2: Using Container ID as Primary Key

**What people do:** Store only container ID in state, query Podman API for case number

**Why it's wrong:**
- Container might be removed outside MC (manual `podman rm`)
- Requires API call for every state lookup (slow)
- Loses metadata when container is gone

**Do this instead:**
- Use case number as primary key in state database
- Store container ID as attribute
- Validate container still exists when accessed
- Gracefully handle missing containers (offer to recreate)

### Anti-Pattern 3: Building Container Image on Every Create

**What people do:** Run `podman build` when creating each case container

**Why it's wrong:**
- Extremely slow (image build takes minutes)
- Defeats purpose of container caching
- Wastes disk space with multiple identical images

**Do this instead:**
- Build image once, tag as `mc:latest`
- Reuse same image for all case containers
- Provide separate `mc build-image` command for updates
- Use `podman pull` to get updates from registry

### Anti-Pattern 4: Storing Credentials in Container

**What people do:** Copy credentials into container filesystem

**Why it's wrong:**
- Security risk (credentials persist in image layers)
- Credentials become stale (offline token expires)
- Need to rebuild container when credentials change

**Do this instead:**
- Mount config directory read-only into container
- Container reads credentials from mount point
- Credentials managed on host, automatically available in container
- Single source of truth for configuration

### Anti-Pattern 5: Using BoltDB for State

**What people do:** Choose BoltDB because Podman historically used it

**Why it's wrong:**
- Podman deprecated BoltDB in v4.8, removing in v6.0 (mid-2026)
- SQLite is now industry standard for container state
- BoltDB is archived, no active development
- Migration path is painful

**Do this instead:**
- Use SQLite from the start (matches Podman v4.8+)
- Simple schema with standard SQL
- Excellent Python support (sqlite3 in stdlib)
- Well-tested, actively maintained

## Project Structure

Based on patterns from kind, devcontainer CLI, and Podman architecture:

```
src/mc/
├── cli/
│   ├── main.py              # Mode detection, entry point
│   ├── commands/
│   │   ├── host.py          # Host-mode CLI (container create/list/stop/exec)
│   │   ├── agent.py         # Container-mode CLI (limited commands)
│   │   ├── case.py          # Existing case commands (MODIFY for container awareness)
│   │   └── other.py         # Existing utility commands (KEEP)
├── controller/
│   ├── workspace.py         # Existing (EXTEND for container mounts)
│   ├── container.py         # NEW: Container lifecycle orchestration
│   └── state.py             # NEW: SQLite state management
├── integrations/
│   ├── redhat_api.py        # Existing (KEEP)
│   ├── ldap.py              # Existing (KEEP)
│   ├── salesforce.py        # NEW: Salesforce API with caching
│   ├── podman.py            # NEW: Podman API wrapper
│   └── terminal.py          # NEW: Cross-platform terminal launcher
├── config/
│   ├── manager.py           # Existing (EXTEND for Salesforce, container config)
│   └── models.py            # Existing (EXTEND)
├── utils/                   # All existing utils (KEEP UNCHANGED)
│   ├── auth.py
│   ├── cache.py
│   ├── downloads.py
│   ├── file_ops.py
│   ├── formatters.py
│   ├── logging.py
│   └── validation.py
└── exceptions.py            # Existing (EXTEND for container errors)

container/
├── Containerfile            # Image definition (RHEL 10, mc, oc, ocm, backplane)
├── build.sh                 # Image build script
└── entrypoint.sh            # Container entrypoint (sets MC_RUNTIME_MODE=container)

tests/
├── unit/
│   ├── test_container_manager.py    # NEW
│   ├── test_state_manager.py        # NEW
│   ├── test_podman_client.py        # NEW
│   ├── test_salesforce_client.py    # NEW
│   └── test_terminal_launcher.py    # NEW
└── integration/
    ├── test_container_lifecycle.py  # NEW (uses testcontainers)
    └── test_end_to_end.py           # NEW
```

### Structure Rationale

- **cli/commands/host.py vs agent.py:** Separate command sets by runtime mode, clear separation
- **controller/container.py:** Central orchestrator for container operations, follows existing controller pattern
- **controller/state.py:** Isolated state management, easy to test, single responsibility
- **integrations/[service].py:** One integration per file, follows existing pattern
- **Shared utils:** All existing utils work in both modes, no duplication
- **Container directory:** Separate from source, clear boundary for image build artifacts

## Testing Strategy

### Unit Testing with Mocking

Following existing pytest patterns from v1.0:

```python
# tests/unit/test_container_manager.py
import pytest
from unittest.mock import Mock, patch
from mc.controller.container import ContainerManager

@pytest.fixture
def mock_podman_client():
    """Mock Podman client."""
    with patch("mc.controller.container.PodmanClient") as mock:
        yield mock.return_value

@pytest.fixture
def mock_state_manager():
    """Mock state manager."""
    with patch("mc.controller.container.StateManager") as mock:
        yield mock.return_value

def test_create_container_new_case(mock_podman_client, mock_state_manager):
    """Test creating container for new case."""
    # Setup
    mock_state_manager.get_container.return_value = None
    mock_podman_client.create_container.return_value = "abc123"

    manager = ContainerManager(
        podman_client=mock_podman_client,
        state_manager=mock_state_manager
    )

    # Execute
    container_id = manager.create_container(
        case_number="12345678",
        workspace_path="/path/to/workspace"
    )

    # Verify
    assert container_id == "abc123"
    mock_podman_client.create_container.assert_called_once()
    mock_state_manager.register_container.assert_called_once()
```

### Integration Testing with Testcontainers

For end-to-end testing with real Podman:

```python
# tests/integration/test_container_lifecycle.py
import pytest
from testcontainers.core.container import DockerContainer

@pytest.fixture(scope="module")
def podman_service():
    """Start Podman service in container for testing."""
    # Use testcontainers to run Podman-in-Docker for testing
    # This ensures tests don't pollute local Podman state
    pass

def test_full_container_lifecycle(tmp_path, podman_service):
    """Test complete container lifecycle: create, exec, stop, remove."""
    # Real integration test with actual Podman calls
    pass
```

## Build Order (Dependency-Driven)

Based on component dependencies and risk:

### Phase 1: State Management Foundation
**Why first:** No external dependencies, easy to test, foundational

1. State Manager (SQLite database)
2. Unit tests for State Manager
3. Manual testing with sqlite3 CLI

### Phase 2: Podman Integration
**Why second:** Core functionality, needed for everything else

1. Podman Client wrapper (podman-py)
2. Unit tests with mocked podman-py
3. Integration tests with real Podman (testcontainers)

### Phase 3: Container Orchestration
**Why third:** Combines State + Podman, core business logic

1. Container Manager (create, list, stop, exec)
2. Unit tests with mocked dependencies
3. Integration tests with real containers

### Phase 4: Salesforce Integration
**Why fourth:** Independent feature, can be added without blocking others

1. Salesforce Client (with caching)
2. Unit tests with mocked requests
3. Integration tests with Salesforce sandbox (optional)

### Phase 5: Terminal Launcher
**Why fifth:** Presentation layer, depends on Container Manager

1. Terminal Launcher (platform-specific)
2. Unit tests with mocked subprocess
3. Manual testing on macOS and Linux

### Phase 6: CLI Integration
**Why sixth:** Ties everything together, user-facing

1. Host mode CLI commands (create, list, stop, exec)
2. Runtime mode detection
3. Update existing commands for container awareness
4. End-to-end tests

### Phase 7: Container Image
**Why seventh:** Depends on working host CLI to test

1. Containerfile (RHEL 10 base + tools)
2. Build script
3. Agent mode CLI commands
4. Container entrypoint
5. Build and test image

### Phase 8: Polish & Documentation
**Why last:** Refinement after core functionality works

1. Config wizard updates (Salesforce credentials)
2. Error messages and help text
3. Documentation updates
4. Performance tuning

## Backwards Compatibility Strategy

**Critical:** All existing v1.0 commands must work exactly as before.

### Compatibility Guarantees

1. **Existing commands unchanged:** `mc create`, `mc attach`, `mc check`, `mc ls`, `mc go` work identically
2. **No required config changes:** Containerization is opt-in via `--container` flag
3. **Workspace structure unchanged:** Files and directories remain the same
4. **Config file compatible:** Existing ~/.config/mc/config.toml works unchanged

### Migration Path

```
User journey:

v1.0 User (no containers):
  mc create 12345678              # Works exactly as before
  mc attach 12345678              # Works exactly as before

v2.0 User (with containers):
  mc create 12345678 --container  # New: Creates container + workspace
  mc attach 12345678              # Auto-detects container, works in container
  mc exec 12345678                # New: Opens terminal in existing container
  mc list                         # New: Shows running containers
```

### Feature Flags

Consider environment variable for gradual rollout:

```bash
# Disable containerization entirely (v1.0 behavior)
export MC_DISABLE_CONTAINERS=1

# Enable containerization (v2.0 behavior)
export MC_ENABLE_CONTAINERS=1  # or unset MC_DISABLE_CONTAINERS
```

## Sources

**Container orchestrator architectures:**
- [kind - Kubernetes IN Docker](https://kind.sigs.k8s.io/)
- [kind Initial Design](https://kind.sigs.k8s.io/docs/design/initial/)
- [DevPod Architecture](https://devpod.sh/docs/how-it-works/overview)
- [Dev Container CLI](https://code.visualstudio.com/docs/devcontainers/devcontainer-cli)

**Podman architecture and state management:**
- [Podman GitHub](https://github.com/containers/podman)
- [Podman Python Library](https://github.com/containers/podman-py)
- [Container Lifecycle Management - Podman](https://deepwiki.com/containers/podman/3.2-container-lifecycle-management)
- [Deep Dive: Why Podman and containerd 2.0 are Replacing Docker in 2026](https://dev.to/dataformathub/deep-dive-why-podman-and-containerd-20-are-replacing-docker-in-2026-32ak)
- [Podman 5.7 & BoltDB to SQLite migration](https://discussion.fedoraproject.org/t/podman-5-7-boltdb-to-sqlite-migration/171172)

**Terminal integration:**
- [Docker Desktop Support for iTerm2](https://www.docker.com/blog/desktop-support-for-iterm2-a-feature-request-from-the-docker-public-roadmap/)
- [iTerm2 Shell Integration](https://iterm2.com/shell_integration.html)
- [Best Linux Terminal Emulators: 2026 Comparison](https://www.glukhov.org/post/2026/01/terminal-emulators-for-linux-comparison/)

**Salesforce API:**
- [Salesforce API Rate Limiting Best Practices](https://developer.salesforce.com/docs/marketing/marketing-cloud/guide/rate-limiting-best-practices.html)
- [Salesforce API Rate Limits](https://coefficient.io/salesforce-api/salesforce-api-rate-limits)

**Container testing:**
- [Testcontainers Python](https://github.com/testcontainers/testcontainers-python)
- [Getting Started with Testcontainers for Python](https://testcontainers.com/guides/getting-started-with-testcontainers-for-python/)

**Container image workflows:**
- [How to Automate Docker Image Building with Pack CLI](https://www.freecodecamp.org/news/automating-docker-image-builds-and-publishing-with-pack-cli/)
- [devcontainers CLI](https://github.com/devcontainers/cli)

---
*Architecture research for: MC v2.0 Container Orchestration*
*Researched: 2026-01-26*
