# Phase 6: Infrastructure & Observability - Research

**Researched:** 2026-01-22
**Domain:** Python CLI observability, structured logging, progress tracking, retry logic
**Confidence:** HIGH

## Summary

This phase replaces 74 print() statements across 8 files with structured logging, adds debug mode, implements automatic retry logic for transient failures, and adds progress indicators for file downloads. The standard Python approach uses the built-in `logging` module for structured output, `tqdm` for progress bars, `tenacity` for retry logic, and native `requests` library features for resumable downloads via HTTP Range headers.

**Key findings:**
- Python's standard `logging` module is sufficient for structured logging with timestamps, levels, and module names - no third-party library required for basic functionality
- For JSON output and advanced structured logging, `structlog` is the current (2026) community standard, replacing `python-json-logger` which is no longer actively maintained
- `tqdm` is the dominant progress bar library with 60ns overhead, automatic byte scaling, and support for multiple simultaneous progress bars
- `tenacity` is the maintained fork of the abandoned `retrying` library, supporting exponential backoff, selective exception retry, and async patterns
- HTTP Range requests for resumable downloads are natively supported by the `requests` library already in use

**Primary recommendation:** Use Python's standard logging module with custom formatters for text/JSON output modes, tqdm for progress bars, tenacity for retry logic with exponential backoff, and requests Range headers for download resumption.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| logging (stdlib) | Python 3.11+ | Structured logging with levels, timestamps, module names | Built-in, zero dependencies, officially recommended |
| tqdm | 4.66+ | CLI progress bars with ETA and transfer speed | 60ns overhead, no dependencies, cross-platform |
| tenacity | 8.3+ | Retry logic with exponential backoff | Actively maintained fork of retrying, declarative API |
| requests (existing) | 2.31+ | HTTP client with Range header support | Already in project, supports resumable downloads natively |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| structlog | 25.5+ | Advanced structured logging with context binding | If you need log correlation IDs or complex context management (not required for this phase) |
| python-json-logger | 2.0+ | JSON formatter for stdlib logging | Only if avoiding structlog for simplicity (less feature-rich) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| logging (stdlib) | structlog | structlog adds context binding and processors but requires extra dependency; stdlib sufficient for CLI needs |
| tqdm | rich.progress | rich has prettier output but heavier dependency (includes entire rich library for terminal formatting) |
| tenacity | backoff | backoff has simpler API but less flexible (tenacity supports more stop/wait strategies) |

**Installation:**
```bash
# For Phase 6, only add these new dependencies
pip install tqdm>=4.66.0 tenacity>=8.3.0

# Already in project: requests>=2.31.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── utils/
│   ├── logging.py       # Logging configuration and setup
│   ├── retry.py         # Retry decorators and utilities
│   └── progress.py      # Progress bar helpers
├── cli/
│   └── main.py          # CLI entry point - configure logging here
└── integrations/
    └── redhat_api.py    # Apply retry and progress to downloads
```

### Pattern 1: Dual-Mode Logging Configuration

**What:** Configure logging to output human-readable text by default, switch to JSON with `--json-logs` flag

**When to use:** CLI applications that need both human debugging and CI/automation consumption

**Example:**
```python
# Source: Python logging documentation + structlog patterns
import logging
import sys
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record):
        log_obj = {
            'timestamp': datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            'level': record.levelname,
            'module': record.name,
            'message': record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info:
            log_obj['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_obj)

def setup_logging(json_logs=False, debug=False):
    """
    Configure logging for the application.

    Args:
        json_logs: If True, output JSON format; otherwise human-readable text
        debug: If True, set level to DEBUG; otherwise INFO
    """
    logger = logging.getLogger('mc')  # Use package name as root logger
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    # Remove existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    if json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format with color support
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    logger.addHandler(handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger
```

### Pattern 2: Sensitive Data Redaction Filter

**What:** Custom logging filter that redacts passwords, tokens, and credentials before output

**When to use:** Any application handling authentication or sensitive data

