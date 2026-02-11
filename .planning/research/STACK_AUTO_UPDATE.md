# Stack Research: Auto-Update and Version Management

**Domain:** CLI tool automatic version management and updates
**Researched:** 2026-02-11
**Confidence:** HIGH

## Executive Summary

MC CLI already has a solid foundation (Python 3.11+, uv tool distribution, TOML config, requests, rich). For automatic version management and auto-updates, we need **minimal new dependencies**. The existing stack contains almost everything needed:

- `packaging` library (only new dependency) for PEP 440 version comparison
- `requests` (already present) for GitHub/Quay.io API calls
- `subprocess` (stdlib) for `uv tool upgrade` execution
- `tomli_w` (already present) for TOML persistence
- `platformdirs` (already present) for cross-platform cache paths
- `rich` (already present) for update banners

The `packaging` library is the de facto standard for Python version comparison and may already be present as a transitive dependency of setuptools or pip.

## Stack Additions for Auto-Update

### Version Comparison

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `packaging` | >=24.0 | Parse and compare PEP 440 version numbers | De facto standard for Python version comparison. 3x faster as of v26.0 (Jan 2026). Handles all PEP 440 edge cases (pre-releases, post-releases, epochs). Battle-tested by pip, setuptools, and the entire Python packaging ecosystem. |

**Rationale:** The `packaging.version.Version` class is the authoritative implementation of PEP 440 version comparison. It handles edge cases like `2.0.4rc1`, `2.1.0.post1`, `2.0.0.dev5` correctly. Recent performance improvements (2-5x faster in v26.0, released Jan 2026) make it ideal for frequent version checks.

**Why PEP 440 matters:** MC CLI uses Python versioning (e.g., `2.0.4`), not strict semantic versioning. PEP 440 is the Python ecosystem standard and supports pre-releases, post-releases, development releases, and epochs—features semantic versioning lacks.

**Alternatives considered:**
- `semver` library: Only handles semantic versioning (MAJOR.MINOR.PATCH), not PEP 440. Fails to parse `2.0.4rc1` or `2.0.0.post1`.
- Manual string comparison: Fails on version ordering (e.g., "2.0.10" < "2.0.9" as strings).
- `distutils.version.LooseVersion`: Deprecated and removed in Python 3.12+.

### No New Dependencies for API Access

**GitHub API Access:**
- Use existing `requests` library
- Endpoint: `https://api.github.com/repos/{owner}/{repo}/releases/latest`
- No authentication required for public repos (60 requests/hour unauthenticated)
- Returns JSON with `tag_name`, `published_at`, `prerelease`, `draft` fields

**Quay.io API Access:**
- Use existing `requests` library
- Two endpoint options:
  - Quay v1 API: `https://quay.io/api/v1/repository/{namespace}/{repo}/tag/`
  - Docker Registry v2 API: `https://quay.io/v2/{namespace}/{repo}/tags/list` (recommended)
- Public repos: No authentication needed
- Private repos: Requires Bearer token authentication

**Auto-Update Execution:**
- Use stdlib `subprocess.run()` to execute `uv tool upgrade mc-cli`
- uv handles version resolution, download, and installation
- Exit code indicates success/failure

**Version Check Throttling:**
- Use `platformdirs.user_cache_dir()` for cross-platform cache directory (already present)
- Store timestamp in `~/.cache/mc/last_version_check.json` (or platform equivalent)
- Use stdlib `time.time()` for current timestamp
- Compare timestamps with simple arithmetic (current - last >= 3600 for hourly)

**TOML Config Persistence:**
- Use existing `tomli_w.dump()` for writing pinned versions to config
- Use existing `tomllib.load()` (stdlib in Python 3.11+) for reading

**Rich Banners:**
- Use existing `rich.console.Console` and `rich.panel.Panel`
- Display update notifications with color and formatting

## Installation Changes

### Add to pyproject.toml dependencies

```toml
dependencies = [
    "backoff>=2.2.1",
    "packaging>=24.0",  # NEW: Version comparison (only new dependency)
    "platformdirs>=4.0.0",  # Already present
    "podman>=5.7.0",
    "requests>=2.31.0",  # Already present
    "rich>=14.0.0",  # Already present
    "simple-salesforce>=1.12.9",
    "tenacity>=8.3.0",
    "tomli-w>=1.0.0",  # Already present
    "tqdm>=4.66.0",
]
```

**Version constraint rationale:**
- `packaging>=24.0`: Ensures PEP 440 compliance. Version 26.0 (Jan 2026) has 2-5x performance improvements over v24.0. Version 26.1 in development.

### Development dependencies (no changes)

No changes needed. Testing of version comparison can use existing `pytest` infrastructure.

## Integration Points with Existing Stack

### 1. uv Tool Integration

**Current:** MC CLI is installed via `uv tool install mc-cli`

