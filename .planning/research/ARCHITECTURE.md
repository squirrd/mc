# Architecture Research: Window Tracking Integration

**Domain:** Terminal automation with persistent window registry
**Researched:** 2026-02-04
**Confidence:** HIGH

## Problem Context

The existing terminal automation system needs window tracking to prevent duplicate terminal windows. Currently, `mc case 12345678` creates a new terminal window every time it's run, even if one already exists for that case. The root cause is an iTerm2 AppleScript limitation: session names get overwritten when commands execute, making title-based searching unreliable.

**Key constraint:** Must integrate with existing architecture without breaking current functionality.

## Current Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   CLI Entry Point (mc case)                  │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────┐    ┌──────────────────┐                 │
│  │ attach.py      │───▶│ launcher.py      │                 │
│  │ Orchestration  │    │ Platform detect  │                 │
│  └────────┬───────┘    └────────┬─────────┘                 │
│           │                     │                            │
│           │          ┌──────────┴──────────┐                 │
│           │          │                     │                 │
│           │    ┌─────▼──────┐      ┌──────▼──────┐          │
│           │    │ macos.py   │      │ linux.py    │          │
│           │    │ iTerm2/    │      │ gnome-      │          │
│           │    │ Terminal   │      │ terminal    │          │
│           │    └────────────┘      └─────────────┘          │
│           │                                                  │
├───────────┴──────────────────────────────────────────────────┤
│                   Container Management                        │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐    ┌──────────────────┐                 │
│  │ manager.py     │───▶│ state.py         │                 │
│  │ Lifecycle ops  │    │ StateDatabase    │                 │
│  └────────────────┘    └──────────────────┘                 │
│                                                               │
├─────────────────────────────────────────────────────────────┤
│                      Persistence Layer                        │
│  ┌──────────────────────────────────────────────────────┐    │
│  │   SQLite Database (containers.db)                    │    │
│  │   - container metadata                                │    │
│  │   - workspace paths                                   │    │
│  │   - reconciliation with Podman                        │    │
│  └──────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Current Implementation |
|-----------|----------------|------------------------|
| `attach.py` | Orchestration workflow for terminal attachment | Python module with `attach_terminal()` function |
| `launcher.py` | Platform detection and launcher selection | Protocol-based interface with `get_launcher()` factory |
| `macos.py` | macOS terminal launching (iTerm2, Terminal.app) | AppleScript execution via `osascript` subprocess |
| `linux.py` | Linux terminal launching (gnome-terminal, etc.) | Direct subprocess execution with CLI flags |
| `manager.py` | Container lifecycle (create, start, stop, delete) | `ContainerManager` class with Podman client |
| `state.py` | SQLite-based state persistence | `StateDatabase` class with WAL mode, connection pooling |

## Existing State Management Pattern

### StateDatabase Architecture

**Location:** `src/mc/container/state.py`

**Key characteristics:**
- SQLite with WAL (Write-Ahead Logging) mode for concurrency
- Context manager pattern for connection lifecycle
- Reconciliation pattern to detect external changes
- Platform-aware database location (platformdirs)

**Schema:**
```sql
CREATE TABLE containers (
    case_number TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
)
CREATE INDEX idx_container_id ON containers(container_id)
CREATE INDEX idx_created_at ON containers(created_at)
```

**Connection Management:**
```python
@contextmanager
def _connection(self) -> Iterator[sqlite3.Connection]:
    # Special handling for :memory: databases (persistent connection)
    # File-based databases: new connection per operation
    # Auto-commit on success, rollback on exception
```

**Reconciliation Pattern:**
```python
def reconcile(self, podman_container_ids: set[str]) -> None:
    """Compare state database with Podman reality.

    Delete state entries for containers that no longer exist in Podman.
    Called before operations to ensure consistency.
    """
```

