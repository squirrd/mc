# MC CLI Installation Guide

Complete installation instructions for MC CLI across development, UAT, and production environments.

## Prerequisites

**Required:**
- Python 3.11 or later
- uv package manager

**Optional:**
- Podman (for container orchestration features)
- Red Hat API offline token (for Salesforce integration)

## Install uv

uv is a fast Python package and tool manager written in Rust. It replaces pip, pipx, and virtualenv with a unified, 10-100x faster workflow.

### macOS/Linux

```bash
# Install via curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv

# Configure shell PATH (one-time)
uv tool update-shell
```

After installation, restart your shell or run:
```bash
source ~/.bashrc  # or ~/.zshrc
```

Verify installation:
```bash
uv --version
```

## Development Workflow

For developers working on the MC CLI codebase.

### Quick Start

```bash
# Clone the repository
git clone <repository_url>
cd mc

# Run MC CLI (auto-creates .venv and syncs from uv.lock on first run)
uv run mc --help
uv run mc --version
```

### Common Development Tasks

```bash
# Run the CLI
uv run mc <command>

# Run tests
uv run pytest
uv run pytest tests/unit/  # Specific test directory

# Run type checker
uv run mypy src/

# Run linters
uv run black src/ tests/
uv run flake8 src/ tests/

# Run security scanner
uv run bandit -r src/
```

### Managing Dependencies

```bash
# Add a new dependency
uv add requests

# Add a dev dependency
uv add --dev pytest-mock

# Upgrade a specific package
uv lock --upgrade-package rich

# Upgrade all packages
uv lock --upgrade

# Sync environment after changes
uv sync
```

### How it Works

- `uv run` automatically creates `.venv/` and syncs from `uv.lock` on first use
- No manual virtual environment activation needed
- Changes to Python code are reflected immediately (editable install)
- After modifying `pyproject.toml`, run `uv sync` to update the environment

## UAT Workflow

For User Acceptance Testing - testing a local build before release.

### Install from Local Directory

```bash
# Navigate to MC CLI source directory
cd /path/to/mc

# Install in editable mode (changes reflected immediately)
uv tool install -e .

# Test the installed tool
mc --version
mc --help
mc cases list
```

### View Installed Tools

```bash
# List all uv-managed tools
uv tool list

# Show installation paths
uv tool list --show-paths
```

### Uninstall

```bash
uv tool uninstall mc-cli
```

### UAT Notes

- Editable mode (`-e` flag) means code changes are reflected immediately without reinstalling
- The `mc` command is available globally in your PATH
- Installation is isolated - won't affect system Python or other projects
- Use this workflow to test releases before publishing to PyPI or git

## Production Workflow

For end users installing MC CLI for daily use.

### Install from Git Repository

```bash
# Install latest version from main branch
uv tool install git+https://github.com/user/mc-cli.git

# Install specific version tag
uv tool install git+https://github.com/user/mc-cli.git@v2.0.0

# Install from specific branch
uv tool install git+https://github.com/user/mc-cli.git@feature-branch
```

### Install from PyPI

When MC CLI is published to PyPI, you can install with:

```bash
uv tool install mc-cli
```

### Verify Installation

```bash
mc --version
mc --help
```

### Upgrade

```bash
# Upgrade to latest version
uv tool upgrade mc-cli

# Or reinstall from git
uv tool install --force git+https://github.com/user/mc-cli.git
```

### Uninstall

```bash
uv tool uninstall mc-cli
```

### Production Notes

- Installs to an isolated environment in `~/.local/bin/`
- Won't conflict with other Python tools or system packages
- Automatic PATH configuration with `uv tool update-shell`
- No manual virtual environment management required

## Troubleshooting

### Command Not Found After Installation

**Problem:** `mc: command not found` after successful installation

**Solution:**
```bash
# Option 1: Configure shell automatically
uv tool update-shell

# Option 2: Add to PATH manually
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Conda Environment Interference

**Problem:** Dependencies install to conda environment instead of `.venv`

**Solution:** Use `uv run` and `uv sync` instead of `uv pip` commands:
```bash
# Don't use: uv pip install <package>
# Use instead: uv add <package>

# Don't use: uv pip sync
# Use instead: uv sync
```

### Changes Not Reflected After Editing pyproject.toml

**Problem:** Added dependencies or modified configuration not taking effect

**Solution:** Run `uv sync` to update the environment:
```bash
uv sync
```

### Virtual Environment Not Created

**Problem:** `.venv/` directory not created after running `uv run`

**Solution:** Ensure you're in the project root directory with `pyproject.toml`:
```bash
cd /path/to/mc
uv run mc --help
```

### Podman Integration Errors

**Problem:** Container commands fail with "podman not found" or connection errors

**Solution:**
```bash
# macOS: Ensure Podman machine is running
podman machine start

# Linux: Install Podman
sudo dnf install podman  # Fedora/RHEL
sudo apt install podman  # Debian/Ubuntu

# Verify Podman is accessible
podman --version
podman ps
```

### Permission Errors on Container Workspaces

**Problem:** Permission denied when accessing files in container workspaces

**Solution:** MC CLI uses rootless containers with UID/GID mapping. Ensure:
- Container created with `--userns=keep-id` (automatic in MC CLI)
- Workspace mounted with `:U` suffix for automatic ownership mapping (automatic in MC CLI)

### API Token Configuration

**Problem:** Salesforce API calls fail with authentication errors

**Solution:** Configure your Red Hat API offline token:
```bash
# Set in ~/.mc/config.toml
[api]
offline_token = "your_token_here"

# Or export temporarily
export RH_API_OFFLINE_TOKEN="your_token_here"
```

## Additional Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [Python Packaging User Guide](https://packaging.python.org/)
- MC CLI GitHub Repository: <repository_url>

## Getting Help

If you encounter issues not covered here:

1. Check existing GitHub issues
2. Run `mc --help` for command-specific help
3. Open a new issue with:
   - Output of `mc --version`
   - Output of `uv --version`
   - Output of `python --version`
   - Error message and steps to reproduce
