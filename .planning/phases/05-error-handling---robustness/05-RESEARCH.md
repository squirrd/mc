# Phase 5: Error Handling & Robustness - Research

**Researched:** 2026-01-22
**Domain:** Python CLI error handling, HTTP retry patterns, file operations
**Confidence:** HIGH

## Summary

Error handling and robustness for Python CLI tools requires a coordinated strategy across multiple domains: HTTP errors with automatic retries, file operation failures with pathlib, subprocess failures from external commands (ldapsearch), and user-facing error messages with actionable guidance. The current MC codebase uses basic error handling (raise_for_status(), try/except for subprocess), but lacks retry logic, structured error messages, exit codes, and recovery mechanisms.

The standard approach combines urllib3.Retry for HTTP retry logic (built into requests), pathlib for robust file operations with proper exception handling, custom exception hierarchies for domain errors, and a logging module for structured error tracking. Modern best practices emphasize user-friendly error messages on stderr (not stdout), specific exit codes for scripting, silent retries with debug visibility, and batch operations that continue on error.

**Primary recommendation:** Use urllib3.Retry with requests.Session for HTTP retries, pathlib with proper exception handling for file operations, custom exception hierarchy for domain errors, logging module for error tracking, and specific exit codes (0=success, 1=general, 2=usage, 64-78=specific types). Focus on actionable error messages following clig.dev guidelines.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | 2.31+ | HTTP client with retry support | De facto standard for HTTP, uses urllib3 underneath which provides Retry class |
| urllib3 | bundled | HTTP connection pooling and retry | Automatically included with requests, provides Retry configuration |
| pathlib | stdlib | Object-oriented file operations | Modern Python standard (3.4+), clearer error semantics than os.path |
| logging | stdlib | Structured error and debug logging | Standard library solution for production error tracking |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| backoff | 2.2+ | Decorator-based retry with exponential backoff | Alternative to urllib3.Retry for non-HTTP operations or more complex retry logic |
| rich | 13.0+ | Terminal formatting and enhanced tracebacks | Optional: Better error messages with color, formatting, tables (requires Python 3.8+) |
| structlog | 24.0+ | Structured JSON logging | Optional: Production environments needing machine-readable logs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| urllib3.Retry | backoff library | backoff is more flexible but urllib3.Retry is built-in and simpler for HTTP |
| logging module | print() to stderr | logging provides levels, formatting, handlers; print() is simpler but not production-ready |
| Custom exit codes | Always exit 1 | Specific codes enable scripting but add complexity; acceptable for simple CLIs |
| pathlib | os.path | os.path is older style, pathlib has clearer exceptions and modern API |

**Installation:**
```bash
# Core dependencies (already in pyproject.toml)
pip install requests>=2.31.0

# Optional enhanced formatting
pip install rich>=13.0.0

# Optional structured logging for production
pip install structlog>=24.0.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── exceptions.py       # Custom exception hierarchy
├── utils/
│   ├── http_client.py  # HTTP client with retry logic
│   ├── file_ops.py     # File operations with pathlib
│   └── errors.py       # Error formatting utilities
└── cli/
    └── main.py         # Exit code handling and error display
```

### Pattern 1: HTTP Client with Retry Logic
**What:** Configure requests.Session with urllib3.Retry for automatic retries on transient failures
**When to use:** All HTTP API calls (RedHat API client)
**Example:**
```python
# Source: https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session_with_retry(max_retries=3, backoff_factor=0.3):
    """Create requests session with retry logic."""
    session = requests.Session()

    # Configure retry strategy
    retry_strategy = Retry(
        total=max_retries,              # Total retries
        connect=max_retries,            # Connection errors
        read=max_retries,               # Read errors
        status=max_retries,             # Status code retries
        status_forcelist=[429, 500, 502, 503, 504],  # Retry these codes
        allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"],
        backoff_factor=backoff_factor,  # {backoff} * (2 ** {retry_count})
        respect_retry_after_header=True # Honor Retry-After header
    )

    # Mount adapter for both HTTP and HTTPS
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

# Usage in RedHatAPIClient
class RedHatAPIClient:
    def __init__(self, access_token, max_retries=3):
        self.session = create_session_with_retry(max_retries)
        self.session.headers.update({'Authorization': f'Bearer {access_token}'})

    def fetch_case_details(self, case_number):
        url = f"{self.BASE_URL}/cases/{case_number}"
        try:
            response = self.session.get(url, timeout=(3.05, 27))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # Handle HTTP errors with user-friendly messages
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(f"Request timed out for case {case_number}")
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"Failed to connect to API: {e}")
```

