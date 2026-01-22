# MC CLI Hardening Project

## What This Is

A production-ready Python CLI tool for Red Hat support case management with comprehensive test coverage, type safety, security hardening, and performance optimizations. The tool manages case workspaces, downloads attachments in parallel, searches employee directories, and integrates with Red Hat's support ecosystem through robust, well-tested interfaces.

## Core Value

Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality.

## Requirements

### Validated

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

No active requirements. Ready for next milestone definition via `/gsd:new-milestone`.

### Out of Scope

- Container orchestration features — deferred to future milestone (separate feature initiative)
- YAML configuration file support — deferred to future milestone (TOML config sufficient for current needs)
- Real-time notifications — not needed for CLI use case
- GUI or web interface — CLI-focused tool by design
- Plugin system — security risks; version compatibility nightmares; CLI tools should have focused scope
- Web-based interface — if web UI needed, make it separate project
- Database storage — file-based storage is simpler and sufficient

## Context

**Current State (v1.0 shipped 2026-01-22):**
- Python 3.11+ CLI tool for Red Hat support case management
- 2,590 lines of production Python code
- 100+ tests with 80%+ coverage on critical modules
- Layered architecture: CLI → Commands → Controller/Integrations → Utilities
- External dependencies: Red Hat Support API, Red Hat SSO, Red Hat LDAP
- Tech stack: pytest, requests, rich, tqdm, tenacity, backoff, platformdirs, types-requests
- Configuration: TOML-based (~/.config/mc/config.toml) with cross-platform support
- Type-safe: mypy strict mode passing with 98% type coverage

**Key Features:**
- Parallel downloads (8 concurrent threads) with rich progress bars
- Case metadata caching (30-minute TTL) reducing API calls
- Structured logging with sensitive data redaction
- Comprehensive error handling with retry logic
- Security hardening (SSL verification, token caching, input validation)
- Modern Python 3.11+ syntax with full type hints

**Known Technical Debt:**
- 2 cosmetic type annotation gaps in config module (ConfigManager.__init__ missing -> None, Dict[] vs dict[] syntax)
- 20 test failures from Path vs string type changes (tests need modernization)

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
*Last updated: 2026-01-22 after v1.0 milestone*
