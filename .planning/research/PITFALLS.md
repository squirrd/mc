# Pitfalls Research

**Domain:** Python CLI Tool Hardening and Test Retrofitting
**Researched:** 2026-01-20
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Refactoring Before Test Coverage (The "Rewrite Trap")

**What goes wrong:**
Teams see untestable code and immediately start refactoring for testability before writing any tests. This leads to breaking existing functionality with no way to detect it, since there are no tests to fail. The hardening project becomes a rewrite.

**Why it happens:**
- Existing code has hardcoded dependencies (file paths, environment variables, external APIs)
- Code appears "too coupled" to test as-is
- Team wants "clean" code before investing in tests
- Refactoring feels like progress

**How to avoid:**
1. **Characterization tests first** - Write tests that capture current behavior (warts and all)
2. **Test the ugly code** - Mock file systems, patch environment variables, stub API calls
3. **Refactor under test coverage** - Only refactor after tests exist to catch breakage
4. **One change at a time** - Never refactor and add tests in the same commit

**Warning signs:**
- More than 20% of existing code modified before first test passes
- Pull requests mixing refactoring and test addition
- "We need to fix X before we can test Y" discussions
- Test files created but still at 0% pass rate after multiple days

**Phase to address:**
Phase 1 (Test Infrastructure Setup) - Establish "characterization tests first" as the workflow

---

### Pitfall 2: Mocking Too Much (The "Unit Test Illusion")

**What goes wrong:**
Every external dependency gets mocked, leading to tests that pass but don't validate actual behavior. Tests mock API responses, file system operations, environment variables—everything. When deployed, the tool breaks because mocks don't match reality.

**Why it happens:**
- "Unit tests should be fast" dogma applied too strictly
- Fear of flaky tests from external dependencies
- Copying patterns from library testing (not appropriate for CLI tools)
- Not understanding the difference between unit, integration, and end-to-end tests

**How to avoid:**
1. **Use real file systems** - Create temp directories, don't mock `os.path.exists`
2. **Integration tests for APIs** - Use VCR.py or recorded fixtures for API calls
3. **Mock at boundaries** - Mock HTTP transport, not business logic
4. **Reserve unit tests for pure logic** - Formatters, validators, parsers
5. **Accept slower tests** - CLI integration tests taking 5-10 seconds is normal

**Warning signs:**
- More than 50% of test code is mock setup
- Tests pass but tool fails with identical inputs
- Changing implementation breaks tests without changing behavior
- "Works on my machine" issues in CI/CD

**Phase to address:**
Phase 2 (Core Component Testing) - Establish testing pyramid with clear boundaries

---

### Pitfall 3: Hardcoded Dependencies Block Testing (The "Configuration Hell")

**What goes wrong:**
Code has hardcoded paths (`/Users/dsquirre/Cases`), hardcoded URLs, hardcoded credentials. Tests can't run in CI, can't run on other machines, require specific environment setup. Testing gets abandoned as "too hard."

**Why it happens:**
- Original code written for single-user use
- Configuration abstraction seen as "overengineering"
- Environment variables used but not injectable
- No separation between "where to find config" and "what config to use"

**How to avoid:**
1. **Dependency injection for paths** - Pass `base_dir` as parameter (already done in this codebase!)
2. **Config object pattern** - Create `Config` class that can be overridden in tests
3. **Test fixtures for environments** - Use `pytest.MonkeyPatch` for env vars
4. **XDG Base Directory support** - Follow standard for config file locations
5. **Graceful degradation** - Tool should work without config (with sane defaults)

**Warning signs:**
- Tests require manual environment setup to run
- Tests fail on CI but pass locally
- "Works on my machine" syndrome
- Tests modify global state (env vars, files in home directory)

**Phase to address:**
Phase 1 (Test Infrastructure) - Create test fixtures for config/environment
Phase 3 (Security Hardening) - Remove hardcoded values, implement proper config

---

### Pitfall 4: External API Dependencies Untested (The "Production-Only Validation")

**What goes wrong:**
Code that calls external APIs (Red Hat Support API, LDAP) is never tested because "we can't mock production." API contract changes, error handling is wrong, rate limiting breaks—all discovered in production.

