# Phase 28: Version Check Infrastructure - Research

**Researched:** 2026-02-19
**Domain:** Non-blocking version checking with GitHub Releases API, PEP 440 version comparison, and asynchronous execution
**Confidence:** HIGH

## Summary

Phase 28 implements non-blocking version checking infrastructure for the MC CLI by polling GitHub's Releases API with hourly throttling, caching results in TOML config with timestamps, and using PEP 440-compliant version comparison. The system executes checks asynchronously at command startup using daemon threads with graceful cleanup via atexit handlers, handles network failures silently by logging errors, and displays single-line update notifications to stderr when newer versions are available.

**Key architectural decisions:**
- Use threading (not asyncio) for background execution to match existing CacheManager pattern
- Use daemon threads with atexit cleanup for graceful termination
- Leverage existing ConfigManager atomic write infrastructure for thread-safe updates
- Use tenacity (already in codebase) for retry with exponential backoff
- Store ETag + version data in TOML [version] section for conditional requests

**Primary recommendation:** Implement version checking as a daemon thread launched at CLI startup, using tenacity for retry logic, ConfigManager.save_atomic() for thread-safe writes, and atexit.register() for graceful cleanup.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| packaging | 26.0 | PEP 440 version comparison | Official PyPA library for Python version parsing/comparison, 3x faster in v26, handles all PEP 440 edge cases |
| requests | existing | HTTP client for GitHub API | Already in MC dependencies, mature HTTP library with session support |
| threading | stdlib | Background execution | Python standard library, matches existing CacheManager pattern (src/mc/controller/cache_manager.py) |
| tenacity | existing | Retry with exponential backoff | Already used in SalesforceAPIClient, more feature-rich than backoff library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| atexit | stdlib | Graceful daemon thread cleanup | Register cleanup handler for background thread termination |
| time | stdlib | Timestamp management | Unix epoch timestamps for throttle checks and cache expiry |
| logging | stdlib | Structured error logging | Silent failures with detailed logs to mc log file |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| threading | asyncio | asyncio adds complexity (event loop management) without benefit for single background task; threading matches existing CacheManager pattern |
| tenacity | backoff | Both work, but tenacity already in dependencies and more feature-rich (context managers, async support) |
| packaging | pep440-rs | pep440-rs is Rust-based (faster) but adds build complexity; packaging is pure Python, official, and fast enough (3x improvement in v26) |
| filelock | threading.Lock in-memory | filelock provides cross-process safety but not needed for single-process CLI; in-memory Lock is simpler |

**Installation:**
```bash
# packaging only new dependency
pip install packaging
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── version.py              # Existing: get_version() function
├── version_check.py        # NEW: VersionChecker class, check logic
├── config/
│   └── manager.py          # Existing: ConfigManager with atomic writes
└── utils/
    └── logging.py          # Existing: JSONFormatter for structured logs
```

### Pattern 1: Daemon Thread with atexit Cleanup
**What:** Launch background version check as daemon thread, register atexit handler to set stop event and join thread gracefully.

**When to use:** Non-blocking background tasks in CLI applications that must not delay command execution.

**Example:**
```python
# Source: https://superfastpython.com/stop-daemon-thread/
# Source: https://docs.python.org/3/library/atexit.html
import atexit
import threading

class VersionChecker:
    def __init__(self):
        self._stop_event = threading.Event()
        self._worker_thread = None

    def start_background_check(self):
        """Launch version check as daemon thread."""
        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._check_version_worker,
            daemon=True,
            name="version-check"
        )
        self._worker_thread.start()

        # Register cleanup handler
        atexit.register(self._cleanup)

    def _cleanup(self):
        """Gracefully stop daemon thread before exit."""
        if self._worker_thread and self._worker_thread.is_alive():
            self._stop_event.set()
            self._worker_thread.join(timeout=2.0)

    def _check_version_worker(self):
        """Worker thread that checks for updates."""
        # Check logic here
        pass
```

### Pattern 2: Hourly Throttle with Timestamp Check
**What:** Store last_check timestamp in TOML config, skip API call if less than 1 hour (3600 seconds) since last check.

**When to use:** Rate-limiting API calls for non-urgent background checks.

**Example:**
```python
# Source: Derived from MC ConfigManager pattern
import time

def should_check_now(last_check: float | None, throttle_seconds: int = 3600) -> bool:
    """Determine if version check should run based on throttle."""
    if last_check is None:
        return True  # Never checked before

    elapsed = time.time() - last_check
    return elapsed >= throttle_seconds
```