### Pattern 2: Pathlib Error Handling
**What:** Use pathlib with proper exception handling and built-in safety parameters
**When to use:** All file operations (workspace management, file downloads)
**Example:**
```python
# Source: https://docs.python.org/3/library/pathlib.html
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def create_workspace_directory(base_dir: str, case_dir: str) -> Path:
    """Create workspace directory with proper error handling."""
    try:
        workspace = Path(base_dir) / case_dir

        # Create with parents, won't raise if exists
        workspace.mkdir(parents=True, exist_ok=True)

        logger.info(f"Created workspace: {workspace}")
        return workspace

    except PermissionError:
        raise WorkspaceError(
            f"Permission denied creating workspace at {base_dir}. "
            f"Try: Check directory permissions with 'ls -ld {base_dir}'"
        )
    except OSError as e:
        raise WorkspaceError(
            f"Failed to create workspace: {e}. "
            f"Check: Disk space and parent directory permissions"
        )

def safe_read_file(file_path: Path) -> str:
    """Read file with comprehensive error handling."""
    try:
        return file_path.read_text()
    except FileNotFoundError:
        raise FileOperationError(
            f"File not found: {file_path}. "
            f"Try: mc case init {case_number} to create workspace"
        )
    except PermissionError:
        raise FileOperationError(
            f"Permission denied reading {file_path}. "
            f"Try: chmod +r {file_path}"
        )
    except OSError as e:
        raise FileOperationError(f"Failed to read {file_path}: {e}")

def safe_delete_file(file_path: Path) -> None:
    """Delete file without raising if it doesn't exist."""
    # missing_ok=True prevents FileNotFoundError
    file_path.unlink(missing_ok=True)
```

### Pattern 3: Custom Exception Hierarchy
**What:** Domain-specific exceptions inheriting from Exception with contextual information
**When to use:** All error conditions across the application
**Example:**
```python
# Source: https://realpython.com/python-raise-exception/
# File: src/mc/exceptions.py

class MCError(Exception):
    """Base exception for MC CLI."""
    exit_code = 1

    def __init__(self, message: str, suggestion: str = None):
        super().__init__(message)
        self.suggestion = suggestion

class AuthenticationError(MCError):
    """Authentication failed."""
    exit_code = 65  # EX_DATAERR from sysexits.h

class APIError(MCError):
    """Base for API-related errors."""
    exit_code = 69  # EX_UNAVAILABLE

class HTTPAPIError(APIError):
    """HTTP error from API."""

    @classmethod
    def from_response(cls, response):
        """Create error from response with helpful message."""
        status_messages = {
            401: "Authentication failed. Try: mc auth login",
            403: "Access forbidden. Check: Your account has case access permissions",
            404: "Resource not found. Check: Case number is correct",
            429: "Rate limited. Try: Wait a moment and retry",
            500: "API server error. Try: Retry in a few minutes",
            503: "API temporarily unavailable. Try: Retry in a few minutes"
        }

        msg = status_messages.get(
            response.status_code,
            f"HTTP {response.status_code} error"
        )

        error = cls(f"{msg} (endpoint: {response.url})")
        error.status_code = response.status_code
        error.response = response
        return error

class APITimeoutError(APIError):
    """API request timed out."""
    pass

class APIConnectionError(APIError):
    """Failed to connect to API."""
    pass

class ValidationError(MCError):
    """Input validation failed."""
    exit_code = 2  # Command line syntax error

class WorkspaceError(MCError):
    """Workspace operation failed."""
    exit_code = 73  # EX_CANTCREAT from sysexits.h

class FileOperationError(MCError):
    """File operation failed."""
    exit_code = 74  # EX_IOERR from sysexits.h
```

