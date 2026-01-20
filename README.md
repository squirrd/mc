# MC CLI - Multi-Case Container Management Tool

MC is a CLI tool for managing Red Hat support case workspaces and container environments.

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

## Installation

### Prerequisites
- Python 3.8 or higher
- Red Hat API offline token
- LDAP access (for `ls` command)

### Setup

1. Clone the repository:
```bash
git clone <repository_url>
cd mc-con
```

2. Install the package:
```bash
pip install -e .
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env and add your RH_API_OFFLINE_TOKEN
export RH_API_OFFLINE_TOKEN="your_token_here"
```

4. Create base directory for cases:
```bash
mkdir -p ~/Cases
```

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

### Running Tests

Run all tests:
```bash
./tests/run_all_tests.sh
```

Run individual test:
```bash
./tests/test_check.sh
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
