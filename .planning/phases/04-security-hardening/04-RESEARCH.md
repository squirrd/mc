# Phase 04: Security Hardening - Research

**Researched:** 2026-01-22
**Domain:** Python security, token management, SSL/TLS, input validation, file operations
**Confidence:** MEDIUM

## Summary

Security hardening for a Python CLI tool requires implementing four key security controls: token expiration validation with file-based caching, explicit SSL certificate verification, input validation for API parameters, and safe handling of large file downloads. The current codebase uses the `requests` library without explicit SSL verification, has no token caching (fetches fresh token on every invocation), performs no input validation on case numbers, and lacks file size checks before downloads.

The standard approach combines Python's built-in security features (`os.chmod` for file permissions, `shutil.disk_usage` for disk space checks) with the `requests` library's SSL capabilities and simple file-based token caching using JSON. For security linting, Bandit is the industry standard tool for identifying common Python security issues. The OAuth2 token refresh pattern should validate expiration with a 5-minute buffer and automatically refresh when needed.

**Primary recommendation:** Use standard library functions for security primitives (file permissions, disk space) rather than external dependencies. Add explicit `verify=True` to all requests calls with support for custom CA bundles via environment variables. Implement simple regex-based validation for 8-digit case numbers. Use file-based token cache at `~/.mc/token` with 0600 permissions.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| requests | >=2.31.0 | HTTP client with SSL support | Already in use, built-in SSL verification, widely adopted |
| bandit | Latest | Security linting | Industry standard for Python security scanning, used by OpenStack |
| Python stdlib | 3.8+ | File ops, permissions, regex | Built-in, no dependencies, cross-platform |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tqdm | Latest | Progress bars for downloads | Optional - for visual feedback on large downloads |
| certifi | Latest | CA certificate bundle | Auto-installed by requests, keep updated for latest root CAs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| File-based token cache | Keyring library | Keyring uses OS credential store (more secure) but adds dependency and complexity |
| Regex validation | Pydantic | Pydantic provides robust validation but overkill for simple 8-digit check |
| requests | httpx | httpx has modern async support but not needed for this use case |

**Installation:**
```bash
# Production dependencies (already installed)
pip install requests>=2.31.0

# Development dependencies (add to pyproject.toml)
pip install bandit>=1.7.0

# Optional for enhanced download UX
pip install tqdm>=4.60.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── utils/
│   ├── auth.py              # Token management with caching
│   ├── validation.py        # Input validation functions
│   └── file_ops.py          # File operations with security checks
├── integrations/
│   └── redhat_api.py        # API client with SSL verification
└── config/
    └── security.py          # Security configuration constants
```

### Pattern 1: Token Cache with Expiration

**What:** File-based token cache with JSON storage, expiration checking, and automatic refresh

**When to use:** For OAuth2/SSO tokens that expire and can be refreshed

**Example:**
```python
# Token cache structure in ~/.mc/token (0600 permissions)
{
    "access_token": "eyJhbGc...",
    "expires_at": 1642876543,  # Unix timestamp
    "token_type": "Bearer"
}

# Usage pattern
import os
import json
import time

TOKEN_CACHE_PATH = os.path.expanduser("~/.mc/token")
EXPIRY_BUFFER_SECONDS = 300  # 5 minutes

def get_cached_token():
    """Get token from cache if valid, otherwise refresh."""
    if os.path.exists(TOKEN_CACHE_PATH):
        with open(TOKEN_CACHE_PATH, 'r') as f:
            cache = json.load(f)

        # Check if token is still valid (with buffer)
        if time.time() < (cache['expires_at'] - EXPIRY_BUFFER_SECONDS):
            return cache['access_token']

    # Token expired or doesn't exist - refresh it
    return refresh_and_cache_token()

def refresh_and_cache_token():
    """Fetch new token and cache it."""
    # Call SSO endpoint to get new token
    token_data = fetch_new_token()

    # Calculate expiration time
    expires_at = time.time() + token_data.get('expires_in', 3600)

    # Create cache structure
    cache = {
        'access_token': token_data['access_token'],
        'expires_at': expires_at,
        'token_type': token_data.get('token_type', 'Bearer')
    }

    # Write cache with secure permissions
    os.makedirs(os.path.dirname(TOKEN_CACHE_PATH), mode=0o700, exist_ok=True)
    with open(TOKEN_CACHE_PATH, 'w') as f:
        json.dump(cache, f)
    os.chmod(TOKEN_CACHE_PATH, 0o600)

    return cache['access_token']
```

