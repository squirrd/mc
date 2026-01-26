---
phase: 10-salesforce-integration-&-case-resolution
plan: 01
subsystem: integrations
tags: [salesforce, simple-salesforce, oauth2, soql, api-client, token-refresh, rate-limiting, tenacity, pytest-mock]

# Dependency graph
requires:
  - phase: 09-container-architecture-&-podman-integration
    provides: "Phase 9 provided container foundation with platform detection and Podman client wrapper"
provides:
  - "SalesforceAPIClient with SOQL queries for case metadata (customer name, cluster ID, summary, severity, status, owner)"
  - "Automatic token refresh 5 minutes before 2-hour expiration"
  - "Rate limiting handling with exponential backoff (429 errors)"
  - "Salesforce credentials in config schema (username, password, security_token)"
  - "get_config_mount_spec() helper for read-only container credential mounting"
affects: [11-container-lifecycle-&-orchestration, case-resolution, workspace-management]

# Tech tracking
tech-stack:
  added: [simple-salesforce 1.12.9]
  patterns:
    - "Proactive token refresh pattern (refresh before expiry to prevent mid-operation failures)"
    - "Read-only config mounting for container credential distribution"
    - "pytest-mock for API client testing (avoid mixing mock strategies)"

key-files:
  created:
    - src/mc/integrations/salesforce_api.py
    - src/mc/controller/config_mount.py
    - tests/unit/test_salesforce_api.py
  modified:
    - src/mc/config/models.py
    - src/mc/exceptions.py
    - pyproject.toml

key-decisions:
  - "Proactive token refresh: Refresh 5 minutes before 2-hour expiry (prevents mid-operation auth failures)"
  - "Read-only config mount: Containers access host config via read-only mount (prevents corruption)"
  - "Retry rate limits only: Retry 429 errors but fail fast on 401/403 (auth errors are permanent)"
  - "simple-salesforce library: Use simple-salesforce for OAuth2 session management (don't hand-roll token requests)"

patterns-established:
  - "Token lifecycle tracking: Store _token_expires_at, check _needs_refresh() before each operation"
  - "Context manager support: __enter__/__exit__ for resource cleanup"
  - "Comprehensive error mapping: Map HTTP status codes to user-friendly suggestions (401: check credentials, 403: check permissions, 404: case not found)"

# Metrics
duration: 10min
completed: 2026-01-26
---

# Phase 10 Plan 01: Salesforce Integration & Case Resolution Summary

**Salesforce API client with automatic token refresh, SOQL case queries, and read-only config mounting for container credential distribution**

## Performance

- **Duration:** 10 min
- **Started:** 2026-01-26T02:04:58Z
- **Completed:** 2026-01-26T02:15:07Z
- **Tasks:** 3
- **Files modified:** 6

## Accomplishments

- SalesforceAPIClient follows RedHatAPIClient pattern with session management and retry logic
- Automatic token refresh 5 minutes before 2-hour expiration prevents mid-operation auth failures
- SOQL query fetches case metadata: CaseNumber, Account.Name, Cluster_ID__c, Subject, Severity__c, Status, Owner.Name, CreatedDate
- Config schema extended with salesforce section (username, password, security_token)
- get_config_mount_spec() enables containers to access host credentials via read-only mount
- 97% test coverage with 16 comprehensive test cases

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Salesforce API client with session management and token refresh** - `c011e9f` (feat)
   - SalesforceAPIClient class with query_case() method
   - Proactive token refresh logic (_needs_refresh, _refresh_session)
   - Retry decorator for rate limiting with exponential backoff
   - SalesforceAPIError exception with status code mapping
   - ConfigError exception for configuration validation

2. **Task 2: Add Salesforce credentials to configuration schema and create container mount helper** - `f7d8aec` (feat)
   - Updated get_default_config() with salesforce section
   - Updated validate_config() to require Salesforce fields
   - Created get_config_mount_spec() for Podman mount specification
   - Read-only mount prevents containers from modifying host config

3. **Task 3: Write comprehensive unit tests for Salesforce client** - `8f55e9d` (test)
   - 16 test cases covering happy path, error cases, retry logic
   - Tests for 404 not found, 401 auth failure, 403 permission denied, 429 rate limiting
   - Tests for proactive token refresh and session lifecycle
   - Tests for missing optional fields (Cluster_ID__c, Account)
   - 97% code coverage for salesforce_api.py

