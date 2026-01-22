# Roadmap: MC CLI Hardening Project

## Overview

Transform the MC CLI from a working prototype into a production-ready tool by systematically addressing technical debt, bugs, security issues, and performance problems. The journey follows a dependency-driven approach: establish test infrastructure first (foundation for all other work), then tackle configuration and error handling (unblock testing and improve UX), followed by logging and performance optimizations (build on solid foundation). Each phase delivers a coherent, verifiable capability while maintaining backward compatibility.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Test Foundation** - Set up pytest framework and infrastructure
- [x] **Phase 2: Critical Path Testing** - Test core components with safety net
- [x] **Phase 3: Code Cleanup** - Fix tech debt and bugs under test coverage
- [x] **Phase 4: Security Hardening** - Production-ready security measures
- [x] **Phase 5: Error Handling & Robustness** - Graceful failures and resilience
- [ ] **Phase 6: Infrastructure & Observability** - Structured logging and recovery
- [ ] **Phase 7: Performance Optimization** - Speed improvements and caching
- [ ] **Phase 8: Type Safety & Modernization** - Future-proof with Python 3.10+ and type hints

## Phase Details

### Phase 1: Test Foundation
**Goal**: Developers can run unit tests and integration tests with proper mocking
**Depends on**: Nothing (first phase)
**Requirements**: TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. pytest runs successfully with configured settings
  2. Test fixtures provide reusable mocks for API responses and test data
  3. Coverage reporting works and shows baseline coverage metrics
  4. CI integration is possible (pytest exits with proper codes)
**Plans**: 1 plan

Plans:
- [x] 01-01-PLAN.md — Configure pytest framework with dependencies, create hierarchical fixtures, verify infrastructure

### Phase 2: Critical Path Testing
**Goal**: Core modules have test coverage protecting against regression
**Depends on**: Phase 1
**Requirements**: TEST-04, TEST-05, TEST-06, TEST-07, TEST-08
**Success Criteria** (what must be TRUE):
  1. Auth module has unit tests covering token retrieval and caching
  2. RedHatAPIClient has unit tests with mocked HTTP responses
  3. WorkspaceManager has unit tests for workspace lifecycle operations
  4. Utility functions (formatters, file_ops) have comprehensive test coverage
  5. LDAP integration can be tested without hitting real LDAP server
  6. Coverage reaches at least 60% for tested modules
**Plans**: 3 plans

Plans:
- [x] 02-01-PLAN.md — Auth and API client tests with HTTP mocking (responses library)
- [x] 02-02-PLAN.md — Workspace and utilities tests with filesystem testing (tmp_path)
- [x] 02-03-PLAN.md — LDAP tests with subprocess mocking and Docker integration

### Phase 3: Code Cleanup
**Goal**: Codebase is clean, consistent, and free of obvious bugs
**Depends on**: Phase 2
**Requirements**: DEBT-01, DEBT-02, DEBT-03, DEBT-04, DEBT-05, BUG-01, BUG-02
**Success Criteria** (what must be TRUE):
  1. Base directory is configurable via MC_BASE_DIR environment variable with sensible default
  2. No duplicate environment variable validation exists
  3. Version is managed from single source of truth (pyproject.toml)
  4. setup.py removed, pyproject.toml is sole packaging configuration
  5. All typos fixed (CLI flags, status classes, help text)
  6. All tests still pass after cleanup
**Plans**: 3 plans

Plans:
- [ ] 03-01-PLAN.md — Config migration to TOML with env var detection and wizard
- [ ] 03-02-PLAN.md — Version consolidation and setup.py removal
- [ ] 03-03-PLAN.md — Typo fixes and test updates

### Phase 4: Security Hardening
**Goal**: Tool follows security best practices for production use
**Depends on**: Phase 3
**Requirements**: SEC-01, SEC-02, SEC-03, SEC-04
**Success Criteria** (what must be TRUE):
  1. Access tokens are validated for expiration and cached appropriately
  2. All HTTP requests explicitly verify SSL certificates
  3. Case number input is validated (8 digits) before making API calls
  4. Large file downloads (>3GB) show warning but don't block workflow
  5. Security linting (bandit) passes with no critical issues
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Token caching with expiration validation and case number input validation
- [x] 04-02-PLAN.md — SSL verification and large file download safety checks
- [x] 04-03-PLAN.md — Bandit security linting configuration and scan