### Pattern 2: Explicit SSL Verification

**What:** Always set `verify=True` explicitly in requests, support custom CA bundles

**When to use:** All production HTTP/HTTPS requests

**Example:**
```python
import os
import requests

def get_ca_bundle():
    """Get CA bundle from config or environment variables."""
    # Check environment variables (requests library convention)
    ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
    if not ca_bundle:
        ca_bundle = os.environ.get('CURL_CA_BUNDLE')

    # Default to True (use certifi bundle)
    return ca_bundle if ca_bundle else True

# In RedHatAPIClient
class RedHatAPIClient:
    def __init__(self, access_token, verify_ssl=None):
        self.access_token = access_token
        self.headers = {'Authorization': f'Bearer {access_token}'}
        # Get CA bundle path or True for default
        self.verify_ssl = verify_ssl if verify_ssl is not None else get_ca_bundle()

    def fetch_case_details(self, case_number):
        url = f"{self.BASE_URL}/cases/{case_number}"
        # Explicit verify parameter
        response = requests.get(url, headers=self.headers, verify=self.verify_ssl)
        response.raise_for_status()
        return response.json()
```

### Pattern 3: Input Validation

**What:** Validate case numbers before API calls using regex and clear error messages

**When to use:** Before any API call that uses user-provided identifiers

**Example:**
```python
import re

def validate_case_number(case_number):
    """
    Validate case number format (exactly 8 digits).

    Args:
        case_number: Case number string to validate

    Returns:
        str: Validated case number

    Raises:
        ValueError: If case number format is invalid
    """
    # Strip whitespace
    case_number = str(case_number).strip()

    # Check format: exactly 8 digits
    if not re.match(r'^\d{8}$', case_number):
        raise ValueError(
            f"Invalid case number format: '{case_number}'. "
            "Case number must be exactly 8 digits. Example: 12345678"
        )

    return case_number

# Usage in commands
def attach(case_number, base_dir):
    # Validate BEFORE making any API calls
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        print(f"Error: {e}")
        exit(1)

    # Proceed with validated input
    access_token = get_access_token()
    api_client = RedHatAPIClient(access_token)
    case_details = api_client.fetch_case_details(case_number)
```

### Pattern 4: Large File Download Warning

**What:** Check disk space and file size before downloading, warn if > threshold

**When to use:** Before initiating file downloads, especially in streaming mode

**Example:**
```python
import os
import shutil

def check_download_safety(file_size, download_path, threshold_gb=3):
    """
    Check if download is safe (enough disk space, reasonable size).

    Args:
        file_size: Size of file in bytes
        download_path: Path where file will be saved
        threshold_gb: Warning threshold in GB

    Returns:
        tuple: (is_safe: bool, warning_msg: str or None)
    """
    threshold_bytes = threshold_gb * 1024 * 1024 * 1024

    # Check file size threshold
    if file_size > threshold_bytes:
        # Get disk usage
        stat = shutil.disk_usage(os.path.dirname(download_path))
        free_gb = stat.free / (1024 ** 3)
        file_gb = file_size / (1024 ** 3)

        # Estimate download time (assume 10 MB/s average connection)
        estimated_seconds = file_size / (10 * 1024 * 1024)
        estimated_minutes = estimated_seconds / 60

        warning = (
            f"⚠️  Large file download warning:\n"
            f"  File size: {file_gb:.2f} GB\n"
            f"  Free disk space: {free_gb:.2f} GB\n"
            f"  Estimated download time: {estimated_minutes:.1f} minutes\n"
        )

        # Check if enough space (need file size + 10% buffer)
        if stat.free < (file_size * 1.1):
            return False, warning + "  ❌ Insufficient disk space!"

        return True, warning

    return True, None

# Usage in download_file
def download_file(self, url, local_filename, force=False):
    # Get file size from HEAD request
    head_response = requests.head(url, headers=self.headers, verify=self.verify_ssl)
    head_response.raise_for_status()
    file_size = int(head_response.headers.get('content-length', 0))

    # Check safety
    is_safe, warning = check_download_safety(file_size, local_filename)

    if warning and not force:
        print(warning)
        if not is_safe:
            raise RuntimeError("Download blocked due to insufficient disk space")

    # Proceed with download
    with requests.get(url, headers=self.headers, stream=True, verify=self.verify_ssl) as response:
        response.raise_for_status()
        with open(local_filename, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
```