**Usage pattern in ContainerManager:**
```python
def create(self, case_number, workspace_path, customer_name):
    # 1. Reconcile state with Podman
    self._reconcile()

    # 2. Check state database for existing container
    existing = self.state.get_container(case_number)

    # 3. Create/start container
    container = self.podman.client.containers.create(...)

    # 4. Record in state database
    self.state.add_container(case_number, container.id, workspace_path)
```

## Recommended Window Registry Architecture

### Integration Strategy: Extend StateDatabase

**Recommendation:** Add window tracking table to existing StateDatabase rather than creating separate registry.

**Rationale:**
1. **Consistency:** Same database location, connection management, WAL mode
2. **Simplicity:** No additional file to manage or coordinate
3. **Atomicity:** Can update container + window state in single transaction
4. **Reuse patterns:** Reconciliation, cleanup, connection pooling already implemented
5. **Platform-aware:** Inherits platformdirs configuration (macOS: `~/Library/Application Support/mc/containers.db`, Linux: `~/.local/share/mc/containers.db`)

### Proposed Schema Extension

```sql
-- Add to existing database schema
CREATE TABLE IF NOT EXISTS window_registry (
    case_number TEXT PRIMARY KEY,
    window_id TEXT NOT NULL,
    tab_id TEXT,  -- Optional: for tab-specific tracking
    platform TEXT NOT NULL,  -- 'darwin' or 'linux'
    terminal TEXT NOT NULL,  -- 'iTerm2', 'Terminal.app', 'gnome-terminal', etc.
    created_at INTEGER NOT NULL,
    last_verified_at INTEGER NOT NULL,
    FOREIGN KEY (case_number) REFERENCES containers(case_number) ON DELETE CASCADE
)
CREATE INDEX IF NOT EXISTS idx_window_id ON window_registry(window_id)
CREATE INDEX IF NOT EXISTS idx_last_verified ON window_registry(last_verified_at)
```

**Schema rationale:**
- `window_id`: Platform-specific window identifier (AppleScript ID on macOS, X11 window ID on Linux)
- `tab_id`: Optional for multi-tab scenarios (iTerm2 can have multiple tabs per window)
- `platform` + `terminal`: Support cross-platform and multi-terminal scenarios
- `last_verified_at`: For cleanup of stale entries (windows closed externally)
- `FOREIGN KEY` + `ON DELETE CASCADE`: Automatically remove window registry when container deleted

### Component Integration Points

#### 1. StateDatabase Extension

**File:** `src/mc/container/state.py`

**New methods:**
```python
class StateDatabase:
    def _ensure_schema(self) -> None:
        """Extend to create window_registry table"""
        # Existing containers table creation
        # + New window_registry table creation

    def store_window(self, case_number: str, window_id: str,
                     platform: str, terminal: str, tab_id: str | None = None) -> None:
        """Store window ID for case."""

    def get_window(self, case_number: str) -> dict | None:
        """Retrieve window metadata by case number."""

    def remove_window(self, case_number: str) -> None:
        """Remove window registry entry."""

    def cleanup_stale_windows(self, active_window_ids: set[str]) -> None:
        """Reconciliation pattern for windows.

        Similar to reconcile() for containers, but for windows.
        Checks if windows still exist and removes stale entries.
        """
```

#### 2. MacOSLauncher Extension

**File:** `src/mc/terminal/macos.py`

**Integration point:** Capture window ID during creation

