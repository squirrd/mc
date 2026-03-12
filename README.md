# MC CLI - Multi-Case Container Management Tool

MC is a CLI tool for managing Red Hat support case workspaces and container environments.

## Installation

### Quick Start

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install MC CLI from GitHub
uv tool install git+https://github.com/squirrd/mc

# Verify installation
mc --version
```

### Upgrading

```bash
# Upgrade to the latest version
mc-update upgrade

# Check current version and update status
mc-update check
```

For detailed installation instructions covering development, UAT, and production workflows, see [INSTALL.md](INSTALL.md).

## Features

- **Case Workspace Management**: Automatically creates organized directory structures for support cases
- **Red Hat API Integration**: Fetches case details, attachments, and account information
- **LDAP Search**: Quick lookup of Red Hat employee information
- **Container Orchestration**: Rootless Podman containers per case with persistent workspaces
- **Terminal Automation**: Auto-attach to containerized case environments
- **Salesforce Integration**: Automatic case metadata caching and workspace resolution

## Commands

### Container Workflows (v2.0)
- `mc case <case_number>` - Launch terminal in containerized case workspace
- `mc container ls` - List all case containers
- `mc container stop <case_number>` - Stop a running container
- `mc container delete <case_number>` - Remove a container

### Case Management (v1.0 - still supported)
- `mc check <case_number>` - Check workspace status for a case
- `mc create <case_number>` - Create workspace structure for a case
- `mc attach <case_number>` - Download case attachments
- `mc case-comments <case_number>` - Display case comments

### Utilities
- `mc go <case_number>` - Print or launch Salesforce case URL
- `mc ls <uid>` - Search for user in LDAP

## Configuration

### Prerequisites
- Python 3.11 or higher (automatically managed by uv)
- Red Hat API offline token (for Salesforce integration)
- Podman (for container orchestration features)
- LDAP access (for `ls` command)

### Setup

Configure your Red Hat API offline token in the config file:

**Config file location (v2.0.1+):**
- **All platforms**: `~/mc/config/config.toml`

```toml
[api]
rh_api_offline_token = "your_token_here"

[workspace]
base_directory = "~/mc"  # Optional, default location for case workspaces
```

Or export temporarily:
```bash
export RH_API_OFFLINE_TOKEN="your_token_here"
```

Case workspaces are created automatically in the configured base directory.

### Consolidated Directory Structure (v2.0.1+)

MC CLI v2.0.1+ uses a unified directory structure across all platforms:

```
~/mc/
├── config/
│   ├── config.toml          # TOML configuration
│   └── cache/               # Case metadata cache (SQLite)
├── state/
│   └── containers.db        # Container state database (SQLite)
└── cases/
    └── <customer>/
        └── <case>/          # Case workspaces
```

**Auto-migration:** On first run, MC automatically migrates config, state, and cache from old platformdirs locations (e.g., `~/Library/Application Support/mc/` on macOS or `~/.config/mc/` on Linux).

For complete platform path documentation, see [.planning/PLATFORM-PATHS.md](.planning/PLATFORM-PATHS.md).

### Container Image

MC automatically pulls pre-built container images from quay.io on first use. No manual build required!

**Automatic pull (default):**
```bash
# Just run mc case - image pulls automatically if needed
mc case 12345678
```

**Manual pull (optional):**
```bash
podman pull quay.io/rhn_support_dsquirre/mc-container:latest
```

**Local build (for development):**
```bash
# From project root
podman build -t mc-rhel10:latest -f container/Containerfile .

# Or use the build script
./container/build.sh
```

## Usage Examples

### Container Workflow (v2.0)

```bash
# Open terminal in containerized case workspace
mc case 12345678

# Inside container: case workspace at /case
ls /case
mc attach 12345678
vim /case/notes.txt

# List all case containers
mc container ls

# Stop container when done
mc container stop 12345678
```

### Legacy Workflow (v1.0)

### Check case workspace
```bash
mc check 12345678
```

### Create workspace and download attachments
```bash
mc create 12345678 --download
```

### Search for a user
```bash
mc ls dsquirre
```

### Open case in Salesforce
```bash
mc go 12345678 --launch
```

## Development

For developers working on MC CLI, see [INSTALL.md](INSTALL.md) for the complete development workflow.

### Quick Start

```bash
# Clone and run
git clone <repository_url>
cd mc
uv run mc --help
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific tests
uv run pytest tests/unit/
uv run pytest tests/integration/

# Run with coverage
uv run pytest --cov=mc --cov-report=html
```

### Code Quality

```bash
# Type checking
uv run mypy src/

# Linting
uv run black src/ tests/
uv run flake8 src/ tests/

# Security scanning
uv run bandit -r src/
```

### Project Structure

```
mc-con/
├── src/mc/              # Main source code
│   ├── cli/            # CLI commands and entry point
│   ├── controller/     # Host-side orchestration (future)
│   ├── agent/          # Container-side agent (future)
│   ├── integrations/   # External API clients
│   ├── config/         # Configuration management (future)
│   └── utils/          # Utility functions
├── container/          # Container build files
├── tests/              # Test scripts
├── config-examples/    # Example configuration files
└── docs/              # Documentation
```

## Future Enhancements

See the architecture design document for planned features:
- Container orchestration with Podman
- Per-case persistent containers
- YAML-based mount configuration
- Customer and case profiles
- Automatic version management
- Container lifecycle management

## License

[License information to be added]

## Contributing

[Contributing guidelines to be added]