### Pattern 4: Error Formatting and Display
**What:** User-friendly error messages to stderr with actionable guidance
**When to use:** All CLI error output
**Example:**
```python
# Source: https://clig.dev/
import sys
import logging

logger = logging.getLogger(__name__)

def format_error_message(error: Exception) -> str:
    """Format error for user display."""
    message = str(error)

    # Add suggestion if available
    if hasattr(error, 'suggestion') and error.suggestion:
        message += f"\n{error.suggestion}"

    return message

def handle_cli_error(error: Exception, debug: bool = False) -> int:
    """
    Handle CLI error with proper output and exit code.

    Returns appropriate exit code for the error type.
    """
    # Log full details (to file or debug output)
    logger.error(f"Error: {error}", exc_info=debug)

    # Print user-friendly message to stderr
    error_msg = format_error_message(error)
    print(f"Error: {error_msg}", file=sys.stderr)

    # Print traceback in debug mode
    if debug:
        import traceback
        traceback.print_exc(file=sys.stderr)

    # Return appropriate exit code
    if hasattr(error, 'exit_code'):
        return error.exit_code
    return 1  # Generic error

# Usage in main CLI entry point
def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true')
    parser.add_argument('--max-retries', type=int, default=3)
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        # Run CLI command
        run_command(args)
        return 0

    except MCError as e:
        return handle_cli_error(e, debug=args.debug)
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 130  # Standard for SIGINT
    except Exception as e:
        logger.exception("Unexpected error")
        if args.debug:
            raise
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1
```

### Pattern 5: Batch Operations Error Aggregation
**What:** Continue processing batch operations on error, report all failures at end
**When to use:** Multi-file downloads, bulk case processing
**Example:**
```python
# Source: https://www.kdnuggets.com/5-error-handling-patterns-in-python-beyond-try-except
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class BatchResult:
    """Results from batch operation."""

    def __init__(self):
        self.succeeded: List[str] = []
        self.failed: List[Tuple[str, Exception]] = []

    @property
    def success_count(self) -> int:
        return len(self.succeeded)

    @property
    def failure_count(self) -> int:
        return len(self.failed)

    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0

def download_attachments(case_number: str, attachment_ids: List[str]) -> BatchResult:
    """
    Download multiple attachments, continue on error.

    Returns BatchResult with succeeded and failed downloads.
    """
    result = BatchResult()

    for att_id in attachment_ids:
        try:
            logger.info(f"Downloading attachment {att_id}")
            download_attachment(case_number, att_id)
            result.succeeded.append(att_id)

        except Exception as e:
            logger.error(f"Failed to download {att_id}: {e}")
            result.failed.append((att_id, e))
            # Continue to next attachment

    return result

# Usage
result = download_attachments("12345678", ["att1", "att2", "att3"])

print(f"Downloaded {result.success_count} attachments")

if result.failure_count > 0:
    print(f"\nFailed to download {result.failure_count} attachments:", file=sys.stderr)
    for att_id, error in result.failed:
        print(f"  - {att_id}: {error}", file=sys.stderr)
    sys.exit(1)
```

### Pattern 6: Subprocess Error Handling
**What:** Handle external command failures (ldapsearch) with clear error messages
**When to use:** LDAP search and any external command execution
**Example:**
```python
# Source: https://docs.python.org/3/library/subprocess.html
import subprocess
import logging

logger = logging.getLogger(__name__)

def run_ldap_search(uid: str) -> Tuple[bool, str]:
    """Run ldapsearch with comprehensive error handling."""
    command = [
        "ldapsearch",
        "-LLL",
        "-z", "10",
        "-x",
        "-H", "ldaps://ldap.corp.redhat.com",
        "-b", "dc=redhat,dc=com",
        f"(uid=*{uid}*)"
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=10
        )

        if not result.stdout.strip():
            return False, f"No LDAP results found for '{uid}'"

        return True, result.stdout

    except FileNotFoundError:
        raise ExternalCommandError(
            "ldapsearch command not found. "
            "Try: Install LDAP tools (apt-get install ldap-utils or yum install openldap-clients)"
        )
    except subprocess.TimeoutExpired:
        raise ExternalCommandError(
            f"LDAP search timed out after 10 seconds. "
            f"Check: Network connectivity to ldap.corp.redhat.com"
        )
    except subprocess.CalledProcessError as e:
        # Parse stderr for specific errors
        stderr = e.stderr.strip()
        if "Can't contact LDAP server" in stderr:
            raise ExternalCommandError(
                "Cannot connect to LDAP server. "
                "Check: Network connectivity and VPN connection"
            )
        else:
            raise ExternalCommandError(
                f"LDAP search failed: {stderr}"
            )
```