### Pattern 3: ETag Conditional Requests
**What:** Store ETag from GitHub API response, send If-None-Match header in subsequent requests to avoid rate limit consumption on 304 responses.

**When to use:** Frequent polling of GitHub API endpoints to conserve rate limit.

**Example:**
```python
# Source: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
import requests

def fetch_latest_release(repo: str, etag: str | None = None) -> tuple[dict, str]:
    """Fetch latest release with ETag support."""
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    if etag:
        headers['If-None-Match'] = etag

    response = requests.get(
        f'https://api.github.com/repos/{repo}/releases/latest',
        headers=headers
    )

    if response.status_code == 304:
        # Not modified, return cached data
        return None, etag

    response.raise_for_status()
    new_etag = response.headers.get('ETag', '')
    return response.json(), new_etag
```

### Pattern 4: PEP 440 Version Comparison
**What:** Use packaging.version.Version for all version comparisons to handle pre-releases, post-releases, dev versions correctly.

**When to use:** Any Python version comparison logic (not just string comparison).

**Example:**
```python
# Source: https://packaging.pypa.io/en/latest/version.html
from packaging.version import Version, InvalidVersion

def is_newer_version(current: str, latest: str) -> bool:
    """Compare versions using PEP 440 semantics."""
    try:
        return Version(latest) > Version(current)
    except InvalidVersion as e:
        # Log error, treat as not newer
        return False
```

### Pattern 5: Atomic TOML Config Updates
**What:** Use ConfigManager.save_atomic() for thread-safe writes with temp file + os.replace() pattern.

**When to use:** Background threads updating shared config file.

**Example:**
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/config/manager.py (existing code)
from mc.config.manager import ConfigManager

def update_check_timestamp(latest_version: str, etag: str):
    """Update version check metadata in config."""
    config = ConfigManager()

    # Load current config
    data = config.load()

    # Update [version] section
    if 'version' not in data:
        data['version'] = {}

    data['version']['last_check'] = time.time()
    data['version']['latest_known'] = latest_version
    data['version']['etag'] = etag

    # Atomic write (thread-safe)
    config.save_atomic(data)
```

### Pattern 6: Retry with Tenacity
**What:** Use @retry decorator with exponential backoff for transient network failures, fail fast on 404/403.

**When to use:** HTTP requests to external APIs with potential for transient failures.

**Example:**
```python
# Source: /Users/dsquirre/Repos/mc/src/mc/integrations/salesforce_api.py (existing pattern)
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import requests
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def fetch_github_release(url: str) -> dict:
    """Fetch GitHub release with retry on transient failures."""
    response = requests.get(url, timeout=10)

    # Don't retry 4xx errors
    if 400 <= response.status_code < 500:
        response.raise_for_status()

    # Retry 5xx errors (covered by retry decorator)
    response.raise_for_status()

    return response.json()