### Anti-Patterns to Avoid

- **Setting `verify=False` globally:** Never disable SSL verification by default. Require explicit `--insecure` flag per endpoint
- **Storing tokens without permissions check:** Always set 0600 permissions on token cache files
- **Validating after API call:** Validate inputs before making network requests to fail fast
- **Ignoring token expiration:** Always check expiration with buffer before using cached tokens
- **Using `eval()` or `exec()` on user input:** Never execute user input as code (Bandit will flag this)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SSL certificate validation | Custom certificate checking | `requests` with `verify=True` | Handles certificate chains, revocation, hostname validation, protocol negotiation |
| CA certificate bundle | Manual certificate management | `certifi` package + env vars | Automatically updated root CAs, widely trusted, cross-platform |
| File permissions | String-based chmod calls | `os.chmod()` with octal | Type-safe, cross-platform, handles edge cases |
| Disk space checking | Parsing `df` output | `shutil.disk_usage()` | Cross-platform (Windows/Unix), reliable, no subprocess overhead |
| JWT token parsing | String manipulation | Standard library `json` + time | Token structure is simple JSON, no need for PyJWT unless validating signatures |
| Progress bars | Custom print statements | `tqdm` library | Handles terminal resizing, ETA calculation, nested progress, multiple formats |
| Regex validation | String operations | `re.match()` with raw strings | Handles edge cases, compiled patterns, Unicode support |

**Key insight:** Python's standard library already provides secure, cross-platform implementations for most security primitives. Adding external libraries for these increases attack surface and dependency burden. The `requests` library handles SSL complexity correctly - just use `verify=True`.

## Common Pitfalls

### Pitfall 1: Virtual Environment Ignoring Environment Variables

**What goes wrong:** `REQUESTS_CA_BUNDLE` and `CURL_CA_BUNDLE` environment variables may be ignored when running inside a Python virtual environment (venv).

**Why it happens:** Virtual environments can isolate environment variable handling, and the requests library may not properly check for these variables in all venv configurations.

**How to avoid:**
- Explicitly read environment variables in code and pass to `verify` parameter
- Document that users may need to specify CA bundle via CLI flag rather than env var
- Test SSL configuration in both venv and system Python

**Warning signs:** SSL verification works in system Python but fails in venv; custom CA certificates not being recognized

### Pitfall 2: Race Condition in Token Cache

**What goes wrong:** Multiple concurrent invocations of the CLI can race to refresh the token, causing unnecessary API calls or corrupted cache files.

**Why it happens:** File-based cache has no locking mechanism for concurrent access.

**How to avoid:**
- Use atomic write pattern (write to temp file, then rename)
- Accept that occasional duplicate refreshes are acceptable for CLI tool (low concurrency)
- Document that tool is designed for interactive single-user use, not high-concurrency batch processing

**Warning signs:** Intermittent "invalid token" errors when running multiple commands simultaneously; corrupted JSON in token cache file

### Pitfall 3: Default Permission Umask

**What goes wrong:** Even when calling `os.chmod(path, 0o600)`, the file may already have been created with default permissions (potentially world-readable), creating a brief window where secrets are exposed.

**Why it happens:** File creation and permission setting are separate operations; the file exists with umask-based permissions between creation and chmod.

**How to avoid:**
- Use `os.open()` with mode parameter for atomic permission setting: `os.fdopen(os.open(path, os.O_CREAT | os.O_WRONLY, 0o600), 'w')`
- Or set umask before file operations: `old_umask = os.umask(0o077); create_file(); os.umask(old_umask)`
- Always verify final permissions after creation

**Warning signs:** Security scanners flagging brief permission window; file readable by other users momentarily

### Pitfall 4: SSL Error Messages Too Technical

**What goes wrong:** SSL verification failures produce cryptic error messages like "CERTIFICATE_VERIFY_FAILED" without context about which host or why it failed.

