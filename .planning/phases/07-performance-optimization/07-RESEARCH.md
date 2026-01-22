# Phase 07: Performance Optimization - Research

**Researched:** 2026-01-22
**Domain:** Python parallel I/O with concurrent downloads and caching
**Confidence:** HIGH

## Summary

Performance optimization for a CLI tool downloading attachments from Red Hat API requires three core capabilities: parallel downloads with ThreadPoolExecutor, intelligent caching with TTL, and rich progress feedback. The Python ecosystem provides mature solutions for all three.

The standard approach uses `concurrent.futures.ThreadPoolExecutor` (Python stdlib) for I/O-bound parallel downloads, the `rich` library for sophisticated terminal progress displays, and simple JSON file-based caching with timestamp-based TTL checking. For retry logic, the `backoff` library provides production-grade exponential backoff with jitter.

Access token caching is already implemented (Phase 4, SEC-01) using file-based cache with expiration tracking. This phase extends that pattern to case metadata and adds parallelism to downloads.

**Primary recommendation:** Use ThreadPoolExecutor with 8 workers, rich.Progress with table layout for concurrent download tracking, backoff decorators for automatic retry with exponential backoff, and simple JSON files for metadata caching (30min TTL). Resume partial downloads using HTTP Range headers. Handle Ctrl+C with try/except KeyboardInterrupt to clean up partial files.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| concurrent.futures | stdlib (3.8+) | Parallel downloads via ThreadPoolExecutor | Built-in, robust, well-documented; ideal for I/O-bound tasks |
| rich | 14.1.0+ | Terminal progress bars and UI | Industry standard for CLI progress displays; supports multiple concurrent tasks |
| backoff | 2.2.1+ | Exponential retry with jitter | Production-grade retry logic; handles rate limiting intelligently |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests | 2.31.0+ (existing) | HTTP downloads with streaming | Already in use; supports Range headers for resumable downloads |
| json | stdlib | File-based cache storage | Simple, human-readable cache files; adequate for metadata caching |
| signal | stdlib | Ctrl+C handling for cleanup | Clean shutdown and partial file removal |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| backoff | Manual retry loops | Backoff handles jitter, max_tries, exception filtering automatically; manual is error-prone |
| rich | tqdm | Rich has better multi-task support, table layouts, and styling; tqdm simpler but less flexible |
| JSON cache | diskcache (5.6.3) | DiskCache more sophisticated (SQLite-backed, LRU eviction) but overkill for simple 30min TTL cache |
| JSON cache | cachetools.TTLCache | In-memory only, lost on restart; file-based survives restarts |

**Installation:**
```bash
pip install rich>=14.0.0 backoff>=2.2.1
# requests already installed
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/utils/
├── auth.py              # Existing: token cache (Phase 4)
├── cache.py             # NEW: Case metadata caching
└── downloads.py         # NEW: Parallel download manager

src/mc/integrations/
└── redhat_api.py        # MODIFY: Add parallel download support
```

### Pattern 1: ThreadPoolExecutor with Rich Progress
**What:** Submit download tasks to thread pool, track each with Rich Progress task
**When to use:** Multiple files to download concurrently
**Example:**
```python
# Source: https://github.com/Textualize/rich/blob/master/examples/downloader.py
from concurrent.futures import ThreadPoolExecutor
from rich.progress import Progress, BarColumn, DownloadColumn, TransferSpeedColumn

progress = Progress(
    TextColumn("[bold blue]{task.fields[filename]}"),
    BarColumn(bar_width=None),
    "[progress.percentage]{task.percentage:>3.1f}%",
    DownloadColumn(),
    TransferSpeedColumn(),
    TimeRemainingColumn(),
)

with progress:
    with ThreadPoolExecutor(max_workers=8) as pool:
        for attachment in attachments:
            task_id = progress.add_task("download", filename=attachment['file_name'], start=False)
            pool.submit(download_file, task_id, attachment, progress)
```