**Modified methods:**
```python
class MacOSLauncher:
    def __init__(self, terminal=None, state_db=None):
        self.terminal = terminal or self._detect_terminal()
        self.state_db = state_db  # NEW: inject StateDatabase

    def launch(self, options: LaunchOptions) -> str:
        """Launch terminal and return window ID.

        NEW: Returns window_id instead of None
        Stores window ID in state database if provided
        """
        # Build AppleScript
        script = self._build_iterm_script_with_id_capture(options)

        # Execute and capture output (window ID)
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10
        )
        window_id = result.stdout.strip()

        # Store in database if available
        if self.state_db:
            case_number = self._extract_case_number(options.title)
            self.state_db.store_window(
                case_number=case_number,
                window_id=window_id,
                platform="darwin",
                terminal=self.terminal,
                tab_id=None  # Could be extracted if needed
            )

        return window_id

    def _build_iterm_script_with_id_capture(self, options) -> str:
        """Modified to return window ID at end."""
        return f'''
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        set name to "{escaped_title}"
        delay 0.1
        write text "{escaped_command}"
    end tell
    -- Capture and return window ID
    return id of current window
end tell
'''

    def find_window_by_case(self, case_number: str) -> bool:
        """NEW: Registry-based window search.

        Replaces find_window_by_title() for reliable detection.
        """
        if not self.state_db:
            return False

        # Look up window from registry
        window_data = self.state_db.get_window(case_number)
        if not window_data:
            return False

        window_id = window_data['window_id']

        # Verify window still exists
        return self._window_exists_by_id(window_id)

    def _window_exists_by_id(self, window_id: str) -> bool:
        """Check if window ID exists in iTerm2."""
        script = f'''
tell application "iTerm"
    repeat with theWindow in windows
        if id of theWindow is "{window_id}" then
            return true
        end if
    end repeat
    return false
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() == "true"

    def focus_window_by_case(self, case_number: str) -> bool:
        """NEW: Registry-based window focus."""
        # Similar to find_window_by_case but with focus action
```

#### 3. LinuxLauncher Extension

**File:** `src/mc/terminal/linux.py`

**Challenge:** Linux window IDs require X11 integration

**Approach:**
```python
class LinuxLauncher:
    def __init__(self, terminal=None, state_db=None):
        self.terminal = terminal or self._detect_terminal()
        self.state_db = state_db

    def launch(self, options: LaunchOptions) -> str | None:
        """Launch terminal, attempt to capture window ID.

        Linux window ID capture is best-effort (requires wmctrl or xdotool).
        """
        # Launch terminal
        process = subprocess.Popen([self.terminal, ...])

        # Wait briefly for window to appear
        time.sleep(0.5)

        # Try to capture window ID using wmctrl
        window_id = self._find_window_id_by_title(options.title)

        # Store if available
        if window_id and self.state_db:
            case_number = self._extract_case_number(options.title)
            self.state_db.store_window(
                case_number=case_number,
                window_id=window_id,
                platform="linux",
                terminal=self.terminal
            )

        return window_id

    def _find_window_id_by_title(self, title: str) -> str | None:
        """Best-effort window ID discovery using wmctrl.

        Returns None if wmctrl not available or window not found.
        """
        if not shutil.which("wmctrl"):
            return None

        try:
            result = subprocess.run(
                ["wmctrl", "-l"],
                capture_output=True,
                text=True,
                timeout=2
            )
            # Parse wmctrl output: "0x0280001c  0 hostname Title Here"
            for line in result.stdout.splitlines():
                if title in line:
                    window_id = line.split()[0]
                    return window_id
        except Exception:
            pass

        return None
```

**Note:** Linux implementation is optional/best-effort. Primary focus is macOS where the problem is acute.

#### 4. attach_terminal Workflow Integration

**File:** `src/mc/terminal/attach.py`

**Modified workflow:**
```python
def attach_terminal(
    case_number: str,
    config_manager: ConfigManager,
    api_client: RedHatAPIClient,
    container_manager: ContainerManager,
) -> None:
    # ... existing setup (validate, fetch metadata, create container) ...

    # Get terminal launcher with state database
    launcher = get_launcher(state_db=container_manager.state)

    # NEW: Check for existing window using registry
    if launcher.find_window_by_case(case_number):
        logger.info("Found existing terminal for case %s, focusing window", case_number)
        if launcher.focus_window_by_case(case_number):
            print(f"Focused existing terminal for case {case_number}")
            return  # Early exit - no new window needed
        else:
            logger.warning("Failed to focus existing window, will launch new one")

    # Launch new terminal (stores window ID internally)
    launch_options = LaunchOptions(
        title=window_title,
        command=exec_command,
        auto_focus=True
    )
    window_id = launcher.launch(launch_options)
    logger.info("Terminal launched with window_id: %s", window_id)
```