### Anti-Patterns to Avoid

- **Silent failures:** Always log errors, even if retrying. Use logging.debug() for retry details.
- **Generic exception catching:** Don't catch `Exception` without re-raising or logging; catch specific exceptions.
- **Missing error context:** Include what operation failed, not just the error message (e.g., "Failed to download case 12345" not "Download failed").
- **Printing to stdout:** Errors go to stderr, not stdout. Use `print(..., file=sys.stderr)` or logging module.
- **Blocking on user input:** In batch/automation mode, never prompt for confirmation; use force flags if needed.
- **Using os.path with bare open():** Use pathlib which has clearer exception semantics and handles edge cases better.
- **Not setting timeouts:** Always set timeouts on HTTP requests and subprocess calls to prevent hanging.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP retry logic | Custom retry loops with sleep | urllib3.Retry with requests.Session | Handles exponential backoff, Retry-After header, connection pooling, partial failures |
| Exponential backoff | Manual calculation of delays | urllib3.Retry backoff_factor or backoff library | Correct formula: backoff_factor * (2 ** retry_count), handles jitter, respects max_backoff |
| Exit code mapping | Custom exit code constants | Use standard codes (0, 1, 2) or os.EX_* constants | os.EX_* available on BSD/Mac but not Windows; simple codes (0/1/2) are portable |
| Error message formatting | String concatenation | Format with context, use f-strings, structured logging | Ensures consistency, enables structured logging, supports localization |
| Path manipulation | String operations on paths | pathlib.Path | Handles platform differences, provides clear exceptions, prevents path traversal issues |
| Timeout handling | threading.Timer or signal | timeout parameter in requests/subprocess | Built-in, reliable, handles cleanup, works cross-platform |
| File locking for partial downloads | Custom lock files | HTTP Range header with proper validation | Standard HTTP feature, server-controlled, validates integrity |
| Traceback formatting | Manual exception parsing | Rich traceback or logging.exception() | Syntax highlighting, local variables, proper formatting |

**Key insight:** Error handling edge cases are complex. HTTP retry needs to handle connection pooling, DNS failures, partial reads, status vs. connection errors, rate limiting headers, and timeout vs. connection timeout. File operations need to handle permission errors, disk full, path too long, invalid characters, symlink loops, and race conditions. Use proven libraries.

## Common Pitfalls

### Pitfall 1: Not Respecting Retry-After Header
**What goes wrong:** When API returns 429 (rate limited) with Retry-After header, ignoring it causes exponential backoff to retry too quickly, leading to continued rate limiting.
**Why it happens:** Default retry logic may not check response headers.
**How to avoid:** Set `respect_retry_after_header=True` in urllib3.Retry configuration. This honors server-specified delays.
**Warning signs:** Repeated 429 errors even with retry logic, API blocking requests.

### Pitfall 2: Catching Exceptions Too Broadly
**What goes wrong:** Using `except Exception:` catches KeyboardInterrupt's parent (BaseException), making Ctrl+C not work. Also catches programming errors that should crash.
**Why it happens:** Defensive programming taken too far, wanting to "handle all errors."
**How to avoid:** Catch specific exceptions (requests.HTTPError, FileNotFoundError). If catching Exception, re-raise programming errors or use `except MCError:` for domain exceptions only.
**Warning signs:** Ctrl+C doesn't stop program, bugs masked by error handlers, "Unexpected error" for everything.

### Pitfall 3: Using os.path with open() Instead of pathlib
**What goes wrong:** os.path.exists() race condition - file can be deleted between check and open(). No clear exception types. String concatenation breaks on Windows vs. Unix.
**Why it happens:** Older code examples, habit from Python 2, not knowing pathlib benefits.
**How to avoid:** Use pathlib.Path with try/except. Path.read_text() is atomic, exceptions are clear (FileNotFoundError vs. PermissionError vs. OSError).
**Warning signs:** Cryptic IOError messages, path handling bugs across platforms, TOCTOU (time-of-check-time-of-use) race conditions.

