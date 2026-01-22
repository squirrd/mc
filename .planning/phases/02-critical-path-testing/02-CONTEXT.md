# Phase 2: Critical Path Testing - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Write comprehensive unit tests for core modules (auth, API client, workspace manager, utilities, LDAP integration) with proper mocking to protect against regression. This phase establishes test coverage for existing functionality built in Phase 1, enabling confident refactoring and feature development in later phases.

</domain>

<decisions>
## Implementation Decisions

### Test depth & coverage strategy
- Focus on **happy path + critical errors** for core modules (auth, API client, workspace manager)
- **Error messages must be validated** - tests verify both exception type AND that error messages are clear and actionable
- **Parameterized tests for utilities** - use pytest.mark.parametrize with multiple inputs to thoroughly test formatters and utility functions
- **Tiered coverage targets** - Claude's discretion to set appropriate coverage based on module risk (likely higher for auth/API client, lighter for utilities)

### Mocking vs. integration boundaries
- **Mix of mocks + real integration tests for HTTP** - most tests mock API calls using responses library, but include integration tests that hit real RedHat API for critical workflows
- **LDAP tested with docker in CI** - spin up test LDAP server in docker for integration tests rather than mocking entirely
- **Filesystem uses tmp_path fixtures primarily** - create real temp files for most tests, mock filesystem only for edge cases (permissions errors, disk full scenarios)
- **Token cache uses real temp files** - Claude's discretion to test with actual cache files in temp directory to validate caching behavior works correctly

### Assertion style & test data
- **Assertion detail** - Claude's discretion to assert key fields for most tests, validate full structure for critical data contracts
- **Realistic sample data** - test fixtures provide data that looks like real API responses and case metadata, not minimal stubs
- **Parameterized test structure** - use pytest.mark.parametrize for testing utilities with multiple input cases (confirmed from earlier decision)
- **Error message context** - Claude's discretion to use standard pytest assertions for simple cases, custom messages with context for complex business logic

### Claude's Discretion
- Exact coverage percentage targets per module (tiered by risk)
- Balance of key field vs. full structure assertions
- When to use custom assertion messages vs. standard pytest output
- Cache testing implementation details

</decisions>

<specifics>
## Specific Ideas

- Use **responses library** for HTTP mocking (already established in Phase 1 dependencies)
- Docker LDAP setup for CI integration tests - ensures LDAP parsing handles real server responses
- Realistic test data should catch issues with actual production data formats and edge cases

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-critical-path-testing*
*Context gathered: 2026-01-22*
