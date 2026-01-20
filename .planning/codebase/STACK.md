# Technology Stack

**Analysis Date:** 2026-01-20

## Languages

**Primary:**
- Python 3.8+ - All application code

**Secondary:**
- Shell (Bash) - Build scripts, test runners, installation scripts
- JavaScript - GSD Claude hooks in `.claude/hooks/`

## Runtime

**Environment:**
- Python 3.8 or higher (tested with Python 3.13.7)

**Package Manager:**
- pip (Python package installer)
- setuptools (build system)
- Lockfile: Not present (dependencies managed via `pyproject.toml` and `setup.py`)

## Frameworks

**Core:**
- argparse (stdlib) - CLI argument parsing
- requests 2.31.0+ - HTTP client for API interactions

**Testing:**
- pytest 7.0.0+ - Test framework
- pytest-cov 4.0.0+ - Coverage reporting

**Build/Dev:**
- setuptools 45+ - Build system
- setuptools_scm 6.2+ - Version management from git
- wheel - Package distribution
- black 23.0.0+ - Code formatting
- flake8 6.0.0+ - Linting
- mypy 1.0.0+ - Static type checking

## Key Dependencies

**Critical:**
- requests 2.31.0+ - Handles all HTTP interactions with Red Hat API and SSO authentication endpoint

**Infrastructure:**
- subprocess (stdlib) - Used for LDAP searches via `ldapsearch` command and launching Chrome browser
- os (stdlib) - File system operations and environment variable access
- re (stdlib) - Regular expressions for text parsing

## Configuration

**Environment:**
- Configuration via environment variables
- Required: `RH_API_OFFLINE_TOKEN` - Red Hat API offline token for authentication
- Optional: `MC_BASE_DIR` - Override base directory for case workspaces (defaults to hardcoded path)
- Configuration file: `.env.example` shows required environment variables
- No central config file currently used (planned: YAML-based config in `config-examples/`)

**Build:**
- `pyproject.toml` - Modern Python project configuration (PEP 517/518)
- `setup.py` - Legacy setup configuration for compatibility
- Black configuration: 100 character line length, targets Python 3.8-3.11
- pytest configuration: Tests in `tests/` directory, follows `test_*.py` naming
- mypy configuration: Python 3.8 compatibility, typed code warnings enabled

## Platform Requirements

**Development:**
- Python 3.8 or higher
- LDAP tools (`ldapsearch` command) - Required for `mc ls` command
- macOS-specific: Chrome browser path hardcoded for `mc go --launch` command
- Red Hat network access for API and LDAP endpoints

**Production:**
- Deployment target: CLI tool installed via pip (`pip install -e .`)
- Entry point: `mc` command registered via console_scripts
- Container support: Containerfile provided for UBI9-based environment
- Container includes: oc, kubectl, ocm-cli, backplane-cli (all ARM64 builds)
- Container base: `registry.access.redhat.com/ubi9/ubi:latest`

---

*Stack analysis: 2026-01-20*
