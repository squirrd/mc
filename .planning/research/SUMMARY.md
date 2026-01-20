# Project Research Summary

**Project:** MC CLI Tool Hardening
**Domain:** Python CLI Tool Production Infrastructure
**Researched:** 2026-01-20
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project focuses on hardening an existing Python 3.8+ CLI tool for production use. The MC CLI already has working core functionality (case management, API integration, file operations) but lacks critical production infrastructure: comprehensive test coverage, structured logging, robust error handling, and performance optimization. The recommended approach is to build test infrastructure first before any refactoring, then systematically add production-ready features under test coverage.

The core technology stack is well-established: pytest 8.0+ with ecosystem plugins (pytest-cov, pytest-mock, pytest-xdist), ruff for unified linting/formatting (replacing black+flake8), and stdlib logging with optional rich CLI enhancements. The architecture should follow a test pyramid (70% unit, 25% integration, 5% E2E) with clear mock boundaries at external service interfaces. The most critical risk is the "refactoring before test coverage" trap - teams often try to clean up code before writing tests, leading to undetected breakage.

The recommended roadmap prioritizes test infrastructure and configuration management first (unlock testing), followed by error handling and validation (improve UX immediately), then logging infrastructure (enable observability), and finally performance optimizations (parallel downloads, intelligent caching). This ordering respects dependencies: you can't safely add features without tests, can't implement retry logic without error classification, and can't cache effectively without proper configuration management.

## Key Findings

### Recommended Stack

The hardening stack builds on existing tools (pytest, mypy, black, flake8) by upgrading versions and adding essential testing infrastructure. The modern Python CLI ecosystem (as of 2025) has converged on unified tooling: ruff replaces three separate tools (black, flake8, isort), responses library provides clean HTTP mocking, and stdlib logging is sufficient for CLI tools without third-party frameworks.

**Core technologies:**
- **pytest 8.0+**: Industry standard test framework — rich plugin ecosystem, excellent CLI output, built-in fixtures
- **pytest-cov 5.0+**: Coverage reporting — integrates coverage.py with pytest, shows untested code
- **pytest-mock 3.14+**: Mocking utilities — provides mocker fixture wrapping unittest.mock
- **responses 0.25+**: HTTP request mocking — declarative API response mocking for requests library
- **ruff 0.6+**: Fast unified linter/formatter — replaces black+flake8+isort, 10-100x faster
- **mypy 1.10+**: Static type checker — progressive typing with stricter settings enabled per-module
- **stdlib logging**: Structured logging — no third-party needed, use basicConfig() for CLI tools
- **bandit 1.7+**: Security linter — detects hardcoded passwords, insecure requests
- **safety 3.0+**: Dependency scanner — checks dependencies against CVE database

**Critical version requirements:**
- Python 3.8+ support maintained (many enterprises lag on upgrades)
- pydantic 2.0+ requires breaking changes from 1.x (migration guide available)
- pytest-xdist requires pytest 7.0+ (already satisfied)

### Expected Features

Production-ready CLI tools have three feature categories: table stakes (users expect these), differentiators (competitive advantage), and anti-features (commonly requested but problematic). The MC CLI has core functionality but lacks critical infrastructure features.

**Must have (table stakes):**
- **Structured Logging** — users need visibility into operations, especially failures (replace print() with logging)
- **Comprehensive Error Handling** — graceful failures with actionable messages for HTTP errors, network timeouts, validation failures
- **Retry Logic** — network operations fail transiently, users expect automatic recovery with exponential backoff
- **Configuration Management** — flexibility beyond hardcoded values via environment variables and config files
- **Input Validation** — prevent bad input early with clear feedback (case number format, path validation)
- **Test Infrastructure** — production tools must be testable with pytest framework, mocking, fixtures, CI integration
- **Proper Exit Codes** — scripting/automation depends on exit codes (0=success, specific codes for failure types)

**Should have (competitive advantage):**
- **Intelligent Caching** — cache case metadata, access tokens, LDAP lookups with TTL expiration
- **Parallel Operations** — parallel attachment downloads using ThreadPoolExecutor
- **Progress Indicators** — download progress bars, spinner for API calls, ETA for large files
- **Debug Mode** — --debug flag enables verbose logging, shows API requests/responses
- **Dry-Run Mode** — --dry-run shows what would happen without side effects
- **Output Formatting** — JSON output for scripting, table output for humans, quiet mode

