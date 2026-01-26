---
phase: 09-container-architecture---podman-integration
plan: 02
subsystem: infra
tags: [podman, podman-py, containers, retry-logic, lazy-initialization]

# Dependency graph
requires:
  - phase: 09-01
    provides: Platform detection (detect_platform, ensure_podman_ready, get_socket_path)
provides:
  - PodmanClient wrapper class with lazy connection and retry logic
  - Podman configuration settings in config models (timeout, retry_attempts, socket_path)
  - Comprehensive unit test suite (25 tests, 91% coverage)
affects: [09-03, 11-container-lifecycle-orchestration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lazy initialization pattern for expensive connections (defer until first use)"
    - "Retry with exponential backoff for transient errors (3 attempts, 2^n delay)"
    - "Platform-specific error messages with remediation steps"
    - "Context manager protocol for resource cleanup"

key-files:
  created:
    - src/mc/integrations/podman.py
    - tests/unit/test_podman_client.py
  modified:
    - src/mc/config/models.py

key-decisions:
  - "Lazy connection: Defer Podman socket connection until first .client property access (enables fast CLI startup, graceful handling of missing Podman)"
  - "Integrated retry: Wrap podman.PodmanClient() instantiation in retry_podman_operation for transparent handling of transient errors"
  - "Platform-specific remediation: Error messages suggest 'podman machine start' (macOS) or 'dnf install podman' (Linux)"
  - "Type safety: Added type: ignore comments for podman-py untyped methods while maintaining strict mypy compliance"

patterns-established:
  - "retry_podman_operation helper: Reusable exponential backoff pattern for Podman API operations"
  - "Lazy connection property: Cache client instance after first access, avoid repeated connection attempts"
  - "Config validation: Optional Podman config section with type validation for fields when present"

# Metrics
duration: 7min
completed: 2026-01-26
---

# Phase 09 Plan 02: Podman Client Wrapper Summary

**Lazy-connecting Podman client with integrated retry logic (3 attempts, exponential backoff) and platform-specific error remediation**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-26T01:39:31Z
- **Completed:** 2026-01-26T01:46:26Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- **PodmanClient wrapper** with lazy initialization pattern - connection deferred until first API access for fast CLI startup
- **Retry logic integration** - podman.PodmanClient() wrapped in retry_podman_operation (3 attempts, exponential backoff) for transparent transient error handling
- **Platform-aware error messages** - macOS suggests "podman machine start", Linux suggests "dnf install podman"
- **Configuration integration** - Added podman.timeout (120s), podman.retry_attempts (3), podman.socket_path (None) to config models
- **Comprehensive test coverage** - 25 unit tests achieving 91% coverage on podman.py module

## Task Commits

Each task was committed atomically:

1. **Task 1: Create PodmanClient wrapper** - `e2eb1db` (feat)
2. **Task 2: Add Podman configuration** - `7ee0279` (feat)
3. **Task 3: Create unit tests** - `74bab61` (test)

**Type safety fixes:** `7a82226` (fix)

## Files Created/Modified

- `src/mc/integrations/podman.py` - PodmanClient class with lazy connection, retry integration, ping/version methods, context manager support
- `src/mc/config/models.py` - Added podman section to default config with timeout, retry_attempts, socket_path fields and validation
- `tests/unit/test_podman_client.py` - 25 unit tests covering initialization, lazy connection, retry logic, platform integration, error handling

## Implementation Details

### PodmanClient Class

**Lazy Connection Pattern:**
- `__init__()` stores configuration but does NOT connect to Podman
- First access to `.client` property triggers:
  1. Platform detection (detect_platform from Plan 01)
  2. Podman readiness check (ensure_podman_ready from Plan 01)
  3. Socket path resolution (get_socket_path from Plan 01)
  4. Connection with retry logic

**Retry Integration:**
```python
def _connect() -> podman.PodmanClient:
    return podman.PodmanClient(base_url=uri, timeout=self._timeout)

self._client = retry_podman_operation(_connect)
```

This ensures ConnectionError/TimeoutError from PodmanClient constructor are retried up to 3 times with exponential backoff (delays: 1s, 2s, 4s).

**Platform-Specific Error Messages:**
- macOS: "Cannot connect to Podman socket. Run 'podman machine start' to start the Podman machine."
- Linux: "Cannot connect to Podman socket. Install Podman: dnf install podman (RHEL/Fedora) or apt install podman (Ubuntu/Debian)"

**API Surface:**
- `client` property: Get connected Podman client (lazy initialization)
- `ping()` -> bool: Verify connection (returns False on error, doesn't raise)
- `get_version()` -> Dict[str, Any]: Get Podman version info
- `close()`: Close connection if open
- Context manager support: `with PodmanClient() as client:`

### Configuration Model

Added to `get_default_config()`:
```python
"podman": {
    "timeout": 120,           # API timeout in seconds
    "retry_attempts": 3,      # Retry count for transient errors
    "socket_path": None       # Override auto-detection (None = auto)
}
```

Validation ensures:
- timeout is int if present
- retry_attempts is int if present
- socket_path is str or None if present
- Podman config section is optional (validated only if present)

### retry_podman_operation Helper

Module-level function implementing exponential backoff:
- Retries on ConnectionError, TimeoutError
- Max retries: 3 (configurable)
- Delay: base_delay * (2 ** attempt)
- Default base_delay: 1.0s (delays: 1s, 2s, 4s)
- Prints retry messages to console for visibility
- Raises final exception if all retries exhausted
- No retry for non-transient exceptions (ValueError, etc.)

### Test Coverage

**25 tests organized into 6 classes:**
1. TestPodmanClientInit (4 tests): Initialization with various parameters
2. TestPodmanClientLazyConnection (3 tests): Lazy connection, caching, failure handling
3. TestPodmanClientMethods (5 tests): ping, get_version, close, context manager
4. TestRetryLogic (6 tests): retry_podman_operation function behavior
5. TestPlatformIntegration (2 tests): macOS/Linux platform-specific handling
6. TestRetryIntegration (5 tests): Verification of retry integration in client property

**Coverage: 91% on podman.py** (missing lines are error handling edge cases)

Key verifications:
- ✅ Connection deferred until first .client access (not __init__)
- ✅ Client cached after first access (subsequent accesses return same instance)
- ✅ retry_podman_operation called during connection establishment
- ✅ Error messages include platform-specific remediation
- ✅ Exponential backoff delays correct (1s, 2s, 4s)
- ✅ Explicit socket_path overrides auto-detection
- ✅ Context manager closes connection on exit

## Decisions Made

**1. Lazy connection over eager connection**
- **Rationale:** Fast CLI startup (no Podman overhead if not needed), graceful degradation (commands work without Podman), testable without Podman installed
- **Impact:** Connection errors deferred to first API access (intentional - fail at usage point)

**2. Integrated retry in client property**
- **Rationale:** Transparent error handling (users don't need to implement retry), single point of retry logic (DRY), handles cold start delays (Podman service starting)
- **Pattern:** Nest _connect() function, call retry_podman_operation(_connect)

**3. Platform-specific error messages**
- **Rationale:** Actionable remediation (users know exact command to run), platform awareness (macOS machine vs Linux native)
- **Implementation:** Check self._platform_type in exception handler, insert platform-specific remediation string

**4. Type: ignore for podman-py untyped methods**
- **Rationale:** podman-py doesn't provide type stubs for .ping(), .version(), .close(), maintaining strict mypy compliance more important than eliminating ignores
- **Future:** Remove when podman-py adds type hints (track in podman-py releases)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**1. Multiple Python environments on macOS**
- **Issue:** pip installed packages to Homebrew Python (3.11) but system python3 is different version
- **Solution:** Used explicit /opt/homebrew/bin/python3.11 path for verification commands
- **Impact:** None (pytest found correct interpreter automatically)

**2. Overall project coverage below threshold**
- **Issue:** pytest failed with "total coverage 11% < 60%" even though podman.py has 91% coverage
- **Reason:** pyproject.toml cov-fail-under=60 checks entire project, not just tested module
- **Solution:** Verified podman.py specific coverage meets 85%+ requirement (success criterion met)
- **Impact:** None (overall coverage low because other modules untested - expected for incremental development)

## User Setup Required

None - no external service configuration required. Podman installation is system-level (not configured by this code).

## Next Phase Readiness

**Ready for Phase 09-03 (Container Creation with UID/GID Mapping):**
- PodmanClient.client provides connected podman.PodmanClient instance
- Platform detection integrated (macOS vs Linux handling)
- Retry logic handles transient errors transparently
- Configuration system ready for additional Podman settings

**API usage example for Phase 09-03:**
```python
from mc.integrations.podman import PodmanClient

with PodmanClient() as client:
    # client.client returns podman.PodmanClient instance
    # Use for container.create(), container.start(), etc.
    container = client.client.containers.create(...)
```

**Known limitations (expected - not blockers):**
- Container operations not yet implemented (planned for Phase 09-03)
- Config file loading not yet integrated (PodmanClient uses hardcoded defaults - config integration planned for Phase 11)
- No version compatibility checking (check_podman_version from Plan 01 exists but not called - planned for Phase 11)

**No blockers for continuation.**

---
*Phase: 09-container-architecture---podman-integration*
*Completed: 2026-01-26*