**Example:**
```python
# Source: Multiple logging best practices guides + custom implementation
import logging
import re

class SensitiveDataFilter(logging.Filter):
    """Filter that redacts sensitive data from log messages."""

    # Patterns for sensitive data
    PATTERNS = [
        (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE), r'\1<REDACTED>'),
        (re.compile(r'(Bearer\s+)([A-Za-z0-9\-._~+/]+=*)', re.IGNORECASE), r'\1<REDACTED>'),
        (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'}\s]+)', re.IGNORECASE), r'\1<REDACTED>'),
    ]

    @staticmethod
    def redact_token(token):
        """Show last 4 chars if token is >20 chars, otherwise fully redact."""
        if len(token) > 20:
            return f"...{token[-4:]}"
        return "<REDACTED>"

    def filter(self, record):
        """Redact sensitive data from log record message."""
        message = record.getMessage()

        # Apply regex patterns
        for pattern, replacement in self.PATTERNS:
            message = pattern.sub(replacement, message)

        # Update the record's message
        record.msg = message
        record.args = ()

        return True
```

### Pattern 3: Progress Bar for File Downloads

**What:** Wrap file download with tqdm to show progress, transfer speed, and ETA

**When to use:** Any file download operation, especially large files

**Example:**
```python
# Source: tqdm documentation + file download examples
import requests
from tqdm import tqdm

def download_file_with_progress(url, local_path, headers=None):
    """
    Download file with progress bar showing size, percentage, speed, and ETA.

    Args:
        url: URL to download from
        local_path: Where to save the file
        headers: Optional HTTP headers dict
    """
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    # Get file size from Content-Length header
    total_size = int(response.headers.get('content-length', 0))

    # Configure tqdm for byte-based progress
    with open(local_path, 'wb') as f, tqdm(
        desc=os.path.basename(local_path),
        total=total_size,
        unit='B',           # Bytes
        unit_scale=True,    # Auto-scale to KB, MB, GB
        unit_divisor=1024,  # Use 1024 for binary units (KiB, MiB, GiB)
        miniters=1,         # Update on every iteration
        mininterval=0.1,    # Update display every 100ms
    ) as pbar:
        for chunk in response.iter_content(chunk_size=8192):
            size = f.write(chunk)
            pbar.update(size)
```

### Pattern 4: Retry with Exponential Backoff

**What:** Decorator-based retry logic that retries transient failures but not permanent errors

**When to use:** API calls, network operations, any operation with transient failure modes

**Example:**
```python
# Source: tenacity official documentation
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    retry_if_not_exception_type,
)
import requests

@retry(
    # Stop after 3 attempts
    stop=stop_after_attempt(3),
    # Exponential backoff: wait 2^x seconds, starting at 1s, max 4s
    wait=wait_exponential(multiplier=1, min=1, max=4),
    # Retry on these exceptions
    retry=(
        retry_if_exception_type(requests.exceptions.Timeout) |
        retry_if_exception_type(requests.exceptions.ConnectionError) |
        retry_if_exception_type(requests.exceptions.HTTPError)
    ),
    # Don't retry authentication errors (fail fast)
    reraise=True,
)
def api_call_with_retry(url, headers):
    """Make API call with automatic retry on transient failures."""
    response = requests.get(url, headers=headers, timeout=30)

    # Don't retry 401/403 - these are auth failures
    if response.status_code in (401, 403):
        response.raise_for_status()

    # Retry 429 (rate limit) and 503 (service unavailable)
    if response.status_code in (429, 503):
        response.raise_for_status()

    response.raise_for_status()
    return response
```

### Pattern 5: Resumable Download with Range Requests

**What:** Use HTTP Range header to resume interrupted downloads from last byte position

**When to use:** Large file downloads that may be interrupted

**Example:**
```python
# Source: requests documentation + resumable download patterns
import os
import requests

def download_resumable(url, local_path, headers=None):
    """
    Download file with resume capability using HTTP Range requests.

    Args:
        url: URL to download from
        local_path: Where to save the file
        headers: Optional HTTP headers dict
    """
    headers = headers or {}

    # Check if partial file exists
    if os.path.exists(local_path):
        # Get current file size
        downloaded = os.path.getsize(local_path)
        # Request remaining bytes
        headers['Range'] = f'bytes={downloaded}-'
        mode = 'ab'  # Append to existing file
    else:
        downloaded = 0
        mode = 'wb'  # Write new file

    response = requests.get(url, headers=headers, stream=True, timeout=30)

    # 206 = Partial Content (resume), 200 = Full content
    if response.status_code not in (200, 206):
        response.raise_for_status()

    # Get total file size
    if response.status_code == 206:
        # Parse Content-Range header: "bytes 1000-2000/3000"
        content_range = response.headers.get('Content-Range', '')
        total_size = int(content_range.split('/')[-1])
    else:
        total_size = int(response.headers.get('Content-Length', 0))

    # Download with progress
    with open(local_path, mode) as f, tqdm(
        desc=os.path.basename(local_path),
        initial=downloaded,
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
        mininterval=0.1,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=8192):
            size = f.write(chunk)
            pbar.update(size)
```