**Why it happens:** `requests.exceptions.SSLError` doesn't include hostname or cert details in the exception message.

**How to avoid:**
- Catch `requests.exceptions.SSLError` and wrap with user-friendly message
- Include hostname, reason (expired, self-signed, wrong host), and remediation steps
- Provide clear `--insecure-host` flag usage example

**Warning signs:** User confusion about SSL errors; support requests asking "which certificate is wrong?"

### Pitfall 5: Bandit False Positives

**What goes wrong:** Bandit flags `subprocess.run()` calls (used for LDAP) as security risks, even when properly configured.

**Why it happens:** Bandit uses static analysis and can't determine if subprocess calls are safe based on runtime context.

**How to avoid:**
- Use `# nosec` comments for known-safe subprocess calls with justification
- Configure Bandit to skip specific checks for specific files via `.bandit` config
- Document why certain warnings are suppressed in code comments

**Warning signs:** Bandit blocking CI pipeline for safe LDAP subprocess call; constant need to suppress same warning

### Pitfall 6: Case Number Validation Too Strict

**What goes wrong:** Users copy-paste case numbers with spaces, leading zeros, or dashes, and validation rejects them even though the API would accept them.

**Why it happens:** Regex validation is exact match only, doesn't normalize input.

**How to avoid:**
- Strip whitespace before validation: `case_number.strip()`
- Consider stripping leading zeros if API accepts both formats
- Provide clear error message showing what was received vs what's expected

**Warning signs:** User frustration with "works when I type it, fails when I paste it"; valid case numbers rejected

## Code Examples

Verified patterns from official sources:

### Token Expiration Validation with Buffer
```python
import time

def is_token_expired(expires_at, buffer_seconds=300):
    """
    Check if token is expired or will expire within buffer period.

    Args:
        expires_at: Unix timestamp when token expires
        buffer_seconds: Safety buffer (default 5 minutes)

    Returns:
        bool: True if token is expired or expiring soon
    """
    current_time = time.time()
    return current_time >= (expires_at - buffer_seconds)

# Usage
cache = load_token_cache()
if cache and not is_token_expired(cache['expires_at']):
    return cache['access_token']
else:
    return refresh_token()
```

### Secure File Creation with Permissions
```python
import os
import json

def save_token_securely(token_data, cache_path):
    """
    Save token to file with secure permissions (0600).

    Args:
        token_data: Dictionary containing token information
        cache_path: Path to cache file
    """
    # Ensure parent directory exists with 0700 permissions
    cache_dir = os.path.dirname(cache_path)
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)

    # Create file with secure permissions atomically
    fd = os.open(cache_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(token_data, f, indent=2)

    # Verify permissions were set correctly
    stat_info = os.stat(cache_path)
    actual_perms = oct(stat_info.st_mode)[-3:]
    if actual_perms != '600':
        raise RuntimeError(f"Failed to set secure permissions on {cache_path}")
```

### Case Number Validation
```python
import re

def validate_case_number(case_number):
    """
    Validate case number is exactly 8 digits.

    Args:
        case_number: Case number to validate (string or int)

    Returns:
        str: Validated case number (as string)

    Raises:
        ValueError: If format is invalid
    """
    # Normalize input
    case_str = str(case_number).strip()

    # Validate format
    if not re.match(r'^\d{8}$', case_str):
        raise ValueError(
            f"Invalid case number: '{case_number}'. "
            f"Case number must be exactly 8 digits. Example: 12345678"
        )

    return case_str
```

### Disk Space Check
```python
import shutil

def has_sufficient_disk_space(file_size, download_path, buffer_percent=10):
    """
    Check if there's enough disk space for download.

    Args:
        file_size: Size in bytes to download
        download_path: Where file will be saved
        buffer_percent: Extra space buffer (default 10%)

    Returns:
        tuple: (has_space: bool, free_gb: float, required_gb: float)
    """
    # Get disk usage for target path
    stat = shutil.disk_usage(os.path.dirname(download_path))

    # Calculate required space with buffer
    required_bytes = file_size * (1 + buffer_percent / 100)

    # Convert to GB for readability
    free_gb = stat.free / (1024 ** 3)
    required_gb = required_bytes / (1024 ** 3)

    has_space = stat.free >= required_bytes

    return has_space, free_gb, required_gb
```