### Pattern 2: Exponential Backoff with Exception Filtering
**What:** Retry transient failures with increasing delays, fail fast on permanent errors
**When to use:** HTTP requests that may encounter rate limiting or network issues
**Example:**
```python
# Source: https://pypi.org/project/backoff/
import backoff
import requests

def fatal_code(e):
    """Don't retry 4xx client errors (except 429 rate limit)"""
    return 400 <= e.response.status_code < 500 and e.response.status_code != 429

@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    giveup=fatal_code,
    jitter=backoff.full_jitter
)
def download_with_retry(url, headers):
    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()
    return response
```

### Pattern 3: HTTP Range Requests for Resumable Downloads
**What:** Resume interrupted downloads from last byte received
**When to use:** Large files that may fail mid-download
**Example:**
```python
# Source: https://medium.com/@rathnak010/resumable-download-667a28fb494d
import os

def resume_download(url, local_path, headers):
    # Check if partial file exists
    if os.path.exists(local_path):
        downloaded_bytes = os.path.getsize(local_path)
        headers['Range'] = f'bytes={downloaded_bytes}-'
        mode = 'ab'  # Append to existing
    else:
        mode = 'wb'  # Write new file

    response = requests.get(url, headers=headers, stream=True)
    # Server returns 206 Partial Content if resuming, 200 if full download

    with open(local_path, mode) as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
```

### Pattern 4: File-Based Cache with TTL
**What:** Store JSON cache files with timestamp, check age before use
**When to use:** Case metadata that changes infrequently (30min validity)
**Example:**
```python
# Source: https://medium.com/@tk512/simple-file-based-json-cache-in-python-61b2c11faa84
import json
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".mc" / "cache"
CACHE_TTL_SECONDS = 30 * 60  # 30 minutes

def get_cached_case(case_number):
    cache_file = CACHE_DIR / f"case_{case_number}.json"

    if not cache_file.exists():
        return None

    with open(cache_file, 'r') as f:
        cache_data = json.load(f)

    # Check if expired
    cache_age = time.time() - cache_data['cached_at']
    if cache_age > CACHE_TTL_SECONDS:
        return None

    return cache_data['data']

def cache_case_data(case_number, data):
    CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)

    cache_file = CACHE_DIR / f"case_{case_number}.json"
    cache_data = {
        'data': data,
        'cached_at': time.time()
    }

    with open(cache_file, 'w') as f:
        json.dump(cache_data, f, indent=2)
```

### Pattern 5: Ctrl+C Cleanup for Partial Downloads
**What:** Catch KeyboardInterrupt to delete incomplete files before exit
**When to use:** Downloads that create partial files on disk
**Example:**
```python
# Source: https://www.xanthium.in/operating-system-signal-handling-in-python3
def download_with_cleanup(url, local_path):
    try:
        with open(local_path, 'wb') as f:
            response = requests.get(url, stream=True)
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except KeyboardInterrupt:
        # Clean up partial file
        if os.path.exists(local_path):
            os.remove(local_path)
        raise
```

### Anti-Patterns to Avoid
- **Don't create deadlocks:** Never have futures waiting on other futures with limited workers (see ThreadPoolExecutor deadlock warnings)
- **Don't retry 404/401/403:** These are permanent errors; only retry transient failures (5xx, timeouts, connection errors, 429)
- **Don't ignore Retry-After header:** For 429 rate limiting, respect server's Retry-After header before falling back to exponential backoff
- **Don't update progress too frequently:** Set reasonable refresh rate (10 Hz default) to avoid CPU overhead
- **Don't forget context managers:** Always use `with ThreadPoolExecutor()` and `with Progress()` for automatic cleanup

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Exponential backoff retry | Custom sleep loops with multipliers | backoff library | Handles jitter, max_tries, exception filtering, logging automatically; prevents thundering herd |
| Progress bars for downloads | Manual terminal cursor control | rich.Progress | Thread-safe updates, automatic refresh, built-in download columns (speed, size, ETA) |
| HTTP retry logic | Manual for loops with sleep | urllib3.util.Retry or backoff | Proper retry decision logic (which status codes), backoff timing, request session integration |
| TTL cache eviction | Manual timestamp checking scattered in code | Centralized cache_get with TTL check | Single source of truth for expiration logic; easier to test and modify |
| Thread pool management | Manual Thread() creation | concurrent.futures.ThreadPoolExecutor | Handles worker lifecycle, exception propagation, graceful shutdown automatically |