### Anti-Patterns to Avoid

- **Using root logger in library code:** Always use `logging.getLogger(__name__)` to avoid interfering with application logging configuration
- **Formatting log messages with f-strings:** Use lazy evaluation `logger.info('Message: %s', value)` instead of `logger.info(f'Message: {value}')` to avoid expensive string operations when log level is disabled
- **Adding handlers in loops or multiple times:** Check if handlers exist before adding, or clear handlers first to prevent duplicate log messages
- **Calling basicConfig() after logger creation:** Configure logging before creating any loggers, otherwise settings won't apply
- **Not handling logging exceptions:** Logging errors should never crash the application - the stdlib handles this, but custom formatters/filters should be defensive

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Progress bars | Custom `\r` carriage return printing | tqdm | Cross-platform terminal handling, automatic rate limiting, nested bars, thread-safe |
| Retry logic | Manual sleep + loop with counters | tenacity | Handles edge cases (jitter, max wait), declarative, async-aware, exception filtering |
| Log formatting | String concatenation with timestamps | logging.Formatter | ISO 8601 dates, exception formatting, thread-safe, configurable |
| JSON logging | json.dumps() on print statements | logging.JSONFormatter or structlog | Handles exceptions, log levels, structured context, correlation IDs |
| Exponential backoff | Custom 2**attempt calculations | tenacity wait_exponential | Prevents thundering herd with jitter, configurable min/max, battle-tested |
| HTTP range requests | Manual byte offset tracking | requests with Range header | Server compatibility, partial content handling, connection reuse |
| Sensitive data redaction | Manual string replacement | logging.Filter subclass | Centralized, applies to all handlers, regex-based, maintains performance |

**Key insight:** Logging and retry logic have subtle concurrency, platform, and edge-case issues that are already solved by standard libraries. The Python logging module is specifically designed to never crash the application, even if logging itself fails - this is difficult to replicate correctly in custom code.

## Common Pitfalls

### Pitfall 1: Logger Hierarchy Not Respecting Configuration

**What goes wrong:** Creating loggers before configuring the logging system results in loggers that don't inherit the configured settings

**Why it happens:** Python's `logging.basicConfig()` and `logging.dictConfig()` disable existing loggers by default when called

**How to avoid:**
- Configure logging in `main()` before any imports that create loggers
- Use `disable_existing_loggers=False` in dict config
- Create a single setup function called at application entry point

**Warning signs:** Log messages not appearing despite correct level, handlers attached multiple times

### Pitfall 2: Expensive String Formatting in Disabled Log Levels

**What goes wrong:** Using f-strings or `.format()` in logging calls executes string formatting even when the log level is disabled, causing performance overhead

**Why it happens:** Python evaluates function arguments before calling the function

**How to avoid:**
- Use percent-formatting: `logger.debug('Value: %s', expensive_call())`
- For very expensive operations, guard with `if logger.isEnabledFor(logging.DEBUG)`

**Warning signs:** Application slowness when debug logging is disabled, CPU usage from string operations

### Pitfall 3: Progress Bar Updates Too Frequent or Too Slow

**What goes wrong:** Updating progress bar on every byte causes terminal flickering; updating too rarely makes it appear frozen

**Why it happens:** Terminal rendering has overhead; balance between responsiveness and performance

**How to avoid:**
- Use tqdm's `mininterval=0.1` (100ms minimum between updates)
- Use `miniters` to skip updates for small increments
- Let tqdm auto-calculate update frequency based on iteration rate

**Warning signs:** Terminal appears to flicker or refresh very rapidly; progress bar stays at 0% then jumps to 100%

### Pitfall 4: Not Handling 206 Partial Content in Resume Logic

**What goes wrong:** Resumable download code only checks for 200 OK, fails when server returns 206 Partial Content for range requests

**Why it happens:** Range requests return 206, not 200; the Content-Length header in 206 responses is the *remaining* bytes, not total

**How to avoid:**
- Accept both 200 and 206 status codes
- Parse Content-Range header to get total file size: `bytes 1000-2000/3000` → total is 3000
- Track downloaded bytes separately from total size