### Phase 5: Error Handling & Robustness
**Goal**: Tool fails gracefully with helpful error messages
**Depends on**: Phase 4
**Requirements**: QUAL-01, QUAL-02, QUAL-03, QUAL-04, QUAL-05
**Success Criteria** (what must be TRUE):
  1. Workspace path construction errors provide clear, actionable messages
  2. LDAP parsing handles malformed responses without crashing
  3. File existence checks use pathlib and provide helpful error messages
  4. HTTP errors (401, 403, 404, 500) display user-friendly messages explaining what went wrong
  5. Transient API failures automatically retry with exponential backoff
  6. Tool exits with specific error codes for different failure types
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — Exception hierarchy and error formatting infrastructure
- [x] 05-02-PLAN.md — HTTP retry logic and enhanced error handling
- [x] 05-03-PLAN.md — Pathlib migration and LDAP robustness

### Phase 6: Infrastructure & Observability
**Goal**: Operations are observable and recoverable
**Depends on**: Phase 5
**Requirements**: INFRA-01, INFRA-02, INFRA-03
**Success Criteria** (what must be TRUE):
  1. All print() statements replaced with structured logging
  2. Debug mode (--debug flag) shows detailed operation logs
  3. Attachment downloads automatically retry on failure with error recovery
  4. Large file downloads show progress indicators with ETA
  5. Log output includes timestamps, levels, and module names
  6. Sensitive data (tokens, credentials) never appears in logs
**Plans**: 3 plans

Plans:
- [ ] 06-01-PLAN.md — Logging infrastructure with dual-mode formatters and sensitive data redaction
- [ ] 06-02-PLAN.md — Print statement migration to structured logging (74 print() statements across 8 files)
- [ ] 06-03-PLAN.md — Progress bars and retry logic for downloads with resumable support

### Phase 7: Performance Optimization
**Goal**: Tool is fast and efficient for typical workflows
**Depends on**: Phase 6
**Requirements**: PERF-01, PERF-02, PERF-03
**Success Criteria** (what must be TRUE):
  1. Multiple attachments download in parallel (8 concurrent threads)
  2. Case metadata is cached with TTL to avoid redundant API calls
  3. Access tokens are cached and reused until expiration
  4. Parallel downloads show aggregated progress and handle errors gracefully
  5. Cache invalidation works correctly (respects TTL, handles manual refresh)
**Plans**: 3 plans

Plans:
- [ ] 07-01-PLAN.md — Case metadata caching with 30-minute TTL and age indicators
- [ ] 07-02-PLAN.md — Parallel downloads with ThreadPoolExecutor and Rich progress tracking
- [ ] 07-03-PLAN.md — Enhanced retry with backoff, resumable downloads, and Ctrl+C cleanup

### Phase 8: Type Safety & Modernization
**Goal**: Codebase is future-proof with modern Python standards
**Depends on**: Phase 7
**Requirements**: DEP-01, DEP-02, DEP-03
**Success Criteria** (what must be TRUE):
  1. Minimum Python version is 3.11+ (updated in pyproject.toml)
  2. All modules have type hints for function signatures and return types
  3. mypy strict mode runs without errors (or with documented exceptions)
  4. Type checking is integrated into development workflow
  5. Type hints improve IDE autocomplete and catch bugs at development time
**Plans**: 1 plan

Plans:
- [ ] 08-01-PLAN.md — Python 3.11+ upgrade, comprehensive type hints, mypy strict mode, modern syntax

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Test Foundation | 1/1 | Complete | 2026-01-20 |
| 2. Critical Path Testing | 3/3 | Complete | 2026-01-22 |
| 3. Code Cleanup | 3/3 | Complete | 2026-01-22 |
| 4. Security Hardening | 3/3 | Complete | 2026-01-22 |
| 5. Error Handling & Robustness | 3/3 | Complete | 2026-01-22 |
| 6. Infrastructure & Observability | 0/1 | Planned | - |
| 7. Performance Optimization | 0/1 | Planned | - |
| 8. Type Safety & Modernization | 0/1 | Planned | - |

---
*Roadmap created: 2026-01-20*
*Last updated: 2026-01-22 — Phase 8 planned*
