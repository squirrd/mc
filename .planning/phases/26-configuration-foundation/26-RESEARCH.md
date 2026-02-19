# Phase 26: Configuration Foundation - Research

**Researched:** 2026-02-19
**Domain:** Python TOML configuration management with atomic writes and concurrent access patterns
**Confidence:** HIGH

## Summary

This phase extends the existing TOML configuration system (built in v1.0) to persist version management fields (`pinned_mc` and `last_check` in a `[version]` section) with safe atomic write patterns. The current implementation uses `tomli/tomllib` for reading and `tomli_w` for writing, which returns plain Python dicts without preserving comments or formatting.

User decisions from CONTEXT.md:
- **Skip file locking** - assume single-user/single-process usage (typical CLI usage pattern)
- **Use temp file + rename pattern** for atomic writes (prevents partial writes on crash)
- **Keep implementation simple** - user emphasized "keep it simple" multiple times
- **Field names**: `pinned_mc` (not `pinned_mc_version`) and `last_check` (not `last_version_check`)
- **Default value**: `"latest"` for `pinned_mc` when field missing (backward compatibility)

**Primary recommendation:** Use Python 3.11+ stdlib `tomllib` for reads (already in use), `tomli_w` for writes (already in use), stdlib `tempfile.NamedTemporaryFile` with `os.replace()` for atomic writes, and Unix epoch float timestamps (consistent with existing cache.py). No additional dependencies needed.

## Standard Stack

The project already uses the modern Python TOML stack. No new dependencies required.

### Core (Already in Use)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tomllib | stdlib 3.11+ | TOML parsing (read-only) | Python's official TOML parser (PEP 680), returns plain dicts |
| tomli | 2.4.0+ | TOML parsing backport | Drop-in backport for tomllib, used for Python <3.11 |
| tomli_w | 1.0.0+ | TOML serialization | Write companion to tomli/tomllib, lightweight and fast |

### Not Needed
| Library | Why Not |
|---------|---------|
| tomlkit | 5x slower than tomli_w, style-preserving features not needed (new `[version]` section) |
| filelock | File locking skipped per user decision (single-process assumption) |
| atomicwrites | Deprecated; Python 3's stdlib `os.replace()` sufficient |

**Installation:**
No new packages needed - already in pyproject.toml dependencies.

## Architecture Patterns

### Current Config Structure (v2.0.3)
```toml
# ~/mc/config/config.toml
base_directory = "~/mc"

[api]
rh_api_offline_token = ""

[salesforce]
username = ""
password = ""
security_token = ""

[podman]
timeout = 120
retry_attempts = 3
socket_path = ""
```

### Target Config Structure (v2.0.4)
```toml
# ~/mc/config/config.toml
base_directory = "~/mc"

[api]
rh_api_offline_token = ""

[salesforce]
username = ""
password = ""
security_token = ""

[podman]
timeout = 120
retry_attempts = 3
socket_path = ""

[version]
pinned_mc = "latest"           # or "2.0.4" when pinned
last_check = 1739990400.0      # Unix epoch timestamp (float)
```

### Pattern 1: Atomic Write with Temp File + Rename
**What:** Write to temporary file in same directory, then atomically replace target file using `os.replace()`
**When to use:** All TOML config write operations (prevents partial writes on crash/interrupt)
**Example:**
```python
# Source: https://docs.python.org/3/library/tempfile.html + https://zetcode.com/python/os-replace/
import os
import tempfile
from pathlib import Path
import tomli_w

def save_config_atomic(config_path: Path, config: dict[str, Any]) -> None:
    """Save config to file atomically using temp file + rename pattern."""
    # Create temp file in same directory (ensures same filesystem)
    temp = tempfile.NamedTemporaryFile(
        mode='wb',
        dir=config_path.parent,  # CRITICAL: same directory as target
        prefix='.config_',       # hidden temp file
        suffix='.tmp',
        delete=False             # manual cleanup for atomic rename
    )

    try:
        # Write config to temp file
        tomli_w.dump(config, temp)
        temp.flush()
        os.fsync(temp.fileno())  # Force write to disk (durability)
        temp.close()

        # Atomic replace: either complete success or complete failure
        os.replace(temp.name, config_path)
    except Exception:
        # Cleanup temp file on failure
        temp.close()
        try:
            os.unlink(temp.name)
        except OSError:
            pass  # Temp file already gone, ignore
        raise
```

