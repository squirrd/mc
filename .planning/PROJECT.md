# MC CLI Hardening Project

## What This Is

A production-ready Python CLI tool and container orchestrator for Red Hat support case management. Provides isolated per-case containerized workspaces with automatic Salesforce integration, terminal automation, and comprehensive lifecycle management. Built with type safety, security hardening, and modern Python 3.11+ practices.

## Core Value

Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality.

## Current Status

**Latest Release:** v2.0.2 (2026-02-08)

**What's Shipped:**
- ✓ Per-case containerized environments eliminating credential/config collisions
- ✓ Automatic Red Hat API integration for case metadata resolution
- ✓ Container lifecycle management (create, list, stop, delete, exec)
- ✓ New terminal window attachment for seamless multi-case workflow
- ✓ Container image with essential tools (mc, RHEL 10 UBI base)
- ✓ Quay.io registry integration with auto-pull and local fallback
- ✓ Modern distribution via uv tool (pipx/uv tool install git+)
- ✓ Window ID tracking system eliminating duplicate terminal windows (macOS and Linux X11)
- ✓ Self-healing window registry with automatic cleanup and reconcile command
- ✓ Production-ready test suite: 530 tests passing with 74.65% coverage

## Requirements

### Validated

Shipped in v2.0.2 (2026-02-08):

**Window Tracking System:**
- ✓ SQLite-backed window registry persists window IDs across mc process restarts — v2.0.2
- ✓ Window registry survives concurrent access (WAL mode, first-write-wins) — v2.0.2
- ✓ System stores window ID when creating terminal window — v2.0.2
- ✓ System retrieves window ID by case number — v2.0.2
- ✓ Running `mc case XXXXX` twice focuses existing window instead of creating duplicate — v2.0.2
- ✓ System validates window still exists before focusing (lazy validation) — v2.0.2
- ✓ System creates new window if previous window was closed manually — v2.0.2
- ✓ System detects and removes stale entries for closed windows — v2.0.2
- ✓ Automatic cleanup on startup reconciles registry with actual windows — v2.0.2
- ✓ Manual `mc container reconcile` command for troubleshooting — v2.0.2
- ✓ Window focusing works on macOS (iTerm2, Terminal.app) — v2.0.2
- ✓ Window focusing works on Linux (X11 with wmctrl/xdotool) — v2.0.2
- ✓ System provides feedback when focusing vs creating new window — v2.0.2
- ✓ Integration test `test_duplicate_terminal_prevention_regression` passes consistently — v2.0.2
- ✓ Unit tests for WindowRegistry store/lookup/cleanup operations (95% coverage) — v2.0.2
- ✓ Platform-specific tests for macOS and Linux — v2.0.2
- ✓ Graceful database corruption recovery — v2.0.2

Shipped in v1.0 (2026-01-22):

**Test Infrastructure:**
- ✓ pytest framework configured and working — v1.0
- ✓ pytest-mock installed for API/external service mocking — v1.0
- ✓ Test fixtures infrastructure set up — v1.0
- ✓ Unit tests for auth module (get_access_token) — v1.0
- ✓ Unit tests for RedHatAPIClient with mocked requests — v1.0
- ✓ Unit tests for WorkspaceManager — v1.0
- ✓ Unit tests for formatters and file_ops utilities — v1.0
- ✓ Mock LDAP responses for integration testing — v1.0

**Tech Debt Resolution:**
- ✓ Fix hardcoded base directory (use TOML config file with default) — v1.0
- ✓ Remove environment variable dependencies and duplicate validation — v1.0
- ✓ Consolidate version management (single source of truth) — v1.0
- ✓ Migrate fully to pyproject.toml (remove setup.py) — v1.0
- ✓ Fix typo "dowloading attachemnts" → "downloading attachments" — v1.0

**Bug Fixes:**
- ✓ Fix LDAP --All flag (change to --all lowercase) — v1.0
- ✓ Fix CheckStaus → CheckStatus typo throughout — v1.0

**Security Hardening:**
- ✓ Add access token expiration validation and caching — v1.0
- ✓ Explicitly set verify=True in all requests calls — v1.0
- ✓ Add case number format validation (8 digits) — v1.0
- ✓ Add file size warning for downloads >3GB — v1.0

**Performance:**
- ✓ Implement parallel attachment downloads (8 concurrent threads) — v1.0
- ✓ Add file-based caching for case metadata with TTL — v1.0
- ✓ Cache access tokens with expiration tracking — v1.0

**Code Quality:**
- ✓ Improve workspace path construction error handling — v1.0
- ✓ Add robust LDAP parsing with error handling — v1.0
- ✓ Improve file existence checks (pathlib) — v1.0
- ✓ Add HTTP error handling with meaningful messages — v1.0
- ✓ Add retry logic for transient API failures — v1.0

**Infrastructure:**
- ✓ Implement structured logging framework (replace print statements) — v1.0
- ✓ Add error recovery and retry for attachment downloads — v1.0
- ✓ Add download progress indication for large files — v1.0

**Dependencies:**
- ✓ Update minimum Python version to 3.11+ — v1.0
- ✓ Add type hints to all modules — v1.0 (98% coverage)
- ✓ Configure mypy strict mode and resolve issues — v1.0