### Pitfall 4: Not Setting Timeouts on HTTP Requests
**What goes wrong:** Request hangs forever if server doesn't respond, CLI appears frozen, user Ctrl+C's and loses trust in tool.
**Why it happens:** requests doesn't set timeout by default, assuming you'll set it per-request.
**How to avoid:** Always set timeout parameter: `session.get(url, timeout=(3.05, 27))` where first is connect timeout, second is read timeout.
**Warning signs:** CLI hangs with no output, network blip causes indefinite wait, subprocess calling CLI times out.

### Pitfall 5: Printing Errors to stdout Instead of stderr
**What goes wrong:** Error messages get piped to next command in shell pipeline, breaks scripting, can't separate errors from data output.
**Why it happens:** Using print() by default goes to stdout.
**How to avoid:** Use `print(..., file=sys.stderr)` for errors or use logging module which defaults to stderr.
**Warning signs:** Pipeline scripts fail mysteriously, error messages appear in output files, can't redirect errors separately.

### Pitfall 6: Silent Retries Without Debug Visibility
**What goes wrong:** User sees slow response, doesn't know if CLI is working or hung, loses trust when operation takes 30 seconds with no feedback.
**Why it happens:** Implementing "silent retry" for clean UX but overdoing it.
**How to avoid:** Log retry details at DEBUG level: `logger.debug(f"Retry {attempt}/{max_retries} for {url}")`. User can enable with --debug flag.
**Warning signs:** Users report "CLI is slow", "not sure if it's working", timeouts happen but no visibility why.

### Pitfall 7: Not Handling Partial File Downloads
**What goes wrong:** Network failure mid-download leaves corrupted file, next run re-downloads entire file instead of resuming, wastes bandwidth and time.
**Why it happens:** No tracking of download state, assuming downloads are atomic.
**How to avoid:** Two strategies: (1) Write to .tmp file, rename on success, delete on failure. (2) Use HTTP Range header to resume if server supports it (check for 206 response).
**Warning signs:** Large files re-download from start, corrupted files in workspace, downloads fail on slow/flaky networks.

### Pitfall 8: Exit Code 0 on Partial Failure
**What goes wrong:** Batch download succeeds for 3/5 files, script exits 0, automation thinks everything worked, missing files go unnoticed.
**Why it happens:** Checking if any files succeeded instead of if all succeeded.
**How to avoid:** Exit non-zero if any operation failed. Use BatchResult pattern, check `result.all_succeeded`.
**Warning signs:** CI/CD doesn't catch failures, partial data in downstream systems, manual verification needed.

### Pitfall 9: Malformed LDAP Response Crashes Tool
**What goes wrong:** LDAP returns unexpected format, regex fails, KeyError on missing field, tool crashes instead of showing "No results" or "Malformed response."
**Why it happens:** Assuming LDAP response structure is always consistent.
**How to avoid:** Use try/except around parsing, handle missing fields with .get(), validate structure before processing. Show partial results if possible.
**Warning signs:** Tool works 95% of time, crashes on edge cases, specific users trigger errors, regex exceptions.

### Pitfall 10: Validation Errors Exit with Generic Code
**What goes wrong:** User runs `mc case init abc`, gets exit code 1, script can't distinguish "invalid input" from "API down" from "disk full."
**Why it happens:** All errors exit with same code (1).
**How to avoid:** Use specific exit codes: 0=success, 1=general error, 2=validation/usage error, 65=auth, 69=API unavailable, 73=can't create, 74=I/O error.
**Warning signs:** Scripts can't handle different error types, have to parse error messages, can't distinguish retryable vs. non-retryable errors.

## Code Examples

Verified patterns from official sources:

