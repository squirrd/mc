# Phase 10: Salesforce Integration & Case Resolution - Research

**Researched:** 2026-01-26
**Domain:** Salesforce API integration, OAuth2 token management, activity-aware caching
**Confidence:** HIGH

## Summary

Phase 10 adapts the existing v1.0 Red Hat API integration pattern to work in the v2.0 containerized architecture. The core challenge is making Salesforce case metadata available to containers while implementing activity-aware caching and automatic token refresh. Research reveals that v1.0's existing API client, caching, and workspace patterns are production-ready and can be reused with minimal adaptation.

The standard approach for Salesforce integration uses the simple-salesforce library (v1.12.9 specified in STATE.md) with OAuth2 username/password/security token authentication. Access tokens expire after 2 hours and require proactive refresh 5-10 minutes before expiration to prevent authentication failures. Rate limiting (HTTP 429) requires exponential backoff with 2-4-8 second retry intervals and respect for Retry-After headers.

Activity-aware caching (5-10 min TTL during active terminal use, paused after 30 min inactivity) requires platform-specific idle detection, which introduces complexity. Research suggests simpler alternatives: fixed-interval background refresh or on-demand refresh during container operations may be more maintainable while achieving the same goal of reducing API calls.

**Primary recommendation:** Reuse v1.0's RedHatAPIClient pattern for Salesforce integration, implement SQLite-based cache with background refresh worker thread, distribute tokens via Podman secrets, and defer activity detection to future optimization if fixed-interval refresh proves insufficient.

## Standard Stack

The established libraries/tools for Salesforce API integration and containerized architecture:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| simple-salesforce | 1.12.9 | Salesforce REST API client | Official PyPI package, 7K+ GitHub stars, supports all auth methods including OAuth2, SOQL queries, metadata operations |
| podman-py | 5.7.0 | Podman container API | Official Python bindings for Podman, required for container lifecycle management |
| requests | 2.31.0+ | HTTP client | Industry standard, already used in v1.0 RedHatAPIClient, proven retry/timeout handling |
| tenacity | 8.2.3+ | Retry/backoff | Already in v1.0, handles exponential backoff for API failures, declarative retry policies |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| platformdirs | 4.0.0+ | Cross-platform cache paths | Already in v1.0, provides ~/.mc/cache location consistently across macOS/Linux |
| sqlite3 | stdlib | State database | When cache needs querying/filtering beyond simple key-value (e.g., list all cached cases, age-based cleanup) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| simple-salesforce | salesforce-api (restforce style) | More granular control but immature ecosystem, simple-salesforce is proven and feature-complete |
| SQLite cache | JSON file cache (v1.0 style) | JSON simpler but SQLite 35x faster reads, 3x smaller storage, built-in concurrency via WAL mode |
| Podman secrets | Environment variables | Environment variables visible in `podman inspect`, secrets are mount-based and more secure |

**Installation:**
```bash
# Already in pyproject.toml dependencies for v2.0
pip install simple-salesforce==1.12.9 podman-py==5.7.0
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/
├── integrations/
│   ├── redhat_api.py          # Existing v1.0 Red Hat API client (reuse pattern)
│   ├── salesforce_api.py      # NEW: Salesforce client using simple-salesforce
│   └── __init__.py
├── controller/
│   ├── workspace.py            # Existing WorkspaceManager (reuse)
│   ├── cache_manager.py        # NEW: Activity-aware cache coordination
│   └── token_manager.py        # NEW: Proactive token refresh before expiry
├── utils/
│   ├── cache.py                # Existing file-based cache (adapt to SQLite)
│   └── formatters.py           # Existing shorten_and_format() (reuse)
└── agent/
    └── __init__.py             # Placeholder for container-side code
```

### Pattern 1: Reuse RedHatAPIClient Pattern for Salesforce

**What:** Apply the same session management, retry logic, and error handling patterns from RedHatAPIClient to Salesforce integration

**When to use:** Always - proven pattern with 100+ tests in v1.0