**Integration patterns:**
```python
import subprocess

# Upgrade to latest (no pin)
result = subprocess.run(
    ["uv", "tool", "upgrade", "mc-cli"],
    check=True,
    capture_output=True,
    text=True
)

# Upgrade to specific version (when un-pinning or changing pin)
result = subprocess.run(
    ["uv", "tool", "install", f"mc-cli=={version}"],
    check=True,
    capture_output=True,
    text=True
)
```

**uv behavior (verified from official docs):**
- `uv tool upgrade <package>`: Upgrades within existing constraints
  - If installed with `uv tool install 'mc-cli>=2.0,<3.0'`, stays in 2.x series
  - If installed without constraints, upgrades to latest available
- `uv tool install <package>==X.Y.Z`: Replaces existing installation with specific version
- `uv tool install <package>`: Installs/upgrades to latest unconstrained version
- `uv tool upgrade --all`: Upgrades all installed tools

**Error handling:**
```python
try:
    subprocess.run(["uv", "tool", "upgrade", "mc-cli"], check=True)
except subprocess.CalledProcessError as e:
    # uv upgrade failed - display error banner
    console.print(f"[red]Update failed:[/red] {e.stderr}")
except FileNotFoundError:
    # uv not installed - should not happen as MC requires uv
    console.print("[red]Error:[/red] uv not found. MC CLI requires uv.")
```

### 2. TOML Config Integration

**Current:** `~/mc/config/config.toml` managed via `platformdirs` and `tomli/tomli_w`

**New config sections:**
```toml
[version]
pinned_cli = "2.0.4"  # Optional: pin MC CLI to specific version
pinned_container = "2.0.4"  # Optional: pin container image to specific tag
last_cli_check = 1707667200  # Unix timestamp of last MC CLI version check
last_container_check = 1707667200  # Unix timestamp of last container version check

[update]
auto_update = true  # Default: true, automatically upgrade unless pinned
check_interval = 3600  # Seconds between version checks (default: 1 hour = 3600)
grace_period = 604800  # Seconds to wait before warning about pinned version (default: 7 days)
```

**Read pattern (Python 3.11+ stdlib tomllib):**
```python
import tomllib
from pathlib import Path

config_path = Path("~/.config/mc/config.toml").expanduser()
with open(config_path, "rb") as f:
    config = tomllib.load(f)

pinned_version = config.get("version", {}).get("pinned_cli")
last_check = config.get("version", {}).get("last_cli_check", 0)
```

**Write pattern (tomli_w already in dependencies):**
```python
import tomli_w
import time
from pathlib import Path

config["version"]["last_cli_check"] = int(time.time())
config["version"]["pinned_cli"] = "2.0.4"

config_path = Path("~/.config/mc/config.toml").expanduser()
with open(config_path, "wb") as f:
    tomli_w.dump(config, f)
```

### 3. GitHub API Integration

**Current:** `requests` library already used for Red Hat API and Salesforce

**Get latest release:**
```python
import requests
from packaging.version import Version

# Get latest release from GitHub
response = requests.get(
    "https://api.github.com/repos/rhn-support-dsquirre/mc/releases/latest",
    timeout=10
)
response.raise_for_status()

data = response.json()
tag_name = data["tag_name"]  # e.g., "v2.0.5" or "2.0.5"

# Strip 'v' prefix if present
version_str = tag_name.lstrip("v")
latest_version = Version(version_str)

# Compare with current version
current_version = Version("2.0.4")
if latest_version > current_version:
    # Update available
    print(f"Update available: {latest_version} (current: {current_version})")
```

**List all releases:**
```python
# Get all releases (for mc-update --list)
response = requests.get(
    "https://api.github.com/repos/rhn-support-dsquirre/mc/releases",
    params={"per_page": 10},  # Limit to 10 most recent
    timeout=10
)
releases = response.json()

for release in releases:
    tag_name = release["tag_name"]
    published_at = release["published_at"]
    prerelease = release["prerelease"]
    print(f"{tag_name} - {published_at} {'(pre-release)' if prerelease else ''}")
```

**Error handling patterns (existing pattern from MC codebase):**
```python
import requests

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
except requests.Timeout:
    # Network timeout - skip update check, retry next time
    logger.warning("Version check timed out")
except requests.ConnectionError:
    # Offline or network issue - skip gracefully
    logger.warning("Version check failed: network unreachable")
except requests.HTTPError as e:
    # HTTP error (404, 500, etc.) - skip gracefully
    logger.warning(f"Version check failed: {e}")
except ValueError:
    # JSON parsing error - malformed response
    logger.warning("Version check failed: invalid response")
```

**GitHub API rate limits:**
- Unauthenticated: 60 requests/hour per IP
- Authenticated: 5,000 requests/hour per user
- MC CLI throttle: 1 request per hour = 24 requests/day
- Well under unauthenticated limit (60/hour)
- No authentication needed