### SSL Verification with Custom CA Bundle
```python
import os
import requests

def make_verified_request(url, headers=None):
    """
    Make HTTPS request with explicit SSL verification.

    Supports custom CA bundles via environment variables:
    - REQUESTS_CA_BUNDLE
    - CURL_CA_BUNDLE

    Args:
        url: URL to request
        headers: Optional request headers

    Returns:
        requests.Response object
    """
    # Get CA bundle from environment or use default
    ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE') or \
                os.environ.get('CURL_CA_BUNDLE') or \
                True  # True = use certifi default

    try:
        response = requests.get(url, headers=headers, verify=ca_bundle)
        response.raise_for_status()
        return response
    except requests.exceptions.SSLError as e:
        # Provide helpful error message
        raise RuntimeError(
            f"SSL certificate verification failed for {url}.\n"
            f"Reason: {str(e)}\n"
            f"To bypass for this host only, use: --insecure-host {url}"
        ) from e
```

### Bandit Configuration
```yaml
# .bandit config file
skips:
  - B603  # subprocess_without_shell_equals_true
  - B607  # start_process_with_partial_path

exclude_dirs:
  - /tests/
  - /docs/

# Only fail on HIGH severity issues
severity: HIGH
confidence: MEDIUM
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `verify=False` by default | `verify=True` explicitly | requests 2.16+ (2017) | Broke code using self-signed certs, improved security |
| Manual cert bundle updates | Auto-updated via certifi | certifi created 2015 | Users no longer need manual CA updates |
| String-based file permissions | Octal literals in Python 3 | Python 3.0 (2008) | Type-safe, clearer intent (0o600 vs "600") |
| Parsing df output | `shutil.disk_usage()` | Python 3.3 (2012) | Cross-platform, no subprocess overhead |
| No token caching | File or keyring-based cache | OAuth2 best practice 2015+ | Reduced API calls, better UX |
| Manual progress tracking | tqdm library | tqdm 1.0 (2015) | Better UX for long operations |
| Custom input validation | Regex + clear errors | Ongoing | Improved error messages, fail-fast |

**Deprecated/outdated:**
- Using `SSLContext` directly for requests: Requests handles this internally, just use `verify` parameter
- Parsing SSL error strings: Use exception hierarchy (`requests.exceptions.SSLError`)
- Hard-coded CA bundle paths: Use certifi and environment variables for portability
- `os.system()` for subprocess: Use `subprocess.run()` with explicit args (safer, Bandit-approved with `check=True`)

## Open Questions

Things that couldn't be fully resolved:

1. **Token refresh retry strategy**
   - What we know: Single retry with exponential backoff is standard OAuth2 pattern
   - What's unclear: Whether to retry on network errors vs auth errors (should differentiate)
   - Recommendation: Retry on network errors (timeouts, connection failures), fail immediately on 401/403 auth errors. Implement simple retry with 1-second delay for network errors only.

2. **Attachment ID validation**
   - What we know: CONTEXT.md marked as "Claude's discretion"
   - What's unclear: API format for attachment IDs (not visible in current code)
   - Recommendation: Research Red Hat API documentation during planning phase. If attachment IDs are UUIDs, validate UUID format. If numeric, validate as integers.

3. **TTY detection for batch mode**
   - What we know: Tool runs both interactively (host CLI) and in batch mode (containers)
   - What's unclear: Best way to detect batch mode (TTY, env var, flag?)
   - Recommendation: Use combination: `sys.stdout.isatty()` for automatic detection, plus `--force` or `--yes` flag for explicit override. Environment variable `MC_BATCH_MODE=1` as third option for containers.

4. **Config file format and location**
   - What we know: CONTEXT mentions `~/.mc/config` for CA bundles
   - What's unclear: Full config file format (YAML? JSON? INI?)
   - Recommendation: Use simple INI format (Python configparser) for now. Can upgrade to YAML later if needed. Store threshold values, default flags, trusted hosts.

## Sources

### Primary (HIGH confidence)

**Official Documentation:**
- [Requests Advanced Usage - SSL Verification](https://requests.readthedocs.io/en/latest/user/advanced/) - Official requests documentation on SSL cert verification
- [Python shutil documentation](https://docs.python.org/3/library/shutil.html#shutil.disk_usage) - Standard library disk_usage function
- [Python os documentation](https://docs.python.org/3/library/os.html#os.chmod) - File permissions with os.chmod
- [Python re documentation](https://docs.python.org/3/library/re.html) - Regular expressions for input validation

**Security Tools:**
- [Bandit GitHub Repository](https://github.com/PyCQA/bandit) - Official Bandit security linter
- [Bandit Documentation](https://bandit.readthedocs.io/) - Official Bandit documentation
- [OpenStack Bandit Guide](https://wiki.openstack.org/wiki/Security/Projects/Bandit) - Production usage patterns from OpenStack

### Secondary (MEDIUM confidence)

**Best Practices Articles:**
- [SSL Certificate Verification - Python requests - GeeksforGeeks](https://www.geeksforgeeks.org/python/ssl-certificate-verification-python-requests/) - SSL verification patterns
- [JWT Best Practices - Curity](https://curity.io/resources/learn/jwt-best-practices/) - Token expiration and validation
- [OAuth 2 Refresh Tokens - Frontegg](https://frontegg.com/blog/oauth-2-refresh-tokens) - Token refresh patterns
- [Python Security Best Practices - ArjanCodes](https://arjancodes.com/blog/best-practices-for-securing-python-applications/) - General Python security guidance
- [Securing Sensitive Data in Python - System Weakness](https://systemweakness.com/securing-sensitive-data-in-python-best-practices-for-storing-api-keys-and-credentials-2bee9ede57ee) - Token storage patterns

**Implementation Examples:**
- [Python requests download file with tqdm progress bar](https://gist.github.com/yanqd0/c13ed29e29432e3cf3e7c38467f42f51) - File download with progress
- [tqdm GitHub Repository](https://github.com/tqdm/tqdm) - Progress bar library
- [How to Securely Save Credentials in Python](https://medium.com/jungletronics/how-to-securely-save-credentials-in-python-dd5c6983741a) - File permissions and secure storage

### Tertiary (LOW confidence)

**Community Discussions:**
- [REQUESTS_CA_BUNDLE ignored in venv - GitHub Issue #6660](https://github.com/psf/requests/issues/6660) - Known issue with env vars in venv
- [Hugging Face disk_usage check - GitHub Issue #1551](https://github.com/huggingface/huggingface_hub/issues/1551) - Pre-download disk space checking pattern
- [Download Time Calculators](https://downloadtimecalculator.com/) - Formula for estimating download time (general reference)

**Standards and Protocols:**
- [OAuth 2.0 Refresh Tokens Best Practices - Stateful](https://stateful.com/blog/oauth-refresh-token-best-practices) - OAuth2 patterns
- [Google OAuth2 Best Practices](https://developers.google.com/identity/protocols/oauth2/resources/best-practices) - OAuth2 implementation guidance

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Using Python stdlib and requests library is well-established, Bandit is industry standard
- Architecture patterns: MEDIUM - Token caching and SSL verification are standard, but file-based cache has known race condition limitations
- Input validation: HIGH - Regex validation for 8-digit numbers is straightforward, well-documented pattern
- File operations: HIGH - shutil.disk_usage and os.chmod are standard library, cross-platform, well-tested
- Pitfalls: MEDIUM - Based on GitHub issues and community reports, not all verified in production

**Research date:** 2026-01-22
**Valid until:** 2026-02-22 (30 days - security practices change slowly, stdlib APIs are stable)

**Current implementation gaps identified:**
1. No token caching (fetches new token every invocation) - in `src/mc/utils/auth.py`
2. No explicit SSL verification (`verify` parameter not used) - in `src/mc/integrations/redhat_api.py`
3. No input validation on case numbers - in `src/mc/cli/commands/case.py`
4. No file size or disk space checking before downloads - in `src/mc/integrations/redhat_api.py`
5. No security linting configured (bandit not in dev dependencies) - in `pyproject.toml`

**Existing code that can be leveraged:**
- LDAP module already has input validation example (uid length check) - in `src/mc/integrations/ldap.py`
- File operations module exists for path checking - in `src/mc/utils/file_ops.py`
- Test infrastructure uses `responses` library for mocking HTTP - can test SSL verification
- CLI uses argparse - can add `--insecure-host` and `--force` flags easily