**Defer to v2+ (not essential for production readiness):**
- **Shell Completion** — tab completion requires platform-specific scripts, high maintenance burden
- **Self-Update Mechanism** — adds complexity, not critical for internal tool
- **Workspace Recovery** — already have --fix flag, full recovery is complex
- **Performance Monitoring** — operation timing and cache hit rates can wait until after correctness

**Anti-features to avoid:**
- GUI/TUI interface (defeats CLI purpose, massive complexity)
- Plugin system (security risks, version compatibility nightmares)
- Real-time notifications (requires background daemon, polling overhead)
- Interactive prompts for everything (breaks scripting/automation)
- Custom DSL or config language (learning curve, use standard YAML/TOML/JSON)

### Architecture Approach

Testing architecture mirrors application structure with clear separation between test types. The test pyramid approach (many fast unit tests, fewer integration tests, minimal E2E tests) ensures fast feedback and isolated failures. Mock boundaries are established at external service interfaces (HTTP, subprocess, filesystem) rather than internal business logic.

**Major components:**
1. **Test Infrastructure Foundation** — conftest.py for shared fixtures, fixtures/ for test data, helpers/ for utilities
2. **Unit Tests** — mirror src/ structure (src/mc/controller/workspace.py → tests/unit/controller/test_workspace.py), test single functions in isolation with mocked dependencies
3. **Integration Tests** — test component interactions without external services, use real objects with mocked APIs via responses library or VCR.py
4. **E2E Tests** — complete workflows through CLI using bash scripts or subprocess calls
5. **Mock Strategy** — mock at boundaries (requests library, subprocess.run) not business logic; use dependency injection for testability

**Key architectural patterns:**
- **Dependency Injection** — pass API clients as parameters instead of creating internally (enables test mocking)
- **Fixture-Based Setup** — pytest fixtures provide pre-configured mocks and test data (DRY principle)
- **Response Mocking** — use responses library for HTTP mocking at requests level (tests real HTTP logic)
- **Progressive Type Safety** — enable mypy per-module as tests are added, not globally at start

**Test distribution target:**
- Unit Tests: 70% (fast, isolated, test single functions)
- Integration Tests: 25% (medium speed, test component interactions)
- E2E Tests: 5% (slow, test complete user workflows)

### Critical Pitfalls

The most dangerous pitfalls for retrofitting tests onto existing code, with prevention strategies:

1. **Refactoring Before Test Coverage** — teams see untestable code and refactor for testability before writing tests, leading to undetected breakage. **Prevention:** Write characterization tests first (capture current behavior), test ugly code with mocks/patches, refactor only under test coverage, never refactor and add tests in same commit.

2. **Mocking Too Much** — every dependency gets mocked, tests pass but don't validate actual behavior. **Prevention:** Use real file systems (tmp_path fixture), integration tests for APIs (VCR.py), mock at boundaries not business logic, reserve unit tests for pure logic, accept that CLI integration tests take 5-10 seconds.

3. **Hardcoded Dependencies Block Testing** — hardcoded paths, URLs, credentials prevent tests from running in CI. **Prevention:** Dependency injection for paths (already done in codebase!), config object pattern, pytest.MonkeyPatch for env vars, XDG Base Directory support, graceful degradation with sane defaults.

4. **External API Dependencies Untested** — code calling Red Hat API and LDAP never tested because "can't mock production". **Prevention:** HTTP recording with VCR.py (record real responses once, replay in tests), contract testing for request/response shapes, separate integration tests marked with pytest.mark.integration, test error paths (timeouts, 500 errors, rate limits).

5. **Test Isolation Failures** — tests pass individually but fail in suite due to shared state (environment variables, config files). **Prevention:** Use monkeypatching instead of modifying os.environ directly, tmp_path fixture for temp files, fixture teardown with yield, avoid module-level state, test in random order with pytest-randomly.

## Implications for Roadmap

Based on research, the roadmap should follow a dependency-driven approach: build test infrastructure first (foundation for all other work), then tackle configuration and error handling (unblock testing and improve UX), followed by logging and performance optimizations (build on solid foundation). This ordering avoids the critical pitfall of refactoring before having test coverage.