**Example:**
```python
# Based on src/mc/integrations/redhat_api.py pattern
from simple_salesforce import Salesforce
from tenacity import retry, stop_after_attempt, wait_exponential

class SalesforceAPIClient:
    """Client for Salesforce case metadata queries."""

    def __init__(self, username: str, password: str, security_token: str):
        self.username = username
        self.password = password
        self.security_token = security_token
        self._sf_session = None
        self._token_expires_at = None

    def _create_session(self) -> Salesforce:
        """Create Salesforce session with automatic token tracking."""
        sf = Salesforce(
            username=self.username,
            password=self.password,
            security_token=self.security_token
        )
        # Token expires in 2 hours (7200 seconds) per Salesforce docs
        self._token_expires_at = time.time() + 7200
        return sf

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=8),
        retry=retry_if_exception_type(SalesforceAPIError),
        reraise=True
    )
    def query_case(self, case_number: str) -> dict[str, Any]:
        """Query case metadata with automatic retry on rate limiting."""
        if self._needs_refresh():
            self._refresh_session()

        try:
            # SOQL query for case metadata
            result = self._sf_session.query(
                f"SELECT CaseNumber, Account.Name, Subject, "
                f"Severity__c, Status FROM Case WHERE CaseNumber = '{case_number}'"
            )
            return result['records'][0] if result['records'] else None
        except SalesforceAPIError as e:
            if e.status_code == 429:
                # Respect Retry-After header for rate limiting
                logger.warning("Rate limited (429), retrying with exponential backoff")
                raise  # Let tenacity handle retry
            raise
```

### Pattern 2: SQLite-Based Cache with Background Refresh

**What:** Replace v1.0's JSON file cache with SQLite using WAL mode for concurrent read/write, add background worker thread for proactive refresh

**When to use:** When cache needs concurrent access from controller (read) and background worker (write), or when filtering/querying cache entries

**Example:**
```python
# Adaptation of src/mc/utils/cache.py to SQLite
import sqlite3
import threading
from contextlib import contextmanager

class CaseMetadataCache:
    """SQLite-based cache with concurrent access support."""

    def __init__(self, cache_dir: Path):
        self.db_path = cache_dir / "case_metadata.db"
        self._init_db()
        self._background_worker = None

    def _init_db(self):
        """Initialize SQLite with WAL mode for concurrent access."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_cache (
                    case_number TEXT PRIMARY KEY,
                    case_data TEXT NOT NULL,
                    account_data TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
            """)

    @contextmanager
    def _get_connection(self):
        """Thread-safe connection context manager."""
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get(self, case_number: str) -> tuple[dict, dict, bool]:
        """Get case metadata from cache (returns tuple: case_data, account_data, was_cached)."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT case_data, account_data, cached_at, ttl_seconds FROM case_cache WHERE case_number = ?",
                (case_number,)
            )
            row = cursor.fetchone()

            if row:
                case_data, account_data, cached_at, ttl_seconds = row
                if not self._is_expired(cached_at, ttl_seconds):
                    return json.loads(case_data), json.loads(account_data), True

        return None, None, False

    def set(self, case_number: str, case_data: dict, account_data: dict, ttl_seconds: int = 300):
        """Cache case metadata with TTL."""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO case_cache (case_number, case_data, account_data, cached_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
            """, (
                case_number,
                json.dumps(case_data),
                json.dumps(account_data),
                time.time(),
                ttl_seconds
            ))
```

### Pattern 3: Proactive Token Refresh (5 Min Before Expiry)

**What:** Track token expiration time and proactively refresh 5 minutes before expiry to prevent authentication failures

**When to use:** Always - Salesforce tokens expire after 2 hours and failed API calls disrupt container operations

**Example:**
```python
# New controller/token_manager.py pattern
class TokenManager:
    """Manages Salesforce token lifecycle with proactive refresh."""

    REFRESH_BUFFER_SECONDS = 300  # 5 minutes before expiry
    TOKEN_LIFETIME_SECONDS = 7200  # 2 hours per Salesforce docs

    def __init__(self, sf_client: SalesforceAPIClient):
        self.sf_client = sf_client
        self._refresh_lock = threading.Lock()

    def _needs_refresh(self) -> bool:
        """Check if token needs refresh (within 5 min of expiry)."""
        if not self.sf_client._token_expires_at:
            return True

        time_until_expiry = self.sf_client._token_expires_at - time.time()
        return time_until_expiry <= self.REFRESH_BUFFER_SECONDS

    def ensure_valid_token(self):
        """Ensure token is valid, refresh if needed (thread-safe)."""
        if self._needs_refresh():
            with self._refresh_lock:
                # Double-check after acquiring lock (another thread may have refreshed)
                if self._needs_refresh():
                    logger.info("Token expiring soon, proactively refreshing")
                    self.sf_client._refresh_session()
```