**Why it happens:**
- Fear of hitting production APIs from tests
- No test/sandbox environment available
- Belief that API testing requires real credentials
- Not knowing about VCR.py, betamax, or HTTP recording libraries

**How to avoid:**
1. **HTTP recording (VCR.py)** - Record real API responses, replay in tests
2. **Contract testing** - Validate request/response shapes, not just mocking
3. **Separate integration tests** - Mark with `@pytest.mark.integration`, run separately
4. **Stubbed API client** - Create test double for `RedHatAPIClient` with realistic responses
5. **Test error paths** - Mock HTTP errors, rate limits, timeouts

**Warning signs:**
- Zero tests for code in `integrations/` directory
- Exception handling code never executed in tests
- API rate limiting discovered in production
- Changes to API client require manual testing

**Phase to address:**
Phase 2 (Core Component Testing) - Implement VCR.py for API tests
Phase 4 (Integration Testing) - End-to-end tests with recorded fixtures

---

### Pitfall 5: CLI Argument Parsing Untested (The "Help Text Works, Tool Doesn't")

**What goes wrong:**
Argument parsing is tested manually ("the help text shows up!") but actual command routing, validation, and error messages are untested. Users get confusing errors, commands silently do the wrong thing, validation is inconsistent.

**Why it happens:**
- argparse is "simple" so testing seems unnecessary
- Confusion about testing argparse vs. testing command logic
- No clear pattern for testing CLI entry points
- Fear of subprocess complexity

**How to avoid:**
1. **Test parse, not subprocess** - Call parser directly, don't invoke CLI as subprocess
2. **Test routing logic** - Verify `args.command` routes to correct function
3. **Test validation** - Invalid inputs should fail parsing, not crash later
4. **Test error messages** - Assert on actual error text users will see
5. **Test defaults** - Verify flag defaults work correctly

**Warning signs:**
- Zero tests in `cli/` directory
- Argument validation done in command functions (not parser)
- No tests for error messages
- Breaking changes to CLI discovered by users

**Phase to address:**
Phase 2 (Core Component Testing) - Test all CLI commands and routing

---

### Pitfall 6: Test Isolation Failures (The "Order-Dependent Flake")

**What goes wrong:**
Tests pass when run individually but fail when run in suite. Tests modify shared state (environment variables, config files, global objects). CI randomly fails because test execution order changes.

**Why it happens:**
- Using `os.environ` directly instead of monkeypatching
- Not cleaning up temp files in teardown
- Shared module-level state
- Not understanding pytest fixture scopes

**How to avoid:**
1. **pytest-env for env vars** - Configure in pytest.ini, don't modify os.environ
2. **tmp_path fixture** - Use pytest's built-in temp directory handling
3. **Fixture teardown** - Use `yield` fixtures with cleanup
4. **No module state** - Avoid global variables, use dependency injection
5. **Test in random order** - Use `pytest-randomly` to catch order dependencies

**Warning signs:**
- "Works when I run it alone" test failures
- Tests fail in CI but pass locally
- Mysterious environment variable changes
- Tests leave files in `/tmp` or home directory

**Phase to address:**
Phase 1 (Test Infrastructure) - Set up pytest fixtures with proper isolation
Phase 2 (Core Component Testing) - Enforce isolation in CI with pytest-randomly

---

### Pitfall 7: Technical Debt "Drive-By Refactoring" (The "Scope Creep Death Spiral")

**What goes wrong:**
While adding tests, developers notice code smells and "fix" them. Each fix reveals another issue. The test-addition PR becomes a massive refactor touching 50 files. PR stalls in review, conflicts accumulate, project timeline explodes.

**Why it happens:**
- "We're already in this code, might as well fix it" thinking
- No clear definition of "done" for test-addition work
- Perfectionism preventing incremental progress
- Not separating "make testable" from "make better"

**How to avoid:**
1. **Two-PR rule** - Test addition is one PR, refactoring is separate PR
2. **Timebox refactoring** - If test requires >100 lines of refactoring, stop and discuss
3. **Mark tech debt** - Add `# TODO: refactor X` comments, don't fix immediately
4. **Test-only PRs** - PR description says "adds tests for X" not "refactors X"
5. **Defer optimization** - Get tests passing first, optimize later under test coverage

