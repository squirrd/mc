# Phase 14: Installation & Distribution - Research

**Researched:** 2026-02-01
**Domain:** Python CLI tool distribution with uv
**Confidence:** HIGH

## Summary

This research investigated modern Python CLI tool distribution workflows using uv, focusing on three distinct use cases: development, UAT (User Acceptance Testing), and production installation. The investigation covered uv's tool management capabilities, Python packaging standards, entry point mechanisms, and testing strategies.

**Key findings:**
- uv provides a unified, fast (10-100x faster than pip) package and tool manager written in Rust
- Three workflows map to uv commands: development (uv run), UAT (uv tool install/uninstall), production (uv tool install)
- Entry points in [project.scripts] automatically generate portable wrapper scripts, eliminating hardcoded shebang issues
- The mc-cli project already has correct [project.scripts] configuration but needs a [build-system] section
- Testing can leverage pytest-console-scripts plugin for entry point validation

**Primary recommendation:** Use uv's project and tool management features to support all three workflows. Development uses `uv run` with automatic editable installs, UAT uses `uv tool install -e .` for temporary testing, and production uses `uv tool install` from PyPI or git.

## Standard Stack

The established tools for Python CLI distribution in 2026:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| uv | 0.5+ | Package/project/tool manager | Official successor to pip/pipx/poetry, 10-100x faster, unified workflow |
| setuptools/hatchling | latest | Build backend | PEP 517/518 compliant, generates entry point wrappers |
| pyproject.toml | - | Project metadata | PEP 621 standard, declarative configuration |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-console-scripts | 1.4+ | Testing CLI entry points | Integration testing of installed commands |
| pytest | 9.0+ | Test framework | Already in project, unit and integration tests |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| uv | pipx | pipx only handles tools, not full project management; uv 10-100x faster |
| uv | poetry | Poetry 2.0+ supports [project] table, but uv is faster and simpler for CLI tools |
| setuptools | hatchling | Hatchling is PyPA-maintained, modern, but setuptools more established |

**Installation:**
```bash
# Install uv (one-time system setup)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv

# Ensure PATH is configured
uv tool update-shell
```

## Architecture Patterns

### Recommended Project Structure
```
mc-cli/
├── pyproject.toml       # Project metadata, dependencies, entry points
├── .python-version      # Pin Python version (3.11+)
├── uv.lock             # Lockfile for reproducible installs
├── .venv/              # Virtual environment (auto-created)
├── src/
│   └── mc/
│       ├── __init__.py
│       └── cli/
│           └── main.py  # Entry point function: main()
├── tests/
│   ├── test_cli.py     # Unit tests
│   └── test_entry_points.py  # Integration tests for CLI
└── README.md           # Installation instructions
```

### Pattern 1: Project Configuration (pyproject.toml)
**What:** Complete project metadata with build system and entry points
**When to use:** Every Python CLI project
**Example:**
```toml
# Source: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
[build-system]
requires = ["setuptools>=61.0", "wheel", "setuptools_scm[toml]>=6.2"]
build-backend = "setuptools.build_meta"

[project]
name = "mc-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "backoff>=2.2.1",
    "platformdirs>=4.0.0",
    # ... other dependencies
]

[project.scripts]
mc = "mc.cli.main:main"

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]
```

### Pattern 2: Entry Point Function
**What:** Entry point must be a callable function, not module-level code
**When to use:** Every [project.scripts] entry
**Example:**
```python
# Source: https://setuptools.pypa.io/en/latest/userguide/entry_point.html
# src/mc/cli/main.py
def main() -> int:
    """Main entry point for mc CLI."""
    # CLI logic here
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

### Pattern 3: Development Workflow
**What:** Use uv run for all development tasks
**When to use:** Development phase (Phase 14 workflow 1)
**Example:**
```bash
# Source: https://docs.astral.sh/uv/guides/projects/
# First run creates .venv and uv.lock automatically
uv run mc --help

# Run tests
uv run pytest

# Run type checker
uv run mypy src/

# Add new dependency
uv add rich

# Upgrade dependencies
uv lock --upgrade-package requests
```

### Pattern 4: UAT Workflow
**What:** Install from local directory for temporary testing
**When to use:** User acceptance testing (Phase 14 workflow 2)
**Example:**
```bash
# Source: https://docs.astral.sh/uv/reference/cli/#uv-tool-install
# Install from local directory (editable or non-editable)
cd /path/to/mc-cli
uv tool install -e .  # Editable for testing changes