### Pattern 4: Podman Secrets for Token Distribution

**What:** Use Podman secrets to securely provide Salesforce credentials to containers without environment variables

**When to use:** Always - environment variables visible in `podman inspect`, secrets are mount-based (mode 0600) and don't persist in images

**Example:**
```python
# Controller-side: Create secret and mount to container
import podman

def create_container_with_secrets(client: podman.PodmanClient, case_number: str, sf_creds: dict):
    """Create container with Salesforce credentials as Podman secrets."""

    # Create secrets (ephemeral, deleted when container stops)
    sf_username_secret = client.secrets.create(
        name=f"mc-{case_number}-sf-username",
        data=sf_creds['username'].encode()
    )
    sf_password_secret = client.secrets.create(
        name=f"mc-{case_number}-sf-password",
        data=sf_creds['password'].encode()
    )
    sf_token_secret = client.secrets.create(
        name=f"mc-{case_number}-sf-token",
        data=sf_creds['security_token'].encode()
    )

    # Mount secrets to container (available as files in /run/secrets/)
    container = client.containers.run(
        image="mc-rhel10:latest",
        name=f"mc-case-{case_number}",
        secrets=[
            {"source": sf_username_secret.name, "target": "sf_username"},
            {"source": sf_password_secret.name, "target": "sf_password"},
            {"source": sf_token_secret.name, "target": "sf_token"}
        ],
        detach=True
    )

    return container

# Agent-side: Read secrets from /run/secrets/
def get_salesforce_credentials() -> dict:
    """Read Salesforce credentials from Podman secrets."""
    secrets_dir = Path("/run/secrets")

    return {
        'username': (secrets_dir / "sf_username").read_text().strip(),
        'password': (secrets_dir / "sf_password").read_text().strip(),
        'security_token': (secrets_dir / "sf_token").read_text().strip()
    }
```

### Anti-Patterns to Avoid

- **Don't use environment variables for secrets**: Visible in `podman inspect` output, persisted in container metadata
- **Don't request tokens on every API call**: Rate limiting triggers after frequent token requests (20 min minimum interval per Salesforce docs)
- **Don't retry 401/403 errors**: Authentication failures are permanent, fail fast and notify user
- **Don't implement activity detection without clear need**: Platform-specific (macOS vs Linux), adds complexity, fixed-interval refresh may be sufficient

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Salesforce SOQL queries | Raw HTTP requests with manual JSON parsing | simple-salesforce library | Handles authentication, session management, response parsing, field access via dot notation, pagination for large result sets |
| Exponential backoff retry | Sleep loops with manual counter | tenacity library | Already in v1.0, declarative retry policies, respects Retry-After headers, configurable max attempts and delays |
| OAuth2 token refresh | Custom token expiry tracking | simple-salesforce built-in refresh | Library tracks token lifetime internally, though proactive refresh (5 min buffer) requires custom logic |
| Cross-platform cache paths | Hardcoded ~/.mc/cache | platformdirs library | Already in v1.0, handles macOS/Linux differences, respects XDG_CACHE_HOME on Linux |
| SQLite connection pooling | Manual connection management | contextmanager + WAL mode | Built-in SQLite support for concurrent readers with WAL (Write-Ahead Logging), no external pool needed |
| Container secret management | Custom file-based secrets | Podman secrets API | Built-in secure mounting, automatic cleanup, mode 0600 permissions, doesn't persist in images |

**Key insight:** Salesforce integration has well-established patterns - use proven libraries and avoid reinventing authentication, retry logic, or secret management.

## Common Pitfalls