**Warning signs:**
- Test PR has >1000 lines changed
- PR description lists 5+ unrelated improvements
- PR open for >2 weeks due to review complexity
- "Just one more thing" commits keep getting added

**Phase to address:**
Phase 1 (Test Infrastructure) - Establish PR size limits and review process
All phases - Maintain "test-only" vs. "refactor" PR discipline

---

### Pitfall 8: Over-Testing Getters/Setters (The "100% Coverage Trap")

**What goes wrong:**
Team writes tests for every line of code, including trivial getters, simple formatters, and obvious logic. Test suite becomes massive, slow, and brittle. Actual bugs aren't caught because focus is on coverage metrics, not behavior.

**Why it happens:**
- "100% coverage" as a goal instead of a byproduct
- Not understanding what coverage actually means
- Testing implementation, not behavior
- Cargo-culting "you should test everything" advice

**How to avoid:**
1. **Test behaviors, not lines** - If it can fail, test it; if it's trivial, skip it
2. **Coverage as diagnostic** - Use to find untested code, not as success metric
3. **Focus on integration** - One integration test > ten unit tests for getters
4. **Mutation testing** - Use `mutmut` to verify tests actually catch bugs
5. **Skip obvious code** - `return self.x` doesn't need a test

**Warning signs:**
- Tests for simple property getters (`def get_x(): return self.x`)
- More test code than implementation code (>3:1 ratio)
- Tests never fail during development (only pass or skip)
- Coverage at 100% but bugs still shipped

**Phase to address:**
Phase 2 (Core Component Testing) - Establish testing philosophy (behavior over coverage)

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip teardown in tests | Tests run faster | State pollution, flaky tests | Never - use fixtures |
| Mock entire API client | Easy test setup | Tests don't validate API contracts | Early prototyping only |
| Hardcode test data in test files | Quick to write | Brittle, hard to maintain | Small, stable datasets only |
| Copy-paste test setup | Faster than fixtures | Inconsistent setup, maintenance nightmare | Never - use fixtures |
| Skip testing error paths | Happy path tests pass | Production errors uncaught | Never for CLI tools (users hit errors) |
| Test implementation details | Easy to write | Refactoring breaks tests | Never - test public API |
| Use production config in tests | "Real world" testing | Tests modify production, credential leaks | Never - always use test config |
| Skip CI test runs to save time | Faster merges | Broken code in main branch | Never - tests must pass in CI |

## Integration Gotchas

Common mistakes when testing components that connect to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Red Hat Support API | Mocking entire response structure | Use VCR.py to record real responses |
| LDAP queries | Not testing at all ("too hard") | Use docker-based test LDAP server or recorded responses |
| File system operations | Mocking `os.path.exists`, `open`, etc. | Use `tmp_path` fixture with real files |
| Environment variables | Modifying `os.environ` directly | Use `monkeypatch.setenv()` or pytest-env |
| HTTP requests | Patching at requests.get level | Patch at transport layer or use VCR.py |
| Workspace creation | Testing against real `/Users/dsquirre/Cases` | Inject `base_dir` parameter, use temp directory |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading all test fixtures into memory | Tests slow down over time | Use fixture factories, lazy loading | >100 test files |
| Not parallelizing tests | CI takes >10 minutes | Use pytest-xdist for parallel execution | >500 tests |
| Recording every API call | VCR cassettes become massive | Record once, reuse cassettes | >50 API integration tests |
| Creating full workspace per test | Temp directory cleanup takes minutes | Share fixtures across tests with appropriate scope | >100 workspace tests |
| Not using test database | Tests conflict on shared state | Each test gets isolated test DB/filesystem | >50 integration tests |

## Security Mistakes

Domain-specific security issues for CLI tools with external integrations.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing API tokens in test fixtures | Credentials leaked to git | Use placeholder tokens, never real credentials |
| Testing against production API | Data corruption, rate limiting | Use test/sandbox API environment or VCR.py |
| Hardcoded paths in tests | Tests fail on CI, leak local paths | Use `tmp_path` and path injection |
| Committing `.env` or test credentials | Credential exposure | Add to `.gitignore`, use `.env.example` |
| Not validating SSL in tests | Tests pass but production fails MITM | Use real HTTPS in integration tests |
| Logging sensitive data in test output | Credentials in CI logs | Sanitize logs, use `capsys` fixture carefully |