**Key changes:**
1. Pass `state_db` to launcher initialization
2. Use `find_window_by_case()` instead of `find_window_by_title()`
3. Use `focus_window_by_case()` instead of `focus_window_by_title()`
4. Early exit when existing window found and focused
5. Window ID automatically stored by `launcher.launch()`

## Data Flow

### Create Flow (First Launch)

```
User runs: mc case 12345678
    ↓
attach_terminal()
    ↓
launcher.find_window_by_case("12345678")
    ↓
state_db.get_window("12345678")  → None (first time)
    ↓
launcher.launch(options)
    ↓
Execute AppleScript: create window + return ID
    ↓
window_id = "itterm2-window-1-12345"
    ↓
state_db.store_window("12345678", window_id, "darwin", "iTerm2")
    ↓
SQLite INSERT: window_registry table
    ↓
Return to user (terminal appears)
```

### Focus Flow (Subsequent Launch)

```
User runs: mc case 12345678 (again)
    ↓
attach_terminal()
    ↓
launcher.find_window_by_case("12345678")
    ↓
state_db.get_window("12345678")  → {window_id: "...", platform: "darwin"}
    ↓
launcher._window_exists_by_id(window_id)
    ↓
Execute AppleScript: check if window ID exists  → True
    ↓
launcher.focus_window_by_case("12345678")
    ↓
Execute AppleScript: select window by ID
    ↓
Print: "Focused existing terminal for case 12345678"
    ↓
Early return (no new window created)
```

### Cleanup Flow (Reconciliation)

```
Periodic or on-demand trigger
    ↓
launcher.cleanup_stale_windows()
    ↓
Get all window IDs from state_db
    ↓
For each window_id:
    ↓
    Check if window exists (AppleScript/wmctrl)
    ↓
    If NOT exists:
        ↓
        state_db.remove_window(case_number)
        ↓
        SQLite DELETE from window_registry
```

## Architectural Patterns

### Pattern 1: Reconciliation Pattern

**What:** Periodically compare state database with external reality (Podman, iTerm2) and remove orphaned entries.

**When to use:** Any persistent state that can be modified externally (user closes window, kills container).

**Trade-offs:**
- **Pro:** Prevents state drift, recovers from external changes
- **Pro:** Self-healing system
- **Con:** Requires periodic execution or trigger on operations
- **Con:** Potential race conditions if reconciliation runs during operations

**Example:**
```python
class StateDatabase:
    def reconcile_containers(self, podman_container_ids: set[str]) -> None:
        """Existing container reconciliation."""
        with self._connection() as conn:
            rows = conn.execute("SELECT case_number, container_id FROM containers").fetchall()
            for row in rows:
                if row["container_id"] not in podman_container_ids:
                    conn.execute("DELETE FROM containers WHERE case_number = ?", (row["case_number"],))

    def reconcile_windows(self, launcher) -> None:
        """NEW: Window reconciliation."""
        with self._connection() as conn:
            rows = conn.execute("SELECT case_number, window_id FROM window_registry").fetchall()
            for row in rows:
                if not launcher._window_exists_by_id(row["window_id"]):
                    conn.execute("DELETE FROM window_registry WHERE case_number = ?", (row["case_number"],))
```

### Pattern 2: Dependency Injection for State

**What:** Inject StateDatabase into launchers instead of creating new instances.

**When to use:** When multiple components need to share state management.

**Trade-offs:**
- **Pro:** Single source of truth, no database file conflicts
- **Pro:** Easier testing (inject mock database)
- **Pro:** Lifecycle managed by caller
- **Con:** More complex initialization
- **Con:** Tighter coupling between components