**Existing Capabilities:**
- ✓ Case workspace management (create, check, navigate workspaces) — existing
- ✓ Red Hat API integration (fetch case details, account info, attachments) — existing
- ✓ Attachment downloads with streaming — existing (enhanced with parallel downloads in v1.0)
- ✓ LDAP employee directory search — existing
- ✓ Salesforce case URL generation and browser launching — existing
- ✓ OAuth token management (offline token to access token) — existing (enhanced with caching in v1.0)
- ✓ Workspace file structure generation based on case data — existing

### Active

(Next milestone requirements - to be defined via `/gsd:new-milestone`)

### Out of Scope

- Container orchestration features — deferred to future milestone (separate feature initiative)
- YAML configuration file support — deferred to future milestone (TOML config sufficient for current needs)
- Real-time notifications — not needed for CLI use case
- GUI or web interface — CLI-focused tool by design
- Plugin system — security risks; version compatibility nightmares; CLI tools should have focused scope
- Web-based interface — if web UI needed, make it separate project
- Database storage — file-based storage is simpler and sufficient

## Context

**Current State (v2.0.2 shipped 2026-02-08):**
- Python 3.11+ CLI tool and container orchestrator for Red Hat support case management
- 7,349 lines of production Python code (cumulative v1.0 + v2.0 + v2.0.1 + v2.0.2)
- Layered architecture: CLI → Commands → Container Manager/Integrations → Utilities
- External dependencies: Red Hat API, Podman, SQLite
- Tech stack: pytest, requests, rich, podman-py, tomli/tomllib, wmctrl/xdotool (Linux X11)
- Configuration: TOML-based (~/mc/config/config.toml) with auto-migration
- Type-safe: mypy strict mode passing with 100% type coverage

**Key Features:**
- Container orchestration with per-case isolated workspaces
- Automatic terminal attachment (iTerm2, Terminal.app, gnome-terminal, konsole)
- Container lifecycle management (create, list, stop, delete, exec)
- Red Hat API integration with 5-minute cache TTL
- SQLite state persistence and reconciliation
- Parallel downloads (8 concurrent threads) with rich progress bars
- Structured logging with sensitive data redaction
- Comprehensive error handling with retry logic
- Security hardening (SSL verification, token caching, input validation)
- Modern Python 3.11+ syntax with full type hints

**Directory Structure (consolidated v2.0.1):**
```
~/mc/
├── config/
│   ├── config.toml          # TOML configuration
│   └── cache/               # Case metadata cache (SQLite)
├── state/
│   └── containers.db        # Container state (SQLite)
└── cases/
    └── <customer>/
        └── <case>/          # Case workspaces
```

**Known Technical Debt:**
- None - v2.0.2 achieved zero test failures and zero tech debt

## Constraints

- **Backward Compatibility**: All existing commands must continue to work exactly as before
- **API Dependencies**: Must maintain integration with Red Hat Support API, SSO, and LDAP
- **Python Version**: 3.11+ minimum (upgraded from 3.8+ for modern syntax and performance)
- **No Breaking Changes**: Users rely on current command structure and output

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Test infrastructure before fixes | TDD approach - establish testing foundation first so all fixes can be verified | ✓ Good - 100+ tests catch regressions |
| Split testing into 2 phases | Phase 1 sets up framework, Phase 2 writes critical path tests - allows faster initial progress | ✓ Good - systematic approach |
| Critical path testing only | Test auth, API client, workspace manager first - most fragile and important modules | ✓ Good - 80%+ coverage on critical modules |
| Modern pytest with importlib mode | Use pytest 9.0+ with importlib import mode for better namespace handling | ✓ Good - clean test execution |
| HTTP mocking via responses library | Use responses instead of generic pytest-mock for requests library mocking | ✓ Good - natural HTTP mocking API |
| TOML chosen for config file format | Python 3.11+ stdlib support, more readable than INI | ✓ Good - cross-platform support working |
| platformdirs for config paths | XDG on Linux, macOS/Windows equivalents for cross-platform support | ✓ Good - proper config locations |
| Fail-fast approach for legacy env vars | No backward compat for environment variables, show unset instructions | ✓ Good - forces migration to TOML |
| File-based token cache over keyring | Simpler, no dependencies, sufficient for CLI use case | ✓ Good - works reliably |
| Python 3.11 minimum version | Native union syntax (X \| Y) without __future__ imports, 10-60% faster | ✓ Good - modern syntax, better performance |
| mypy as separate test command | Not pytest plugin for cleaner separation (pytest tests behavior, mypy checks types) | ✓ Good - simple and effective |
| TypedDict for API responses | Provides structure for dict-based API responses without runtime overhead | ✓ Good - IDE autocomplete working |
| 8 concurrent downloads default | Balances download speed with API rate limits and system resources | ✓ Good - 8x faster for multiple files |
| Rich progress library | Multi-file progress tracking with per-file speed/ETA | ✓ Good - excellent UX |
| Backoff library for retry | Exponential backoff with jitter prevents thundering herd | ✓ Good - resilient network operations |

---
*Last updated: 2026-02-08 after v2.0.2 milestone*