**Key insight:** I/O-bound concurrency has well-established patterns in Python. ThreadPoolExecutor + requests + rich is the standard stack for concurrent downloads. Hand-rolling retry logic inevitably misses edge cases (jitter, retry-after headers, proper exception filtering).

## Common Pitfalls

### Pitfall 1: Silent Task Failures in ThreadPoolExecutor
**What goes wrong:** Tasks submitted to ThreadPoolExecutor can fail silently without the user knowing
**Why it happens:** ThreadPoolExecutor swallows exceptions by default; they're only raised when calling `.result()` on the Future
**How to avoid:** Always call `.result()` on returned Futures, wrap in try/except to handle task exceptions
**Warning signs:** No error messages but expected side effects (downloaded files) missing

**Example fix:**
```python
# Source: https://superfastpython.com/threadpoolexecutor-exception-handling/
with ThreadPoolExecutor(max_workers=8) as pool:
    futures = [pool.submit(download_file, url) for url in urls]

    for future in concurrent.futures.as_completed(futures):
        try:
            future.result()  # Raises exception if task failed
        except Exception as exc:
            print(f"Download failed: {exc}")
            # Continue with other downloads
```

### Pitfall 2: Ignoring HTTP 429 Retry-After Header
**What goes wrong:** Exponential backoff retries too quickly when server sends Retry-After header, leading to more rate limiting
**Why it happens:** Standard exponential backoff doesn't check for server-provided retry timing
**How to avoid:** Check response headers for Retry-After, use that value before falling back to exponential backoff
**Warning signs:** Repeated 429 errors despite backoff, rate limit duration increasing

**Example fix:**
```python
# Source: https://www.aifreeapi.com/en/posts/claude-api-429-error-fix
def get_retry_delay(response):
    """Get retry delay from Retry-After header or use exponential backoff"""
    if 'Retry-After' in response.headers:
        retry_after = response.headers['Retry-After']
        # Can be seconds (int) or HTTP date (parse it)
        try:
            return int(retry_after)
        except ValueError:
            # Parse HTTP date format if needed
            pass
    return None  # Fall back to backoff library's exponential delay
```

### Pitfall 3: Race Conditions with Shared Progress State
**What goes wrong:** Multiple threads updating progress causes UI corruption or incorrect percentages
**Why it happens:** Concurrent writes to shared state without synchronization
**How to avoid:** Rich Progress is thread-safe; use its built-in update methods, don't track progress in separate variables
**Warning signs:** Progress jumps backward, percentages exceed 100%, garbled terminal output

**Example fix:**
```python
# WRONG: Shared state updated from threads
total_bytes = 0  # Race condition!
def download(url):
    global total_bytes
    for chunk in response.iter_content():
        total_bytes += len(chunk)  # Multiple threads write simultaneously

# RIGHT: Use Rich's thread-safe progress tracking
def download(task_id, url, progress):
    for chunk in response.iter_content():
        progress.update(task_id, advance=len(chunk))  # Thread-safe
```

### Pitfall 4: Not Cleaning Up Partial Files on Ctrl+C
**What goes wrong:** Interrupted downloads leave corrupted partial files on disk, confusing users or breaking resume logic
**Why it happens:** KeyboardInterrupt exits immediately without cleanup unless caught
**How to avoid:** Wrap download logic in try/except KeyboardInterrupt, delete partial file before re-raising
**Warning signs:** Partial files accumulate in download directory, resume attempts fail due to corrupted partials