### Pitfall 1: Token Expiry During Long-Running Operations
**What goes wrong:** Salesforce access tokens expire after 2 hours. If controller starts container at T=0 and token expires at T+2h, any API calls after that fail with 401 Unauthorized.

**Why it happens:** Tokens are created once at container start but not refreshed proactively.

**How to avoid:** Implement proactive token refresh 5 minutes before expiry (as shown in Pattern 3). Track token creation time and refresh before the 2-hour mark.

**Warning signs:** Intermittent 401 errors after ~2 hours of uptime, API calls failing with "Session expired or invalid" errors.

### Pitfall 2: Rate Limiting from Excessive Token Requests
**What goes wrong:** Requesting new access tokens too frequently triggers HTTP 429 rate limiting, blocking all API access temporarily.

**Why it happens:** Salesforce recommends "don't request more than one access token every 20 minutes" but developers often create new sessions per API call for simplicity.

**How to avoid:** Cache the Salesforce session object (simple-salesforce `Sf` instance) and reuse it for multiple queries. Only create new session when token expires or on authentication failure.

**Warning signs:** HTTP 429 errors appearing during normal operation (not high-volume queries), Retry-After headers with 20+ minute delays.

### Pitfall 3: Ignoring Retry-After Header on 429 Errors
**What goes wrong:** Exponential backoff retries immediately after 429 error, ignoring the Retry-After header, leading to continued rate limiting.

**Why it happens:** Standard exponential backoff (2-4-8 seconds) doesn't check Retry-After header which may specify 60+ seconds.

**How to avoid:** Parse Retry-After header from 429 response and use as minimum wait time before retry. Salesforce API includes this header to indicate exact wait duration.

**Warning signs:** Retries failing immediately after 429 error, multiple consecutive 429s in logs, rate limiting persisting despite backoff.

### Pitfall 4: Activity Detection Complexity
**What goes wrong:** Implementing terminal activity detection requires platform-specific code (macOS: IOKit/Quartz APIs, Linux: X11/Wayland APIs, SSH: parsing `w` command output), each with different edge cases.

**Why it happens:** Desire for "smart" caching that reduces API calls during idle periods, but underestimating cross-platform complexity.

**How to avoid:** Start with simpler approach: fixed-interval background refresh (e.g., every 5 minutes) or on-demand refresh during container operations. Measure actual API call volume before adding activity detection.

**Warning signs:** Cache TTL logic has platform-specific branches, import errors on different OSes, incorrect idle detection in SSH/tmux sessions.

### Pitfall 5: Workspace Path Pinning at Wrong Time
**What goes wrong:** If workspace path is constructed at container creation time using stale cached metadata, path may not match latest case data (customer renamed, case summary updated).

**Why it happens:** Cache has 30-minute TTL but workspace path is generated once and used for duration of container lifecycle.

**Context decision clarification:** CONTEXT.md specifies "Container workspace path pinned at creation time (no auto-updates)" - this is intentional to prevent paths changing underneath running containers.

**How to avoid:** This is expected behavior per CONTEXT.md. Workspace path stability is more important than reflecting metadata updates. Document that users should recreate container if case metadata changes significantly.

**Warning signs:** User confusion when workspace path doesn't match current case summary, containers with outdated customer names in path.

## Code Examples

Verified patterns from existing v1.0 codebase and official documentation:

### Workspace Path Construction (Reuse v1.0 Pattern)
```python
# Source: src/mc/controller/workspace.py (v1.0, production-tested)
from mc.utils.formatters import shorten_and_format

class WorkspaceManager:
    def __init__(self, base_dir: Path, case_number: str, account_name: str, case_summary: str):
        self.base_dir = Path(base_dir)
        self.case_number = case_number
        self.account_name_formatted = shorten_and_format(account_name)
        self.case_summary_formatted = shorten_and_format(case_summary)

    def get_workspace_path(self) -> Path:
        """Get workspace path for case."""
        return (
            self.base_dir /
            self.account_name_formatted /
            f"{self.case_number}-{self.case_summary_formatted}"
        )
```

