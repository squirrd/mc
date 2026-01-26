# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-26)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently
**Current focus:** Phase 10 - Salesforce Integration & Case Resolution

## Current Position

Milestone: v2.0 Containerization
Phase: 10 of 13 (Salesforce Integration & Case Resolution)
Plan: 02 of 03 complete
Status: In progress
Last activity: 2026-01-26 - Completed 10-02-PLAN.md (SQLite cache with background refresh)

Progress: [█████████░░░░░░░░░░░] 50% (12 of 24 total plans complete across all milestones)

## Performance Metrics

**v1.0 Milestone (SHIPPED 2026-01-22):**
- Total plans completed: 21
- Average duration: 4.0 min
- Total execution time: 1.32 hours
- Timeline: 2 days (2026-01-20 → 2026-01-22)

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
| 8 (Type Safety & Modernization) | 1 | 12min | 12min |

**v2.0 Status:**
- Roadmap created: 5 phases (9-13)
- Plans completed: 4
- Phase 9 complete (2/2 plans)
- Phase 10 in progress (2/3 plans)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 9 (Container Architecture & Podman Integration) | 2 | 11min | 5.5min |
| 10 (Salesforce Integration & Case Resolution) | 2 | 14min | 7min |

## Accumulated Context

### v1.0 Shipped (2026-01-22)

**Major Accomplishments:**
- 100+ tests with 80%+ coverage on critical modules
- Python 3.11+ with 98% type coverage and mypy strict validation
- Production-ready security (token caching, SSL verification, input validation)
- Structured logging (74 print statements migrated, sensitive data redaction)
- 8x faster downloads (parallel with rich progress bars, intelligent retry)
- TOML configuration system replacing environment variables

**Tech Stack:**
- Python 3.11+, pytest, requests, rich, tqdm, tenacity, backoff, platformdirs
- 2,590 lines of production code
- 110 files modified

### v2.0 Containerization

**Architecture:** Host-controller + container-agent pattern with shared codebase (80% code reuse)

**Stack:** podman-py 5.7.0, simple-salesforce 1.12.9, SQLite for state, platform-specific terminal launchers

**Phase 9 Complete (2/2 plans) — VERIFIED:**
- ✅ Plan 01: Platform detection with macOS/Linux support, Podman availability checking, socket path resolution (224 lines, 100% test coverage)
- ✅ Plan 02: PodmanClient wrapper with lazy connection, retry logic (3 attempts, exponential backoff), platform-specific error messages (187 lines, 91% test coverage)
- All success criteria met, 8/8 must-haves verified, INFRA-01/03/04 requirements complete

**Phase 10 Progress (2/3 plans):**
- ✅ Plan 01: SalesforceAPIClient with SOQL queries, automatic token refresh, rate limiting (71 lines, 97% test coverage, 16 tests)
- ✅ Plan 02: SQLite cache with WAL mode, background refresh worker (4-minute intervals), CacheManager (292 lines, 88%/72% coverage, 12 tests)

**Phase Overview:**
- Phase 9: Podman integration, platform detection, UID/GID mapping
- Phase 10: Salesforce API integration, caching, token refresh
- Phase 11: Container lifecycle orchestration, state management with SQLite
- Phase 12: Terminal automation (iTerm2/gnome-terminal), auto-attach workflow
- Phase 13: RHEL 10 container image with tools, backwards compatibility

**Key Decisions (Phase 9):**

**Plan 01:**
- Lazy platform detection (no import-time overhead, testable without Podman)
- Sliding window version compatibility (warn at 3 versions, fail at 7+)
- Socket path priority: CONTAINER_HOST → XDG_RUNTIME_DIR → UID-based → rootful fallback
- macOS Podman machine: interactive prompt to start (no silent auto-start)

**Plan 02:**
- Lazy connection: Defer Podman socket connection until first .client property access (fast CLI startup, graceful degradation)
- Integrated retry: Wrap podman.PodmanClient() in retry_podman_operation for transparent transient error handling
- Platform-specific remediation: Error messages suggest 'podman machine start' (macOS) or 'dnf install podman' (Linux)
- Type safety: Added type: ignore for podman-py untyped methods while maintaining strict mypy compliance

**Key Decisions (Phase 10):**

**Plan 01:**
- Proactive token refresh: Refresh 5 minutes before 2-hour expiry (prevents mid-operation auth failures)
- Read-only config mount: Containers access host config via read-only mount (prevents corruption)
- Retry rate limits only: Retry 429 errors but fail fast on 401/403 (auth errors are permanent)
- simple-salesforce library: Use simple-salesforce for OAuth2 session management (don't hand-roll token requests)

**Plan 02:**
- Separate cache database: ~/.mc/cache/case_metadata.db (not integrated into state.db) - different access patterns
- 5-minute TTL: Reduced from 30 minutes to balance freshness with API rate limiting
- 4-minute refresh interval: Refresh before 5-minute TTL expires to ensure cache stays fresh
- Error handling: Log refresh failures but continue worker (one case failure shouldn't block all refreshes)
- WAL mode: Enable Write-Ahead Logging for concurrent readers while background worker writes

### Pending Todos

- [2026-01-22] Fix Phase 8 type annotation cosmetic gaps (area: config)

### Blockers/Concerns

**From research (critical for v2.0):**
- Phase 9: UID/GID mapping must use `--userns=keep-id` and `:U` suffix (prevent permission errors)
- Phase 10: Salesforce tokens expire after 2 hours (proactive refresh 5 min before expiry)
- Phase 11: State reconciliation required (orphaned containers from crashes)
- Phase 12: Terminal launcher needs cross-platform testing (macOS vs Linux)

**Tech debt from v1.0:**
- 2 cosmetic type annotation gaps in config module (not blocking)
- 20 test failures from Path vs string type changes (deferred)

## Session Continuity

Last session: 2026-01-26
Stopped at: Completed 10-02-PLAN.md (SQLite cache with background refresh)
Resume: Continue Phase 10 with next plan (workspace path resolution or case metadata integration)

---
*State initialized: 2026-01-20*
*Last updated: 2026-01-26 (10-02 completion)*
