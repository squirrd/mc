# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MC CLI is a production-ready Python CLI tool and container orchestrator for Red Hat support case management. It provides isolated per-case containerized workspaces with automatic Salesforce integration, terminal automation, and comprehensive lifecycle management.

**Current Version:** v2.0.4 (597 tests, 75% coverage)
**Python Version:** Minimum 3.11+ (uses native `tomllib` for TOML parsing)
**Package Manager:** `uv` (not pip, pipx, or poetry)

## Quick Reference

**Run CLI:**
```bash
uv run mc --help              # Show all commands
uv run mc --debug <command>   # Run in debug mode
uv run mc 12345678            # Quick access to case (shorthand for mc case 12345678)
```

**Testing:**
```bash
uv run pytest                           # Run all tests
uv run pytest tests/unit/               # Unit tests only
uv run pytest tests/integration/        # Integration tests only
uv run pytest -m "not integration"      # Skip integration tests (fast)
uv run pytest --cov=mc --cov-report=html  # With coverage report
```

**Build Container:**
```bash
./container/build.sh                    # Local build
podman build -t mc-rhel10:latest -f container/Containerfile .
```

**Code Quality:**
```bash
uv run mypy src/                        # Type checking (strict mode)
uv run black src/ tests/                # Formatting (line length: 100)
uv run flake8 src/ tests/               # Linting
uv run bandit -r src/                   # Security scanning
```

## Architecture

### Full Project Structure

```
mc/
├── .planning/              # GSD methodology tracking
│   ├── milestones/         # Completed milestone archives
│   ├── PROJECT.md          # Requirements & shipped features
│   ├── MILESTONES.md       # Release history
│   └── STATE.md            # Current work context
├── container/              # Container build artifacts
│   ├── Containerfile       # Multi-stage build definition
│   └── build.sh            # Build helper script
├── docs/                   # Developer documentation
│   ├── INTEGRATION_TEST_BEST_PRACTICES.md
│   ├── INTEGRATION_TEST_NO_MOCKING.md
│   ├── USING_BUG_TO_TEST.md
│   └── skills/             # Claude Code skill documentation
├── scripts/                # Developer automation scripts
│   └── fix_integration_tests.py  # Parallel integration test fixer
├── src/mc/                 # Python source code (see below)
├── tests/                  # Test suite
│   ├── unit/               # Unit tests (mocked dependencies)
│   ├── integration/        # Integration tests (real Podman)
│   └── conftest.py         # Shared pytest fixtures
├── ~/mc/                   # Runtime directories (user home)
│   ├── config/             # config.toml, cache/
│   └── state/              # containers.db
├── CLAUDE.md               # This file
├── PROJECT.md              # Project requirements
├── pyproject.toml          # Python project configuration
└── uv.lock                 # Dependency lock file
```

### Source Code Architecture

```
src/mc/
├── cli/              # CLI commands and argument parsing (main.py entry point)
├── controller/       # Host-side orchestration (workspace, cache, case resolution)
├── agent/            # Container-side agent (future)
├── container/        # Container lifecycle management (manager, state, models)
├── terminal/         # Terminal automation (launcher, attach, window tracking)
├── integrations/     # External API clients (Podman, Red Hat API, LDAP, Salesforce)
├── config/           # Configuration management (TOML files, wizard, manager)
└── utils/            # Utility functions (file ops, formatters, validation, errors)
```

### Container Image

**Multi-stage Containerfile** (`container/Containerfile`):
1. `ocm-downloader` - Downloads OCM CLI binary with SHA256 verification
2. `backplane-downloader` - Downloads backplane CLI binary with SHA256 verification
3. `mc-builder` - Builds MC CLI from source
4. `final` - Runtime image with all tools (RHEL 10 UBI base)

**Images:**
- Local development: `mc-rhel10:latest`
- Production registry: `quay.io/rhn_support_dsquirre/mc-container:latest`

### Runtime Architecture

**Runtime Modes:**

The codebase supports two runtime modes (detected via `runtime.py`):

- **host** - Running on user's machine (default)
  - Manages containers and terminals for individual cases
  - All commands work but may not be associated with case artifacts
  - Version checks and auto-updates enabled

- **agent** - Running inside container
  - Detected via `MC_RUNTIME_MODE=agent` environment variable
  - Manages specific case (accessing/storing Salesforce, Jira details, artifacts)
  - Version checks and auto-updates disabled (prevents containerized self-updating)
  - Creating terminals and containers is disabled

**State & Configuration:**

- **Configuration File:** `~/mc/config/config.toml`
  - Consolidated from old platformdirs locations
  - Managed by `config/manager.py` with atomic writes and auto-migration
  - Format: TOML with `[api]`, `[workspace]`, and `[version]` sections

- **State Databases:**
  - Container state: `~/mc/state/containers.db` (SQLite)
  - Window registry: Platform-specific via platformdirs
    - Linux: `~/.local/share/mc/window.db`
    - macOS: `~/Library/Application Support/mc/window.db`
  - Case metadata cache: `~/mc/config/cache/` (SQLite)
  - All databases use WAL (Write-Ahead Logging) mode for concurrent access

### Key Components

**Container Management:**
- `container/manager.py` - ContainerManager orchestrates Podman operations with state tracking
- `container/state.py` - StateDatabase manages SQLite persistence for container metadata
- `integrations/podman.py` - PodmanClient wraps podman-py library for container operations

**Terminal Automation:**
- `terminal/launcher.py` - Platform-specific terminal window creation (macOS/Linux)
- `terminal/registry.py` - WindowRegistry tracks terminal window IDs in SQLite with WAL mode
- `terminal/attach.py` - Container attachment logic with auto-reconnect