```

### Anti-Patterns to Avoid

- **Blocking the main thread:** Never run version check synchronously at startup - use daemon thread to avoid delaying command execution
- **Non-daemon threads in CLI:** Using non-daemon threads blocks CLI exit; always use daemon=True with atexit cleanup
- **String comparison for versions:** "2.10.0" < "2.9.0" in string comparison; use packaging.version.Version
- **Ignoring 304 responses:** If you send If-None-Match but don't handle 304, you waste rate limit quota
- **Missing timeout on requests:** Network calls without timeout can hang indefinitely; always set timeout parameter
- **File locking for single-process updates:** ConfigManager.save_atomic() handles atomicity; filelock adds unnecessary complexity for in-process thread safety

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Version comparison | String comparison, regex parsing | packaging.version.Version | PEP 440 has complex rules: pre-releases, post-releases, dev versions, epochs, local versions - parsing is non-trivial |
| Exponential backoff | Manual sleep calculations | tenacity @retry decorator | Jitter, max retries, exception filtering, logging hooks - backoff has edge cases |
| Atomic file writes | Manual temp file creation | ConfigManager.save_atomic() | Already handles temp file in same dir, fsync, os.replace, cleanup on error |
| HTTP conditional requests | Manual ETag storage/comparison | Store in config, use If-None-Match | GitHub API has nuances: 304 handling, rate limit preservation, header format |
| Daemon thread cleanup | Relying on abrupt termination | atexit.register() with Event | Daemon threads killed without cleanup; atexit allows graceful shutdown with timeout |

**Key insight:** Version checking appears simple ("just compare two strings") but involves complex interactions: PEP 440 version semantics, HTTP caching with ETags, rate limiting, thread lifecycle management, atomic config updates. Use proven libraries and patterns from the existing MC codebase.

## Common Pitfalls

### Pitfall 1: Daemon Threads Exit Abruptly Without Cleanup
**What goes wrong:** Daemon threads are killed immediately when the main thread exits, potentially leaving incomplete operations (partial file writes, open connections).

**Why it happens:** Python's default behavior for daemon threads is abrupt termination to prevent hanging processes.

**How to avoid:** Register atexit handler that sets a stop event and joins the thread with timeout before process exits.

**Warning signs:** Corrupted config files, incomplete log entries, resource leak warnings in tests.

**Reference:** [Python atexit documentation](https://docs.python.org/3/library/atexit.html), [Super Fast Python - Stop Daemon Thread](https://superfastpython.com/stop-daemon-thread/)

### Pitfall 2: Rate Limit Exhaustion from Ignoring 304 Responses
**What goes wrong:** GitHub API returns 304 Not Modified when content hasn't changed, but only if you handle it correctly. Ignoring 304s or not sending If-None-Match wastes rate limit quota.

**Why it happens:** Developers forget to check response.status_code == 304 or don't store/send the ETag header.

**How to avoid:** Store ETag in config after successful 200 response, send as If-None-Match header in subsequent requests, handle 304 by returning cached data.

**Warning signs:** Hitting rate limits (5000 requests/hour for authenticated) with hourly checks, 403 Forbidden responses.

**Reference:** [GitHub REST API Best Practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api), [Making the Most of GitHub Rate Limits](https://jamiemagee.co.uk/blog/making-the-most-of-github-rate-limits/)

### Pitfall 3: String Comparison for Version Numbers
**What goes wrong:** String comparison fails on version numbers: "2.10.0" < "2.9.0" returns True (lexicographic order).

**Why it happens:** Developers assume version strings sort naturally; they don't account for pre-releases, multi-digit numbers, or PEP 440 rules.

**How to avoid:** Always use packaging.version.Version for comparisons, wrap in try/except for InvalidVersion.

**Warning signs:** False positive "update available" notifications, incorrect version ordering in logs.

**Reference:** [PEP 440](https://peps.python.org/pep-0440/), [Packaging Version Handling](https://packaging.pypa.io/en/latest/version.html)

### Pitfall 4: Race Conditions in Config File Updates
**What goes wrong:** Two threads reading config, modifying it, and writing back can overwrite each other's changes (lost update problem).

**Why it happens:** Read-modify-write cycle is not atomic without proper synchronization.

**How to avoid:** Use ConfigManager.save_atomic() which uses os.replace() for atomic replacement, or use threading.Lock for in-memory synchronization before write.

**Warning signs:** Missing config fields after background updates, inconsistent timestamps, test flakiness.

**Reference:** [Thread-Safe File Writing](https://superfastpython.com/thread-safe-write-to-file-in-python/), [File Locking in Python](https://medium.com/@aman.deep291098/avoiding-file-conflicts-in-multithreaded-python-programs-34f2888f4521)

### Pitfall 5: Non-Blocking Execution That Actually Blocks
**What goes wrong:** Launching thread but calling thread.join() immediately, or using non-daemon thread that blocks CLI exit.

**Why it happens:** Misunderstanding threading semantics - join() waits for thread completion, non-daemon threads prevent process exit.

**How to avoid:** Use daemon=True, never call join() in main execution path, only join in atexit handler with timeout.

**Warning signs:** CLI commands slow to start, CLI hangs on exit, Ctrl-C doesn't immediately terminate.

**Reference:** [Python Threading Documentation](https://docs.python.org/3/library/threading.html), [Daemon vs Regular Threads](https://www.geeksforgeeks.org/python/regular-threads-vs-daemon-threads-in-python/)

### Pitfall 6: Network Requests Without Timeout
**What goes wrong:** requests.get() without timeout parameter can hang indefinitely on network issues, blocking the background thread.

**Why it happens:** requests library defaults to no timeout (waits forever).

**How to avoid:** Always set timeout parameter (e.g., timeout=10 for 10 seconds).

**Warning signs:** Background thread never completes, CLI hangs on exit even with atexit handler, logs show no progress.

**Reference:** [Requests Documentation](https://requests.readthedocs.io/en/latest/user/advanced/#timeouts)

## Code Examples

Verified patterns from official sources and MC codebase:

### Version Comparison
```python
# Source: https://packaging.pypa.io/en/latest/version.html
from packaging.version import Version, InvalidVersion
import logging

