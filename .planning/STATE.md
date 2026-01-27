# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-01-26)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently
**Current focus:** Phase 12 - Terminal Attachment & Exec

## Current Position

Milestone: v2.0 Containerization
Phase: 12 of 13 (Terminal Attachment & Exec)
Plan: 3 of 3 (Phase complete)
Status: Phase complete
Last activity: 2026-01-27 - Completed 12-03-PLAN.md (Terminal attachment workflow)

Progress: [█████████████░░░░░░░] 87% (13 of 15 v2.0 plans complete)

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
- Plans completed: 13
- Phase 9 complete (2/2 plans)
- Phase 10 complete (3/3 plans)
- Phase 11 complete (5/5 plans)
- Phase 12 complete (3/3 plans)
- Phase 13 in progress (0/2 plans)

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 9 (Container Architecture & Podman Integration) | 2 | 11min | 5.5min |
| 10 (Salesforce Integration & Case Resolution) | 3 | 18min | 6min |
| 11 (Container Lifecycle & State Management) | 5 | 32min | 6.4min |
| 12 (Terminal Attachment & Exec) | 3 | 10min | 3.3min |

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

**Phase 10 Complete (3/3 plans) — VERIFIED:**
- ✅ Plan 01: SalesforceAPIClient with SOQL queries, automatic token refresh, rate limiting (71 lines, 97% test coverage, 16 tests)
- ✅ Plan 02: SQLite cache with WAL mode, background refresh worker (4-minute intervals), CacheManager (292 lines, 88%/72% coverage, 12 tests)
- ✅ Plan 03: CaseResolver with workspace path resolution, WorkspaceManager.from_case_number() integration (137 lines, 95% test coverage, 15 tests)

**Phase 11 Complete (5/5 plans) — VERIFIED:**
- ✅ Plan 01: StateDatabase with WAL mode, CRUD operations, reconciliation for orphaned state cleanup (244 lines, 96% test coverage, 28 tests)
- ✅ Plan 02: ContainerManager with create() orchestration, auto-restart pattern, workspace auto-creation, userns_mode=keep-id (259 lines, 85%+ coverage, 14 tests)
- ✅ Plan 03: ContainerManager.list() with state reconciliation, metadata enrichment, uptime calculation (260 lines, 63% coverage, 13 tests)
- ✅ Plan 04: Container lifecycle operations (stop, delete, status, logs) with 10s graceful shutdown, workspace preservation (98 lines, excellent coverage, 30 tests)
- ✅ Plan 05: exec() with auto-restart, complete CLI commands (create/list/stop/delete/exec), mc <case_number> quick access (193 lines CLI, 100% CLI coverage, 31 tests)

**Phase 12 Complete (3/3 plans) — VERIFIED:**
- ✅ Plan 01: Terminal launcher abstraction with macOS (iTerm2, Terminal.app) and Linux (gnome-terminal, konsole, xfce4-terminal) support, AppleScript automation, non-blocking subprocess execution (140 lines, 93-97% coverage, 45 tests)
- ✅ Plan 02: Custom bashrc and welcome banner with case metadata, PS1 prompt [MC-{case_number}], helper aliases/functions (50 lines, 100% test coverage, 25 tests)
- ✅ Plan 03: Terminal attachment orchestration with TTY detection, auto-create/auto-start workflow, CLI integration for mc case <number> command (244 lines attach.py, 90% coverage, 21 tests)

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

**Plan 03:**
- Metadata validation with fallbacks: case_summary falls back to Subject, account_name falls back to account_data.name
- Workspace path pinning: Pass metadata to WorkspaceManager constructor (no re-queries, stable paths)
- Circular import avoidance: Import CaseResolver inside WorkspaceManager.from_case_number() method, use TYPE_CHECKING for type hints

**Key Decisions (Phase 11):**

**Plan 01:**
- Platform-appropriate database location: Use platformdirs.user_data_dir("mc", "redhat") for state database (~/Library/Application Support/mc/containers.db on macOS, ~/.local/share/mc/containers.db on Linux)
- WAL mode configuration: Enable Write-Ahead Logging with PRAGMA synchronous=NORMAL and cache_size=10000 for concurrent read/write
- :memory: database handling: Maintain persistent connection with check_same_thread=False for testing (file-based databases create new connections per operation)
- Reconciliation pattern: Accept set of container IDs from Podman, delete state entries NOT in set (detects external deletions without background polling)
- Timestamp storage: Store as Unix integers (int(time.time())) for simplicity and cross-platform consistency
- Connection timeout: 30-second timeout for SQLite connections (conservative for single-user CLI)