### Error Handling Pattern (Reuse v1.0 HTTPAPIError)
```python
# Source: src/mc/exceptions.py (v1.0, production-tested)
# Adapt this pattern for Salesforce API errors

class SalesforceAPIError(APIError):
    """Salesforce API error with helpful suggestions."""

    @classmethod
    def from_response(cls, status_code: int, message: str) -> 'SalesforceAPIError':
        """Create error with user-friendly message."""
        suggestions = {
            401: "Authentication failed. Check: Salesforce credentials in config",
            403: "Access forbidden. Check: Salesforce user has case read permissions",
            404: "Case not found. Check: Case number exists in Salesforce",
            429: "Rate limited. Try: Wait before retrying (check Retry-After header)",
            500: "Salesforce server error. Try: Retry in a few minutes",
        }

        suggestion = suggestions.get(status_code)
        error = cls(f"Salesforce API error {status_code}: {message}", suggestion)
        error.status_code = status_code
        return error
```

### Cache TTL Configuration
```python
# Adaptation of src/mc/utils/cache.py for activity-aware TTL
class ActivityAwareCacheConfig:
    """Cache TTL configuration based on terminal activity."""

    # During active terminal use (keystroke activity detected)
    ACTIVE_TTL_SECONDS = 300  # 5 minutes

    # During inactive periods (30+ min since last keystroke)
    INACTIVE_TTL_SECONDS = 0  # Pause updates (use cached data indefinitely)

    # Inactivity threshold (switch from active to inactive TTL)
    INACTIVITY_THRESHOLD_SECONDS = 1800  # 30 minutes

    # Background refresh interval (when active)
    REFRESH_INTERVAL_SECONDS = 240  # 4 minutes (before 5 min TTL expires)
```

