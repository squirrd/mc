# Architecture Research: Auto-Update Integration for MC CLI

**Domain:** CLI Tool Version Management and Auto-Update
**Researched:** 2026-02-11
**Confidence:** HIGH

## Standard Architecture for CLI Auto-Update Systems

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  main() → version_check_hook() → parse_args()       │    │
│  └────────────────┬───────────────────────────────────┘     │
│                   │ (non-blocking)                           │
├───────────────────┴──────────────────────────────────────────┤
│                  Version Check Layer                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │VersionChecker│  │ThrottleCache │  │UpdateBanner  │       │
│  │ - check_pypi │  │ - timestamp  │  │ - rich panel │       │
│  │ - compare    │  │ - hourly TTL │  │ - display    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
├─────────────────────────────────────────────────────────────┤
│                  Config Extension Layer                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  ConfigManager (existing)                            │    │
│  │  + pinned_mc_version (opt)                          │    │
│  │  + pinned_container_version (opt)                   │    │
│  │  + last_version_check (timestamp)                   │    │
│  │  + available_mc_version (cached)                    │    │
│  └─────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────┤
│                  Update Execution Layer                      │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  mc-update CLI (separate console_scripts entry)     │    │
│  │  - Survives mc updates                              │    │
│  │  - Calls: subprocess(['uv', 'tool', 'upgrade', ...])│    │
│  │  - Pre-flight checks (uv installed, pinned version) │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **VersionChecker** | Query PyPI API, compare versions | Requests to `pypi.org/pypi/{package}/json`, ETag caching |
| **ThrottleCache** | Timestamp tracking, hourly throttling | TOML datetime field, `timedelta` comparison |
| **UpdateBanner** | Display update notification | Rich Panel/Rule with version info and update command |
| **mc-update** | Execute update subprocess | console_scripts entry calling `uv tool upgrade mc` |

## Recommended Integration Points for MC CLI

### 1. CLI Entry Point Hook (main.py)

**Where:** `src/mc/cli/main.py:main()` - immediately after logging setup, before config load

**Pattern:**
```python
def main() -> ExitCode:
    # ... logging setup (lines 138-142)

    # Version check hook (NON-BLOCKING)
    check_and_notify_updates()  # NEW: <= 0.01s or skip

    # ... rest of main() continues (config load, command routing)
```

**Why here:**
- Runs on every `mc` invocation (any command)
- After logging setup (can log failures)
- Before command execution (user sees banner before output)
- Non-blocking (throttled, cached, fast-fail on network errors)

### 2. Config Schema Extension (config/models.py)

**Where:** `src/mc/config/models.py:get_default_config()`

**Pattern:**
```python
def get_default_config() -> dict[str, Any]:
    return {
        # ... existing fields ...
        "version_management": {
            "pinned_mc_version": "",  # optional: pin to specific version
            "pinned_container_version": "",  # optional: pin container tag
            "last_version_check": None,  # datetime or None
            "available_mc_version": "",  # cached latest version from PyPI
        }
    }
```

**Why here:**
- Extends existing config schema cleanly
- Nested under `version_management` namespace (clear separation)
- Compatible with existing ConfigManager (no breaking changes)
- TOML datetime support via tomllib (RFC 3339 format)

### 3. Update Banner Integration (terminal/banner.py or new utils/update_banner.py)

**Where:** New module `src/mc/utils/update_banner.py` (parallel to existing utils)

**Pattern:**
```python
from rich.console import Console
from rich.panel import Panel

def display_update_banner(current: str, available: str) -> None:
    """Display update notification using Rich formatting."""
    console = Console()
    message = (
        f"Update available: {current} → {available}\n"
        f"Run: mc-update"
    )
    console.print(Panel(message, style="yellow", title="Update Available"))
```