### Complete HTTP Client with Retry and Error Handling
```python
# Source: urllib3 docs + requests docs + clig.dev
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class RedHatAPIClient:
    """Red Hat API client with retry logic and error handling."""

    BASE_URL = "https://api.access.redhat.com/support/v1"

    def __init__(
        self,
        access_token: str,
        max_retries: int = 3,
        timeout: tuple = (3.05, 27)
    ):
        """
        Initialize API client.

        Args:
            access_token: Red Hat API access token
            max_retries: Maximum retry attempts for transient failures
            timeout: (connect_timeout, read_timeout) in seconds
        """
        self.access_token = access_token
        self.timeout = timeout
        self.session = self._create_session(max_retries)

    def _create_session(self, max_retries: int) -> requests.Session:
        """Create session with retry configuration."""
        session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
            backoff_factor=0.3,  # 0.3, 0.6, 1.2, 2.4... seconds
            respect_retry_after_header=True
        )

        # Mount adapter
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Set headers
        session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': 'mc-cli/0.1.0'
        })

        return session

    def fetch_case_details(self, case_number: str) -> dict:
        """
        Fetch case details with retry and error handling.

        Raises:
            HTTPAPIError: For HTTP errors (401, 403, 404, etc.)
            APITimeoutError: For timeout
            APIConnectionError: For connection failures
        """
        url = f"{self.BASE_URL}/cases/{case_number}"

        try:
            logger.debug(f"Fetching case {case_number} from {url}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)

        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out for case {case_number}. "
                f"Check: Network connection and API availability"
            )

        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to Red Hat API. "
                f"Check: Network connectivity and VPN status. "
                f"Details: {e}"
            )

        except requests.exceptions.RequestException as e:
            # Catch-all for other request errors
            raise APIError(f"API request failed: {e}")

    def close(self):
        """Close session and cleanup."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# Usage
try:
    with RedHatAPIClient(token, max_retries=3) as client:
        case = client.fetch_case_details("12345678")
except HTTPAPIError as e:
    if e.status_code == 404:
        print(f"Case not found: {e}", file=sys.stderr)
        sys.exit(1)
    elif e.status_code == 401:
        print(f"Authentication failed: {e}", file=sys.stderr)
        sys.exit(65)
except APIError as e:
    print(f"API error: {e}", file=sys.stderr)
    sys.exit(69)
```

### Workspace Manager with Pathlib Error Handling
```python
# Source: pathlib official docs
from pathlib import Path
from typing import List, Tuple
import logging

logger = logging.getLogger(__name__)

class WorkspaceManager:
    """Workspace manager with robust error handling."""

    def __init__(self, base_dir: str, case_number: str, account_name: str, case_summary: str):
        """Initialize workspace manager."""
        self.base_dir = Path(base_dir)
        self.case_number = case_number
        self.account_name_formatted = shorten_and_format(account_name)
        self.case_summary_formatted = shorten_and_format(case_summary)

        # Validate base directory exists
        if not self.base_dir.exists():
            raise WorkspaceError(
                f"Base directory does not exist: {self.base_dir}. "
                f"Try: Create it with 'mkdir -p {self.base_dir}'"
            )

        if not self.base_dir.is_dir():
            raise WorkspaceError(
                f"Base path is not a directory: {self.base_dir}. "
                f"Check: Path conflicts with existing file"
            )

    def _get_workspace_path(self) -> Path:
        """Get workspace path for case."""
        return (
            self.base_dir /
            self.account_name_formatted /
            f"{self.case_number}-{self.case_summary_formatted}"
        )

    def create_workspace(self) -> Path:
        """
        Create workspace directory structure.

        Returns:
            Path to workspace root

        Raises:
            WorkspaceError: If creation fails
        """
        workspace = self._get_workspace_path()

        try:
            # Create directory structure
            (workspace / "files" / "attach").mkdir(parents=True, exist_ok=True)
            (workspace / "files" / "dp").mkdir(parents=True, exist_ok=True)
            (workspace / "files" / "cp").mkdir(parents=True, exist_ok=True)

            # Create files
            self._create_file(workspace / "00-caseComments.md")
            self._create_file(workspace / "10-notes.md")
            self._create_file(workspace / "20-notes.md")
            self._create_file(workspace / "30-notes.md")
            self._create_file(workspace / "80-scratch.md")

            logger.info(f"Created workspace: {workspace}")
            return workspace

        except PermissionError:
            raise WorkspaceError(
                f"Permission denied creating workspace at {workspace}. "
                f"Try: Check permissions with 'ls -ld {workspace.parent}'"
            )
        except OSError as e:
            raise WorkspaceError(
                f"Failed to create workspace: {e}. "
                f"Check: Disk space and path length limits"
            )

    def _create_file(self, file_path: Path) -> None:
        """Create file if it doesn't exist."""
        try:
            file_path.touch(exist_ok=True)
        except PermissionError:
            raise WorkspaceError(
                f"Permission denied creating file {file_path}. "
                f"Try: chmod +w {file_path.parent}"
            )
        except OSError as e:
            raise WorkspaceError(f"Failed to create {file_path}: {e}")

    def check_workspace(self) -> Tuple[str, List[str]]:
        """
        Check workspace status.

        Returns:
            (status, missing_items) where status is 'OK', 'PARTIAL', or 'MISSING'
        """
        workspace = self._get_workspace_path()

        if not workspace.exists():
            return 'MISSING', [str(workspace)]

        expected_files = [
            workspace / "files" / "attach",
            workspace / "files" / "dp",
            workspace / "files" / "cp",
            workspace / "00-caseComments.md",
            workspace / "10-notes.md",
            workspace / "20-notes.md",
            workspace / "30-notes.md",
            workspace / "80-scratch.md"
        ]

        missing = []
        for path in expected_files:
            if not path.exists():
                missing.append(str(path))

        if not missing:
            return 'OK', []
        else:
            return 'PARTIAL', missing

    def get_attachment_dir(self) -> Path:
        """Get attachment directory path."""
        return self._get_workspace_path() / "files" / "attach"
```