### 4. Quay.io API Integration

**Two endpoint options:**

**Option A: Docker Registry v2 API (RECOMMENDED)**
```python
import requests
from packaging.version import Version, InvalidVersion

# Get all tags using Docker Registry v2 API
response = requests.get(
    "https://quay.io/v2/rhn_support_dsquirre/mc-container/tags/list",
    timeout=10
)
response.raise_for_status()

data = response.json()
tags = data["tags"]  # List of tag names: ["2.0.4", "2.0.5", "latest", ...]

# Filter to valid version tags
valid_versions = []
for tag in tags:
    try:
        valid_versions.append(Version(tag))
    except InvalidVersion:
        pass  # Skip non-version tags like "latest", "stable", "dev"

# Find latest version
if valid_versions:
    latest_version = max(valid_versions)
    print(f"Latest container version: {latest_version}")
```

**Recommendation:** Use Docker Registry v2 API (`/v2/.../tags/list`) for simplicity and standard compliance. Quay.io supports both APIs. v2 is simpler (just tag names), whereas Quay v1 returns more metadata (manifest digests, expiration, last_modified).

**Option B: Quay.io v1 API (if metadata needed)**
```python
# Quay v1 API returns more metadata per tag
response = requests.get(
    "https://quay.io/api/v1/repository/rhn_support_dsquirre/mc-container/tag/",
    headers={"Authorization": f"Bearer {token}"},  # If private repo
    timeout=10
)
data = response.json()

for tag_obj in data["tags"]:
    tag_name = tag_obj["name"]
    last_modified = tag_obj["last_modified"]  # Unix timestamp
    manifest_digest = tag_obj["manifest_digest"]
```

**Public vs. Private repos:**
- MC container is public: No authentication needed
- If private: Requires Bearer token via `Authorization` header

**Version filtering (same for both APIs):**
```python
from packaging.version import Version, InvalidVersion

def filter_version_tags(tags: list[str]) -> list[Version]:
    """Filter tags to valid PEP 440 versions, excluding non-version tags."""
    versions = []
    for tag in tags:
        try:
            versions.append(Version(tag))
        except InvalidVersion:
            # Skip tags like "latest", "stable", "dev", "rc-2024-01-01"
            pass
    return versions

valid_versions = filter_version_tags(tags)
latest_version = max(valid_versions) if valid_versions else None
```

### 5. Rich Banner Integration

**Current:** `rich` used for console output throughout MC CLI

**Update available notification:**
```python
from rich.console import Console
from rich.panel import Panel

console = Console()

# Update available (CLI)
console.print(Panel(
    "[yellow]Update available:[/yellow] MC CLI 2.0.5 (you have 2.0.4)\n"
    "Run [cyan]mc-update[/cyan] to upgrade or [cyan]mc-update --pin[/cyan] to stay on 2.0.4",
    title="Version Update",
    border_style="yellow"
))

# Update available (container)
console.print(Panel(
    "[yellow]Update available:[/yellow] Container image 2.0.5 (you have 2.0.4)\n"
    "Will auto-update on next container launch",
    title="Container Update",
    border_style="yellow"
))
```

**Pinned version warning (after grace period):**
```python
# Warning after 7 days of being pinned with newer version available
console.print(Panel(
    "[yellow]Warning:[/yellow] MC CLI 2.0.4 is pinned but 2.0.6 is available (2 versions behind).\n"
    "Pinned since: 2026-02-04 (7 days ago)\n"
    "Run [cyan]mc-update --unpin[/cyan] to enable auto-updates",
    title="Pinned Version Warning",
    border_style="yellow"
))
```

**Update success banner:**
```python
# After successful upgrade
console.print(Panel(
    "[green]Success![/green] MC CLI upgraded to 2.0.5\n"
    "Restart your terminal or run [cyan]hash -r[/cyan] to use the new version",
    title="Update Complete",
    border_style="green"
))
```

**Update failure banner:**
```python
# After failed upgrade
console.print(Panel(
    "[red]Update failed:[/red] Could not upgrade MC CLI\n"
    "Error: {error_message}\n"
    "Try manually: [cyan]uv tool upgrade mc-cli[/cyan]",
    title="Update Failed",
    border_style="red"
))
```

### 6. Throttle File Pattern

**Cache directory (platformdirs already present):**
```python
from platformdirs import user_cache_dir
from pathlib import Path
import json
import time

cache_dir = Path(user_cache_dir("mc", "mc-cli"))
cache_dir.mkdir(parents=True, exist_ok=True)

throttle_file = cache_dir / "version_check.json"

# Read last check time
if throttle_file.exists():
    with open(throttle_file) as f:
        data = json.load(f)
        last_cli_check = data.get("last_cli_check", 0)
        last_container_check = data.get("last_container_check", 0)
else:
    last_cli_check = 0
    last_container_check = 0

# Check if throttle period has passed
current_time = time.time()
check_interval = 3600  # 1 hour

if current_time - last_cli_check >= check_interval:
    # Perform version check
    # ...

    # Update throttle file
    data["last_cli_check"] = int(current_time)
    with open(throttle_file, "w") as f:
        json.dump(data, f)
```