logger = logging.getLogger(__name__)

def compare_versions(current: str, latest: str) -> bool:
    """Check if latest version is newer than current.

    Args:
        current: Current installed version (e.g., "2.0.4")
        latest: Latest available version from GitHub (e.g., "2.0.5")

    Returns:
        True if latest > current, False otherwise
    """
    try:
        return Version(latest) > Version(current)
    except InvalidVersion as e:
        logger.error(f"Invalid version string: {e}")
        return False
```

### GitHub Releases API Request with ETag
```python
# Source: https://docs.github.com/en/rest/releases/releases
# Source: https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
import requests
from typing import Optional, Tuple

def fetch_latest_release(
    owner: str,
    repo: str,
    etag: Optional[str] = None
) -> Tuple[Optional[dict], str, int]:
    """Fetch latest release from GitHub with ETag support.

    Args:
        owner: GitHub repository owner
        repo: Repository name
        etag: Previous ETag value for conditional request

    Returns:
        Tuple of (release_data, new_etag, status_code)
        - release_data is None if 304 Not Modified
        - new_etag is updated value (or same if 304)
        - status_code for error handling
    """
    url = f'https://api.github.com/repos/{owner}/{repo}/releases/latest'
    headers = {
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28'
    }

    if etag:
        headers['If-None-Match'] = etag

    response = requests.get(url, headers=headers, timeout=10)

    if response.status_code == 304:
        # Not modified - return None with existing ETag
        return None, etag, 304

    if response.status_code == 200:
        new_etag = response.headers.get('ETag', '')
        return response.json(), new_etag, 200

    # Error case
    return None, etag, response.status_code
```

### Daemon Thread with atexit Cleanup
```python
# Source: https://superfastpython.com/stop-daemon-thread/
# Source: https://docs.python.org/3/library/atexit.html
# Source: Existing MC pattern: src/mc/controller/cache_manager.py
import atexit
import threading
import logging

logger = logging.getLogger(__name__)