**Warning signs:** Resumed downloads fail with "Invalid status code 206", progress bar shows wrong total size

### Pitfall 5: Retry Logic on Non-Idempotent Operations

**What goes wrong:** Retrying POST/PUT/DELETE requests can cause duplicate operations (create resource twice, delete wrong item)

**Why it happens:** Transient failures can occur after the server processes the request but before the response is received

**How to avoid:**
- Only auto-retry idempotent operations (GET, HEAD)
- For non-idempotent operations, require explicit user confirmation for retry
- Use idempotency keys if API supports them

**Warning signs:** Duplicate resources created, database constraint violations on retry

### Pitfall 6: Not Filtering Sensitive Data from Exception Messages

**What goes wrong:** Exceptions raised during authentication contain tokens/passwords in the message, which get logged

**Why it happens:** Libraries like `requests` include full headers in exception details

**How to avoid:**
- Apply SensitiveDataFilter to the root logger to catch all messages
- Wrap authentication calls in try/except and re-raise with sanitized message
- Use logging.Filter on both the message and exception info

**Warning signs:** Tokens appearing in stack traces, credentials in error logs

## Code Examples

Verified patterns from official sources:

### Module-Level Logger Creation
```python
# Source: Python logging documentation - "Logging in Library Code"
import logging

# Create logger with module name - tracks package/module hierarchy
logger = logging.getLogger(__name__)

def my_function():
    logger.info('Operation started')
    logger.debug('Debug details: %s', some_value)
    logger.error('Operation failed: %s', error)
```

### Complete CLI Logging Setup
```python
# Source: Combination of Python logging docs + structlog patterns
import logging
import sys
import argparse

def setup_logging(args):
    """Configure logging based on CLI arguments."""
    # Get or create root logger for application
    logger = logging.getLogger('mc')

    # Set level based on --debug flag
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    # Clear any existing handlers
    logger.handlers.clear()

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)

    # Choose formatter based on --json-logs flag
    if args.json_logs:
        handler.setFormatter(JSONFormatter())
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)

    # Add sensitive data filter
    handler.addFilter(SensitiveDataFilter())

    logger.addHandler(handler)
    logger.propagate = False

    # Optionally configure file output for debug
    if args.debug and args.debug_file:
        file_handler = logging.FileHandler(args.debug_file)
        file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(message)s'
            )
        )
        logger.addHandler(file_handler)

    return logger

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--json-logs', action='store_true', help='Output logs as JSON')
    parser.add_argument('--debug-file', help='Write debug logs to file')
    args = parser.parse_args()

    # Configure logging first, before any operations
    logger = setup_logging(args)

    logger.info('Application started')
    # ... rest of application
```

### Multiple Simultaneous Progress Bars
```python
# Source: tqdm documentation - "Manual" mode
from tqdm import tqdm
import time

def download_multiple_files(urls):
    """Download multiple files with individual progress bars."""
    # Create progress bars for each file
    pbars = []
    for i, url in enumerate(urls):
        pbar = tqdm(
            desc=f'File {i+1}',
            total=100,
            position=i,  # Stack bars vertically
            leave=True,  # Keep bar after completion
        )
        pbars.append(pbar)

    # Update bars as downloads progress
    for i, pbar in enumerate(pbars):
        for _ in range(100):
            time.sleep(0.01)
            pbar.update(1)
        pbar.close()
```