**Plan 02:**
- Auto-restart pattern: Existing stopped/exited containers restart instead of creating duplicates (prevents container proliferation)
- Workspace auto-creation: Create workspace directory before mount with exist_ok=True (prevents mount failures when directory missing)
- Non-fatal reconciliation: Reconciliation failures print warning but don't block operations (degraded mode for offline scenarios)
- Cleanup on state failure: If state persistence fails, stop and remove container to prevent orphaned containers (all-or-nothing consistency)

**Plan 03:**
- Reconcile before listing: Call _reconcile() before querying containers to detect external deletions (ensures list accuracy)
- Sort by created_at: Sort containers newest-first by state database timestamp (better UX for developers working on recent cases)
- Missing metadata handling: Return "N/A" for workspace_path and "Unknown" for created_at when container not in state (edge case - shouldn't happen with proper create flow)
- Uptime format: Human-readable format prioritizes larger units (days > hours > minutes > seconds) for readability
- Empty uptime for stopped: Only running containers show uptime (stopped/exited containers have empty string)

**Plan 04:**
- Workspace preserved by default: delete() requires explicit remove_workspace=True flag (safety measure prevents accidental data loss)
- 10-second graceful shutdown: Podman standard timeout (SIGTERM → 10s wait → SIGKILL if still running)
- Auto-reconciliation on status: status() auto-reconciles state when container deleted externally (no manual reconciliation needed)
- Non-fatal workspace deletion: Workspace deletion failures log warning but don't block container deletion (state cleanup succeeds regardless)

**Plan 05:**
- Auto-restart helper extraction: _get_or_restart(case_number) extracted as standalone method for reusability across operations (attach, logs streaming)
- Quick access pattern: Implemented via sys.argv manipulation before argument parsing (detects 8-digit case number and inserts 'quick_access' command)
- Workspace resolution strategy: Quick access uses ConfigManager base_directory + case_number (Phase 11 baseline, Phase 10 will enhance with Salesforce customer data)
- CLI commands helper: _get_manager() helper avoids duplication across command functions (instantiates ContainerManager with correct dependencies)

**Key Decisions (Phase 12):**

**Plan 01:**
- Protocol-based launcher abstraction: Python Protocol enables static type checking while allowing platform-specific implementations without inheritance overhead
- Non-blocking subprocess execution: subprocess.Popen() with background threading.Thread cleanup to return control immediately while preventing zombie processes
- AppleScript string escaping: Escape backslashes first, then quotes for injection safety on macOS terminal automation
- Priority-based terminal detection: macOS (iTerm2 > Terminal.app), Linux (gnome-terminal > konsole > xfce4-terminal > xterm) for predictable selection

**Plan 02:**
- BASH_ENV over --rcfile: Use BASH_ENV environment variable for bashrc injection (works in both interactive and non-interactive contexts)
- Conditional sections: Summary and next steps sections only displayed if metadata present (cleaner banner for minimal metadata)
- Comments excluded: Comments field stored in metadata but NOT displayed in banner per CONTEXT.md requirements
- Prefix alignment: Text wrapping includes prefix length calculation for multi-line field alignment

**Plan 03:**
- TTY detection mandatory: sys.stdout.isatty() prevents terminal launch when stdout piped/redirected (protects scripting use cases)
- Case number validation at attachment layer: Enforce 8-digit format before Salesforce call for early failure detection
- Metadata fallbacks for robustness: account_name defaults to "Unknown", description uses subject if case_summary missing
- Error messages brief with fix hints: "Terminal launch failed. Run: mc --check-terminal" per CONTEXT.md requirements
- CLI routing via lazy import: case_terminal() imported inside main.py command routing to avoid circular dependency

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

Last session: 2026-01-27
Stopped at: Completed 12-03-PLAN.md (Terminal attachment workflow) - Phase 12 complete
Resume: Ready for Phase 13 (Container Image & Deployment)

---
*State initialized: 2026-01-20*
*Last updated: 2026-01-27 (Phase 12 complete - 3/3 plans, Phase 13 ready)*