### Pitfall 5: Wrong Worker Count for I/O-Bound Tasks
**What goes wrong:** Using too few workers (like CPU count) underutilizes network; too many wastes memory
**Why it happens:** Confusion between I/O-bound (waiting on network) and CPU-bound (compute) parallelism
**How to avoid:** For I/O-bound tasks, use 4-16 workers regardless of CPU count; Python 3.13+ defaults to `min(32, cpu_count + 4)`
**Warning signs:** Downloads slower than single-threaded (too few workers), excessive memory usage (too many)

**Guidance:**
- 4 workers: Conservative, good for rate-limited APIs
- 8 workers: Balanced for typical broadband connections (as specified in CONTEXT.md)
- 16+ workers: High-bandwidth connections, no rate limiting

### Pitfall 6: Forgetting to Close ThreadPoolExecutor
**What goes wrong:** Program hangs on exit waiting for threads to finish; threads not cleaned up
**Why it happens:** Manual executor.shutdown() forgotten or executed after blocking operation
**How to avoid:** Always use context manager `with ThreadPoolExecutor()` for automatic shutdown
**Warning signs:** Program doesn't exit cleanly, threads visible in debugger after main() completes

### Pitfall 7: Incorrect Chunk Size for Streaming Downloads
**What goes wrong:** Too small (e.g., 512 bytes) causes excessive function calls; too large (e.g., 1MB) delays progress updates
**Why it happens:** No clear documentation on optimal chunk size
**How to avoid:** Use 8192 bytes (8KB) for most cases; 32768 (32KB) for high-bandwidth; 65536 (64KB) for very large files
**Warning signs:** Slow downloads despite good bandwidth, or jerky progress bar updates

## Code Examples

Verified patterns from official sources:

### Complete Parallel Download with Progress Tracking
```python
# Source: https://github.com/Textualize/rich/blob/master/examples/downloader.py
# Source: https://docs.python.org/3/library/concurrent.futures.html
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)
import requests

def download_file(task_id, url, dest_path, progress):
    """Download single file with progress updates"""
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()

        total = int(response.headers.get('content-length', 0))
        progress.update(task_id, total=total)
        progress.start_task(task_id)

        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                progress.update(task_id, advance=len(chunk))
    except Exception as exc:
        progress.console.print(f"[red]Failed: {dest_path} - {exc}[/red]")
        raise

def download_multiple_files(urls, dest_dir, max_workers=8):
    """Download multiple files in parallel with progress tracking"""
    progress = Progress(
        TextColumn("[bold blue]{task.fields[filename]}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {}
            for url in urls:
                filename = url.split('/')[-1]
                dest_path = os.path.join(dest_dir, filename)
                task_id = progress.add_task("download", filename=filename, start=False)
                future = pool.submit(download_file, task_id, url, dest_path, progress)
                futures[future] = filename

            # Collect results and handle failures
            failed = []
            for future in as_completed(futures):
                filename = futures[future]
                try:
                    future.result()  # Raises if download failed
                except Exception:
                    failed.append(filename)

            if failed:
                progress.console.print(f"\n[red]Failed downloads: {', '.join(failed)}[/red]")
```

### Exponential Backoff with Rate Limit Handling
```python
# Source: https://pypi.org/project/backoff/
# Source: https://www.aifreeapi.com/en/posts/claude-api-429-error-fix
import backoff
import requests
import time

def should_retry(e):
    """Retry transient errors, fail fast on permanent errors"""
    if not isinstance(e, requests.exceptions.RequestException):
        return False

    if not hasattr(e, 'response') or e.response is None:
        return True  # Network error, retry

    status = e.response.status_code

    # Retry these
    if status in [429, 500, 502, 503, 504]:
        return True

    # Don't retry 4xx client errors (except 429 handled above)
    if 400 <= status < 500:
        return False

    return True

@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    giveup=lambda e: not should_retry(e),
    jitter=backoff.full_jitter,
    on_backoff=lambda details: print(f"Retry {details['tries']}/{details['max_tries']}, waiting {details['wait']:.1f}s")
)
def download_with_retry(url, headers):
    response = requests.get(url, headers=headers, stream=True, timeout=30)

    # Check for Retry-After header on 429
    if response.status_code == 429 and 'Retry-After' in response.headers:
        retry_after = int(response.headers['Retry-After'])
        print(f"Rate limited, server says retry after {retry_after}s")
        time.sleep(retry_after)
        raise requests.exceptions.RequestException(response=response)  # Trigger retry

    response.raise_for_status()
    return response
```