**Throttle file format:**
```json
{
  "last_cli_check": 1707667200,
  "last_container_check": 1707667200
}
```

**Why not store in config.toml?**
- Cache directory is for transient data (throttle timestamps)
- Config directory is for user-editable settings (pins, preferences)
- Separating concerns: cache can be cleared without losing config

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `apscheduler` or `schedule` libraries | Overkill for simple hourly checks. Adds complexity (background threads, scheduling logic) and dependencies (6+ transitive deps). CLI already runs frequently enough for inline checks. | Simple timestamp comparison in cache file |
| `python-semver` library | Only handles semantic versioning (MAJOR.MINOR.PATCH), not PEP 440. Won't parse `2.0.4rc1`, `2.0.0.post1`, or `2.0.0.dev1`. | `packaging.version.Version` (PEP 440 compliant) |
| `distutils.version` module | Deprecated and removed in Python 3.12+. MC targets Python 3.11+ where it still exists but will break in future. | `packaging.version.Version` |
| `PyGithub` library | Heavy dependency (150+ KB) for simple REST API call. Adds 10+ transitive dependencies (PyJWT, cryptography, etc.). Async-first API is overkill for synchronous CLI. | Direct `requests.get()` call (already present) |
| Custom version comparison logic | Error-prone. Edge cases: pre-releases (`2.0.4rc1 < 2.0.4`), post-releases (`2.0.4.post1 > 2.0.4`), epochs (`1!2.0.0 > 2.1.0`). Reinventing a battle-tested wheel. | `packaging.version.Version` (handles all edge cases) |
| `quay-api` Python library | Unmaintained (last update 2021). Adds unnecessary dependency. Simple API calls don't warrant a library. | Direct `requests.get()` to Quay.io API or Docker Registry v2 |
| Background daemon or service | CLI tools should not spawn background processes. Violates user expectations. Adds complexity (daemon management, IPC). | Inline checks at CLI startup with throttle file |
| Cron job for version checks | Requires external setup. Platform-specific (no Windows Task Scheduler equivalent). User must manually configure. | Inline checks triggered by CLI invocations |
| `setuptools_scm` for version | Already uses this for *build-time* versioning from git. Not for *runtime* version comparison of releases. | Keep setuptools_scm for builds, use `packaging.version` for comparisons |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `packaging.version.Version` | `python-semver` | Never for MC CLI. MC uses PEP 440 versions, not pure semantic versioning. If project strictly follows semantic versioning (MAJOR.MINOR.PATCH only), semver is more prescriptive. |
| Direct `requests.get()` to GitHub API | `PyGithub` library | If you need advanced GitHub features (issues, PRs, workflows, repository management, webhooks). MC CLI only needs releases—overkill to add 10+ dependencies. |
| Simple timestamp file in cache | `apscheduler` or `schedule` library | If you need complex scheduling (daily, weekly, monthly, cron-style expressions). MC CLI only needs hourly checks—simple arithmetic suffices. |
| Docker Registry v2 API | Quay.io v1 API | If you need detailed metadata (manifest digests, security scan results, tag expiration policies). MC CLI only needs tag lists—v2 is simpler. |
| `subprocess.run(["uv", "tool", "upgrade"])` | Downloading and manually installing from GitHub releases | If uv is not available. But MC CLI already requires uv for installation—no reason to bypass it. |
| Inline version check at CLI startup | Background daemon checking versions | If tool is rarely invoked (e.g., once per week). MC CLI is invoked frequently (multiple times per day)—inline check with throttle is simpler. |

## Stack Patterns by Variant

### If user has pinned version

```python
from packaging.version import Version
import time

pinned_version = config.get("version", {}).get("pinned_cli")
if pinned_version:
    # Skip auto-update execution
    current_version = Version("2.0.4")
    latest_version = check_github_latest()  # Still check for notification

    if latest_version > Version(pinned_version):
        # Check grace period for warning
        pin_timestamp = config.get("version", {}).get("pin_timestamp", 0)
        grace_period = config.get("update", {}).get("grace_period", 604800)  # 7 days

        if time.time() - pin_timestamp > grace_period:
            # Display warning banner
            console.print(Panel(
                f"[yellow]Warning:[/yellow] Pinned to {pinned_version} but {latest_version} available",
                title="Update Available",
                border_style="yellow"
            ))
```

### If user has unpinned version (default)

