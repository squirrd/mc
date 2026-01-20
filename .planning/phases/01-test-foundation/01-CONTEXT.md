# Phase 1: Test Foundation - Context

**Gathered:** 2026-01-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Setting up pytest framework and infrastructure so developers can run unit tests and integration tests with proper mocking. This phase establishes the testing foundation - test execution, fixtures, mocking patterns, and coverage reporting. Writing actual tests for modules is Phase 2.

</domain>

<decisions>
## Implementation Decisions

### Test Organization
- Tests live in `tests/` directory at root (separate from source code)
- Exact mirror of source structure: `tests/test_module.py` for each `src/module.py`
- Separate directories: `tests/unit/` and `tests/integration/` for clear separation
- Test function naming: `test_function_name` convention (simple descriptive names)
- conftest.py files per directory (tests/, tests/unit/, tests/integration/) for scoped fixtures

### Fixture Design
- Core fixtures must provide:
  - Mock API responses (RedHat API calls, case data, attachments)
  - Test file system (temporary directories/files for workspace testing)
  - Mock auth tokens (valid/expired/invalid scenarios)
  - Sample test data (case numbers, user data, LDAP responses)
- Fixtures must cover both success and error scenarios (200 responses, 401/404/500 errors, timeouts)

### Coverage Expectations
- Baseline coverage target: 60-70% (balanced goal for foundation + critical path testing)
- Report format: Both terminal summary AND HTML reports (quick feedback + detailed analysis)
- CI enforcement: YES - fail CI build if coverage drops below threshold

### Claude's Discretion
- Test data file organization (fixtures directory vs co-located)
- pytest configuration location (pyproject.toml vs pytest.ini)
- Fixture scope choices (function/module/session per fixture type)
- Cleanup/teardown patterns (yield vs finalizers)
- Fixture parametrization (where it adds value)
- API response fixture structure (JSON files vs Python dicts)
- Fixture reusability across unit/integration tests
- Factory fixture usage
- Mock library choice (unittest.mock, pytest-mock, responses)
- HTTP mocking approach (mock requests directly vs mock APIClient)
- File system mocking approach (tmp_path vs mocks)
- LDAP mocking approach (mock calls vs test server)
- Coverage tool choice (pytest-cov vs coverage.py)

</decisions>

<specifics>
## Specific Ideas

No specific requirements - open to Python/pytest best practices.

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope.

</deferred>

---

*Phase: 01-test-foundation*
*Context gathered: 2026-01-20*
