# MC CLI - Multi-Case Container Management Tool

MC is a CLI tool for managing Red Hat support case workspaces and container environments.

## Installation

### Quick Start

```bash
# Install uv package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install MC CLI from git
uv tool install git+https://github.com/user/mc-cli.git

# Verify installation
mc --version
```

For detailed installation instructions covering development, UAT, and production workflows, see [INSTALL.md](INSTALL.md).

## Features

- **Case Workspace Management**: Automatically creates organized directory structures for support cases
- **Red Hat API Integration**: Fetches case details, attachments, and account information
- **LDAP Search**: Quick lookup of Red Hat employee information
- **Container Orchestration** (planned): Rootless Podman containers per case with persistent workspaces
- **Multi-user Support** (planned): Admin and user privilege levels within containers

## Current Commands

### Case Management
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

Configure your Red Hat API offline token in `~/.mc/config.toml`:

```toml
[api]
offline_token = "your_token_here"
```

Or export temporarily:
```bash
export RH_API_OFFLINE_TOKEN="your_token_here"
```

Case workspaces are created automatically in the configured base directory (default: `~/Cases`).

## Usage Examples

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
