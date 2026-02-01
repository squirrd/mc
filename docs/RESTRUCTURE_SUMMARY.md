# Project Restructure Summary

## Date: 2026-01-20

## Overview
Successfully restructured the mc-con project from a monolithic script to a modular, maintainable Python package architecture.

## Changes Made

### 1. New Directory Structure

```
mc-con/
├── src/mc/                  # Main package
│   ├── cli/                # Command-line interface
│   │   ├── main.py        # Entry point with argument parsing
│   │   └── commands/      # Command implementations
│   │       ├── case.py    # Case-related commands
│   │       └── other.py   # Utility commands
│   ├── controller/        # Host-side orchestration
│   │   └── workspace.py   # Workspace management
│   ├── agent/             # Container-side code (future)
│   ├── integrations/      # External API clients
│   │   ├── redhat_api.py  # Red Hat Support API
│   │   └── ldap.py        # LDAP integration
│   ├── config/            # Configuration handling (future)
│   │   └── schemas/       # YAML schema definitions
│   ├── utils/             # Utility modules
│   │   ├── auth.py        # Authentication utilities
│   │   ├── formatters.py  # String formatting
│   │   └── file_ops.py    # File operations
│   └── version.py         # Version information
│
├── container/             # Container build files
│   ├── Containerfile     # Container definition
│   ├── build.sh          # Build script
│   └── run.sh            # Run script
│
├── config-examples/       # Example configurations
│   ├── mounts.yaml.example
│   ├── customer.yaml.example
│   ├── case.yaml.example
│   └── compact.yaml.example
│
├── tests/                 # Test suite
│   ├── test_go.sh
│   ├── test_ls.sh
│   ├── test_check.sh
│   ├── test_create.sh
│   ├── test_case_comments.sh
│   └── run_all_tests.sh
│
├── archive/               # Old files (moved from root)
│   ├── mc_old.py
│   ├── orig/
│   ├── orig-002/
│   └── tmp/
│
├── docs/
│   └── RESTRUCTURE_SUMMARY.md (this file)
│
├── mc                     # New executable wrapper
├── .gitignore
├── .env.example
├── README.md
├── requirements.txt
├── setup.py
└── pyproject.toml
```

### 2. Code Refactoring

#### Monolithic mc.py Split Into:
- **src/mc/cli/main.py**: Main entry point and argument parsing
- **src/mc/cli/commands/case.py**: Case commands (attach, check, create, case-comments)
- **src/mc/cli/commands/other.py**: Utility commands (go, ls)
- **src/mc/controller/workspace.py**: Workspace management logic
- **src/mc/integrations/redhat_api.py**: API client class
- **src/mc/integrations/ldap.py**: LDAP search functions
- **src/mc/utils/**: Utility functions (auth, formatters, file_ops)

### 3. Command Changes

#### Renamed Commands:
- `mc login` → `mc case-comments` (to avoid confusion with future architecture)

#### All Commands:
- `mc attach <case>` - Download case attachments
- `mc check <case> [--fix]` - Check workspace status
- `mc create <case> [--download]` - Create workspace
- `mc case-comments <case>` - Display case comments (renamed from login)
- `mc ls <uid> [-A]` - LDAP user search
- `mc go <case> [--launch]` - Salesforce URL

### 4. New Files Created

#### Configuration:
- `.gitignore` - Git ignore patterns
- `.env.example` - Environment variable template
- `setup.py` - Package installation config
- `pyproject.toml` - Modern Python project config
- `requirements.txt` - Python dependencies

#### Documentation:
- `README.md` - Project overview and usage guide
- `docs/RESTRUCTURE_SUMMARY.md` - This file

#### Example Configs (for future features):
- `config-examples/mounts.yaml.example` - Container mount configuration
- `config-examples/customer.yaml.example` - Customer profile
- `config-examples/case.yaml.example` - Case profile
- `config-examples/compact.yaml.example` - Compaction rules

#### Container Scripts:
- `container/build.sh` - Container build script
- `container/run.sh` - Container run script

### 5. Files Archived

Moved to `archive/` directory:
- `mc_old.py` (original monolithic script)
- `mc-con.old`, `mc-con.sh.old` (old wrapper scripts)
- `pbuild` (old build script)
- `Containers/` (old container directory)
- `orig/`, `orig-002/`, `tmp/` (backup directories)
- `ai.py` (separate utility, excluded from restructure)

### 6. Tests Updated

All test scripts updated to:
- Use new `./mc` command instead of `./mc.py`
- Test renamed `case-comments` command
- All tests passing (5/5)

## Benefits of New Structure

### Maintainability
- Clear separation of concerns
- Each module has a single responsibility
- Easy to locate and modify specific functionality

### Extensibility
- Ready for future enhancements (container orchestration, profiles, etc.)
- Plugin-style integration architecture
- Configuration-driven approach

### Testing
- Easier to write unit tests for individual modules
- Current shell tests still functional
- Foundation for pytest integration tests

### Development
- Standard Python package structure
- Proper dependency management
- Can be installed with pip
- Version management in place

## Migration Path for Developers

### Old Code:
```bash
./mc.py check 12345678
```

### New Code:
```bash
./mc check 12345678
```

### Installation:
```bash
pip install -e .  # Install in development mode
mc check 12345678  # Use system-wide command
```

## Next Steps

Ready for implementation of planned enhancements:
1. Container orchestration
2. YAML-based configuration
3. Customer/case profiles
4. Mount management
5. Multi-user container support
6. Automatic version management

## Validation

- ✅ All existing commands working
- ✅ All tests passing (5/5)
- ✅ Code properly modularized
- ✅ Documentation created
- ✅ Old files archived
- ✅ Ready for future development

## Commands Reference

### Test Suite:
```bash
./tests/run_all_tests.sh                # Run all tests
./tests/test_<command>.sh               # Run specific test
```

### Development:
```bash
pip install -e .                        # Install package
./mc --help                             # Show help
```

### Container:
```bash
# Build container image (mc-rhel10:latest)
./container/build.sh

# Or manually from project root:
podman build -t mc-rhel10:latest -f container/Containerfile .

# Run via mc CLI (recommended):
mc case <case_number>

# Or use legacy run script:
./container/run.sh <case_id>
```