### Case Metadata Cache with TTL
```python
# Source: https://medium.com/@tk512/simple-file-based-json-cache-in-python-61b2c11faa84
import json
import time
from pathlib import Path

CACHE_DIR = Path.home() / ".mc" / "cache"
CACHE_TTL = 30 * 60  # 30 minutes in seconds

def get_case_metadata(case_number, api_client):
    """Get case metadata from cache or API, with TTL"""
    cache_file = CACHE_DIR / f"case_{case_number}.json"

    # Try cache first
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            cached = json.load(f)

        age_seconds = time.time() - cached['cached_at']
        if age_seconds < CACHE_TTL:
            age_minutes = int(age_seconds / 60)
            print(f"Using cached data (cached {age_minutes}m ago)")
            return cached['data']

    # Cache miss or expired - fetch from API
    data = api_client.fetch_case_details(case_number)

    # Save to cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    cached = {
        'data': data,
        'cached_at': time.time()
    }
    with open(cache_file, 'w') as f:
        json.dump(cached, f, indent=2)

    return data
```

### Resumable Download with Range Requests
```python
# Source: https://medium.com/@rathnak010/resumable-download-667a28fb494d
import os
import requests

def download_resumable(url, local_path, headers):
    """Download file with resume capability using HTTP Range requests"""
    # Check for existing partial download
    if os.path.exists(local_path):
        downloaded_bytes = os.path.getsize(local_path)
        headers = headers.copy()
        headers['Range'] = f'bytes={downloaded_bytes}-'
        mode = 'ab'  # Append
    else:
        downloaded_bytes = 0
        mode = 'wb'  # New file

    response = requests.get(url, headers=headers, stream=True, timeout=30)

    # 206 = Partial Content (resuming), 200 = Full content (new download)
    if response.status_code not in [200, 206]:
        response.raise_for_status()

    total_size = int(response.headers.get('content-length', 0))

    try:
        with open(local_path, mode) as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
    except KeyboardInterrupt:
        print(f"\nDownload interrupted, partial file saved for resume")
        raise
```