# Test the installed tool
mc --help
mc cases list

# View installed tools
uv tool list --show-paths

# Uninstall when done
uv tool uninstall mc-cli
```

### Pattern 5: Production Workflow
**What:** Global installation from PyPI or git
**When to use:** Production deployment (Phase 14 workflow 3)
**Example:**
```bash
# Source: https://docs.astral.sh/uv/guides/tools/
# From PyPI (when published)
uv tool install mc-cli

# From git repository
uv tool install git+https://github.com/user/mc-cli.git

# From git tag/branch
uv tool install git+https://github.com/user/mc-cli.git@v2.0.0

# Upgrade
uv tool upgrade mc-cli

# Uninstall
uv tool uninstall mc-cli
```

### Anti-Patterns to Avoid
- **Hardcoded shebangs:** Never create bin/mc with `#!/path/to/venv/python`. Use [project.scripts] instead.
- **Manual activation:** Don't use `source .venv/bin/activate`. Use `uv run` for automatic environment management.
- **setup.py:** Deprecated. Use pyproject.toml with [build-system] and [project] tables.
- **requirements.txt for projects:** Use pyproject.toml dependencies and uv.lock for reproducibility.
- **Mixing pip and uv:** If using uv, stick with uv commands. Avoid `pip install` in uv-managed projects.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CLI wrapper scripts | Custom bin/mc with shebang | [project.scripts] entry points | Setuptools auto-generates portable wrappers, handles shebang correctly across platforms |
| Virtual environment management | Custom venv scripts | uv run / uv sync | Automatic syncing, dependency resolution, lockfile management |
| Dependency pinning | Manual requirements.txt | uv.lock | Cross-platform, exact version locking, faster resolution |
| Tool installation | Custom install scripts | uv tool install | Isolated environments, PATH management, upgrade/uninstall support |
| Testing CLI commands | subprocess.run(['mc', ...]) | pytest-console-scripts | In-process or subprocess modes, stdout/stderr capture, fixture-based |

**Key insight:** Python's packaging ecosystem has standardized on entry points for CLI tools. Manually creating executable scripts is error-prone (shebang portability, PATH issues, environment activation) and unnecessary.

## Common Pitfalls

### Pitfall 1: Missing [build-system] Section
**What goes wrong:** Project can't be installed with `uv tool install` or `pip install`, even though [project.scripts] is defined.
**Why it happens:** The [build-system] section tells installers how to build the package. Without it, there's no build backend to generate entry point wrappers.
**How to avoid:** Always include [build-system] in pyproject.toml for installable packages.
**Warning signs:** Errors like "No pyproject.toml with build-system found" or "Could not build wheels for mc-cli"

```toml
# Required for installable packages
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"
```

### Pitfall 2: Entry Point Function vs Module
**What goes wrong:** Entry point like `mc = "mc.cli.main"` (pointing to module) instead of `mc = "mc.cli.main:main"` (pointing to function).
**Why it happens:** Confusion about entry point syntax. Console scripts must call functions.
**How to avoid:** Entry point format is always `command = "package.module:function"`
**Warning signs:** Import errors or "module is not callable" when running installed command

### Pitfall 3: uv run vs uvx Confusion
**What goes wrong:** Using `uvx mc` to test local project instead of `uv run mc`, causing "package not found" errors.
**Why it happens:** `uvx` (alias for `uv tool run`) searches for PyPI packages, not local projects.
**How to avoid:** Use `uv run` for local project development, `uvx` only for published packages.
**Warning signs:** "No executables provided by mc" when package isn't published to PyPI

### Pitfall 4: PATH Not Configured for uv Tools
**What goes wrong:** `uv tool install mc-cli` succeeds but `mc` command not found in shell.
**Why it happens:** Tool executables install to `~/.local/bin` which may not be in PATH.
**How to avoid:** Run `uv tool update-shell` once to configure shell, or manually add to PATH.
**Warning signs:** "command not found: mc" after successful installation

### Pitfall 5: Conda Environment Interference
**What goes wrong:** `uv pip` installs to conda environment instead of .venv, causing version mismatches.
**Why it happens:** uv searches VIRTUAL_ENV, then CONDA_PREFIX, then .venv. Conda takes precedence.
**How to avoid:** Use `uv sync` and `uv run` instead of `uv pip` for project management.
**Warning signs:** Dependencies installed but tests fail with import errors