**Configuration Management:**
- `config/manager.py` - ConfigManager handles TOML file operations with atomic writes
- `config/wizard.py` - Interactive setup wizard for initial configuration

**External Integrations:**
- `integrations/podman.py` - Podman container runtime
- `integrations/redhat.py` - Red Hat Customer Portal API
- `integrations/salesforce.py` - Salesforce API for case data
- `integrations/ldap.py` - LDAP directory services

## Development

### Setup

**Prerequisites:**
- Python 3.11+
- `uv` package manager
- Podman or Docker (for integration tests)

**Installation:**
```bash
# Clone repository
git clone <repository-url>
cd mc

# uv automatically manages dependencies when you run commands
uv run mc --help
```

### Testing

**Test Philosophy:**
- **Unit tests** - Mock external dependencies (API calls, Podman operations)
- **Integration tests** - Require real Podman/Docker, marked with `@pytest.mark.integration`
- **Fixtures** - Shared in `tests/conftest.py` (case numbers, mock URLs, response factories)

**Test Markers:**
- `@pytest.mark.integration` - Integration tests requiring external dependencies
- `@pytest.mark.backwards_compatibility` - Backward compatibility validation tests

**Coverage Targets:**
- Unit tests: Total 75%; per file 60%
- Integration tests: Total 70%; per file 55%
- Current: v2.0.4 has 597 tests with 75% coverage
- Configured minimum: 60% (in `pyproject.toml`)

**Writing Tests:**
- Use `pytest-mock` for mocking (unit tests only, external dependencies only)
- Use `responses` library for HTTP mocking
- Keep test names descriptive: `test_<function>_<scenario>_<expected_result>`
- Use parametrize for multiple test cases: `@pytest.mark.parametrize("input,expected", [...])`

**Test Commands:**
```bash
# Run single test file or function
uv run pytest tests/unit/test_container_manager_create.py
uv run pytest tests/unit/test_container_manager_create.py::test_create_new_container

# Generate coverage report
uv run pytest --cov=mc --cov-report=term-missing
```

### Code Quality

**Type Safety:**
- All functions must have complete type hints
- Strict mypy configuration: `disallow_untyped_defs=true`
- No `Any` types without justification
- Use `from __future__ import annotations` for forward references

**Code Standards:**
- Line length: 100 characters
- Black formatter for consistent style
- Flake8 for linting
- Bandit for security scanning

## Development Patterns

### Error Handling

Use structured exceptions from `exceptions.py`:
- `MCError` - Base exception for all MC-specific errors
- Errors include proper exit codes (defined in `utils/errors.py`)

### Logging

Use Python's logging framework (configured in `utils/logging.py`):
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
logger.error("Error: %s", error)
```

**DO NOT use print statements** except in these specific cases:
- Setup wizard output (`config/wizard.py`)
- Environment variable migration errors (before logging configured)
- User interruption messages (Ctrl+C handling)

### Configuration Access

```python
from mc.config.manager import ConfigManager

config_mgr = ConfigManager()
config = config_mgr.load()

# Access nested values with defaults
offline_token = config.get("api", {}).get("rh_api_offline_token")
base_dir = config.get("base_directory", os.path.expanduser("~/mc"))
```

### SQLite with WAL Mode

Window registry and container state use SQLite with WAL (Write-Ahead Logging) mode for concurrent access:
- Enables multiple readers and one writer simultaneously
- Prevents "database is locked" errors
- Includes graceful corruption recovery

## Important Constraints

1. **No Environment Variables** - Configuration migrated from env vars to TOML file in v2.0
   - Legacy env vars (`MC_BASE_DIR`, `RH_API_OFFLINE_TOKEN`) trigger migration error
   - All config must be in `~/mc/config/config.toml`

2. **No Backwards-Incompatible Changes** - Must maintain compatibility with existing:
   - Config files (old `api.offline_token` key deprecated but supported)
   - Database schemas (migrations required for schema changes)
   - CLI commands and arguments

3. **Type Safety** - All functions must have complete type hints
   - Mypy strict mode: `disallow_untyped_defs=true`
   - No `Any` types without justification
   - Use `from __future__ import annotations` for forward references

4. **Security** - All external requests must:
   - Set `verify=True` explicitly
   - Validate input (case numbers are 8 digits)
   - Handle sensitive data securely (tokens, credentials)
   - Use retry logic with exponential backoff

## Project-Specific Features

### Quick Access Pattern

Users can run `mc 12345678` (just case number) instead of `mc case 12345678`:
- Implemented in `cli/main.py` by detecting 8-digit argument
- Internally routes to `quick_access` command
- See `cli/commands/container.py:quick_access()`

### GSD Methodology

GSD is still extensively used, but where possible the maintainer is trying to move to skills, commands, agents that improve on this methodology and is focused on Test Driven Development. Where possible, note alternatives to GSD where possible.

This project uses GSD (Get Shit Done) methodology with:
- Phases and milestones tracked in `.planning/`
- PROJECT.md defines requirements and shipped features
- MILESTONES.md tracks release history
- STATE.md captures current work context

GSD skills available: `/gsd:help`, `/gsd:progress`, `/gsd:execute-phase`, etc.

**Project-specific Claude Code skills** are defined in `.claude/commands/`:
- `fix-integration-tests.md` - Parallel integration test fixer (also see `scripts/fix_integration_tests.py`)
- `bug-to-test.md` - Convert bug reports into automated tests