### Suppress Progress in JSON/Quiet Mode
```python
# Source: https://rich.readthedocs.io/en/stable/reference/console.html
from rich.console import Console
from rich.progress import Progress
import argparse

def should_suppress_progress(args):
    """Determine if progress bars should be suppressed"""
    # Suppress if --quiet flag
    if args.quiet:
        return True

    # Suppress if --json flag (conflicts with JSON parsing)
    if hasattr(args, 'json') and args.json:
        return True

    return False

def download_with_conditional_progress(files, args):
    """Download files with progress only when appropriate"""
    if should_suppress_progress(args):
        # No progress - just download
        for url in files:
            download_file_silent(url)
    else:
        # Show progress
        with Progress() as progress:
            download_with_progress(files, progress)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual thread management | ThreadPoolExecutor context manager | Python 3.2 (2011) | Automatic cleanup, exception handling |
| GIL-limited parallelism | Still true for CPU-bound; irrelevant for I/O-bound | Ongoing | ThreadPool perfect for I/O, avoid for CPU tasks |
| tqdm for progress | rich.Progress for sophisticated UIs | rich 1.0 (2020) | Better multi-task support, styling, table layouts |
| Manual retry loops | backoff library with jitter | backoff 1.0 (2015) | Prevents thundering herd, better rate limit handling |
| In-memory caching only | File-based cache survives restarts | Always available | User expectations: cache persists across CLI invocations |
| Simple exponential backoff | Exponential backoff + jitter + Retry-After | AWS blog 2015 | Critical for rate-limited APIs, prevents synchronized retries |

**Deprecated/outdated:**
- **multiprocessing.dummy.Pool**: Deprecated alias for ThreadPool; use concurrent.futures.ThreadPoolExecutor instead
- **urllib.request for downloads**: Works but lacks modern features; requests library is standard
- **Manual jitter implementation**: Use backoff.full_jitter (AWS-recommended algorithm)

## Open Questions

Things that couldn't be fully resolved:

1. **Optimal chunk size for Red Hat API downloads**
   - What we know: 8KB (8192) is standard, 32KB for high-bandwidth
   - What's unclear: Red Hat API's specific behavior with different chunk sizes
   - Recommendation: Start with 8192 bytes, make configurable if needed

2. **Red Hat API rate limit specifics**
   - What we know: Should handle HTTP 429 with Retry-After header
   - What's unclear: Whether Red Hat API actually rate limits download endpoints
   - Recommendation: Implement 429 handling defensively even if not currently rate-limited

3. **Cache invalidation strategy for stale case data**
   - What we know: 30-minute TTL decided by user (CONTEXT.md)
   - What's unclear: Whether manual refresh flag needed to bypass cache
   - Recommendation: Implement TTL-based expiration; defer manual refresh to future enhancement

## Sources

### Primary (HIGH confidence)
- [Python concurrent.futures documentation](https://docs.python.org/3/library/concurrent.futures.html) - ThreadPoolExecutor API, best practices, deadlock warnings
- [Rich Progress documentation](https://rich.readthedocs.io/en/stable/progress.html) - Progress bars with multiple tasks, columns, customization
- [Rich downloader.py example](https://github.com/Textualize/rich/blob/master/examples/downloader.py) - Complete pattern for ThreadPoolExecutor + Rich Progress
- [backoff library (PyPI)](https://pypi.org/project/backoff/) - Exponential backoff with jitter, exception filtering

### Secondary (MEDIUM confidence)
- [How to Handle Exceptions in ThreadPoolExecutor](https://superfastpython.com/threadpoolexecutor-exception-handling/) - Silent failures pattern
- [ThreadPoolExecutor Common Errors](https://superfastpython.com/threadpoolextor-common-errors/) - Pitfalls and prevention
- [Streaming Downloads with Python Requests](https://proxiesapi.com/articles/streaming-downloads-with-python-requests) - Chunk sizes and streaming patterns
- [Resumable Download (Medium)](https://medium.com/@rathnak010/resumable-download-667a28fb494d) - HTTP Range requests implementation
- [Simple file based JSON cache in Python (Medium)](https://medium.com/@tk512/simple-file-based-json-cache-in-python-61b2c11faa84) - TTL cache pattern
- [How to Fix Claude API 429 Rate Limit Error](https://www.aifreeapi.com/en/posts/claude-api-429-error-fix) - Retry-After header handling
- [Operating System Signal Handling in Python](https://www.xanthium.in/operating-system-signal-handling-in-python3) - Ctrl+C cleanup pattern
- [DiskCache (PyPI)](https://pypi.org/project/diskcache/) - Alternative cache library (evaluated but not chosen)

### Tertiary (LOW confidence)
- Various Medium articles and blog posts on exponential backoff, rate limiting - Cross-referenced with official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - concurrent.futures is stdlib, rich is industry standard, backoff is production-grade
- Architecture: HIGH - Patterns verified with official examples and documentation
- Pitfalls: HIGH - Well-documented in Super Fast Python series and official Python docs
- Cache implementation: MEDIUM - Simple JSON approach is straightforward but not extensively documented for this exact use case

**Research date:** 2026-01-22
**Valid until:** 2026-02-22 (30 days - stable domain, stdlib APIs don't change frequently)
