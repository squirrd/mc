# Phase 3: Code Cleanup - Research

**Researched:** 2026-01-22
**Domain:** Python project modernization, configuration management, technical debt remediation
**Confidence:** HIGH

## Summary

Phase 3 focuses on cleaning up technical debt and fixing bugs under the safety of test coverage from Phase 2. The core areas are: (1) migrating from environment variables to a TOML config file system, (2) consolidating version management to use pyproject.toml as single source of truth, (3) removing setup.py in favor of modern pyproject.toml-only packaging, and (4) systematically fixing typos in CLI flags and status classes.

The Python ecosystem has standardized on TOML for configuration (Python 3.11+ includes tomllib for reading), pyproject.toml for package metadata (PEP 621), and importlib.metadata for runtime version access. Environment variable migration requires startup detection with helpful error messages providing shell-specific unset instructions. Breaking changes are acceptable in 0.x versions under semantic versioning, making this the ideal time for typo fixes.

**Primary recommendation:** Use TOML config file with platformdirs for cross-platform config location, importlib.metadata for version access, pytest's monkeypatch for testing config changes, and codespell for systematic typo detection.

## Standard Stack

The established libraries/tools for Python configuration and project modernization:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tomllib | stdlib (3.11+) | Read TOML config files | Built into Python 3.11+, official TOML parser (PEP 680) |
| tomli-w | 1.1.0+ | Write TOML config files | Complementary writer for tomllib, simple API |
| platformdirs | 4.0+ | Cross-platform config paths | Handles XDG on Linux, appropriate equivalents on macOS/Windows |
| importlib.metadata | stdlib (3.8+) | Access package version at runtime | Standard way to read installed package metadata |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| codespell | 2.4.0+ | Detect and fix typos | Automated typo detection across codebase |
| tomlkit | 0.13.0+ | Style-preserving TOML | If need to preserve comments/formatting (not needed here) |
| tomli | 2.4.0+ | TOML parser backport | Only for Python <3.11 (project requires 3.8+) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| TOML | INI (configparser) | INI is simpler but less structured, only supports 1-level hierarchy |
| TOML | YAML (PyYAML) | YAML more complex, indentation-sensitive, overkill for simple config |
| TOML | JSON | No comments, less human-friendly for editing |
| platformdirs | Manual XDG paths | Breaks cross-platform compatibility, misses edge cases |
| importlib.metadata | Parse pyproject.toml | Doesn't work for installed packages, fragile in development |

**Installation:**
```bash
# For Python 3.11+
pip install tomli-w platformdirs codespell

# For Python 3.8-3.10 (add backport)
pip install tomli tomli-w platformdirs codespell
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── config/
│   ├── __init__.py          # Public API: load_config(), save_config()
│   ├── manager.py           # Config file I/O, path resolution
│   ├── models.py            # Config data models/schema
│   └── wizard.py            # Interactive setup wizard
├── cli/
│   └── main.py              # Startup: check legacy env vars, load config
└── version.py               # DEPRECATED - remove in favor of importlib.metadata
```

### Pattern 1: Config File Location (Cross-Platform)
**What:** Use platformdirs to get OS-appropriate config directory
**When to use:** Any application-level configuration file
**Example:**
```python
# Source: https://github.com/tox-dev/platformdirs
from platformdirs import user_config_dir
from pathlib import Path

def get_config_path(app_name: str = "mc") -> Path:
    """Get cross-platform config file path.

    Linux: ~/.config/mc/config.toml
    macOS: ~/Library/Application Support/mc/config.toml
    Windows: %LOCALAPPDATA%\\mc\\config.toml
    """
    config_dir = Path(user_config_dir(app_name, appauthor=False))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.toml"
```