```python
import subprocess

# Check for updates (throttled)
if should_check_version():
    latest_version = check_github_latest()
    current_version = get_current_version()

    if latest_version > current_version:
        # Auto-update enabled
        try:
            subprocess.run(["uv", "tool", "upgrade", "mc-cli"], check=True)
            # Display success banner
            console.print(Panel(
                f"[green]Updated[/green] MC CLI to {latest_version}",
                border_style="green"
            ))
        except subprocess.CalledProcessError as e:
            # Display failure banner
            console.print(Panel(
                f"[red]Update failed:[/red] {e.stderr}",
                border_style="red"
            ))

        # Update throttle timestamp
        update_last_check_timestamp()
```

### If GitHub API is unreachable (offline, rate-limited)

```python
import requests
import logging

logger = logging.getLogger(__name__)

try:
    response = requests.get(
        "https://api.github.com/repos/rhn-support-dsquirre/mc/releases/latest",
        timeout=10
    )
    response.raise_for_status()
except requests.RequestException as e:
    # Log warning but don't crash
    logger.warning(f"Version check failed: {e}")
    # Skip update check, retry on next CLI invocation (after throttle period)
    return None
```

**Graceful degradation:**
- No banner displayed if API is unreachable
- No error message to user (logged for debugging)
- CLI continues normal operation
- Next invocation (after throttle period) will retry

### If uv upgrade fails

```python
import subprocess
from rich.console import Console
from rich.panel import Panel

console = Console()

try:
    result = subprocess.run(
        ["uv", "tool", "upgrade", "mc-cli"],
        check=True,
        capture_output=True,
        text=True
    )
except subprocess.CalledProcessError as e:
    # Display error banner with troubleshooting
    console.print(Panel(
        f"[red]Update failed:[/red] {e.stderr}\n\n"
        "Troubleshooting steps:\n"
        "1. Check internet connection\n"
        "2. Verify uv is up to date: [cyan]uv self update[/cyan]\n"
        "3. Manually upgrade: [cyan]uv tool upgrade mc-cli[/cyan]\n"
        "4. Check uv logs: [cyan]uv tool upgrade mc-cli --verbose[/cyan]",
        title="Update Failed",
        border_style="red"
    ))
    # Don't update config (preserve last successful state)
    return
```

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| `packaging` | >=24.0 | Python 3.9+ | Version 26.0 (Jan 2026) has 2-5x performance improvements. Requires Python 3.8+ but MC CLI targets 3.11+. |
| `requests` | >=2.31.0 | Python 3.8+ | Already in MC CLI. Handles GitHub and Quay.io APIs. Security fixes for CVE-2023-32681. |
| `tomli_w` | >=1.0.0 | Python 3.7+ | Already in MC CLI. TOML writing for config persistence. |
| `rich` | >=14.0.0 | Python 3.8+ | Already in MC CLI. Update banners and notifications. |
| `platformdirs` | >=4.0.0 | Python 3.8+ | Already in MC CLI. Cross-platform cache directory for throttle file. |

**Python version requirements:**
- Python 3.11+ (current MC CLI requirement, unchanged)
- `tomllib` (stdlib in 3.11+) for reading TOML
- `subprocess.run()` with `check=True` (stdlib)
- `pathlib` (stdlib) for file operations
- `json` (stdlib) for throttle file
- `time` (stdlib) for timestamps

**No version conflicts:**
- `packaging` has no dependencies
- All other components already present in MC CLI stack

## Implementation Architecture

### Version Check Flow (Background)

```
CLI Startup (e.g., `mc ls`)
  ↓
Load config.toml (check if pinned, get check_interval)
  ↓
Read throttle file (~/.cache/mc/version_check.json)
  ↓
Check: current_time - last_check >= check_interval?
  ↓ YES (throttle period passed)
GitHub API: GET /repos/{owner}/{repo}/releases/latest
  ↓
Parse version with packaging.version.Version
  ↓
Compare: latest_version > current_version?
  ↓ YES (update available)
Check if pinned in config.toml
  ↓ NOT PINNED (auto-update enabled)
subprocess.run(["uv", "tool", "upgrade", "mc-cli"])
  ↓
Update throttle file with current timestamp
  ↓
Display success/failure banner (rich)
  ↓
Continue with normal CLI operation (mc ls)
```

**Key design decisions:**
- Check happens *inline* at CLI startup, not in background daemon
- Throttle prevents checking on every invocation (performance)
- Failures are logged but don't block CLI operation
- Auto-update only if not pinned (respects user choice)

### mc-update Utility Flow

```
Run `mc-update` (bypasses throttle)
  ↓
GitHub API: GET /repos/{owner}/{repo}/releases/latest
  ↓
Display current vs. latest version
  ↓
Parse command-line arguments:
  - (no args): Interactive menu or auto-upgrade
  - --upgrade: Upgrade to latest
  - --pin [version]: Pin to specific version
  - --unpin: Remove pin, enable auto-update
  - --list: Show all available versions
  - --check: Check for updates without upgrading
  ↓
Execute uv commands based on choice:
  - Upgrade: uv tool upgrade mc-cli
  - Pin: uv tool install mc-cli=={version}
  - Unpin: uv tool upgrade mc-cli (removes constraints)
  ↓
Update config.toml:
  - Set/remove pinned_cli
  - Update pin_timestamp (for grace period)
  ↓
Display result banner (rich)
```