### Salesforce SOQL Query Example
```python
# Pattern based on simple-salesforce documentation and Salesforce SOQL reference
def fetch_case_metadata(sf: Salesforce, case_number: str) -> dict:
    """Query case metadata using SOQL."""
    query = f"""
        SELECT
            CaseNumber,
            Account.Name,
            Subject,
            Severity__c,
            Status,
            Owner.Name,
            CreatedDate,
            ClosedDate
        FROM Case
        WHERE CaseNumber = '{case_number}'
        LIMIT 1
    """

    result = sf.query(query)

    if not result['records']:
        raise HTTPAPIError(
            f"Case {case_number} not found in Salesforce",
            "Check: Case number is correct and accessible to your Salesforce user"
        )

    # simple-salesforce returns OrderedDict with field access
    case = result['records'][0]

    return {
        'case_number': case['CaseNumber'],
        'account_name': case['Account']['Name'],  # Relationship field access
        'case_summary': case['Subject'],
        'severity': case.get('Severity__c', 'Unknown'),  # Custom field may be null
        'status': case['Status'],
        'owner': case['Owner']['Name'],
    }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| JSON file cache with 30-min TTL | SQLite cache with activity-aware TTL | v2.0 (2026) | 35x faster reads, 3x smaller storage, concurrent access support for background refresh |
| Environment variables for secrets | Podman secrets with mount-based access | v2.0 (2026) | Secrets not visible in `podman inspect`, automatic cleanup, mode 0600 permissions |
| Reactive token refresh (on 401) | Proactive refresh (5 min before expiry) | Best practice 2026 | Eliminates authentication failures during operations, smoother UX |
| Fixed 30-min cache TTL | Activity-aware TTL (5-10 min active, paused inactive) | v2.0 decision | Reduces API calls during active use while respecting rate limits |
| Manual retry with sleep loops | Declarative retry policies (tenacity) | v1.0 (2026-01-22) | Respects Retry-After headers, configurable backoff, cleaner code |

**Deprecated/outdated:**
- **simple-salesforce 0.x**: Use 1.12.9+ for Python 3.11+ support and improved OAuth2 handling
- **SQLite without WAL mode**: Enable WAL (Write-Ahead Logging) for concurrent reads during background writes
- **Direct environment variable access for secrets**: Use Podman secrets API for container credentials

## Open Questions

Things that couldn't be fully resolved:

1. **Activity Detection Implementation**
   - What we know: Platform-specific APIs exist (macOS: IOKit, Linux: X11/Wayland), PyPI `idle-time` package available for Linux/Wayland
   - What's unclear: Whether activity detection is necessary given simpler alternatives (fixed-interval refresh, on-demand refresh)
   - Recommendation: Start with fixed 5-minute background refresh during container uptime, measure API call volume, defer activity detection unless rate limiting becomes problem

2. **Salesforce Custom Field Names**
   - What we know: Case metadata requires customer name, case summary, severity, owner - standard fields are `Account.Name`, `Subject`, `Owner.Name`
   - What's unclear: Whether Red Hat's Salesforce instance uses custom field for severity (`Severity__c` convention) or standard field
   - Recommendation: Query Salesforce schema during Phase 10 implementation to identify exact field names, handle null values gracefully

3. **Cache Storage Location Decision**
   - What we know: CONTEXT.md leaves cache storage location to Claude's discretion (host filesystem vs SQLite state database)
   - What's unclear: Whether to use separate SQLite database for cache or integrate into Phase 11's state database
   - Recommendation: Use separate cache database in v2.0 (~/.mc/cache/case_metadata.db) for separation of concerns, can consolidate in future if state database proves viable

4. **Background Refresh Failure Notification**
   - What we know: CONTEXT.md requires "notify user immediately if background refresh fails (network error, API down)"
   - What's unclear: Notification mechanism in terminal-attached containers (log to container stdout? Desktop notification? Both?)
   - Recommendation: Log error to container stdout (visible in `podman logs`) and controller logs, evaluate desktop notifications in Phase 12 (terminal automation) if needed

## Sources

### Primary (HIGH confidence)
- **simple-salesforce GitHub repository**: https://github.com/simple-salesforce/simple-salesforce - Authentication methods, features, error handling patterns
- **Salesforce OAuth2 Refresh Token Flow**: https://developer.salesforce.com/docs/platform/mobile-sdk/guide/oauth-refresh-token-flow.html - Token expiration (2 hours), refresh flow mechanics
- **Salesforce Rate Limiting Best Practices**: https://developer.salesforce.com/docs/marketing/marketing-cloud/guide/rate-limiting-best-practices.html - HTTP 429 handling, exponential backoff (2-4-8 seconds), Retry-After header, 20-minute token request interval
- **v1.0 codebase** (mc/integrations/redhat_api.py, mc/utils/cache.py, mc/controller/workspace.py): Production-tested patterns for API clients, caching, workspace management

### Secondary (MEDIUM confidence)
- **SQLite Performance Comparison**: https://www.sqliteforum.com/p/implementing-cache-strategies-for - 35x faster reads than PostgreSQL, 150k TPS with WAL mode, verified via multiple benchmarks
- **Podman Secrets Documentation**: https://docs.podman.io/en/latest/markdown/podman-secret-create.1.html - Secret creation, mounting, security model, lifecycle management
- **Python Background Task Processing (2025)**: https://danielsarney.com/blog/python-background-task-processing-2025-handling-asynchronous-work-modern-applications/ - Modern patterns for background workers, thread safety, cache refresh strategies

### Tertiary (LOW confidence)
- **Python idle-time detection**: https://pypi.org/project/idle-time/ - PyPI package for Linux/Wayland idle detection, unverified cross-platform support
- **Activity detection patterns**: https://medium.com/@gonchogo/checking-idle-time-by-python-d3c78e88336 - Platform-specific approaches (macOS IOKit, Windows GetLastInputInfo), marked for validation
- **Salesforce token expiration discussions**: https://dev.to/xkit/when-do-salesforce-access-tokens-expire-1ih9 - Community reports of 2-hour expiration, should verify with official Salesforce documentation during implementation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - simple-salesforce is industry standard, v1.0 patterns proven in production
- Architecture: HIGH - Podman secrets, SQLite cache, token refresh patterns well-documented
- Pitfalls: HIGH - Rate limiting, token expiry, Retry-After header handling verified in official docs
- Activity detection: MEDIUM - Platform-specific complexity confirmed, simpler alternatives exist
- Salesforce schema: MEDIUM - Standard field names known, custom field verification needed during implementation

**Research date:** 2026-01-26
**Valid until:** 2026-02-26 (30 days - Salesforce API and simple-salesforce are stable, token/rate limit behavior unlikely to change)