### Phase 1: Test Infrastructure Foundation

**Rationale:** Everything depends on having tests. Can't safely refactor, add features, or optimize without test coverage to catch breakage. High complexity means tackling early while team is fresh.

**Delivers:**
- pytest configuration (pyproject.toml with strict markers, coverage requirements)
- Shared fixtures (conftest.py, api_responses.py, mock_helpers.py)
- Utility test suite (formatters, file operations, authentication)
- Test pyramid established (70/25/5 split enforced in CI)

**Addresses:**
- Test Infrastructure (table stakes feature)
- Test isolation setup prevents Pitfall #6

**Avoids:**
- Pitfall #1 (refactoring before tests) by establishing "characterization tests first" workflow
- Pitfall #6 (test isolation failures) by setting up proper fixtures from start

**Research needs:** Standard patterns, skip deep research

### Phase 2: Core Component Testing

**Rationale:** With test foundation in place, test existing components to establish safety net before any changes. Focus on integration layer (API, LDAP) and controller (workspace management).

**Delivers:**
- Integration tests with VCR.py for Red Hat API
- LDAP mocking with subprocess.run patches
- Workspace lifecycle tests with tmp_path
- CLI argument parsing and routing tests
- 60% code coverage target

**Uses:** pytest-mock, responses, VCR.py from stack

**Implements:** Mock boundaries at external services (HTTP, subprocess, filesystem)

**Addresses:**
- Integration testing patterns from architecture
- Input Validation (table stakes feature)

**Avoids:**
- Pitfall #2 (mocking too much) by using VCR.py for real API responses
- Pitfall #4 (API untested) by recording real HTTP interactions
- Pitfall #5 (CLI untested) by testing argument parsing directly

**Research needs:** VCR.py integration patterns may need research-phase investigation

### Phase 3: Configuration Management

**Rationale:** Low complexity, high impact. Unblocks hardcoded values (current blocker: base directory). Foundation for features that need tuning (caching, retry logic, parallel operations).

**Delivers:**
- Config object with environment variable precedence
- XDG Base Directory support for config files
- Graceful degradation with sane defaults
- Test fixtures for config override

**Uses:** stdlib only (no third-party config library needed)

**Addresses:**
- Configuration Management (table stakes feature)
- Hardcoded dependencies resolved

**Avoids:**
- Pitfall #3 (hardcoded dependencies block testing) by making everything configurable

**Research needs:** Standard patterns, skip deep research

### Phase 4: Error Handling & Validation