**mc-update command interface:**
```bash
# Check for updates (no action)
mc-update --check

# Upgrade to latest
mc-update --upgrade
mc-update  # Same as --upgrade if non-interactive

# List available versions
mc-update --list

# Pin to specific version
mc-update --pin 2.0.4

# Pin to current version (prevent auto-updates)
mc-update --pin

# Unpin (enable auto-updates)
mc-update --unpin

# Show current status
mc-update --status
```

### Container Version Check Flow

```
CLI Startup or `mc container` command
  ↓
Read throttle file (~/.cache/mc/version_check.json)
  ↓
Check: current_time - last_container_check >= check_interval?
  ↓ YES (throttle period passed)
Quay.io API: GET /v2/{namespace}/{repo}/tags/list
  ↓
Filter tags with packaging.version.Version (exclude "latest", "stable")
  ↓
Find latest valid version tag: max(valid_versions)
  ↓
Compare with current container version (from state DB or config)
  ↓ NEWER VERSION AVAILABLE
Check if container pinned in config.toml
  ↓ NOT PINNED (auto-update enabled)
podman pull quay.io/{namespace}/{repo}:{latest_tag}
  ↓
Update state DB with new container version
  ↓
Update throttle file with current timestamp
  ↓
Display success banner (rich)
  ↓
Continue with container operation
```

**Integration with existing podman-py:**
```python
from podman import PodmanClient
from packaging.version import Version

client = PodmanClient()

# Pull new container image
image = client.images.pull(
    f"quay.io/rhn_support_dsquirre/mc-container:{latest_version}"
)

# Verify pulled image tag
assert str(latest_version) in image.tags
```

## Testing Strategy

### Unit Tests (pytest)

```python
from packaging.version import Version
import pytest

def test_version_comparison():
    """Test PEP 440 version comparison."""
    assert Version("2.0.5") > Version("2.0.4")
    assert Version("2.1.0") > Version("2.0.99")
    assert Version("2.0.4rc1") < Version("2.0.4")
    assert Version("2.0.4.post1") > Version("2.0.4")
    assert Version("2.0.0.dev1") < Version("2.0.0rc1")
    assert Version("1!2.0.0") > Version("2.1.0")  # Epoch

def test_version_parsing():
    """Test version string parsing and normalization."""
    # Strip 'v' prefix
    assert Version("2.0.4") == Version("v2.0.4".lstrip("v"))

    # Invalid versions raise exception
    from packaging.version import InvalidVersion
    with pytest.raises(InvalidVersion):
        Version("latest")
    with pytest.raises(InvalidVersion):
        Version("stable")
    with pytest.raises(InvalidVersion):
        Version("not-a-version")

def test_github_api_parsing(responses):
    """Test GitHub API response parsing."""
    import requests

    # Mock GitHub API response
    responses.add(
        responses.GET,
        "https://api.github.com/repos/rhn-support-dsquirre/mc/releases/latest",
        json={
            "tag_name": "v2.0.5",
            "published_at": "2026-02-11T12:00:00Z",
            "prerelease": False,
            "draft": False
        },
        status=200
    )

    # Test parsing logic
    response = requests.get(
        "https://api.github.com/repos/rhn-support-dsquirre/mc/releases/latest"
    )
    data = response.json()

    version = Version(data["tag_name"].lstrip("v"))
    assert version == Version("2.0.5")
    assert data["prerelease"] is False

def test_throttle_logic(tmp_path):
    """Test version check throttle."""
    import json
    import time
    from pathlib import Path

    throttle_file = tmp_path / "version_check.json"

    # Initial state: no throttle file
    assert not throttle_file.exists()

    # First check: should proceed
    current_time = time.time()
    assert should_check_version(throttle_file, interval=3600)

    # Write throttle file
    throttle_file.write_text(json.dumps({"last_cli_check": int(current_time)}))

    # Immediate second check: should skip (throttled)
    assert not should_check_version(throttle_file, interval=3600)

    # Check after interval: should proceed
    old_time = current_time - 3601
    throttle_file.write_text(json.dumps({"last_cli_check": int(old_time)}))
    assert should_check_version(throttle_file, interval=3600)

def test_config_pin_persistence(tmp_path):
    """Test TOML config pin read/write."""
    import tomli_w
    import tomllib
    from pathlib import Path

    config_file = tmp_path / "config.toml"

    # Write pin
    config = {"version": {"pinned_cli": "2.0.4", "pin_timestamp": 1707667200}}
    with open(config_file, "wb") as f:
        tomli_w.dump(config, f)

    # Read pin
    with open(config_file, "rb") as f:
        loaded = tomllib.load(f)

    assert loaded["version"]["pinned_cli"] == "2.0.4"
    assert loaded["version"]["pin_timestamp"] == 1707667200
```