## UX Pitfalls

Common user experience mistakes when hardening CLI tools.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Silent failures in test suite | Developers miss broken tests | Use `-v` flag by default, fail loudly |
| Unclear test failure messages | Can't diagnose what broke | Use descriptive assertion messages |
| Tests require manual setup | New contributors can't run tests | Document test setup in README, use fixtures |
| No way to run subset of tests | Full suite too slow for TDD | Use pytest markers (`@pytest.mark.slow`) |
| Test names like `test_1`, `test_2` | Can't tell what's being tested | Use descriptive names: `test_workspace_creation_with_invalid_case_number` |
| No test documentation | Don't know what's tested | Add docstrings to test functions |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Test Infrastructure:** Tests exist but don't run in CI — verify GitHub Actions/CI config
- [ ] **Mocking Setup:** HTTP calls mocked but error paths untested — verify timeout, 500, 404 tests exist
- [ ] **Fixture Cleanup:** Temp files created but not cleaned — verify `teardown`/`finally` blocks
- [ ] **Environment Isolation:** Tests pass locally but fail in CI — verify no hardcoded paths/env vars
- [ ] **Coverage Gaps:** 80% coverage but critical paths untested — verify error handling, edge cases tested
- [ ] **API Contract Tests:** Mocks exist but don't match real API — verify VCR.py cassettes or contract tests
- [ ] **CLI Integration:** Unit tests pass but CLI fails — verify end-to-end CLI invocation tests
- [ ] **Documentation:** Tests exist but no one knows how to run them — verify test README exists

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Refactored before testing | HIGH | 1. Revert refactoring, 2. Write characterization tests, 3. Re-apply refactoring under test coverage |
| Over-mocked integration tests | MEDIUM | 1. Implement VCR.py, 2. Record real API responses, 3. Replace mocks with cassettes |
| Hardcoded dependencies | MEDIUM | 1. Add config object, 2. Inject dependencies, 3. Update tests to use test config |
| Test isolation failures | LOW | 1. Add pytest-randomly to CI, 2. Fix failures one by one, 3. Add isolation to test template |
| Scope creep refactoring | LOW | 1. Split PR into test-only and refactor PRs, 2. Merge test PR first, 3. Review refactor separately |
| Over-testing trivial code | LOW | 1. Delete trivial tests, 2. Use mutation testing to validate remaining tests, 3. Focus on behavior |
| API credentials in git | HIGH (security) | 1. Rotate credentials immediately, 2. Use git-filter-repo to remove from history, 3. Add to .gitignore |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Refactoring before test coverage | Phase 1: Test Infrastructure | Characterization tests passing before any refactoring |
| Mocking too much | Phase 2: Core Component Testing | Integration tests using VCR.py exist |
| Hardcoded dependencies | Phase 1: Test Infrastructure | Tests run successfully in CI |
| External API untested | Phase 2: Core Component Testing | VCR cassettes exist for all API integrations |
| CLI argument parsing untested | Phase 2: Core Component Testing | Tests exist for all CLI commands |
| Test isolation failures | Phase 1: Test Infrastructure | pytest-randomly enabled in CI, no order-dependent failures |
| Technical debt scope creep | All phases | PR review checklist enforces test-only vs. refactor separation |
| Over-testing trivial code | Phase 2: Core Component Testing | Testing philosophy documented, mutation testing shows value |

## Sources

- Python unittest documentation (official): https://docs.python.org/3/library/unittest.html
- pytest documentation on good practices (HIGH confidence for fixture patterns)
- VCR.py library for HTTP recording (industry standard for Python API testing)
- Personal knowledge of Python testing best practices (based on training data through January 2025)
- Codebase analysis: `/Users/dsquirre/Repos/mc/src/mc/` (current state inspection)

**Confidence notes:**
- HIGH confidence on Python testing patterns (official documentation verified)
- HIGH confidence on pytest fixtures and isolation (standard library)
- MEDIUM confidence on this specific codebase's pitfalls (based on code inspection, not team interviews)
- LOW confidence on timeline/effort estimates (no historical data on this team's velocity)

---
*Pitfalls research for: Python CLI Tool Hardening and Test Retrofitting*
*Researched: 2026-01-20*