### Pitfall 6: Testing Without Installation
**What goes wrong:** Integration tests for CLI commands fail because entry points aren't registered.
**Why it happens:** Entry points only exist after package installation (even editable).
**How to avoid:** Use `uv run pytest` which auto-installs project in editable mode before running tests.
**Warning signs:** ImportError or ModuleNotFoundError in tests for CLI entry points

### Pitfall 7: Reinstallation Required After Changes
**What goes wrong:** Changes to pyproject.toml (new dependencies, entry points) don't take effect.
**Why it happens:** Editable installs reflect code changes but not metadata changes.
**How to avoid:** After modifying pyproject.toml, run `uv sync` to update the environment.
**Warning signs:** New dependencies not found, new entry points not available

## Code Examples

Verified patterns from official sources:

### Testing Entry Points with pytest-console-scripts
```python
# Source: https://pypi.org/project/pytest-console-scripts/
# tests/test_entry_points.py
from pytest_console_scripts import ScriptRunner

def test_mc_version(script_runner: ScriptRunner) -> None:
    """Test mc --version command."""
    result = script_runner.run(['mc', '--version'])
    assert result.returncode == 0
    assert 'mc-cli' in result.stdout

def test_mc_help(script_runner: ScriptRunner) -> None:
    """Test mc --help command."""
    result = script_runner.run(['mc', '--help'])
    assert result.returncode == 0
    assert 'usage:' in result.stdout.lower()
```

### Testing in Subprocess Mode for Real-World Simulation
```python
# Source: https://pypi.org/project/pytest-console-scripts/
import pytest

@pytest.mark.script_launch_mode('subprocess')
def test_mc_real_execution(script_runner: ScriptRunner) -> None:
    """Test mc in subprocess mode (closer to real usage)."""
    result = script_runner.run(['mc', 'cases', 'list'], check=True)
    assert result.returncode == 0
```

### Development Workflow Script
```bash
# Source: https://docs.astral.sh/uv/guides/projects/
#!/usr/bin/env bash
# scripts/dev-setup.sh

set -e

# Install uv if not present
if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Configure shell PATH for uv tools
uv tool update-shell

# Sync project dependencies
uv sync

echo "Development environment ready!"
echo "Run: uv run mc --help"
```

### UAT Testing Script
```bash
# Source: https://docs.astral.sh/uv/reference/cli/#uv-tool-install
#!/usr/bin/env bash
# scripts/uat-install.sh

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Installing mc-cli for UAT testing..."
uv tool install -e "${PROJECT_DIR}"

echo "Installation complete. Testing..."
mc --version
mc --help

echo ""
echo "UAT installation successful!"
echo "To uninstall: uv tool uninstall mc-cli"
```

### Production Installation Documentation
```markdown
<!-- Source: https://www.pyopensci.org/python-package-guide/documentation/repository-files/readme-file-best-practices.html -->
# mc-cli Installation

## Prerequisites
- Python 3.11 or later
- uv package manager

## Install uv
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Configure shell (one-time)
uv tool update-shell
```

## Install mc-cli

### From PyPI (when published)
```bash
uv tool install mc-cli
```

### From Git Repository
```bash
# Latest version
uv tool install git+https://github.com/user/mc-cli.git

# Specific version
uv tool install git+https://github.com/user/mc-cli.git@v2.0.0
```

## Verify Installation
```bash
mc --version
mc --help
```

## Upgrade
```bash
uv tool upgrade mc-cli
```

## Uninstall
```bash
uv tool uninstall mc-cli
```
```

### CI/CD Workflow for Testing Installations
```yaml
# Source: https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python
# .github/workflows/test-installation.yml
name: Test Installation Methods

on: [push, pull_request]

jobs:
  test-editable-install:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Test development workflow
        run: |
          uv run pytest
          uv run mc --version

  test-tool-install:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - name: Test UAT workflow
        run: |
          uv tool install -e .
          mc --version
          mc --help
          uv tool uninstall mc-cli
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| setup.py | pyproject.toml [project] table | PEP 621 (2020), widely adopted 2023+ | Declarative metadata, tool-agnostic |
| setup.cfg | pyproject.toml | PEP 621 (2020) | Single source of truth |
| requirements.txt | dependencies in [project] | PEP 621 (2020) | Better dependency resolution |
| pipx | uv tool | uv released Aug 2023, matured 2024+ | 10-100x faster, unified tooling |
| pip + venv | uv project management | 2024-2025 | Automatic locking, faster resolution |
| #!/usr/bin/env python | Entry points auto-generate shebangs | Longstanding, emphasized 2020+ | Cross-platform portability |