**Existing test infrastructure (no changes needed):**
- `pytest>=9.0.0` (already present)
- `responses>=0.25.0` (already present) for mocking HTTP requests
- `pytest-mock>=3.15.0` (already present) for subprocess mocking

### Integration Tests

```python
import pytest
import subprocess

@pytest.mark.integration
def test_uv_tool_commands():
    """Test uv tool commands (requires uv installed)."""
    # Check uv is available
    result = subprocess.run(["uv", "--version"], capture_output=True)
    assert result.returncode == 0

    # Test uv tool list (should not fail)
    result = subprocess.run(["uv", "tool", "list"], capture_output=True)
    assert result.returncode == 0

@pytest.mark.integration
def test_github_api_real():
    """Test GitHub API with real request (skip if offline)."""
    import requests

    try:
        response = requests.get(
            "https://api.github.com/repos/rhn-support-dsquirre/mc/releases/latest",
            timeout=10
        )
        assert response.status_code == 200

        data = response.json()
        assert "tag_name" in data
        assert "published_at" in data
    except requests.RequestException:
        pytest.skip("GitHub API unreachable")

@pytest.mark.integration
def test_quay_api_real():
    """Test Quay.io API with real request (skip if offline)."""
    import requests

    try:
        response = requests.get(
            "https://quay.io/v2/rhn_support_dsquirre/mc-container/tags/list",
            timeout=10
        )
        assert response.status_code == 200

        data = response.json()
        assert "tags" in data
        assert isinstance(data["tags"], list)
    except requests.RequestException:
        pytest.skip("Quay.io API unreachable")
```

**Integration test markers (already configured in pyproject.toml):**
```toml
[tool.pytest.ini_options]
markers = [
    "integration: marks tests as integration tests (deselect with '-m \"not integration\"')",
]
```

**Run unit tests only:**
```bash
pytest -m "not integration"
```

**Run all tests including integration:**
```bash
pytest
```

## Security Considerations

### API Authentication

**GitHub:**
- No authentication needed for public repos
- Rate limit: 60 requests/hour (unauthenticated), 5,000/hour (authenticated)
- MC CLI throttle: 1 request per hour = 24 requests/day
- Well under unauthenticated limit
- No API key storage required

**Quay.io:**
- Public repos: No authentication needed for read
- Private repos: Would need Bearer token (not applicable for MC, repo is public)
- If future private repo: Store token in config.toml with 0600 permissions

### Subprocess Safety

**Command injection prevention:**
```python
# SAFE: List arguments (no shell=True)
subprocess.run(["uv", "tool", "upgrade", "mc-cli"], check=True)
subprocess.run(["uv", "tool", "install", f"mc-cli=={version}"], check=True)

# UNSAFE: String concatenation with shell=True (DON'T DO THIS)
subprocess.run(f"uv tool upgrade {package}", shell=True)  # VULNERABLE
```

**Version validation before subprocess:**
```python
from packaging.version import Version, InvalidVersion

def safe_install_version(version_str: str) -> None:
    """Safely install a specific version after validation."""
    try:
        # Validate version format
        version_obj = Version(version_str)
    except InvalidVersion:
        raise ValueError(f"Invalid version format: {version_str}")

    # Use validated version in subprocess
    subprocess.run(
        ["uv", "tool", "install", f"mc-cli=={version_obj}"],
        check=True
    )
```

**Why this is safe:**
- `packaging.version.Version()` rejects malicious input (e.g., `"; rm -rf /"`)
- List arguments in `subprocess.run()` prevent shell injection
- No `shell=True` means no shell metacharacter interpretation

### TOML Injection Prevention

**Safe writing (tomli_w handles escaping):**
```python
import tomli_w

# tomli_w handles escaping and serialization safely
config["version"]["pinned_cli"] = user_input  # No injection risk
tomli_w.dump(config, file)
```

**Why this is safe:**
- `tomli_w` properly escapes TOML special characters
- User input becomes a TOML string value, not interpreted as TOML syntax
- No manual string concatenation or f-strings for TOML generation

### File Permission Hardening

**Config file permissions:**
```python
import os
from pathlib import Path

config_path = Path("~/.config/mc/config.toml").expanduser()

# Set restrictive permissions (user read/write only)
config_path.chmod(0o600)

# Verify permissions (defensive)
stat = config_path.stat()
if stat.st_mode & 0o077:
    raise PermissionError("Config file has insecure permissions")
```

**Cache file permissions:**
```python
# Cache directory: user read/write/execute only
cache_dir.chmod(0o700)

# Throttle file: user read/write only
throttle_file.chmod(0o600)
```

