# Architecture

**Analysis Date:** 2026-01-20

## Pattern Overview

**Overall:** Layered CLI Application with Domain-Driven Design

**Key Characteristics:**
- Command-line interface with subcommands for case management operations
- Clear separation between CLI, business logic (controller), and external integrations
- Utility functions isolated in dedicated modules
- Thin command layer that orchestrates between API clients and workspace management

## Layers

**CLI Layer:**
- Purpose: Parse arguments and route commands to appropriate handlers
- Location: `src/mc/cli/`
- Contains: Main entry point, command handlers, argument parsing
- Depends on: Controller layer, integrations, utilities
- Used by: Entry point script (`mc`)

**Command Layer:**
- Purpose: Implement command-specific logic and orchestration
- Location: `src/mc/cli/commands/`
- Contains: `case.py` (case operations), `other.py` (utility commands)
- Depends on: Controller, integrations, utilities
- Used by: CLI main entry point

**Controller Layer:**
- Purpose: Manage domain objects and business logic
- Location: `src/mc/controller/`
- Contains: `workspace.py` (WorkspaceManager class)
- Depends on: Utilities
- Used by: Command layer

**Integration Layer:**
- Purpose: Interface with external systems
- Location: `src/mc/integrations/`
- Contains: `redhat_api.py` (Red Hat API client), `ldap.py` (LDAP operations)
- Depends on: External services (Red Hat API, LDAP server)
- Used by: Command layer

**Utilities Layer:**
- Purpose: Provide reusable helper functions
- Location: `src/mc/utils/`
- Contains: `auth.py`, `file_ops.py`, `formatters.py`
- Depends on: Standard library, requests
- Used by: All other layers

**Configuration Layer:**
- Purpose: Configuration schemas and settings (currently empty/placeholder)
- Location: `src/mc/config/`
- Contains: Empty `__init__.py` files
- Depends on: None
- Used by: Not yet implemented

**Agent Layer:**
- Purpose: Placeholder for future agent functionality
- Location: `src/mc/agent/`
- Contains: Empty `__init__.py`
- Depends on: Not yet implemented
- Used by: Not yet implemented

## Data Flow

**Case Creation Flow:**

1. User runs `mc create <case_number>` command
2. CLI main (`src/mc/cli/main.py`) parses arguments
3. Routes to `case.create()` in `src/mc/cli/commands/case.py`
4. `case.create()` fetches access token via `get_access_token()` from `src/mc/utils/auth.py`
5. Creates `RedHatAPIClient` instance from `src/mc/integrations/redhat_api.py`
6. Fetches case and account details from Red Hat API
7. Creates `WorkspaceManager` instance from `src/mc/controller/workspace.py`
8. `WorkspaceManager` generates file/directory structure based on case data
9. Checks existing workspace status
10. Creates missing files/directories via utilities in `src/mc/utils/file_ops.py`

**Case Attachment Download Flow:**

1. User runs `mc attach <case_number>` command
2. CLI routes to `case.attach()` in `src/mc/cli/commands/case.py`
3. Authenticates and creates API client
4. Fetches case/account details from API
5. Creates `WorkspaceManager` to locate attachment directory
6. Lists attachments via API
7. Downloads each attachment to workspace using `RedHatAPIClient.download_file()`

**LDAP Search Flow:**

1. User runs `mc ls <uid>` command
2. CLI routes to `other.ls()` in `src/mc/cli/commands/other.py`
3. Calls `ldap_search()` from `src/mc/integrations/ldap.py`
4. Executes external `ldapsearch` command via subprocess
5. Parses and formats output
6. Displays formatted user cards to terminal

**State Management:**
- Stateless design - no persistent in-memory state
- File system is the source of truth for workspace state
- API calls fetch fresh data on each command execution
- Authentication tokens are ephemeral (fetched per command)

## Key Abstractions

**WorkspaceManager:**
- Purpose: Encapsulates case workspace file structure and operations
- Examples: `src/mc/controller/workspace.py`
- Pattern: Domain object with methods for check/create/access operations
- Responsibilities: Generate file structure, validate workspace, create missing files

**RedHatAPIClient:**
- Purpose: Encapsulates Red Hat Support API interactions
- Examples: `src/mc/integrations/redhat_api.py`
- Pattern: API client class with REST methods
- Responsibilities: Fetch case/account details, list/download attachments

**Command Functions:**
- Purpose: Implement individual CLI subcommands
- Examples: `attach()`, `create()`, `check()` in `src/mc/cli/commands/case.py`
- Pattern: Procedural functions that orchestrate multiple components
- Responsibilities: Validate inputs, coordinate API calls, manage workflow

## Entry Points

**CLI Entry Point:**
- Location: `src/mc/cli/main.py:main()`
- Triggers: Invoked by console script entry point or wrapper script
- Responsibilities: Environment validation, argument parsing, command routing

**Wrapper Script:**
- Location: `/mc` (root directory)
- Triggers: Direct execution by user
- Responsibilities: Set up Python path and invoke main entry point

**Console Script:**
- Location: Defined in `setup.py` and `pyproject.toml`
- Triggers: Installation via pip/setuptools creates `mc` command
- Responsibilities: Entry point registration

## Error Handling

**Strategy:** Fail-fast with explicit error messages

**Patterns:**
- Environment validation at startup (base directory, offline token)
- HTTP errors raised via `requests.raise_for_status()`
- File existence checks before operations
- Exit with code 1 on fatal errors
- Workspace status system: OK, WARN, FATAL states

## Cross-Cutting Concerns

**Logging:** Print statements to stdout/stderr (no structured logging framework)

**Validation:**
- Environment variable checks in `main()`
- Path existence validation via `does_path_exist()`
- LDAP search term length validation (4-15 characters)
- Workspace state validation via `WorkspaceManager.check()`

**Authentication:**
- OAuth2 token exchange via `get_access_token()` in `src/mc/utils/auth.py`
- Bearer token passed to all API requests via headers
- Offline refresh token stored in `RH_API_OFFLINE_TOKEN` environment variable

---

*Architecture analysis: 2026-01-20*