**Deprecated/outdated:**
- **setup.py:** Still works but discouraged for new projects. Use pyproject.toml.
- **python setup.py install:** Removed in setuptools 58+. Use pip/uv install.
- **pipenv:** Superseded by poetry/uv for most use cases. Development stalled.
- **Manual PATH manipulation:** uv tool update-shell handles automatically.

## Open Questions

Things that couldn't be fully resolved:

1. **PyPI Publishing Workflow**
   - What we know: uv can build packages, but publishing workflow not fully documented
   - What's unclear: Integration with PyPI publishing (twine equivalent in uv)
   - Recommendation: Research in Phase 15 (if publishing to PyPI is required). For now, focus on git-based distribution.

2. **Windows PATH Configuration**
   - What we know: Executables install to %USERPROFILE%\.local\bin on Windows
   - What's unclear: Whether uv tool update-shell works reliably on all Windows shells (cmd, PowerShell, Git Bash)
   - Recommendation: Test Windows installation in UAT phase, document manual PATH setup as fallback

3. **Conda Compatibility**
   - What we know: Conda environments can interfere with uv pip commands
   - What's unclear: Best practices when users have conda installed but don't want to use it
   - Recommendation: Document workaround (use uv run/sync, not uv pip) and consider detecting conda in installation tests

## Sources

### Primary (HIGH confidence)
- [uv Official Documentation](https://docs.astral.sh/uv/) - Tool management, project workflows
- [uv Concepts: Tools](https://docs.astral.sh/uv/concepts/tools/) - Tool installation architecture
- [uv Reference: Storage](https://docs.astral.sh/uv/reference/storage/) - Directory structure
- [uv Reference: Environment Variables](https://docs.astral.sh/uv/reference/environment/) - Configuration options
- [uv CLI Reference: tool install](https://docs.astral.sh/uv/reference/cli/#uv-tool-install) - Command documentation
- [Python Packaging User Guide: pyproject.toml](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) - Standard specification
- [setuptools: Entry Points](https://setuptools.pypa.io/en/latest/userguide/entry_point.html) - Console scripts mechanism
- [GitHub Docs: Building and Testing Python](https://docs.github.com/en/actions/use-cases-and-examples/building-and-testing/building-and-testing-python) - CI/CD patterns

### Secondary (MEDIUM confidence)
- [Real Python: Managing Python Projects With uv](https://realpython.com/python-uv/) - Practical workflows (2026)
- [Python Developer Tooling Handbook: uv run vs uvx](https://pydevtools.com/handbook/explanation/when-to-use-uv-run-vs-uvx/) - Best practices
- [Simon Willison: Using uv to develop Python CLI apps](https://til.simonwillison.net/python/uv-cli-apps) - Real-world example
- [pyOpenSci: README Best Practices](https://www.pyopensci.org/python-package-guide/documentation/repository-files/readme-file-best-practices.html) - Documentation standards
- [pytest-console-scripts](https://pypi.org/project/pytest-console-scripts/) - Testing plugin
- [Python Shebang Best Practices](https://www.datacamp.com/tutorial/python-shebang) - Entry points as alternative

### Tertiary (LOW confidence)
- [dasroot.net: Python Packaging Best Practices 2026](https://dasroot.net/posts/2026/01/python-packaging-best-practices-setuptools-poetry-hatch/) - Build backend comparison (blog post)
- Various Medium articles on uv - Community perspectives, not authoritative

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official uv documentation, Python Packaging User Guide
- Architecture: HIGH - Verified with official docs and working examples
- Pitfalls: MEDIUM-HIGH - Combination of official docs and community-reported issues
- Code examples: HIGH - All sourced from official documentation or verified tools
- Testing strategies: HIGH - pytest-console-scripts is established, well-documented

**Research date:** 2026-02-01
**Valid until:** ~2026-03-31 (60 days - uv is mature but evolving rapidly)

**Note on mc-cli project:** The existing pyproject.toml already has [project.scripts] correctly configured (`mc = "mc.cli.main:main"`). The main gap is the [build-system] section, which is trivial to add. The project is well-positioned for all three workflows.