### Pattern 2: TOML Config Read/Write
**What:** Use tomllib for reading, tomli_w for writing
**When to use:** Application configuration management
**Example:**
```python
# Source: https://docs.python.org/3/library/tomllib.html
# Source: https://realpython.com/python-toml/
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w

def load_config(path: Path) -> dict:
    """Load TOML config file."""
    with open(path, "rb") as f:
        return tomllib.load(f)

def save_config(path: Path, config: dict) -> None:
    """Save TOML config file."""
    with open(path, "wb") as f:
        tomli_w.dump(config, f)
```

### Pattern 3: Environment Variable Detection with Migration Help
**What:** Detect legacy env vars at startup, fail with helpful migration instructions
**When to use:** Migrating from environment variables to config file
**Example:**
```python
# Source: https://www.freecodecamp.org/news/how-to-work-with-environment-variables-in-python/
import os
import sys

def check_legacy_env_vars():
    """Check for deprecated environment variables and guide migration."""
    legacy_vars = ["MC_BASE_DIR", "RH_API_OFFLINE_TOKEN"]
    found_vars = [var for var in legacy_vars if var in os.environ]

    if not found_vars:
        return

    # Detect shell for tailored instructions
    shell = os.environ.get("SHELL", "").lower()

    if "fish" in shell:
        unset_cmd = "\n".join(f"set -e {var}" for var in found_vars)
    else:  # bash/zsh
        unset_cmd = "\n".join(f"unset {var}" for var in found_vars)

    print(f"ERROR: Legacy environment variables detected: {', '.join(found_vars)}")
    print("\nEnvironment variables are no longer supported.")
    print("Configuration is now managed via config file.")
    print("\nTo migrate:")
    print("1. Remove environment variables:")
    print(f"\n{unset_cmd}\n")
    print("2. Run 'mc config setup' to create config file")
    sys.exit(1)
```

### Pattern 4: Interactive Config Wizard
**What:** Prompt for config values with sensible defaults on first run
**When to use:** Initial setup or config regeneration
**Example:**
```python
# Source: https://click.palletsprojects.com/en/stable/prompts/
# Note: Current project doesn't use Click, use built-in input()
from pathlib import Path

def run_setup_wizard() -> dict:
    """Interactive configuration wizard with defaults."""
    print("MC Configuration Setup")
    print("=" * 50)

    # Prompt with default
    default_base = str(Path.home() / "mc")
    base_dir = input(f"Base directory [{default_base}]: ").strip()
    if not base_dir:
        base_dir = default_base

    # Prompt for required value
    while True:
        offline_token = input("Red Hat API offline token: ").strip()
        if offline_token:
            break
        print("ERROR: Offline token is required")

    return {
        "base_directory": base_dir,
        "api": {
            "offline_token": offline_token
        }
    }
```

### Pattern 5: Version from importlib.metadata
**What:** Read version from installed package metadata, fall back to pyproject.toml in dev
**When to use:** Single source of truth for version string
**Example:**
```python
# Source: https://packaging.python.org/en/latest/discussions/single-source-version/
# Source: https://gist.github.com/benkehoe/066a73903e84576a8d6d911cfedc2df6
from importlib.metadata import version, PackageNotFoundError
import sys
from pathlib import Path

def get_version() -> str:
    """Get package version from metadata or pyproject.toml."""
    try:
        # Works for installed package
        return version("mc-cli")
    except PackageNotFoundError:
        # Development mode: parse pyproject.toml
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        return pyproject["project"]["version"]
```

### Pattern 6: setup.py Removal Verification
**What:** Ensure all metadata migrated to pyproject.toml before removing setup.py
**When to use:** Migrating legacy packaging to modern pyproject.toml-only
**Example:**
```bash
# Source: https://packaging.python.org/en/latest/guides/modernize-setup-py-project/
# Verify installation works without setup.py
pip install -e .

# Verify all metadata preserved
pip show mc-cli

# Verify entry points work
which mc
mc --version

# Build and verify distribution
pip install build
python -m build
pip install dist/mc_cli-*.whl
```