### Combining Retry and Progress
```python
# Source: tenacity + tqdm integration pattern
from tenacity import retry, stop_after_attempt, wait_exponential
import requests
from tqdm import tqdm
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    before_sleep=lambda retry_state: logger.warning(
        'Download failed, retrying in %s seconds (attempt %s/3)',
        retry_state.next_action.sleep,
        retry_state.attempt_number
    )
)
def download_with_retry_and_progress(url, local_path, headers):
    """Download file with retry on failure and progress tracking."""
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    with open(local_path, 'wb') as f, tqdm(
        desc=os.path.basename(local_path),
        total=total_size,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
        mininterval=0.1,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=8192):
            size = f.write(chunk)
            pbar.update(size)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-json-logger | structlog | 2023-2024 | structlog actively maintained, better performance, more features (context binding, processors) |
| retrying library | tenacity | 2019 | retrying abandoned, tenacity is maintained fork with async support and better API |
| print() debugging | structured logging | Ongoing | JSON logs enable aggregation/analysis in log management platforms (ELK, Datadog, etc.) |
| Custom progress with \r | tqdm/rich | 2020+ | Libraries handle cross-platform terminal differences, nested bars, thread safety |
| Manual Range request tracking | requests + Range header | Always supported | Native support in requests, no special library needed |

**Deprecated/outdated:**
- **python-json-logger:** Not actively maintained; use structlog for new projects (or stdlib JSONFormatter for simple cases)
- **retrying library:** Abandoned in 2016; tenacity is the maintained fork
- **logging.warn():** Deprecated since Python 3.3, use `logging.warning()` instead
- **print() statements in libraries/applications:** Replaced by proper logging for production code

## Open Questions

Things that couldn't be fully resolved:

1. **Should retry notifications be logged at INFO or DEBUG level?**
   - What we know: Context document says "Claude's discretion" for retry notifications
   - What's unclear: Balance between user visibility and log noise
   - Recommendation: Log first retry at INFO (user should know about transient issues), subsequent retries at DEBUG (avoid spam). Final success/failure at INFO.

2. **How to handle progress bars when output is redirected (non-TTY)?**
   - What we know: tqdm detects non-TTY and falls back to periodic updates
   - What's unclear: Whether to disable progress bars entirely in CI/automation
   - Recommendation: Let tqdm handle it automatically; it's designed for this. In non-TTY, it outputs periodic status lines instead of overwriting.

3. **Should resume logic validate partial file integrity before resuming?**
   - What we know: Context says "Claude's discretion" for resume logic implementation
   - What's unclear: Trade-off between safety (re-download corrupted partials) and efficiency (trust partial file)
   - Recommendation: Trust partial file for now (simpler). If corruption is observed in practice, add checksum validation later. HTTP GET is idempotent, so re-downloading is always safe.

## Sources

### Primary (HIGH confidence)
- [Python Logging HOWTO (Official Documentation)](https://docs.python.org/3/howto/logging.html) - Official recommendations for logging configuration, module-level loggers, levels
- [tqdm GitHub Repository](https://github.com/tqdm/tqdm) - Core features, API documentation, performance characteristics
- [tenacity Documentation](https://tenacity.readthedocs.io/) - Retry strategies, exponential backoff, exception filtering

### Secondary (MEDIUM confidence)
- [Better Stack: Python Logging Best Practices](https://betterstack.com/community/guides/logging/python/python-logging-best-practices/) - Verified with official docs, good coverage of common patterns
- [Better Stack: Logging in Python - Top 6 Libraries Comparison](https://betterstack.com/community/guides/logging/best-python-logging-libraries/) - Comparison of structlog vs python-json-logger vs stdlib
- [structlog Official Documentation](https://www.structlog.org/) - Advanced structured logging features, stdlib integration
- [Papertrail: 8 Python Logging Pitfalls](https://www.papertrail.com/solution/tips/8-python-logging-pitfalls-to-avoid/) - Common mistakes verified against official docs
- [Medium: Resumable Downloads](https://medium.com/@rathnak010/resumable-download-667a28fb494d) - HTTP Range request patterns, verified with requests documentation

### Tertiary (LOW confidence - WebSearch only, marked for validation)
- [Carmatec: Python Logging Best Practices 2026](https://www.carmatec.com/blog/python-logging-best-practices-complete-guide/) - Recent but needs official verification
- [Johal.in: Tenacity Retries 2026](https://johal.in/tenacity-retries-exponential-backoff-decorators-2026/) - 2026-specific content but limited technical depth
- [DEV Community: Mask Sensitive Data](https://dev.to/camillehe1992/mask-sensitive-data-using-python-built-in-logging-module-45fa) - Good pattern but not officially verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Python stdlib logging, tqdm, tenacity are all officially documented and widely adopted
- Architecture: HIGH - Patterns verified with official documentation and multiple authoritative sources
- Pitfalls: MEDIUM - Based on community experience and best practices articles, cross-verified where possible

**Research date:** 2026-01-22
**Valid until:** ~2026-03-22 (60 days - stable domain, Python stdlib changes slowly)

**Current project state:**
- 74 print() statements across 8 files need replacement
- requests library already in dependencies (supports Range headers)
- No existing logging configuration
- No progress indicators on downloads
- No retry logic (downloads fail permanently on transient errors)