**Example:**
```python
# Before (independent)
launcher = MacOSLauncher()
launcher.launch(options)  # No state tracking

# After (injected)
state_db = StateDatabase()  # Shared instance
launcher = MacOSLauncher(state_db=state_db)
launcher.launch(options)  # Automatically stores window ID
```

### Pattern 3: Platform-Specific Registry with Fallback

**What:** Track windows when platform supports it, gracefully degrade when not.

**When to use:** Cross-platform features where capability varies.

**Trade-offs:**
- **Pro:** Best experience on supported platforms
- **Pro:** Doesn't break unsupported platforms
- **Con:** Feature parity issues
- **Con:** Testing complexity

**Example:**
```python
def find_window_by_case(self, case_number: str) -> bool:
    # Try registry-based search first
    if self.state_db:
        window_data = self.state_db.get_window(case_number)
        if window_data:
            return self._window_exists_by_id(window_data['window_id'])

    # Fallback to title-based search (unreliable but better than nothing)
    return self._find_window_by_title_legacy(case_number)
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-100 cases | Single SQLite database, no cleanup needed (manual close suffices) |
| 100-1000 cases | Add periodic reconciliation (cleanup stale windows weekly), consider index optimization |
| 1000+ cases | Partition window_registry by time (archive old entries), add TTL for auto-cleanup |

### Scaling Priorities

1. **First bottleneck:** Database lock contention if many parallel `mc case` invocations
   - **Fix:** WAL mode already enabled, handles concurrent reads + 1 writer
   - **Monitor:** If `database is locked` errors appear, increase timeout or add retry logic

2. **Second bottleneck:** Stale entry accumulation (windows closed manually, not cleaned up)
   - **Fix:** Periodic reconciliation job (cron or on-demand via `mc container reconcile`)
   - **Monitor:** `SELECT COUNT(*) FROM window_registry` vs expected active count

## Anti-Patterns

### Anti-Pattern 1: Separate Window Registry File

**What people do:** Create `window_registry.db` separate from `containers.db`

**Why it's wrong:**
- Requires coordinating two database files
- No transactional guarantees across files
- Can't use FOREIGN KEY to cascade deletes
- Duplicate connection management code
- Race conditions between databases

**Do this instead:** Extend existing `StateDatabase` with `window_registry` table

### Anti-Pattern 2: Storing Window Titles Instead of IDs

**What people do:** Store window title in registry, search by title

**Why it's wrong:**
- Defeats purpose: titles still get overwritten by iTerm2
- Original problem remains unsolved
- Adds complexity without benefit

**Do this instead:** Store immutable window IDs that persist regardless of title changes

### Anti-Pattern 3: Blocking Launch Waiting for Window ID

**What people do:**
```python
# Wait for window to appear before returning
launcher.launch(options)
time.sleep(5)  # Hope window appears
window_id = find_window_by_title(title)
```

**Why it's wrong:**
- Race conditions (window might not appear in 5s)
- Blocks CLI unnecessarily (bad UX)
- Fragile timing assumptions

**Do this instead:** Capture window ID synchronously from AppleScript return value

## Integration Points

### External Dependencies

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| iTerm2 | AppleScript via `osascript` subprocess | ID capture via script return value |
| Terminal.app | AppleScript via `osascript` subprocess | Same pattern as iTerm2 |
| gnome-terminal | Direct subprocess launch | Window ID via `wmctrl` (best-effort) |
| Podman | Python API via `podman-py` | Container reconciliation pattern |
| SQLite | Python `sqlite3` stdlib | WAL mode, contextmanager pattern |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| attach.py ↔ launcher.py | Function calls with LaunchOptions | Injected state_db dependency |
| launcher.py ↔ state.py | Direct method calls | store_window(), get_window(), reconcile_windows() |
| state.py ↔ SQLite | SQL via sqlite3 | Connection pooling, transaction management |
| attach.py ↔ manager.py | Shared state_db instance | Both use container_manager.state |

## Implementation Phases

### Phase 1: Database Schema Extension (1 hour)
- Add `window_registry` table to StateDatabase schema
- Add `store_window()`, `get_window()`, `remove_window()` methods
- Add unit tests for window registry CRUD operations
- **Success criteria:** Tests pass, backward compatible with existing containers table

### Phase 2: MacOSLauncher Window ID Capture (2 hours)
- Modify `_build_iterm_script()` to return window ID
- Update `launch()` to capture and store window ID
- Add `_window_exists_by_id()` helper
- **Success criteria:** Window ID captured and stored in database after launch

### Phase 3: Registry-Based Search and Focus (2 hours)
- Add `find_window_by_case()` method
- Add `focus_window_by_case()` method
- Update `attach_terminal()` to use registry-based search
- **Success criteria:** Second `mc case XXXXX` invocation focuses existing window

### Phase 4: Reconciliation and Cleanup (1 hour)
- Add `reconcile_windows()` to StateDatabase
- Trigger reconciliation in `attach_terminal()` or periodic job
- **Success criteria:** Manually closed windows are removed from registry

### Phase 5: Linux Support (Optional, 2 hours)
- Implement `_find_window_id_by_title()` using wmctrl
- Add Linux window ID capture to LinuxLauncher
- Fallback gracefully when wmctrl unavailable
- **Success criteria:** Linux duplicate prevention works when wmctrl installed

### Phase 6: Testing and Documentation (2 hours)
- Update `test_duplicate_terminal_prevention_regression` to verify fix
- Add integration tests for window registry
- Document window tracking architecture
- Update UAT 5.2 status
- **Success criteria:** All tests pass, documentation complete

## Migration Path

### Backward Compatibility

**Existing behavior:** Continues to work if `state_db` not injected into launcher.

**Upgrade path:**
1. Deploy schema changes (adds table, doesn't modify existing tables)
2. Update launcher initialization to inject `state_db`
3. Existing windows won't be tracked (first launch after upgrade creates entry)
4. Users see benefit immediately on next `mc case` invocation

**Rollback:** Remove `state_db` injection, system reverts to old behavior (duplicate windows tolerated).

## Sources

### Architecture Patterns
- [Kubernetes and Reconciliation Patterns](https://hkassaei.com/posts/kubernetes-and-reconciliation-patterns/) - Reconciliation loop pattern for state management
- [The Principle of Reconciliation](https://www.chainguard.dev/unchained/the-principle-of-reconciliation) - Declarative state and idempotency
- [Registry Pattern - GeeksforGeeks](https://www.geeksforgeeks.org/system-design/registry-pattern/) - Registry pattern for resource management
- [Python Registry Pattern](https://dev.to/dentedlogic/stop-writing-giant-if-else-chains-master-the-python-registry-pattern-ldm) - Python implementation patterns

### SQLite and State Management
- [SQLite Architecture](https://sqlite.org/arch.html) - Official SQLite architecture documentation
- [Offline-first frontend apps 2025: IndexedDB and SQLite](https://blog.logrocket.com/offline-first-frontend-apps-2025-indexeddb-sqlite/) - State management patterns
- [Appropriate Uses For SQLite](https://sqlite.org/whentouse.html) - When to use SQLite vs other databases

### System Design
- [AI System Design Patterns for 2026](https://zenvanriel.nl/ai-engineer-blog/ai-system-design-patterns-2026/) - Idempotency patterns for preventing duplicate operations
- [Manager Design Pattern](https://www.eventhelix.com/design-patterns/manager/) - Managing multiple entities of the same type

### Project Context
- `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md` - Original phase proposal for window tracking
- `.planning/INTEGRATION_TEST_FIX_REPORT.md` - Root cause analysis of iTerm2 AppleScript limitation
- `src/mc/container/state.py` - Existing StateDatabase implementation
- `src/mc/terminal/macos.py` - Current MacOSLauncher implementation

---
*Architecture research for: Window tracking integration for terminal automation*
*Researched: 2026-02-04*