### Anti-Patterns to Avoid
- **Dual version sources:** Don't maintain version in both pyproject.toml and version.py - creates drift
- **Silent env var deprecation:** Don't ignore legacy env vars - users won't know to migrate
- **Config in user home:** Don't use `~/.mcrc` - use platformdirs for OS-appropriate location
- **Manual TOML parsing:** Don't hand-roll TOML parser - use stdlib tomllib
- **Backward compat shims for typos:** Don't accept both `--All` and `--all` - clean break is clearer

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cross-platform config paths | Manual `~/.config` logic | platformdirs.user_config_dir() | Handles XDG env vars, macOS/Windows differences, edge cases |
| TOML parsing | Custom parser | tomllib (3.11+) or tomli | TOML spec has subtypes, datetime handling, escape sequences |
| Version access | Parse pyproject.toml manually | importlib.metadata.version() | Breaks when installed, misses version from git tags |
| Shell detection | Parse $SHELL | os.environ.get("SHELL") + simple string checks | Sufficient for unset instructions, no need for complexity |
| Typo detection | Manual grep | codespell --write-changes | Has dictionary of 1000s of common typos, handles context |
| Interactive prompts | Raw input() validation loops | Built-in input() with defaults (simple use case) | Project doesn't use Click/Typer, input() sufficient for wizard |

**Key insight:** Python ecosystem has standardized on specific tools for these problems. Using standards improves maintainability and reduces bugs from edge cases.

## Common Pitfalls

### Pitfall 1: TOML Read Mode
**What goes wrong:** Opening TOML file in text mode causes UnicodeDecodeError on some systems
**Why it happens:** tomllib.load() requires binary mode, easy to forget
**How to avoid:** Always use `open(path, "rb")` for tomllib, `open(path, "wb")` for tomli_w
**Warning signs:** UnicodeDecodeError, decode errors on Windows

### Pitfall 2: Config Directory Creation
**What goes wrong:** Config file write fails because parent directory doesn't exist
**Why it happens:** platformdirs returns path but doesn't create directory
**How to avoid:** Always call `config_dir.mkdir(parents=True, exist_ok=True)` before writing
**Warning signs:** FileNotFoundError when trying to save config

### Pitfall 3: Python 3.11+ tomllib Import
**What goes wrong:** ImportError for tomllib on Python 3.8-3.10
**Why it happens:** tomllib only added in 3.11, need backport for older versions
**How to avoid:** Conditional import with fallback to tomli package
**Warning signs:** ImportError: No module named 'tomllib'

### Pitfall 4: Version Access in Development
**What goes wrong:** importlib.metadata.version() fails with PackageNotFoundError in development
**Why it happens:** Package not "installed", metadata not available
**How to avoid:** Catch PackageNotFoundError and fall back to parsing pyproject.toml
**Warning signs:** PackageNotFoundError when running from source

### Pitfall 5: Incomplete setup.py Removal
**What goes wrong:** Build fails or metadata missing after removing setup.py
**Why it happens:** Missed migrating some metadata (classifiers, long_description, etc.)
**How to avoid:** Compare `pip show` output before/after, verify build succeeds
**Warning signs:** Missing project description, classifiers, or entry points

### Pitfall 6: Environment Variable Scope
**What goes wrong:** Tests fail because env vars persist across tests
**Why it happens:** os.environ is global state, changes affect other tests
**How to avoid:** Use pytest's monkeypatch fixture for all env var changes
**Warning signs:** Flaky tests, order-dependent test failures

### Pitfall 7: Breaking Changes Without Version Bump
**What goes wrong:** Users confused when flags/behavior change without clear signal
**Why it happens:** Forgot to bump version and document breaking changes
**How to avoid:** Bump minor version (0.1.0 -> 0.2.0), document in CHANGELOG
**Warning signs:** User reports "it stopped working" without code changes

### Pitfall 8: Typo Fixes Breaking Tests
**What goes wrong:** Tests fail after fixing typos in output strings
**Why it happens:** Tests hardcode the typo'd strings for assertion
**How to avoid:** Fix typos in both source and tests atomically in same commit
**Warning signs:** Test failures with "CheckStaus" vs "CheckStatus" mismatches