**Type safety fix:** `5a32c2f` (fix: mypy strict mode compliance)

## Files Created/Modified

- `src/mc/integrations/salesforce_api.py` - Salesforce API client with SOQL queries, token refresh, and retry logic
- `src/mc/controller/config_mount.py` - Podman mount spec helper for read-only config access
- `tests/unit/test_salesforce_api.py` - 16 unit tests with pytest-mock
- `src/mc/config/models.py` - Extended schema with salesforce credentials section
- `src/mc/exceptions.py` - Added SalesforceAPIError and ConfigError exceptions
- `pyproject.toml` - Added simple-salesforce>=1.12.9 dependency and mypy override

## Decisions Made

**1. Proactive token refresh 5 minutes before expiry**
- **Rationale:** Salesforce tokens expire after 2 hours. Refreshing 5 minutes before expiry prevents mid-operation authentication failures
- **Implementation:** Track _token_expires_at on session creation, check _needs_refresh() before each query

**2. Read-only config mounting for containers**
- **Rationale:** Containers need access to host credentials (Red Hat API + Salesforce) but shouldn't modify them
- **Implementation:** get_config_mount_spec() returns Podman mount spec with "ro" option, mounting to /root/.mc/config.toml

**3. Retry rate limits (429) but fail fast on auth errors (401/403)**
- **Rationale:** Rate limiting is transient (wait and retry), but authentication failures are permanent (fix credentials)
- **Implementation:** @retry decorator with retry_if_exception_type(SalesforceAPIError) and status code checking

**4. Use simple-salesforce library for OAuth2 session management**
- **Rationale:** Don't hand-roll OAuth2 token requests - library handles session creation, token tracking, and error handling
- **Implementation:** simple_salesforce.Salesforce() handles authentication, we track expiry for proactive refresh

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**1. SalesforceError exception signature mismatch in tests**
- **Problem:** Initial tests used incorrect signature for SalesforceError (expected message string, but requires url, status, resource_name, content)
- **Solution:** Checked actual signature with help(SalesforceError.__init__), updated tests to use correct parameters
- **Resolution:** All tests pass with proper exception instantiation

**2. Mypy type ignore warnings**
- **Problem:** simple-salesforce doesn't have type stubs, mypy complained about imports
- **Solution:** Added mypy override to pyproject.toml (module "simple_salesforce.*"), used type: ignore[attr-defined] on import line
- **Resolution:** Passes mypy strict mode validation

## User Setup Required

**External services require manual configuration.** Salesforce credentials must be added to config file:

**Environment variables:**
- `SF_USERNAME` - Red Hat Salesforce account username (corporate email)
- `SF_PASSWORD` - Red Hat Salesforce account password
- `SF_SECURITY_TOKEN` - Salesforce security token (get via: Salesforce Dashboard → Settings → Reset My Security Token, emailed to user)

**Dashboard configuration:**
- Verify user has Case read permissions: Salesforce → Setup → Users → Permission Sets

**Verification:**
```bash
# Test config validation
python3 -c "from mc.config.models import get_default_config, validate_config; c = get_default_config(); c['salesforce']['username'] = 'test'; c['salesforce']['password'] = 'pass'; c['salesforce']['security_token'] = 'tok'; assert validate_config(c); print('Config validation OK')"

# Test imports
python3 -c "from mc.integrations.salesforce_api import SalesforceAPIClient; from mc.exceptions import SalesforceAPIError; from mc.controller.config_mount import get_config_mount_spec; print('Imports OK')"
```

## Next Phase Readiness

**Ready for Phase 11 (Container Lifecycle & Orchestration):**
- ✅ SalesforceAPIClient ready to query case metadata in container orchestration flow
- ✅ get_config_mount_spec() ready for container credential mounting
- ✅ Config schema includes salesforce section (will need config wizard updates in future)
- ✅ Error handling provides clear suggestions (401: check credentials, 403: check permissions)

**No blockers.**

**Note for Phase 11:**
- Container orchestration will call query_case(case_number) to resolve case numbers to customer names and workspace paths
- Use get_config_mount_spec() to mount host config into containers with read-only access
- Token refresh happens automatically on host - containers just read credentials from mounted config

---
*Phase: 10-salesforce-integration-&-case-resolution*
*Completed: 2026-01-26*