**Rationale:** Improves user experience immediately (graceful failures vs crashes). Foundation for retry logic (can't retry without error classification). Medium complexity but high user value.

**Delivers:**
- Custom exception hierarchy (MCError, APIError, AuthenticationError, ValidationError)
- HTTP error handling (401, 403, 404, 500+) with user-friendly messages
- Network timeout handling
- Input validation (case number format, path validation)
- Specific exit codes per error type

**Addresses:**
- Comprehensive Error Handling (table stakes feature)
- Input Validation (table stakes feature)
- Exit Codes (table stakes feature)

**Avoids:**
- User-facing errors improved (currently crashes on common failures)

**Research needs:** Standard patterns, skip deep research

### Phase 5: Retry Logic

**Rationale:** Depends on error handling (Phase 4) to classify transient vs permanent failures. High user value (automatic recovery from network blips). Medium complexity with exponential backoff.

**Delivers:**
- Exponential backoff for API calls
- Configurable retry limits (from Phase 3 config)
- Transient vs permanent error classification
- Retry logging (builds on Phase 6 logging)

**Uses:** tenacity library for retry decorators (or custom implementation)

**Addresses:**
- Retry Logic (table stakes feature)

**Avoids:**
- Users manually retrying failed operations

**Research needs:** Tenacity vs alternatives may need quick research

### Phase 6: Performance Optimization

**Rationale:** Depends on error handling (parallel operations need error aggregation) and configuration (tuning parameters). High user value (dramatic speedup). Medium complexity.

**Delivers:**
- Intelligent caching (case metadata, access tokens, LDAP lookups with TTL)
- Parallel attachment downloads (ThreadPoolExecutor)
- Cache invalidation strategies
- Configurable concurrency limits

**Uses:** stdlib threading, cache configuration from Phase 3

**Addresses:**
- Intelligent Caching (differentiator feature)
- Parallel Operations (differentiator feature)

**Avoids:**
- Sequential downloads bottleneck

**Research needs:** Caching patterns and concurrency error handling may need research-phase

### Phase 7: Structured Logging

**Rationale:** Foundation for debug mode and observability. Systematic replacement of print() across codebase. Medium effort but improves error handling (Phase 4) and retry logic (Phase 5) retroactively.

**Delivers:**
- Module-level loggers (logging.getLogger(__name__))
- Console handler (INFO+) and optional file handler (DEBUG+)
- Structured log format (timestamp, level, module, message)
- Verbosity flag (--verbose for DEBUG level)
- Log sanitization (no sensitive data in logs)

**Uses:** stdlib logging (no third-party framework)

**Addresses:**
- Structured Logging (table stakes feature)
- Foundation for Debug Mode (differentiator)

**Avoids:**
- Pitfall #8 (security mistake: logging sensitive data)

**Research needs:** Standard patterns, skip deep research

### Phase 8: UX Enhancements

**Rationale:** Polish features that depend on logging infrastructure (Phase 7). Low complexity, nice improvements to professional feel.

**Delivers:**
- Progress indicators (download progress bars, API spinners)
- Debug mode (--debug flag with verbose logging)
- Dry-run mode (--dry-run preview without side effects)
- Output formatting (--json for scripting, --quiet mode)

**Uses:** rich library for progress bars (optional), logging from Phase 7

**Addresses:**
- Progress Indicators (table stakes feature)
- Debug Mode (differentiator feature)
- Dry-Run Mode (differentiator feature)
- Output Formatting (differentiator feature)

**Research needs:** Rich library integration may need quick investigation

### Phase Ordering Rationale

**Dependency chain:**
1. **Test Infrastructure First** (Phase 1) → Everything depends on this, can't safely work without tests
2. **Component Testing** (Phase 2) → Establishes safety net before making changes
3. **Configuration** (Phase 3) → Low complexity, unblocks hardcoded values, needed by later phases
4. **Error Handling** (Phase 4) → Foundation for retry logic, improves UX immediately
5. **Retry Logic** (Phase 5) → Depends on error classification from Phase 4
6. **Performance** (Phase 6) → Depends on config (Phase 3) and error handling (Phase 4) for parallel error aggregation
7. **Logging** (Phase 7) → Enhances earlier phases retroactively, foundation for debug mode
8. **UX Polish** (Phase 8) → Depends on logging infrastructure from Phase 7

**Grouping rationale:**
- Phases 1-2: Foundation (testing infrastructure and coverage)
- Phases 3-5: Robustness (configuration, error handling, retry)
- Phases 6: Performance (caching, parallelization)
- Phases 7-8: Observability and UX (logging, debug mode, progress indicators)

**Pitfall avoidance:**
- Phase 1 first prevents Pitfall #1 (refactoring before tests)
- Phase 2 with VCR.py prevents Pitfall #2 (over-mocking) and Pitfall #4 (API untested)
- Phase 3 prevents Pitfall #3 (hardcoded dependencies)
- Testing in random order prevents Pitfall #6 (isolation failures)
- PR discipline across all phases prevents Pitfall #7 (scope creep)

### Research Flags

**Phases likely needing deeper research during planning:**
- **Phase 2 (Core Component Testing):** VCR.py integration patterns for Red Hat API — complex API with authentication, need to verify cassette recording workflow
- **Phase 5 (Retry Logic):** Tenacity library vs alternatives — verify tenacity is still recommended, check for breaking changes
- **Phase 6 (Performance Optimization):** Caching invalidation strategies and parallel error aggregation — concurrency patterns need validation

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Test Infrastructure):** pytest configuration is well-documented
- **Phase 3 (Configuration Management):** stdlib env vars and config files are standard
- **Phase 4 (Error Handling):** Custom exceptions and HTTP error handling are standard Python patterns
- **Phase 7 (Structured Logging):** stdlib logging is official Python documentation
- **Phase 8 (UX Enhancements):** CLI flags and output formatting are well-established patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | pytest ecosystem is stable and well-documented; ruff is newer (2023+) but rapidly becoming standard; stdlib logging verified with official Python 3.14 docs |
| Features | MEDIUM | Based on analysis of industry-standard CLI tools (AWS CLI, GitHub CLI, pip, npm) and Python CLI ecosystem patterns; table stakes are well-established, differentiators are pattern-based not user research |
| Architecture | HIGH | Test pyramid and fixture patterns are industry standard; mock boundaries and dependency injection are proven patterns from official pytest documentation |
| Pitfalls | HIGH | Patterns validated from official Python testing documentation and established best practices; refactoring-before-tests trap is well-documented in brownfield codebases |