## Performance Considerations

### Throttling is Critical

**Without throttling:**
- GitHub API call on every `mc` command invocation
- Typical latency: 200-500ms per call
- User experience: Noticeable delay on every command
- Rate limiting: Hit GitHub's 60/hour limit quickly

**With 1-hour throttle:**
- Max 24 API calls/day (well under GitHub's 60/hour limit)
- Cache file read: <1ms (simple JSON timestamp)
- 99%+ of invocations skip network call (instant)
- Update checks happen transparently without user noticing

### Async vs. Sync

**Why synchronous is correct:**
- Version check happens at CLI startup (already blocking on other I/O)
- Single HTTP request with 10s timeout (acceptable latency)
- Async overhead (event loop, async context) is unnecessary
- Existing MC codebase is synchronous (no refactoring needed)
- `requests` library is already present (no new dependency)

**When async would make sense:**
- If checking multiple APIs in parallel (GitHub + Quay + PyPI)
- If version check ran in background thread while CLI continues
- If MC CLI had async architecture throughout

**Decision:** Use synchronous `requests.get()` for simplicity and consistency with existing codebase.

### Version Comparison Performance

**`packaging` library performance (v26.0):**
- Parsing "2.0.4": ~10 microseconds (0.00001 seconds)
- Comparison: ~1 microsecond (0.000001 seconds)
- Negligible overhead for CLI startup

**Performance improvements in v26.0 (Jan 2026):**
- Version parsing: 2x faster than v24.0
- SpecifierSet parsing: 3x faster than v24.0
- Other operations: up to 5x faster

**Source:** [How we made Python's packaging library 3x faster](https://iscinumpy.dev/post/packaging-faster/)

### Network Timeout Strategy

**Timeout values:**
```python
# GitHub API: 10 second timeout
response = requests.get(url, timeout=10)

# Quay.io API: 10 second timeout
response = requests.get(url, timeout=10)
```

**Why 10 seconds:**
- Typical API response: 200-500ms (fast path)
- Network issues: 5-10s before DNS/connection timeout
- User experience: 10s is acceptable for startup latency
- Prevents hanging indefinitely on network issues

**Graceful degradation:**
- Timeout exception caught and logged
- CLI continues normal operation
- Next invocation (after throttle) retries

## Sources

### Version Comparison

- [PEP 440 – Version Identification and Dependency Specification](https://peps.python.org/pep-0440/) — Official Python versioning standard (HIGH confidence)
- [packaging.version.Version documentation](https://packaging.pypa.io/en/stable/version.html) — Official packaging library docs (HIGH confidence)
- [Python Packaging User Guide - Versioning](https://packaging.python.org/en/latest/discussions/versioning/) — Official guide (HIGH confidence)
- [How we made Python's packaging library 3x faster](https://iscinumpy.dev/post/packaging-faster/) — Performance improvements in v26.0, Jan 2026 (HIGH confidence)

### GitHub API

- [GitHub REST API - Releases](https://docs.github.com/en/rest/releases/releases) — Official documentation (HIGH confidence)
- [REST API endpoints for releases - GitHub Docs](https://developer.github.com/v3/repos/releases/) — Endpoint reference (HIGH confidence)

### Quay.io API

- [Quay.io API Documentation](https://docs.quay.io/api/) — Official documentation (HIGH confidence)
- [Quay Documentation - API Swagger](https://docs.quay.io/api/swagger/) — Official API explorer (HIGH confidence)
- [Docker Registry v2 API - List Tags](https://www.baeldung.com/ops/docker-registry-api-list-images-tags) — Docker Registry API tutorial (MEDIUM confidence)
- [Red Hat Quay API guide](https://docs.redhat.com/en/documentation/red_hat_quay/3/html-single/red_hat_quay_api_guide/index) — Official Red Hat docs (HIGH confidence)

### uv Tool Management

- [uv Tool Management Guide](https://docs.astral.sh/uv/guides/tools/) — Official documentation (HIGH confidence)
- [How to upgrade uv – Python Developer Tooling Handbook](https://pydevtools.com/handbook/how-to/how-to-upgrade-uv/) — 2026 guide (MEDIUM confidence)
- [Installing and managing Python | uv](https://docs.astral.sh/uv/guides/install-python/) — Official uv docs (HIGH confidence)

### Rate Limiting and Throttling

- [requests-ratelimiter · PyPI](https://pypi.org/project/requests-ratelimiter/) — Official PyPI package (HIGH confidence, but NOT recommended for MC CLI)
- [Python file timestamps - note.nkmk.me](https://note.nkmk.me/en/python-os-stat-file-timestamp/) — Timestamp patterns (MEDIUM confidence)

---

*Stack research for: MC CLI Auto-Update and Version Management*
*Researched: 2026-02-11*
*Confidence: HIGH (all core technologies verified via official documentation)*