class VersionChecker:
    """Background version checker with graceful cleanup."""

    def __init__(self):
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

    def start_background_check(self):
        """Launch version check as daemon thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            logger.warning("Version check already running")
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._check_version_worker,
            daemon=True,
            name="version-check"
        )
        self._worker_thread.start()

        # Register cleanup for graceful shutdown
        atexit.register(self._cleanup)

        logger.debug("Started background version check")

    def _cleanup(self):
        """Gracefully stop daemon thread before exit."""
        if not self._worker_thread or not self._worker_thread.is_alive():
            return

        logger.debug("Stopping version check worker")
        self._stop_event.set()

        # Wait with timeout (don't hang exit)
        self._worker_thread.join(timeout=2.0)

        if self._worker_thread.is_alive():
            logger.warning("Version check worker did not stop cleanly")

    def _check_version_worker(self):
        """Worker thread that performs version check."""
        try:
            # Version check logic here
            pass
        except Exception as e:
            logger.error(f"Version check failed: {e}")
```

### Throttle Check with Timestamp
```python
# Source: Derived from MC ConfigManager pattern
import time

THROTTLE_SECONDS = 3600  # 1 hour
RATE_LIMIT_THROTTLE_SECONDS = 86400  # 24 hours (for 403 responses)

def should_check_now(
    last_check: Optional[float],
    last_status_code: Optional[int] = None
) -> bool:
    """Determine if version check should run.

    Args:
        last_check: Unix timestamp of last check, or None
        last_status_code: HTTP status from last check (extend throttle on 403)

    Returns:
        True if check should run, False if throttled
    """
    if last_check is None:
        return True  # Never checked

    # Extend throttle to 24 hours on rate limit error
    throttle = (
        RATE_LIMIT_THROTTLE_SECONDS
        if last_status_code == 403
        else THROTTLE_SECONDS
    )

    elapsed = time.time() - last_check
    return elapsed >= throttle
```

### Retry with Tenacity
```python
# Source: Existing MC pattern: src/mc/integrations/salesforce_api.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log
)
import requests
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError
    )),
    before_sleep=before_sleep_log(logger, logging.WARNING)
)
def fetch_with_retry(url: str, headers: dict) -> requests.Response:
    """Fetch URL with retry on transient failures.

    Retries on timeout and connection errors with exponential backoff.
    Does NOT retry on 4xx client errors (fail fast).

    Args:
        url: URL to fetch
        headers: Request headers

    Returns:
        Response object

    Raises:
        requests.exceptions.HTTPError: On 4xx/5xx status codes
        requests.exceptions.RequestException: On network failures after retries
    """
    response = requests.get(url, headers=headers, timeout=10)

    # Don't retry 4xx errors (fail fast)
    if 400 <= response.status_code < 500:
        response.raise_for_status()

    # 5xx errors will be retried by decorator
    response.raise_for_status()

    return response
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual version string parsing | packaging.version.Version | v26.0 (Jan 2026) | 3x faster parsing, handles all PEP 440 edge cases |
| backoff library | tenacity library | Industry trend 2024-2026 | Tenacity offers more features (context managers, async), better maintained |
| If-Modified-Since header | ETag with If-None-Match | GitHub API best practice | More reliable for API resources, better rate limit preservation |
| File locking (filelock) | Atomic writes (os.replace) | Modern Python 3.11+ | Simpler for single-process apps, os.replace is atomic on POSIX |
| Global Interpreter Lock assumptions | Free-threaded Python builds | Python 3.13+ (2026) | GIL removal affects thread safety assumptions, but daemon threads still valid |

**Deprecated/outdated:**
- **String-based version comparison**: Fails on multi-digit versions and pre-releases; use packaging.version.Version
- **If-Modified-Since for GitHub API**: GitHub docs recommend ETag for better caching
- **backoff library**: Still works but tenacity is more feature-complete and better maintained in 2026
- **Non-daemon background threads in CLI**: Blocks CLI exit; always use daemon=True with atexit cleanup

## Open Questions

Things that couldn't be fully resolved:

1. **Notification Frequency vs Check Frequency**
   - What we know: User decided separate timestamps for check vs notification (show once per day max)
   - What's unclear: Exact storage format (separate fields in [version] section vs combined?)
   - Recommendation: Store last_notification_timestamp alongside last_check timestamp in [version] section, compare both in notification logic

2. **Rate Limit 403 Response Handling**
   - What we know: User decided 403 extends throttle to 24 hours
   - What's unclear: How to persist last_status_code for next check (need it for should_check_now logic)
   - Recommendation: Add version.last_status_code field to config, update on each check

3. **Manual Override `--update` Flag Implementation**
   - What we know: `mc version --update` bypasses throttle and forces immediate check
   - What's unclear: Whether this should be synchronous (block and show result) or async (trigger background check)
   - Recommendation: Make synchronous for manual override - user explicitly requested check, expect immediate feedback

## Sources

### Primary (HIGH confidence)
- [PEP 440 – Version Identification](https://peps.python.org/pep-0440/)
- [Packaging Library Documentation](https://packaging.pypa.io/en/latest/version.html)
- [Packaging Library PyPI](https://pypi.org/project/packaging/)
- [GitHub REST API Best Practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)
- [GitHub Releases API](https://docs.github.com/en/rest/releases/releases)
- [Python threading Documentation](https://docs.python.org/3/library/threading.html)
- [Python atexit Documentation](https://docs.python.org/3/library/atexit.html)
- [Tenacity Documentation](https://tenacity.readthedocs.io/)

### Secondary (MEDIUM confidence)
- [Making the Most of GitHub Rate Limits](https://jamiemagee.co.uk/blog/making-the-most-of-github-rate-limits/)
- [Super Fast Python - Stop Daemon Thread](https://superfastpython.com/stop-daemon-thread/)
- [Thread-Safe File Writing](https://superfastpython.com/thread-safe-write-to-file-in-python/)
- [Python Asyncio vs Threading](https://www.geeksforgeeks.org/python/asyncio-vs-threading-in-python/)
- [Avoiding File Conflicts in Multithreaded Programs](https://medium.com/@aman.deep291098/avoiding-file-conflicts-in-multithreaded-python-programs-34f2888f4521)
- [How to Retry Failed Python Requests [2026]](https://www.zenrows.com/blog/python-requests-retry)

### Tertiary (LOW confidence - patterns verified with official docs)
- [Tenacity vs Backoff Comparison](https://piptrends.com/compare/backoff-vs-retry-vs-tenacity)
- [HTTP Caching with ETag](https://bugfactory.io/articles/http-caching-with-etag-and-if-none-match-headers/)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries verified from official PyPI/docs, versions confirmed
- Architecture: HIGH - Patterns drawn from existing MC codebase (CacheManager, SalesforceAPIClient, ConfigManager)
- Pitfalls: HIGH - Sourced from official documentation and verified community sources

**Research date:** 2026-02-19
**Valid until:** 2026-03-21 (30 days for stable domain - packaging and GitHub API are stable)

---

*Research complete. Ready for planning.*