**Overall confidence:** MEDIUM-HIGH

The stack recommendations are highly confident (official documentation and stable tools), architecture patterns are proven (industry standard test pyramid), and pitfalls are well-documented. Medium confidence on specific version numbers (should verify against PyPI) and feature prioritization (based on pattern analysis not user research). Low confidence areas are timing estimates and specific library adoption timelines (ruff, pydantic 2.0).

### Gaps to Address

**Version number verification:**
- Stack recommendations specify versions (pytest 8.0+, mypy 1.10+, ruff 0.6+) based on training data (January 2025). Verify all version numbers against current PyPI releases before finalizing dependency specifications.
- **How to handle:** Quick PyPI check during Phase 1 setup, update versions if newer releases available

**Caching library choice:**
- Research suggests intelligent caching but doesn't specify library (requests-cache, cachetools, custom implementation). Need to validate approach against current best practices.
- **How to handle:** Phase 6 may need research-phase investigation for caching patterns

**Retry library validation:**
- Recommendation uses tenacity library but notes "or custom implementation". Should verify tenacity is still recommended and check for breaking changes.
- **How to handle:** Quick verification during Phase 5 planning, potentially research-phase if alternatives needed

**VCR.py integration:**
- VCR.py recommended for API testing but integration pattern with Red Hat API (authentication, headers) not verified.
- **How to handle:** Phase 2 may need research-phase for VCR.py cassette recording workflow

**Coverage targets:**
- Suggested 60% → 75% → 85% progression but no validation that these thresholds are achievable for this codebase.
- **How to handle:** Treat as guidance not hard requirements, adjust based on actual progress

## Sources

### Primary (HIGH confidence)
- Python logging documentation (https://docs.python.org/3/library/logging.html) — Verified 2026-01-20, Python 3.14 docs, stdlib logging patterns
- pytest documentation (https://docs.pytest.org/) — Test framework patterns, fixture usage, mock strategies
- Python unittest documentation (https://docs.python.org/3/library/unittest.html) — Official testing guidance

### Secondary (MEDIUM confidence)
- Training data knowledge of pytest ecosystem (pytest, pytest-cov, pytest-mock, pytest-xdist) — Widely adopted tools as of January 2025
- Analysis of production CLI tools (AWS CLI, GitHub CLI, Heroku CLI, pip, npm) — Established patterns for logging, error handling, configuration
- mypy type checking best practices — Progressive typing patterns
- responses/VCR.py for HTTP mocking — Industry standard Python libraries
- bandit/safety for security scanning — Standard security tools
- Direct code inspection of /Users/dsquirre/Repos/mc/ — Current state analysis from PROJECT.md, pyproject.toml, source files

### Tertiary (LOW confidence)
- Specific version numbers (pytest 8.0, mypy 1.10, ruff 0.6, etc.) — Based on training data, should verify against PyPI
- ruff adoption timeline as black+flake8 replacement — Tool emerged ~2023, rapidly growing but relatively new
- pydantic 2.0 adoption and migration timeline — Breaking changes from 1.x, migration guide exists but adoption timing uncertain
- Effort estimates (2-4 hours, 4-6 hours, 8-12 hours per phase) — Based on typical developer velocity, no historical data for this team

**Recommendation:** Verify version numbers against PyPI before finalizing dependencies. Validate caching and retry library choices during Phase 5-6 planning. Consider research-phase investigation for VCR.py integration in Phase 2.

---
*Research completed: 2026-01-20*
*Ready for roadmap: yes*