### Logging Configuration with Error Handling
```python
# Source: Python logging best practices 2026
import logging
import logging.config
import sys
from pathlib import Path

def setup_logging(debug: bool = False, log_file: Path = None) -> None:
    """
    Configure logging with appropriate levels and handlers.

    Args:
        debug: Enable debug level logging
        log_file: Optional file to write logs to
    """
    log_level = logging.DEBUG if debug else logging.WARNING

    # Base configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            },
            'detailed': {
                'format': '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'standard',
                'stream': 'ext://sys.stderr'  # Errors to stderr
            }
        },
        'root': {
            'level': log_level,
            'handlers': ['console']
        }
    }

    # Add file handler if specified
    if log_file:
        try:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            config['handlers']['file'] = {
                'class': 'logging.handlers.RotatingFileHandler',
                'level': logging.DEBUG,
                'formatter': 'detailed',
                'filename': str(log_file),
                'maxBytes': 10485760,  # 10MB
                'backupCount': 3
            }
            config['root']['handlers'].append('file')
        except OSError as e:
            print(f"Warning: Could not create log file {log_file}: {e}", file=sys.stderr)

    logging.config.dictConfig(config)

    # Log exceptions with full traceback
    def exception_handler(exc_type, exc_value, exc_traceback):
        """Log uncaught exceptions."""
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        logging.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )

    sys.excepthook = exception_handler
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual retry loops | urllib3.Retry with requests.Session | urllib3 1.0 (2014) | Handles Retry-After, exponential backoff, connection pooling automatically |
| os.path + open() | pathlib.Path | Python 3.4 (2014) | Clearer exceptions, object-oriented, platform-agnostic paths |
| print() debugging | logging module with levels | Always available | Structured, configurable, production-ready logging |
| Generic exit code 1 | Specific codes (0, 1, 2, 65-78) | Unix sysexits.h (1993) | Scripting can distinguish error types, automation can retry appropriately |
| String error messages | Exception hierarchy with context | Modern Python | Type-safe error handling, catch specific errors, add context |
| exists() then open() | try/except or pathlib methods | TOCTOU awareness | Eliminates race condition, atomic operations |
| print() for errors | stderr via file=sys.stderr | Unix convention | Separates data from errors, enables pipeline scripting |
| backoff library | urllib3.Retry (for HTTP) | urllib3 native support | One less dependency for common case |

**Deprecated/outdated:**
- **os.path for new code:** Still works but pathlib is modern standard (Python 3.4+)
- **Generic Exception catching:** Catch specific exceptions or custom base exceptions
- **No timeouts on requests:** Always set timeout, requests library won't do it for you
- **Printing errors to stdout:** Use stderr or logging module
- **subprocess.call/check_call:** Use subprocess.run() (Python 3.5+) with capture_output and timeout

## Open Questions

Things that couldn't be fully resolved:

1. **Rich library adoption**
   - What we know: Rich provides enhanced tracebacks, terminal formatting, requires Python 3.8+
   - What's unclear: Whether to add as dependency or keep simple (MC requires Python 3.8+, so compatible)
   - Recommendation: Optional dependency for now. Could add later for better UX if users want it.

2. **Exit code granularity on Windows**
   - What we know: os.EX_* codes work on BSD/Mac but not Windows. Simple codes (0, 1, 2) work everywhere.
   - What's unclear: Whether MC CLI needs to support Windows (likely internal Red Hat tool, likely Linux/Mac)
   - Recommendation: Use specific codes (65=auth, 69=API, 73=create, 74=I/O) for Linux/Mac. Document codes for scripting.

3. **Partial download resume strategy**
   - What we know: HTTP Range header works if server supports it (206 response). Red Hat API may or may not support it.
   - What's unclear: Whether Red Hat API supports resumable downloads
   - Recommendation: Phase 5 should implement write-to-.tmp-rename-on-success pattern. Future enhancement could add Range header support if API supports it.

4. **Structured logging format**
   - What we know: JSON logging is best practice for production, enables log aggregation. structlog provides this.
   - What's unclear: Whether MC CLI needs machine-readable logs or human-readable is sufficient
   - Recommendation: Use standard logging module with human-readable format. Can add structlog later if needed for monitoring/aggregation.

## Sources

### Primary (HIGH confidence)
- [urllib3.util.Retry documentation](https://urllib3.readthedocs.io/en/stable/reference/urllib3.util.html) - Retry class parameters and backoff calculation
- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) - Exception handling and best practices
- [requests Advanced Usage documentation](https://requests.readthedocs.io/en/latest/user/advanced/) - Session objects, timeouts, exceptions
- [clig.dev CLI Guidelines](https://clig.dev/) - Error messages, exit codes, stderr usage
- [Python logging HOWTO](https://docs.python.org/3/howto/logging.html) - Official logging documentation

### Secondary (MEDIUM confidence)
- [How to Retry Failed Python Requests [2026] - ZenRows](https://www.zenrows.com/blog/python-requests-retry) - Verified urllib3.Retry approach
- [Python Logging Best Practices 2026](https://betterstack.com/community/guides/logging/python/python-logging-best-practices/) - Production logging patterns
- [Exception Handling Best Practices - Real Python](https://realpython.com/ref/best-practices/exception-handling/) - Raise low, catch high pattern
- [requests.exceptions documentation](https://requests.readthedocs.io/en/latest/_modules/requests/exceptions/) - Exception hierarchy
- [ldap3 Exceptions documentation](https://ldap3.readthedocs.io/en/latest/exceptions.html) - LDAP error handling

### Tertiary (LOW confidence)
- [5 Error Handling Patterns in Python - KDnuggets](https://www.kdnuggets.com/5-error-handling-patterns-in-python-beyond-try-except) - Batch error aggregation pattern
- [Rich library traceback documentation](https://rich.readthedocs.io/en/latest/traceback.html) - Enhanced traceback formatting
- [Python Requests Timeout Guide - Oxylabs](https://oxylabs.io/blog/python-requests-timeout) - Timeout best practices
- [Resumable Downloads with Python - Medium](https://medium.com/@rathnak010/resumable-download-667a28fb494d) - HTTP Range header pattern

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - urllib3.Retry, pathlib, logging are proven standards with official documentation
- Architecture: HIGH - Patterns verified from official docs (urllib3, pathlib, requests) and authoritative sources (clig.dev)
- Pitfalls: MEDIUM - Based on community best practices and documentation, not all verified in production MC context
- LDAP error handling: MEDIUM - ldap3 library documented but MC uses subprocess ldapsearch, not Python library
- Exit codes: MEDIUM - sysexits.h standard documented but Windows compatibility unclear

**Research date:** 2026-01-22
**Valid until:** 2026-02-21 (30 days - stable domain with mature libraries)