**Why here:**
- MC CLI already uses Rich library for terminal output
- Consistent with existing banner pattern (`terminal/banner.py`)
- Non-intrusive banner display (doesn't block workflow)

### 4. mc-update Entry Point (pyproject.toml)

**Where:** `pyproject.toml` console_scripts section

**Pattern:**
```toml
[project.scripts]
mc = "mc.cli.main:main"
mc-update = "mc.cli.update:main"  # NEW: separate entry point
```

**Why separate entry point:**
- Survives `uv tool upgrade mc` (re-installed with package)
- Clean separation of concerns (update logic isolated)
- Can be invoked independently (`mc-update` vs `mc --update`)

## Recommended Project Structure

```
src/mc/
├── cli/
│   ├── main.py              # MODIFY: add version check hook
│   ├── update.py            # NEW: mc-update CLI implementation
│   └── commands/            # EXISTING: no changes
├── config/
│   ├── manager.py           # EXISTING: no changes (backward compatible)
│   └── models.py            # MODIFY: extend default_config schema
├── utils/
│   ├── version_checker.py   # NEW: VersionChecker class (PyPI API)
│   └── update_banner.py     # NEW: Rich banner display
├── terminal/                # EXISTING: no changes
└── version.py               # EXISTING: no changes
```

### Structure Rationale

- **cli/update.py:** Isolates update execution logic; separate console_scripts entry survives package updates
- **utils/version_checker.py:** Reusable VersionChecker class; throttling, caching, PyPI API logic encapsulated
- **utils/update_banner.py:** Banner display isolated; follows existing Rich output patterns
- **config/models.py:** Minimal schema change; backward compatible (new fields optional)

## Architectural Patterns

### Pattern 1: Non-Blocking Version Check with Hourly Throttle

**What:** Check PyPI for latest version on every CLI invocation, but throttle to 1 check/hour using cached timestamp.

**When to use:** CLI tools that run frequently (multiple times per hour), need to notify about updates without slowing commands.

**Trade-offs:**
- **Pros:** No noticeable performance impact (<0.01s when throttled), users see updates promptly (within 1 hour)
- **Cons:** Network failures must be silently swallowed (can't block CLI on network errors)

**Example:**
```python
from datetime import datetime, timedelta, timezone
from mc.config.manager import ConfigManager

def should_check_version() -> bool:
    """Return True if >= 1 hour since last check."""
    config_mgr = ConfigManager()
    try:
        config = config_mgr.load()
        last_check = config.get("version_management", {}).get("last_version_check")

        if last_check is None:
            return True

        # TOML datetimes are parsed as datetime objects by tomllib
        now = datetime.now(timezone.utc)
        elapsed = now - last_check
        return elapsed >= timedelta(hours=1)
    except Exception:
        # Fail-safe: if config read fails, skip check (don't block CLI)
        return False

def update_last_check_timestamp() -> None:
    """Update last_version_check to current UTC time."""
    config_mgr = ConfigManager()
    config = config_mgr.load()
    config.setdefault("version_management", {})
    config["version_management"]["last_version_check"] = datetime.now(timezone.utc)
    config_mgr.save(config)
```

### Pattern 2: PyPI JSON API with ETag Caching

**What:** Query PyPI's JSON API for latest package version, use HTTP ETag caching to reduce bandwidth.

**When to use:** Hourly/daily version checks where caching improves performance and reduces PyPI load.

**Trade-offs:**
- **Pros:** Efficient (304 Not Modified when no new version), reliable (official PyPI API)
- **Cons:** Requires storing ETag in config, adds complexity

**Example:**
```python
import requests
from mc.version import get_version

def check_pypi_version(timeout: float = 2.0) -> str | None:
    """Check PyPI for latest mc-cli version.

    Returns:
        Latest version string, or None on error/timeout
    """
    try:
        # PyPI JSON API endpoint
        url = "https://pypi.org/pypi/mc-cli/json"
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()

        data = response.json()
        latest_version = data["info"]["version"]
        return latest_version
    except Exception:
        # Network error, timeout, or PyPI API change - fail silently
        return None

def needs_update() -> tuple[bool, str | None]:
    """Check if update is available.

    Returns:
        (needs_update, available_version)
    """
    current = get_version()
    latest = check_pypi_version()

    if latest is None:
        return (False, None)

    # Simple version comparison (assumes semver X.Y.Z format)
    return (latest != current, latest)
```

### Pattern 3: Pinned Version Support

**What:** Allow users to pin to specific version (opt-out of auto-update notifications).

**When to use:** Enterprise environments, CI/CD pipelines, users who need version stability.

**Trade-offs:**
- **Pros:** User control, no surprise updates, stable environments
- **Cons:** Users may not see security updates, requires config management

**Example:**
```python
def should_notify_update(available_version: str) -> bool:
    """Check if user should be notified about available version.

    Returns False if:
    - User has pinned to specific version
    - Available version matches pinned version
    """
    config_mgr = ConfigManager()
    try:
        config = config_mgr.load()
        pinned = config.get("version_management", {}).get("pinned_mc_version")

        if pinned:
            # User has pinned - only notify if available != pinned
            # (Allows "upgrade to X.Y.Z" notifications)
            return available_version != pinned

        # No pin - notify about any new version
        return True
    except Exception:
        # Fail-safe: if config fails, don't notify
        return False
```

## Data Flow

### Version Check Flow

```
[mc invocation]
    ↓
[main() entry point]
    ↓
[check_and_notify_updates()] ←──────────┐
    ↓                                    │
[should_check_version()?] ──NO─────────>│ (skip - throttled)
    ↓ YES                                │
[check_pypi_version()] ──FAIL──────────>│ (skip - network error)
    ↓ SUCCESS                            │
[needs_update()?] ──NO─────────────────>│ (skip - already latest)
    ↓ YES                                │
[should_notify_update()?] ──NO─────────>│ (skip - pinned version)
    ↓ YES                                │
[display_update_banner()]                │
    ↓                                    │
[update_last_check_timestamp()]          │
    ↓                                    │
[continue to command execution] <───────┘
```

### Update Execution Flow (mc-update)

```
[User runs: mc-update]
    ↓
[mc.cli.update:main()]
    ↓
[Pre-flight checks]
  - uv installed?
  - pinned version configured?
  - network accessible?
    ↓
[Display current → target version]
    ↓
[Confirm with user (Y/n)]
    ↓ YES
[subprocess.run(['uv', 'tool', 'upgrade', 'mc'])]
    ↓ or
[subprocess.run(['uv', 'tool', 'install', 'mc==X.Y.Z'])]  # if pinned
    ↓
[Verify new version installed]
    ↓
[Display success message]
```

### Config Read/Write Flow

```
[ConfigManager.load()]
    ↓
[tomllib.load(config.toml)] → {
    "version_management": {
        "last_version_check": datetime(2026, 2, 11, 14, 30, 0, tzinfo=UTC),
        "available_mc_version": "2.1.0",
        "pinned_mc_version": "",  # empty = no pin
    }
}
    ↓
[Application logic uses values]
    ↓
[ConfigManager.save()]
    ↓
[tomli_w.dump(config)] → TOML file with ISO 8601 timestamps
```

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1-10 users | Standard hourly throttle pattern, no changes needed |
| 10-100 users | Increase throttle to 4-6 hours (reduce PyPI load), ETag caching |
| 100+ users | Consider self-hosted update check server (caches PyPI responses) |

### Scaling Priorities

1. **First bottleneck:** PyPI rate limiting (if checking too frequently)
   - **Fix:** Increase throttle interval from 1 hour to 6 hours
   - **Fix:** Implement ETag caching (304 Not Modified responses)

2. **Second bottleneck:** Config file lock contention (high-frequency CLI usage)
   - **Fix:** In-memory cache of last check timestamp (process-local)
   - **Fix:** Only write to config on successful version check (not every invocation)

## Anti-Patterns

### Anti-Pattern 1: Blocking Version Check

**What people do:** Make synchronous HTTP request to PyPI on every CLI invocation without throttling or timeout.

**Why it's wrong:**
- Adds 100-500ms latency to every command
- CLI becomes unusable when network is slow/unavailable
- PyPI rate limiting can block legitimate package installs

**Do this instead:**
- Throttle checks to 1/hour minimum (configurable)
- Set aggressive timeout (2 seconds max)
- Fail silently on network errors (never block CLI execution)

### Anti-Pattern 2: In-Place Self-Update

**What people do:** CLI script downloads new version and replaces its own executable during runtime.

**Why it's wrong:**
- Brittle on Windows (can't replace running executable)
- Breaks digital signatures/permissions
- Leaves system in inconsistent state on failure
- Conflicts with package managers (uv, pip, system packages)

**Do this instead:**
- Provide separate `mc-update` command that calls `uv tool upgrade`
- Let package manager (uv) handle atomic updates
- Display notification banner with update instructions
- Trust user's installation method (uv, pip, system package)

### Anti-Pattern 3: Opaque Auto-Updates

**What people do:** Silently update CLI tool without user confirmation or notification.

**Why it's wrong:**
- Breaks CI/CD reproducibility (different versions on different runs)
- Violates principle of least surprise
- Can introduce breaking changes mid-workflow
- Conflicts with enterprise change management policies

**Do this instead:**
- Display notification banner (user awareness)
- Require explicit `mc-update` command (user consent)
- Support version pinning (opt-out mechanism)
- Log version in output (debugging aid)

### Anti-Pattern 4: Treating Config as Database

**What people do:** Write to config file on every CLI invocation to update last-check timestamp.

**Why it's wrong:**
- Frequent disk I/O (performance penalty)
- File lock contention (multiple concurrent `mc` processes)
- Config file churn (Git diffs, merge conflicts if versioned)

**Do this instead:**
- Only write config when version check actually runs (hourly, not per-invocation)
- Cache last-check timestamp in memory for process lifetime
- Consider separate cache file (e.g., `~/.cache/mc/version_check.json`) outside config

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| PyPI JSON API | HTTPS GET to `pypi.org/pypi/mc-cli/json` | 2 second timeout, fail silently, ETag caching optional |
| uv tool manager | subprocess.run(['uv', 'tool', 'upgrade', 'mc']) | mc-update command only, check uv installed first |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| CLI → VersionChecker | Direct function call at startup | Non-blocking, <0.01s when throttled |
| VersionChecker → Config | ConfigManager.load/save | Read last_check timestamp, write on update |
| mc-update → subprocess | subprocess.run with check=True | Raises CalledProcessError on failure |
| UpdateBanner → Rich | Console.print(Panel(...)) | Consistent with existing terminal output |

## Build Order Recommendations

Based on existing MC architecture and dependencies, suggested implementation sequence:

### Phase 1: Config Schema Extension
**Why first:** Foundation for all version management features, minimal risk, backward compatible

1. Extend `config/models.py:get_default_config()` with `version_management` section
2. Add validation in `config/models.py:validate_config()`
3. Test backward compatibility (existing configs without version_management work)

### Phase 2: Version Checker Core
**Why second:** No UI dependencies, pure logic, easy to test in isolation

1. Create `utils/version_checker.py` with PyPI API client
2. Implement throttle logic (should_check_version, update_timestamp)
3. Implement version comparison (needs_update)
4. Unit tests for all functions (mock PyPI responses)

### Phase 3: Update Banner Display
**Why third:** Depends on VersionChecker, uses existing Rich library (low risk)

1. Create `utils/update_banner.py` with Rich Panel display
2. Integrate banner into version check flow
3. Test banner appearance in terminal (manual QA)

### Phase 4: CLI Entry Point Hook
**Why fourth:** Integrates all previous phases, adds hook to main.py (moderate risk)

1. Create `check_and_notify_updates()` function in `cli/main.py`
2. Call hook from `main()` after logging setup
3. Integration test: full CLI flow with mocked PyPI API

### Phase 5: mc-update Utility
**Why last:** Independent of notification system, can be built/tested separately

1. Create `cli/update.py` with main() function
2. Add console_scripts entry to pyproject.toml: `mc-update`
3. Implement pre-flight checks (uv installed, pinned version handling)
4. Implement subprocess call to `uv tool upgrade mc`
5. Test mc-update survives package upgrade (install, upgrade, verify mc-update still works)

## Deeper Research Flags

Areas that may need phase-specific investigation:

### Version Comparison Algorithm
**Current assumption:** Simple string comparison (`"2.1.0" != "2.0.2"`)
**Potential issue:** Semantic versioning edge cases (pre-release, build metadata)
**Research needed:** Should MC use `packaging.version.Version` for robust semver comparison?

### ETag Caching Implementation
**Current assumption:** ETag caching is optional optimization
**Potential issue:** Requires storing ETag in config, additional complexity
**Research needed:** Measure real-world PyPI API response times - is ETag worth implementing?

### uv Installation Detection
**Current assumption:** Check if `uv` binary exists in PATH
**Potential issue:** Users may have installed mc via pip, not uv
**Research needed:** How to detect installation method? Should mc-update support pip upgrade too?

### Container Version Pinning
**Current assumption:** `pinned_container_version` pins container image tag
**Potential issue:** Unclear interaction with container build/pull logic
**Research needed:** How does container version pinning integrate with existing ContainerManager?

## Sources

**CLI Auto-Update Patterns:**
- [Salesforce CLI Auto-Update Documentation](https://developer.salesforce.com/docs/atlas.en-us.sfdx_setup.meta/sfdx_setup/sfdx_setup_disable_autoupdate.htm)
- [Azure CLI Automatic Updates](https://learn.microsoft.com/en-us/cli/azure/update-azure-cli)
- [Improve UX of CLI Tools with Version Update Warnings (Medium)](https://medium.com/trabe/improve-the-ux-of-cli-tools-with-version-update-warnings-23eb8fcb474a)

**Python Implementation Patterns:**
- [check4updates - Python Package for Update Notifications](https://github.com/MatthewReid854/check4updates)
- [update-checker - Python Module for Package Updates](https://github.com/bboe/update_checker)
- [PyPI JSON API Discussion](https://discuss.python.org/t/api-to-get-latest-version-of-a-pypi-package/10197)

**UV Tool Management:**
- [How to Upgrade UV](https://pydevtools.com/handbook/how-to/how-to-upgrade-uv/)
- [UV Python Upgrade Features (2026 Release)](https://github.com/astral-sh/uv/releases)
- [UV Tool Management](https://realpython.com/python-uv/)

**Configuration and Throttling:**
- [Python and TOML - Real Python](https://realpython.com/python-toml/)
- [Rate Limiting vs Throttling - LogRocket](https://blog.logrocket.com/advanced-guide-rate-limiting-api-traffic-management/)

**Python CLI Frameworks:**
- [argparse Official Documentation](https://docs.python.org/3/library/argparse.html)
- [Entry Points Specification - Python Packaging](https://packaging.python.org/en/latest/specifications/entry-points/)
- [Setuptools Entry Points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html)

**Rich Library (Terminal Formatting):**
- [Rich - Python Library for Terminal Formatting](https://github.com/Textualize/rich)
- [Rich Documentation](https://rich.readthedocs.io/en/stable/introduction.html)
- [Rich Python Library for Advanced CLI Design](https://arjancodes.com/blog/rich-python-library-for-interactive-cli-tools/)

---
*Architecture research for: MC CLI Auto-Update Integration*
*Researched: 2026-02-11*
