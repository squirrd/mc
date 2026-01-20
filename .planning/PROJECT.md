# MC CLI Hardening Project

## What This Is

A systematic cleanup and hardening initiative for the `mc` CLI tool. This project addresses all technical debt, bugs, security issues, and performance problems documented in CONCERNS.md to make the codebase production-ready and maintainable before adding new features.

## Core Value

Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality.

## Requirements

### Validated

These capabilities already exist in the codebase:

- ✓ Case workspace management (create, check, navigate workspaces) — existing
- ✓ Red Hat API integration (fetch case details, account info, attachments) — existing
- ✓ Attachment downloads with streaming — existing
- ✓ LDAP employee directory search — existing
- ✓ Salesforce case URL generation and browser launching — existing
- ✓ OAuth token management (offline token to access token) — existing
- ✓ Workspace file structure generation based on case data — existing

### Active

Phase 1-2: Test Infrastructure and Critical Path Coverage
- [ ] **TEST-01**: pytest framework configured and working
- [ ] **TEST-02**: pytest-mock installed for API/external service mocking
- [ ] **TEST-03**: Test fixtures infrastructure set up
- [ ] **TEST-04**: Unit tests for auth module (get_access_token)
- [ ] **TEST-05**: Unit tests for RedHatAPIClient with mocked requests
- [ ] **TEST-06**: Unit tests for WorkspaceManager
- [ ] **TEST-07**: Unit tests for formatters and file_ops utilities
- [ ] **TEST-08**: Mock LDAP responses for integration testing

Phase 3: Tech Debt Resolution
- [ ] **DEBT-01**: Fix hardcoded base directory (use MC_BASE_DIR env var with default)
- [ ] **DEBT-02**: Remove duplicate RH_API_OFFLINE_TOKEN validation
- [ ] **DEBT-03**: Consolidate version management (single source of truth)
- [ ] **DEBT-04**: Migrate fully to pyproject.toml (remove setup.py)
- [ ] **DEBT-05**: Fix typo "dowloading attachemnts" → "downloading attachments"

Phase 4: Bug Fixes
- [ ] **BUG-01**: Fix LDAP --All flag (change to --all lowercase)
- [ ] **BUG-02**: Fix CheckStaus → CheckStatus typo throughout

Phase 5: Security Hardening
- [ ] **SEC-01**: Add access token expiration validation and caching
- [ ] **SEC-02**: Explicitly set verify=True in all requests calls
- [ ] **SEC-03**: Add case number format validation (8 digits)
- [ ] **SEC-04**: Add file size warning for downloads >3GB (no prompting)

Phase 6: Performance Improvements
- [ ] **PERF-01**: Implement parallel attachment downloads (4+ threads with ThreadPoolExecutor)
- [ ] **PERF-02**: Add file-based caching for case metadata with TTL
- [ ] **PERF-03**: Cache access tokens with expiration tracking

Phase 7: Code Quality and Robustness
- [ ] **QUAL-01**: Improve workspace path construction error handling
- [ ] **QUAL-02**: Add robust LDAP parsing with error handling for malformed responses
- [ ] **QUAL-03**: Improve file existence checks (better error messages, pathlib)
- [ ] **QUAL-04**: Add HTTP error handling with meaningful messages (401, 403, 404, 500)
- [ ] **QUAL-05**: Add retry logic for transient API failures

Phase 8: Infrastructure Features
- [ ] **INFRA-01**: Implement structured logging framework (replace print statements)
- [ ] **INFRA-02**: Add error recovery and retry for attachment downloads
- [ ] **INFRA-03**: Add download progress indication for large files

Phase 9: Dependency Updates and Type Safety
- [ ] **DEP-01**: Update minimum Python version to 3.10+
- [ ] **DEP-02**: Add type hints to all modules
- [ ] **DEP-03**: Configure mypy strict mode and resolve issues

### Out of Scope

- Container orchestration features — deferred to future project (separate feature initiative)
- YAML configuration file support — deferred to future project (separate feature initiative)
- Real-time notifications — not needed for CLI use case
- GUI or web interface — CLI-focused tool

## Context

**Existing Codebase:**
- Python 3.8+ CLI tool for Red Hat support case management
- Layered architecture: CLI → Commands → Controller/Integrations → Utilities
- External dependencies: Red Hat Support API, Red Hat SSO, Red Hat LDAP
- Current testing: Bash-based integration tests only (no unit tests)
- ~1,342 lines across 7 codebase analysis documents

**Technical Environment:**
- Python 3.13.7 tested, 3.8+ supported
- pytest, black, flake8, mypy configured but not actively used
- requests library for HTTP (considering httpx for async future)

**Known Issues:**
- No unit test coverage
- All tests hit live APIs (no mocking)
- Several hardcoded values (base directory, URLs)
- Performance issues (sequential downloads, token refresh every run)
- Missing logging infrastructure
- Fragile parsing (LDAP output, workspace paths)

**User Workflow:**
User manages Red Hat support cases, needs workspace creation, attachment downloads, and employee lookups. Tool currently works but is brittle and hard to maintain/extend.

## Constraints

- **Backward Compatibility**: All existing commands must continue to work exactly as before
- **API Dependencies**: Must maintain integration with Red Hat Support API, SSO, and LDAP
- **Python Version**: Currently 3.8+ but noted as EOL concern (will update to 3.10+)
- **No Breaking Changes**: Users rely on current command structure and output

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Test infrastructure before fixes | TDD approach - establish testing foundation first so all fixes can be verified | — Pending |
| Split testing into 2 phases | Phase 1 sets up framework, Phase 2 writes critical path tests - allows faster initial progress | — Pending |
| Critical path testing only | Test auth, API client, workspace manager first - most fragile and important modules | — Pending |
| Defer containers and YAML configs | These are new features, not cleanup - separate future project | — Pending |
| Parallel downloads without prompts | User expects large files, just warn at 3GB+ but don't block workflow | — Pending |
| Infrastructure features in scope | Logging and error recovery are critical for production readiness, not "nice to have" | — Pending |

---
*Last updated: 2026-01-20 after initialization*
