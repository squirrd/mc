# Coding Conventions

**Analysis Date:** 2026-01-20

## Naming Patterns

**Files:**
- Snake_case for Python modules: `redhat_api.py`, `file_ops.py`, `workspace.py`
- Test files: Use `test_*.sh` pattern for bash integration tests
- Empty `__init__.py` files in all packages

**Functions:**
- Snake_case: `get_access_token()`, `fetch_case_details()`, `shorten_and_format()`
- Descriptive names: `does_path_exist()`, `create_directory()`, `print_ldap_cards()`

**Variables:**
- Snake_case for all variables: `case_number`, `base_dir`, `offline_token`, `access_token`
- f-strings preferred for formatting: `f"{self.BASE_URL}/cases/{case_number}"`

**Classes:**
- PascalCase: `WorkspaceManager`, `RedHatAPIClient`
- Descriptive names that indicate purpose

**Constants:**
- UPPER_CASE: `BASE_URL` in `RedHatAPIClient`

## Code Style

**Formatting:**
- Tool: Black
- Line length: 100 characters (configured in `pyproject.toml`)
- Target versions: Python 3.8, 3.9, 3.10, 3.11

**Linting:**
- Tool: flake8 (version 6.0.0+)
- Type checking: mypy (version 1.0.0+)
- mypy configuration: `disallow_untyped_defs = false` (type hints not required)

**Indentation:**
- 4 spaces (standard Python)

## Import Organization

**Order:**
1. Standard library imports first
2. Third-party imports second
3. Local application imports last

**Example from** `src/mc/cli/main.py`:
```python
import argparse
import os
from mc.cli.commands import case, other
from mc.utils.file_ops import does_path_exist
```

**Example from** `src/mc/cli/commands/case.py`:
```python
import os
from mc.utils.auth import get_access_token
from mc.integrations.redhat_api import RedHatAPIClient
from mc.controller.workspace import WorkspaceManager
```

**Path Aliases:**
- No path aliases used
- Standard relative imports from `mc` package root

## Error Handling

**Patterns:**
- Use `requests.HTTPError` with `response.raise_for_status()` for HTTP errors
- Call `exit(1)` for fatal configuration errors (missing env vars, missing directories)
- Return tuple `(success: bool, message: str)` for operations that may fail gracefully (e.g., `ldap_search()`)
- Use `subprocess.CalledProcessError` for subprocess failures

**Examples:**

Authentication error in `src/mc/utils/auth.py`:
```python
offline_token = os.environ.get('RH_API_OFFLINE_TOKEN', None)
if offline_token is None:
    print("The env variable 'RH_API_OFFLINE_TOKEN' must be set")
    exit(1)
```

API error in `src/mc/integrations/redhat_api.py`:
```python
response = requests.get(url, headers=self.headers)
response.raise_for_status()
return response.json()
```

Subprocess error in `src/mc/integrations/ldap.py`:
```python
try:
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    output = result.stdout
except FileNotFoundError:
    return False, "Error: 'ldapsearch' command not found."
except subprocess.CalledProcessError as e:
    return False, f"Error executing ldapsearch: {e.stderr}"
```

## Logging

**Framework:** Built-in `print()` function

**Patterns:**
- Use `print()` for user-facing messages
- Use f-strings for formatting: `print(f"Downloading attachments for case number: {case_number}")`
- Use `pprint` for complex data structures (e.g., `pprint(case_details['comments'])`)
- Status prefixes: "WARN:", "FATAL:", "OK" for check results
- Separator lines with dashes for visual breaks: `print("-" * 40)`

**Examples from** `src/mc/cli/commands/case.py`:
```python
print(f"Downloading attachments for case number: {case_number}")
print("----------------------------")
print(f"FATAL: Failed file check")
```

## Comments

**Module-level docstrings:**
- Every module has a docstring: `"""Case-related commands."""`
- Brief, one-line descriptions

**Function docstrings:**
- Google-style format with Args, Returns, and Raises sections
- Example from `src/mc/utils/formatters.py`:
```python
def shorten_and_format(input_string):
    """
    Shorten and format a string for use in file/directory names.

    - Substrings all words to 7 characters
    - Removes non-alphanumeric characters
    - Replaces spaces and hyphens with underscores
    - Limits total length to 22 characters

    Args:
        input_string: The string to format

    Returns:
        Formatted string suitable for file/directory names
    """
```

**Class docstrings:**
- Brief description with initialization details
- Example from `src/mc/integrations/redhat_api.py`:
```python
class RedHatAPIClient:
    """Client for interacting with Red Hat Support APIs."""
```

**Inline comments:**
- Used sparingly for complex logic
- Example from `src/mc/cli/main.py`: `# Verify offline token is set`

## Function Design

**Size:**
- Functions range from 5-60 lines
- Average is 20-30 lines
- Largest function: `create()` at 49 lines in `src/mc/cli/commands/case.py`

**Parameters:**
- Positional parameters for required values
- Keyword parameters with defaults for optional flags: `fix=False`, `download=False`, `show_all=False`
- Use descriptive parameter names: `case_number`, `base_dir`, `local_filename`

**Return Values:**
- Return `None` for side-effect functions (print output, create files)
- Return data structures (dict, list) from API calls
- Return tuples for operations with success/failure: `(bool, str)`
- Return status strings for checks: `"OK"`, `"WARN"`, `"FATAL"`

## Module Design

**Exports:**
- Functions exported directly (no `__all__` used)
- Classes exported at module level

**Package Structure:**
- `src/mc/` - Main package
  - `cli/` - Command-line interface
    - `commands/` - Command implementations
  - `controller/` - Business logic (workspace management)
  - `integrations/` - External service clients (Red Hat API, LDAP)
  - `utils/` - Helper functions (auth, formatters, file operations)
  - `config/` - Configuration (currently empty)
  - `agent/` - Agent logic (currently empty)

**Barrel Files:**
- Not used - all `__init__.py` files are empty

## String Handling

**Formatting:**
- f-strings are standard: `f"Case {case_number}"`
- No .format() or % formatting observed
- Multi-line strings use standard Python continuation

**Constants:**
- Hardcoded paths: `base_dir = "/Users/dsquirre/Cases"` (in `src/mc/cli/main.py`)
- URLs as class constants: `BASE_URL = "https://api.access.redhat.com/support/v1"`

## File Operations

**Pattern:**
- Wrap `os` module calls in utility functions
- Check existence before operations: `os.path.exists(path)`
- Use context managers for file I/O: `with open(file_path, 'wb') as file:`
- Use `makedirs(exist_ok=True)` for directory creation

**Location:** `src/mc/utils/file_ops.py`

## CLI Argument Parsing

**Framework:** argparse

**Pattern:**
- Create main parser with subparsers for commands
- Use `add_argument()` for positional and optional arguments
- Boolean flags with `action='store_true'`
- Route commands with `if/elif` on `args.command`

**Location:** `src/mc/cli/main.py`

---

*Convention analysis: 2026-01-20*
