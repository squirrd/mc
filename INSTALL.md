# MC CLI Installation Guide

Installation instructions for MC CLI across development, UAT, and production environments.

## Prerequisites

- Python 3.11 or later
- `uv` package manager
- Podman (for container orchestration features)
- Red Hat API offline token (for Salesforce integration)

## Install uv

uv is a fast Python package and project manager. It replaces pip, pipx, and virtualenv.

```bash
# macOS/Linux via curl
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via Homebrew
brew install uv
```

After installation, restart your shell or run `source ~/.bashrc` (or `~/.zshrc`).

## Development

### Quick Start

```bash
git clone <repository_url>
cd mc

# uv auto-creates .venv and syncs from uv.lock on first run
uv run mc --help
```

### Testing a Specific Branch

To run or test MC from a particular branch (e.g. to validate a fix or pre-release):

```bash
# Clone and switch to the branch
git clone <repository_url>
cd mc
git checkout v2.0.8

# Sync dependencies for this branch
uv sync

# Run MC from the branch
uv run mc --version
uv run mc --help
```

If you already have the repo cloned:

```bash
git fetch origin
git checkout v2.0.8

# Re-sync after switching branches (picks up any dependency changes)
uv sync

uv run mc --version
```

Run tests on the branch:

```bash
uv run pytest                        # All tests
uv run pytest tests/unit/            # Unit tests only
uv run pytest -m "not integration"   # Skip integration tests (fast)
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

# Sync environment after pyproject.toml changes
uv sync
```

## UAT (Pre-Release Testing)

Install from a local directory to test a build before release:

```bash
cd /path/to/mc

# Install in editable mode (code changes reflected immediately)
uv tool install -e .

# Verify
mc --version
mc --help
```

Editable mode means the `mc` command reflects your local source without reinstalling after each change.

### Uninstall

```bash
uv tool uninstall mc-cli
```

## Production

### Install from Git

```bash
# Latest from main branch
uv tool install git+https://github.com/squirrd/mc.git

# Specific version tag
uv tool install git+https://github.com/squirrd/mc.git@v2.0.0

# Specific branch
uv tool install git+https://github.com/squirrd/mc.git@v2.0.8
```

### Upgrade

```bash
uv tool upgrade mc-cli

# Or force reinstall
uv tool install --force git+https://github.com/squirrd/mc.git
```

### Uninstall

```bash
uv tool uninstall mc-cli
```

## Troubleshooting

### Command Not Found After Installation

```bash
# Configure shell PATH automatically
uv tool update-shell

# Or add manually
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Conda Environment Interference

Use `uv add`/`uv sync` instead of `uv pip` commands to avoid installing into the conda environment:

```bash
# Don't: uv pip install <package>
# Do:    uv add <package>

# Don't: uv pip sync
# Do:    uv sync
```

### Changes Not Taking Effect After Editing pyproject.toml

```bash
uv sync
```

### Podman Not Found or Connection Errors

```bash
# macOS: start the Podman machine
podman machine start

# Linux (Fedora/RHEL)
sudo dnf install podman

# Verify
podman ps
```

### Container Image Not Found

MC CLI pulls the container image automatically on first use. If that fails:

```bash
# Pull manually
podman pull quay.io/rhn_support_dsquirre/mc-container:latest

# Or build locally (for development)
podman build -t mc-rhel10:latest -f container/Containerfile .
./container/build.sh
```

### API Token Configuration

Configure your Red Hat API offline token in `~/mc/config/config.toml`:

```toml
[api]
rh_api_offline_token = "your_token_here"
```

v2.0.1+ auto-migrates config from old platformdirs locations on first run. If upgrading from v1.x, rename `api.offline_token` to `api.rh_api_offline_token` (old key is deprecated but still supported).

## Additional Resources

- [uv Documentation](https://docs.astral.sh/uv/)
- [MC CLI README](README.md)