**Why os.replace() not os.rename():**
- `os.replace()` works across different filesystems (Windows MoveFileEx, Unix rename(2))
- `os.replace()` overwrites destination atomically on all platforms
- `os.rename()` fails if destination exists on Windows

### Pattern 2: Backward Compatible Config Reading with Defaults
**What:** Return default values when new fields missing (v1.0 configs don't have `[version]` section)
**When to use:** Reading version management fields from config
**Example:**
```python
# Source: https://realpython.com/python-toml/ + existing mc/config/manager.py
def get_version_config(config_manager: ConfigManager) -> dict[str, Any]:
    """Get version config with backward-compatible defaults.

    Returns:
        dict with keys: pinned_mc (str), last_check (float | None)
    """
    try:
        config = config_manager.load()
        version_section = config.get('version', {})
    except FileNotFoundError:
        # No config file yet
        version_section = {}

    return {
        'pinned_mc': version_section.get('pinned_mc', 'latest'),  # Default: "latest"
        'last_check': version_section.get('last_check', None),    # Default: None (never checked)
    }
```

### Pattern 3: Unix Epoch Timestamps (Consistent with Existing Cache)
**What:** Store timestamps as Unix epoch floats (seconds since 1970-01-01 UTC)
**When to use:** `last_check` timestamp field
**Example:**
```python
# Source: Existing mc/utils/cache.py line 170, mc/utils/auth.py line 49
import time

# Get current timestamp for storage
current_timestamp = time.time()  # Returns float: 1739990400.123456

# Check if check is recent (within 1 hour = 3600 seconds)
def should_check_version(last_check: float | None) -> bool:
    """Return True if version check needed (>1 hour since last check)."""
    if last_check is None:
        return True  # Never checked before

    elapsed = time.time() - last_check
    return elapsed >= 3600  # 1 hour in seconds
```

**Why Unix epoch (float) not ISO 8601 string:**
- **Consistency**: Existing `cache.py` uses `time.time()` for `cached_at` (line 170)
- **Consistency**: Existing `auth.py` uses `time.time()` for `expires_at` (line 82)
- **Simplicity**: Direct subtraction for elapsed time calculation (no parsing)
- **Efficiency**: 8 bytes (float64) vs 20+ bytes (ISO string)
- **Stdlib**: No imports needed beyond `time` module (already used everywhere)

### Anti-Patterns to Avoid
- **Don't use ISO 8601 strings for last_check** - breaks consistency with cache.py and auth.py timestamp patterns
- **Don't use tomlkit for simple writes** - 5x slower, style-preserving features wasted on new section
- **Don't add file locking** - user explicitly decided to skip (single-process assumption)
- **Don't use os.rename()** - use `os.replace()` for cross-platform atomic replace
- **Don't create temp file in /tmp** - must be same directory as target (same filesystem for atomic replace)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file writes | Custom write + rename | `tempfile.NamedTemporaryFile` + `os.replace()` | Handles edge cases (permissions, cleanup on error, cross-platform), security (0600 mode), same-filesystem guarantee |
| TOML serialization | Custom TOML writer | `tomli_w.dump()` | Already in dependencies, handles escaping/quoting/types correctly |
| Backward compatibility | Manual key checking | `dict.get(key, default)` | Pythonic, concise, handles missing sections and missing keys |
| Timestamp arithmetic | String parsing | `time.time()` subtraction | Direct float subtraction, no timezone bugs, consistent with existing code |

**Key insight:** Python stdlib + existing dependencies already handle all needed patterns. The "keep it simple" directive means using what's already there, not adding new libraries or custom implementations.

## Common Pitfalls

### Pitfall 1: Temp File on Different Filesystem
**What goes wrong:** `os.replace()` fails if temp file not on same filesystem as target
**Why it happens:** Using system temp directory (`/tmp` or `%TEMP%`) instead of target directory
**How to avoid:** Pass `dir=config_path.parent` to `NamedTemporaryFile()` (creates temp in same dir as target)
**Warning signs:** `OSError: [Errno 18] Invalid cross-device link` on some systems

### Pitfall 2: Forgetting fsync() Before Rename
**What goes wrong:** Power loss after rename but before disk write → target file exists but empty/partial
**Why it happens:** OS buffers writes; rename() updates directory metadata before data written
**How to avoid:** Call `os.fsync(temp.fileno())` before `temp.close()` and `os.replace()`
**Warning signs:** File corruption reports after crashes, integration tests pass but production fails

### Pitfall 3: Not Cleaning Up Temp Files on Error
**What goes wrong:** `.config_*.tmp` files accumulate in config directory after errors
**Why it happens:** Exception during write leaves temp file orphaned
**How to avoid:** Wrap `os.replace()` in try/except, call `os.unlink(temp.name)` in except block
**Warning signs:** `ls ~/.mc/config/` shows multiple `.config_*.tmp` files

### Pitfall 4: Using delete=True with NamedTemporaryFile for Atomic Writes
**What goes wrong:** File deleted on `close()`, before `os.replace()` can use it
**Why it happens:** Default `delete=True` auto-removes file when closed
**How to avoid:** Always use `delete=False` when using temp file for atomic rename pattern
**Warning signs:** `FileNotFoundError` at `os.replace()` call

### Pitfall 5: Mixing Timestamp Formats
**What goes wrong:** Inconsistent timestamp handling across modules (some float, some ISO string)
**Why it happens:** Not checking existing codebase patterns before implementing
**How to avoid:** Grep for existing timestamp usage: `cache.py` line 170 and `auth.py` line 82 both use `time.time()` (float)
**Warning signs:** Type errors when comparing timestamps, parsing errors

### Pitfall 6: Breaking Backward Compatibility on Missing Fields
**What goes wrong:** KeyError when reading old config files without `[version]` section
**Why it happens:** Accessing `config['version']['pinned_mc']` directly without checking existence
**How to avoid:** Always use `config.get('version', {}).get('pinned_mc', 'latest')` pattern
**Warning signs:** Errors reported by users with v2.0.3 configs after upgrading to v2.0.4

## Code Examples

Verified patterns from official sources and existing codebase:

### Reading Version Config with Backward Compatibility
```python
# Source: Existing mc/config/manager.py get() method (line 92-116)
def get_pinned_version(config_manager: ConfigManager) -> str:
    """Get pinned MC version from config with backward-compatible default.

    Returns:
        "latest" if not pinned or config missing, otherwise version string like "2.0.4"
    """
    return config_manager.get('version.pinned_mc', 'latest')

def get_last_check_timestamp(config_manager: ConfigManager) -> float | None:
    """Get last version check timestamp from config.

    Returns:
        Unix epoch timestamp (float) or None if never checked
    """
    return config_manager.get('version.last_check', None)
```

### Writing Version Config Atomically
```python
# Source: Existing mc/config/manager.py save() method + atomic write pattern
import os
import tempfile
from pathlib import Path
import tomli_w
from mc.config.manager import ConfigManager

def update_version_config(
    config_manager: ConfigManager,
    pinned_mc: str | None = None,
    last_check: float | None = None
) -> None:
    """Update version config fields atomically.

    Args:
        config_manager: Config manager instance
        pinned_mc: New pinned version or None to keep current
        last_check: New timestamp or None to keep current
    """
    # Load current config (or get defaults)
    try:
        config = config_manager.load()
    except FileNotFoundError:
        from mc.config.models import get_default_config
        config = get_default_config()

    # Ensure [version] section exists
    if 'version' not in config:
        config['version'] = {}

    # Update only specified fields
    if pinned_mc is not None:
        config['version']['pinned_mc'] = pinned_mc
    if last_check is not None:
        config['version']['last_check'] = last_check

    # Atomic write using temp file + rename
    config_path = config_manager.get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    temp = tempfile.NamedTemporaryFile(
        mode='wb',
        dir=config_path.parent,
        prefix='.config_',
        suffix='.tmp',
        delete=False
    )

    try:
        tomli_w.dump(config, temp)
        temp.flush()
        os.fsync(temp.fileno())
        temp.close()
        os.replace(temp.name, config_path)
    except Exception:
        temp.close()
        try:
            os.unlink(temp.name)
        except OSError:
            pass
        raise
```

### Checking if Version Check Needed (Hourly Throttle)
```python
# Source: Requirement VCHK-03 + existing cache.py _is_expired pattern
import time

HOURLY_THROTTLE_SECONDS = 3600  # 1 hour

def should_check_version(last_check: float | None) -> bool:
    """Return True if version check needed (hourly throttle).

    Args:
        last_check: Unix epoch timestamp of last check, or None if never checked

    Returns:
        True if >1 hour elapsed since last check or never checked
    """
    if last_check is None:
        return True  # Never checked before

    elapsed = time.time() - last_check
    return elapsed >= HOURLY_THROTTLE_SECONDS
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| toml library (deprecated) | tomllib/tomli + tomli_w | Python 3.11 (2022) | Stdlib support, faster parsing, no maintenance |
| atomicwrites library | os.replace() + tempfile | Python 3.3+ (2026 best practice) | Fewer dependencies, stdlib sufficient |
| ISO 8601 string timestamps | Unix epoch float timestamps | Established in v1.0 (cache.py, auth.py) | Simple arithmetic, no parsing/timezone bugs |
| File locking (fcntl/filelock) | Single-process assumption | v2.0.4 (user decision) | Simpler implementation, fewer edge cases |

**Deprecated/outdated:**
- **toml (PyPI)**: Deprecated, replaced by tomllib in stdlib (PEP 680)
- **atomicwrites**: Maintainer states Python 3's os.replace() is sufficient
- **os.rename()**: Use os.replace() for atomic overwrites (Windows compatibility)

## Open Questions

Things that couldn't be fully resolved:

1. **Should we validate pinned_mc value format when writing?**
   - What we know: User can set `pinned_mc = "2.0.4"` or `"latest"`
   - What's unclear: Should we validate version string format (PEP 440) or allow any string?
   - Recommendation: Defer validation to version checking phase (Phase 27) - config layer just persists strings

2. **Should we migrate old configs to add [version] section immediately?**
   - What we know: Backward compat pattern returns defaults when section missing
   - What's unclear: Auto-migrate on first write vs lazy migration (only create section when needed)
   - Recommendation: Lazy migration - only create `[version]` section when first version check completes (simpler)

3. **Should we document the temp file naming convention?**
   - What we know: Using `.config_*.tmp` prefix (hidden file + .tmp suffix)
   - What's unclear: Users might see these files on crashes and wonder what they are
   - Recommendation: Add comment in code, no user-facing docs needed (keep it simple)

## Sources

### Primary (HIGH confidence)
- Python 3.13 stdlib documentation - [tempfile](https://docs.python.org/3/library/tempfile.html)
- Python 3.13 stdlib documentation - [tomllib](https://docs.python.org/3/library/tomllib.html)
- PEP 680: tomllib in stdlib - [peps.python.org](https://peps.python.org/pep-0680/)
- tomli PyPI package - [pypi.org/project/tomli](https://pypi.org/project/tomli/)
- tomli_w PyPI package - [pypi.org/project/tomli-w](https://tomli-w.readthedocs.io/)
- os.replace() documentation - [zetcode.com](https://zetcode.com/python/os-replace/)
- Existing mc/config/manager.py implementation (lines 76-128)
- Existing mc/utils/cache.py timestamp usage (line 170: `time.time()`)
- Existing mc/utils/auth.py timestamp usage (line 82: `time.time()`)

### Secondary (MEDIUM confidence)
- Real Python TOML guide - [realpython.com/python-toml](https://realpython.com/python-toml/)
- tomlkit documentation - [github.com/python-poetry/tomlkit](https://github.com/python-poetry/tomlkit) (evaluated but not needed)
- Atomic write pattern - [activestate.com recipe](https://code.activestate.com/recipes/579097-safely-and-atomically-write-to-a-file/)
- File locking libraries - [py-filelock.readthedocs.io](https://py-filelock.readthedocs.io/) (evaluated but not needed per user decision)
- Timestamp best practices - [devtoolbox.dedyn.io/epoch-unix-timestamp-guide](https://devtoolbox.dedyn.io/blog/epoch-unix-timestamp-guide)

### Tertiary (LOW confidence)
- WebSearch results on concurrent write testing - limited specific guidance for config files
- Poetry/tomlkit concurrent safety - no explicit documentation found (assume not thread-safe)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - tomllib/tomli/tomli_w already in use, well-documented stdlib/PyPI packages
- Architecture: HIGH - atomic write pattern well-established, existing timestamp patterns clear from codebase
- Pitfalls: HIGH - based on official docs and common production issues (cross-filesystem, fsync timing, cleanup)
- Testing strategies: MEDIUM - concurrent write testing patterns less documented, but single-process assumption simplifies

**Research date:** 2026-02-19
**Valid until:** 60 days (stable domain - TOML stdlib and atomic write patterns don't change frequently)

**User constraints applied:**
- Skip file locking (CONTEXT.md line 23-25)
- Keep implementation simple (CONTEXT.md line 29, 44, 51)
- Field names: `pinned_mc` and `last_check` (CONTEXT.md line 18)
- Default `pinned_mc = "latest"` (CONTEXT.md line 19, 33)
- Use `[version]` section (CONTEXT.md line 17)