## Code Examples

Verified patterns from official sources:

### Configuration Manager Module
```python
# Source: Combined from platformdirs docs and tomllib docs
import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w
from platformdirs import user_config_dir

class ConfigManager:
    """Manage application configuration file."""

    def __init__(self, app_name: str = "mc"):
        self.app_name = app_name
        self._config_path: Optional[Path] = None

    @property
    def config_path(self) -> Path:
        """Get config file path, creating directory if needed."""
        if self._config_path is None:
            config_dir = Path(user_config_dir(self.app_name, appauthor=False))
            config_dir.mkdir(parents=True, exist_ok=True)
            self._config_path = config_dir / "config.toml"
        return self._config_path

    def exists(self) -> bool:
        """Check if config file exists."""
        return self.config_path.exists()

    def load(self) -> dict:
        """Load configuration from file."""
        with open(self.config_path, "rb") as f:
            return tomllib.load(f)

    def save(self, config: dict) -> None:
        """Save configuration to file."""
        with open(self.config_path, "wb") as f:
            tomli_w.dump(config, f)
```

### pytest monkeypatch for Environment Variables
```python
# Source: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
import pytest
import os

def test_legacy_env_var_detection(monkeypatch):
    """Test that legacy env vars are detected and cause failure."""
    # Set legacy environment variable
    monkeypatch.setenv("MC_BASE_DIR", "/old/path")

    # Application startup should detect and fail
    with pytest.raises(SystemExit) as exc_info:
        check_legacy_env_vars()

    assert exc_info.value.code == 1

def test_config_loading_isolated(monkeypatch, tmp_path):
    """Test config loading with isolated environment."""
    # Clear any real env vars
    monkeypatch.delenv("MC_BASE_DIR", raising=False)

    # Set up test config
    config_file = tmp_path / "config.toml"
    config_file.write_text('[api]\noffline_token = "test123"\n')

    # Test loads config correctly
    config = load_config(config_file)
    assert config["api"]["offline_token"] == "test123"
```

### Temporary Config Directory Testing
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
import pytest
from pathlib import Path

def test_config_creation(tmp_path):
    """Test config file creation in temporary directory."""
    # tmp_path is a pathlib.Path to a temporary directory
    config_manager = ConfigManager()

    # Override config path to use test directory
    config_manager._config_path = tmp_path / "config.toml"

    # Create config
    test_config = {
        "base_directory": str(tmp_path / "mc"),
        "api": {"offline_token": "test_token"}
    }
    config_manager.save(test_config)

    # Verify file exists and is valid TOML
    assert config_manager.exists()
    loaded = config_manager.load()
    assert loaded == test_config
```

### Automated Typo Detection and Fixing
```bash
# Source: https://github.com/codespell-project/codespell
# Check for typos without fixing
codespell src/ tests/

# Interactive mode: confirm each fix
codespell --write-changes --interactive 3 src/ tests/

# Automatic fix with custom ignore list
codespell --write-changes \
  --skip="*.pyc,*.git" \
  --ignore-words=.codespell-ignore \
  src/ tests/

# Skip specific directories
codespell --skip="./venv,./build,./dist" .
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| setup.py only | pyproject.toml (PEP 621) | 2020 (PEP 621) | setup.py now optional, declarative metadata |
| No TOML in stdlib | tomllib builtin | Python 3.11 (2022) | No need for third-party TOML parser |
| Manual config paths | platformdirs | ~2019 (tox-dev) | Cross-platform config location standardized |
| setup.cfg + setup.py | pyproject.toml only | 2024-2025 | Single file for all metadata |
| License classifiers | SPDX expressions (PEP 639) | Dec 2024 | License:: classifiers deprecated by Feb 2026 |
| String version parsing | importlib.metadata | Python 3.8+ (2019) | Standard API for package metadata |

