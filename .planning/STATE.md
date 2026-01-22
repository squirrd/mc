# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-20)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently
**Current focus:** Phase 7 - Performance Optimization

## Current Position

Phase: 7 of 8 (Performance Optimization)
Plan: 3 of 3 plans
Status: Phase complete
Last activity: 2026-01-22 — Completed 07-03-PLAN.md (resource optimization)

Progress: [███████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 19
- Average duration: 3.5 min
- Total execution time: 1.12 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 (Test Foundation) | 1 | 4min | 4min |
| 2 (Critical Path Testing) | 3 | 8min | 2.7min |
| 3 (Code Cleanup) | 3 | 18min | 6min |
| 4 (Security Hardening) | 3 | 12min | 4min |
| 5 (Error Handling) | 3 | 11min | 3.7min |
| 6 (Infrastructure & Observability) | 4 | 11min | 2.8min |
| 7 (Performance Optimization) | 3 | 16min | 5.3min |

**Recent Trend:**
- Last 5 plans: 1min, 3min, 7min, 3min, 6min
- Trend: Consistent velocity, 4min average for recent plans

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Test infrastructure before fixes: TDD approach establishes testing foundation first so all fixes can be verified
- Critical path testing only: Test auth, API client, workspace manager first (most fragile and important modules)
- Infrastructure features in scope: Logging and error recovery are critical for production readiness
- Modern pytest with importlib mode: Use pytest 9.0+ with importlib import mode for better namespace handling (01-01)
- Coverage threshold 60%: Set now but won't be met until Phase 2 when real tests are written (01-01)
- HTTP mocking via responses library: Use responses instead of generic pytest-mock for requests library mocking (01-01)
- Hierarchical fixture organization: Three-tier structure (root, unit, integration) for proper scoping (01-01)
- Parametrized HTTP error tests for 401, 403, 404, 500 status codes (02-01)
- Error message validation captures stdout for SystemExit scenarios (02-01)
- 100% coverage exceeds 80% target for critical modules (02-01)
- tmp_path for real filesystem testing over mocking validates actual behavior (02-02)
- Parametrized tests with 18 variations for comprehensive input coverage (02-02)
- stdout capture using io.StringIO for testing print-based functions (02-02)
- Subprocess mocking over mockldap library (unmaintained) for LDAP testing (02-03)
- Docker LDAP integration tests with rroemhild/test-openldap for real parsing validation (02-03)
- pytest.mark.integration for selective test execution in CI environments (02-03)
- Server URL mocking in Docker tests to redirect hardcoded production LDAP to localhost (02-03)
- TOML chosen for config file format over INI/YAML/JSON (Python 3.11+ stdlib support) (03-01)
- platformdirs for cross-platform config paths (XDG on Linux, macOS/Windows equivalents) (03-01)
- Fail-fast approach for legacy env vars with shell-specific unset instructions (no backward compat) (03-01)
- Auto-run wizard on first use rather than requiring explicit setup command (better UX) (03-01)
- Binary mode (rb/wb) for TOML I/O to avoid UnicodeDecodeError (03-01)
- Parameter passing for offline_token through command handlers (no global state) (03-01)
- setup.py removed completely in favor of pyproject.toml-only packaging (03-01)
- importlib.metadata for version access with pyproject.toml fallback for development (03-01)
- Fixed --All to --all following argparse lowercase convention (03-03)
- Corrected CheckStaus to CheckStatus for professional output (03-03)
- Fixed attachment message typo for better UX (03-03)
- Used codespell for automated typo validation (03-03)
- PEP 621 compliant pyproject.toml with SPDX license expression (03-02)
- Early argument parsing for --version/--help before config check (03-02)
- Version fallback pattern: importlib.metadata → pyproject.toml parsing (03-02)
- File-based token cache over keyring library (simpler, no dependencies) (04-01)
- Atomic file write using os.open with O_CREAT flag for secure permissions (04-01)
- 5-minute expiry buffer prevents tokens expiring mid-request (04-01)
- 1-hour default TTL when SSO doesn't provide expires_in (04-01)
- Validation at command layer (not API client) for fail-fast error handling (04-01)
- Regex validation for exactly 8 digits (Red Hat case number format) (04-01)
- SSL verification enabled by default with environment variable override support (04-02)
- 3GB threshold for large file warnings (configurable) (04-02)
- 10% disk space buffer required beyond file size (04-02)
- RuntimeError used to signal download failures to CLI layer (04-02)
- Force parameter at API level (CLI flag deferred to future enhancement) (04-02)
- HEAD request before streaming download for file size validation (04-02)
- 30-second HTTP timeout for all requests (prevents indefinite hangs) (04-03)
- HIGH severity threshold in Bandit config (prevents noise from low-priority warnings) (04-03)
- nosec annotations with detailed justifications (documents why code is safe) (04-03)
- Timeout prevents DoS vulnerability from slow/unresponsive servers (04-03)
- Exit codes follow sysexits.h: 65=auth, 69=API, 2=validation, 73=workspace, 74=file I/O (05-01)
- HTTPAPIError.from_response() maps status codes to actionable suggestions (05-01)
- Logging to stderr at DEBUG/WARNING levels based on --debug flag (05-01)
- KeyboardInterrupt returns exit code 130 (standard SIGINT) (05-01)
- 3 retries default with configurable max_retries parameter (05-02)
- Retry on 429, 500, 502, 503, 504 status codes with exponential backoff (05-02)
- Timeout (3.05s connect, 27s read) prevents indefinite hangs (05-02)
- Respect Retry-After header when present (05-02)
- Batch downloads continue on error, report failures at end (05-02)
- Session cleanup via context manager support (05-02)
- Debug logging for all HTTP operations (05-02)
- pathlib chosen over os.path for type safety and modern API (05-03)
- File operations validate parent directories before creating files (05-03)
- LDAP parsing continues on malformed entries rather than failing completely (05-03)
- ValidationError raised for invalid LDAP search terms instead of returning error tuple (05-03)
- stdlib logging module sufficient without structlog dependency for CLI logging needs (06-01)
- Dual-mode formatters: human-readable text default, JSON via --json-logs flag (06-01)
- SensitiveDataFilter redacts passwords, Bearer tokens, api_keys before any output (06-01)
- Logging setup called after argument parsing but before command routing (06-01)
- Debug mode enables DEBUG level with optional file output via --debug-file (06-01)
- Lazy % formatting for performance (avoid f-strings in logging calls) (06-02)
- Intentional user output preserved with # print OK markers (06-02)
- Log levels: INFO for operations, DEBUG for details, WARNING/ERROR for issues (06-02)
- Interactive prompts kept as print() for user experience (06-02)
- tenacity retry decorator with exponential backoff (1s, 2s, 4s max) for network errors and transient failures (06-03)
- tqdm progress bars with 100ms update interval and binary byte scaling (1024-based) (06-03)
- HTTP Range header support for resumable downloads from partial file position (06-03)
- 401/403 authentication errors fail fast without retry, 429/503 trigger retry (06-03)
- Retry attempts logged at WARNING level via before_sleep_log (06-03)
- Sequential downloads (one at a time) for clean terminal output with progress bars (06-03)
- All logger calls now use lazy % formatting for consistent performance optimization (06-04)
- File-based case metadata cache at ~/.mc/cache/ with 30-minute TTL (07-01)
- Cache age indicator "(cached Xm ago)" for user transparency (07-01)
- Transparent cache wrapper pattern returns same data structure as direct API calls (07-01)
- Corrupted cache auto-deleted and refetched for graceful degradation (07-01)
- 8 concurrent downloads via ThreadPoolExecutor for parallel attachment downloads (07-02)
- Rich progress library for multi-file progress tracking with per-file speed/ETA (07-02)
- --serial flag for sequential download debugging (07-02)
- --quiet flag suppresses progress but shows errors for CI/automation (07-02)
- Parallel mode as default for better UX with multiple attachments (07-02)
- Failed downloads don't crash others via as_completed() pattern (07-02)
- Backoff library for exponential retry with jitter (max 5 attempts) for network resilience (07-03)
- Fail fast on 4xx client errors (404, 401, 403), retry on 5xx and 429 (07-03)
- HTTP Range headers for resumable downloads from partial file position (07-03)
- Ctrl+C deletes incomplete files for clean state, network errors preserve for resume (07-03)
- Respect Retry-After header on 429 rate limiting before backoff retry (07-03)
- 206 Partial Content status accepted for resume requests (07-03)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-01-22T08:56:19Z
Stopped at: Completed 07-03-PLAN.md - resource optimization (retry, resume, cleanup)
Resume file: None

---
*State initialized: 2026-01-20*
*Last updated: 2026-01-22*