**Deprecated/outdated:**
- **setup.py for metadata:** Use pyproject.toml [project] table instead (PEP 621)
- **License:: classifiers:** Use SPDX expressions in `license =` field (PEP 639, deadline Feb 2026)
- **version.py files:** Use importlib.metadata.version() with pyproject.toml as source
- **toml package:** Use tomllib (3.11+) or tomli (backport), toml package is unmaintained
- **Manual XDG paths:** Use platformdirs.user_config_dir() instead of hardcoded ~/.config

## Open Questions

Things that couldn't be fully resolved:

1. **Config file format preferences**
   - What we know: TOML is standard for Python tooling, has stdlib support, human-editable
   - What's unclear: Whether project maintainer prefers INI for simplicity
   - Recommendation: Use TOML based on (a) CONTEXT.md gives Claude discretion, (b) project already uses pyproject.toml, (c) stdlib support in 3.11+, (d) better structure than INI

2. **Migration timeline for env vars**
   - What we know: User wants fail-fast approach with migration help
   - What's unclear: Whether to support both during transition period
   - Recommendation: Clean break per CONTEXT.md "no backward compatibility shims" - fail immediately if env vars detected

3. **Interactive wizard invocation**
   - What we know: Need wizard on first run when config missing
   - What's unclear: Whether to auto-run wizard or require explicit `mc config setup` command
   - Recommendation: Auto-run on first invocation of any command for better UX, but also expose `mc config setup` for explicit re-configuration

4. **Version bump strategy**
   - What we know: 0.x versions allow breaking changes in minor bumps (0.1.0 -> 0.2.0)
   - What's unclear: Whether to bump to 0.2.0 or wait for 1.0.0
   - Recommendation: Bump to 0.2.0 - signals breaking changes, maintains 0.x development status

## Sources

### Primary (HIGH confidence)
- Python tomllib documentation: https://docs.python.org/3/library/tomllib.html
- Python importlib.metadata: https://packaging.python.org/en/latest/discussions/single-source-version/
- pytest monkeypatch documentation: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
- pytest tmp_path documentation: https://docs.pytest.org/en/stable/how-to/tmp_path.html
- platformdirs GitHub: https://github.com/tox-dev/platformdirs
- PEP 621 (pyproject.toml metadata): https://peps.python.org/pep-0621/
- PEP 639 (license expressions): https://peps.python.org/pep-0639/
- PEP 680 (tomllib): https://peps.python.org/pep-0680/

### Secondary (MEDIUM confidence)
- Real Python TOML guide: https://realpython.com/python-toml/
- Python Packaging User Guide (modernize setup.py): https://packaging.python.org/en/latest/guides/modernize-setup-py-project/
- codespell project: https://github.com/codespell-project/codespell
- PyOpenSci changelog guide: https://www.pyopensci.org/python-package-guide/documentation/repository-files/changelog-file.html
- Semantic Versioning spec: https://semver.org/

### Tertiary (LOW confidence)
- WebSearch: "Python application config file best practices 2026" - Found general consensus on TOML for Python projects
- WebSearch: "Python detect user shell" - Found $SHELL environment variable approach
- Medium articles on pyproject.toml migration - Provided practical examples but not authoritative

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All recommendations from official docs (stdlib, PyPA)
- Architecture: HIGH - Patterns from official documentation and established projects
- Pitfalls: MEDIUM - Based on common issues in Python community, some from experience
- Config file location: HIGH - platformdirs is widely used (pytest, black, tox)
- TOML handling: HIGH - Official stdlib and recommended companion libraries
- Version management: HIGH - Official Python Packaging User Guide recommendations
- Testing patterns: HIGH - Official pytest documentation
- Typo detection: MEDIUM - codespell is established but manual fixes may still be needed

**Research date:** 2026-01-22
**Valid until:** 2026-04-22 (90 days - Python packaging ecosystem is stable)

**Critical deadline:** 2026-02-18 - setuptools will no longer support deprecated license classifiers (PEP 639)
