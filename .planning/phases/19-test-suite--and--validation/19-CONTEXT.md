# Phase 19: Test Suite & Validation - Context

**Gathered:** 2026-02-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Comprehensive testing that proves no duplicate terminals are created across different scenarios and platforms. This phase validates the entire window tracking system (phases 15-18) through integration tests, unit tests, and platform-specific validation. NOT adding new window tracking capabilities - only testing what was built.

</domain>

<decisions>
## Implementation Decisions

### Test Coverage Strategy
- **Platform focus:** macOS-only for now (Linux support can expand later)
- **Coverage approach:** Happy path + critical edge cases, not exhaustive matrix testing
- **Real components:** Integration tests use real APIs, containers, terminals - never mock
- **Terminal windows:** Actually create and verify real iTerm/Terminal windows during tests
- **Negative testing:** Explicitly verify duplicate prevention - assert window count stays at 1
- **Regression test:** Fix and expand existing `test_duplicate_terminal_prevention_regression`
- **Test organization:** Both unit tests (WindowRegistry operations) and integration tests (full workflow)

### Edge Cases to Test
- **Window lifecycle:** User manually closes window → registry cleanup → next `mc case` creates new window
- **Registry corruption recovery:** Registry gets corrupted/deleted → graceful fallback behavior
- **Stale window IDs:** Window ID in registry but window was force-killed → detection and handling

### Test Data
- **Case numbers for testing:** Use these specific numbers to avoid conflicts with real work:
  - 04300354, 04330024, 04339264, 04363448, 04309442, 04345930
  - 04347611, 04355568, 04359219, 04363690, 04366093, 04366220
- **Environment:** Tests run on local PC where real case windows may already exist
- **Isolation:** Claude decides approach (considering provided case numbers)

### Test Execution Approach
- **Development workflow:** Pre-commit hooks run tests automatically before git commit
- **CI/CD:** Skip CI integration for now - focus on local testing first
- **Test speed:** Run everything always - no fast/slow separation, accept slower feedback
- **Prerequisites:** Require Podman running - fail fast with clear error if not available
- **Cleanup strategy:** Configurable cleanup with pytest option (e.g., --keep-on-failure)
  - Default: clean up containers/windows after tests
  - Option: preserve artifacts on failure for debugging
- **Verification approach:** Both unit tests (registry operations) and integration tests (AppleScript queries)

### Failure Handling & Debugging
- **Debug information captured on failure:**
  - Registry state snapshot (all case numbers → window ID mappings)
  - AppleScript command logs (exact commands executed, responses, errors)
  - Window state at failure (all iTerm/Terminal windows, IDs, titles, focus state)
  - Test assertion context (expected vs actual values)
- **Artifact storage:** Write debugging artifacts to temp files (`/tmp/mc-test-debug-{timestamp}/`)
- **Reproduction support:** Keep it simple initially, expand as necessary

### Success Validation
- **Primary signal:** `test_duplicate_terminal_prevention_regression` passes consistently
- **Coverage goal:** Improve by 5-10 percentage points (77% → 82-87%)
- **Completion criteria:** All success criteria from roadmap pass:
  1. Integration test passes consistently
  2. Unit tests validate WindowRegistry operations
  3. Manual testing documented and verified
  4. Platform-specific tests pass
- **Bug handling:** Severity-based approach
  - Critical bugs (duplicates still created) must be fixed in this phase
  - Minor bugs (cleanup timing, edge cases) can be documented and deferred

### Claude's Discretion
- Test isolation approach (registry cleanup vs unique case numbers vs separate DB files)
- Retry logic for async window operations (immediate fail vs wait-and-retry)
- Test output verbosity (verbose vs quiet default)
- When to use specific reproduction aids (seeds, timing logs)

</decisions>

<specifics>
## Specific Ideas

- Tests must work alongside real working environment - don't disrupt actual case windows
- Use real Podman containers and terminals - no mocking of core infrastructure
- Basic cleanup verification is sufficient (don't over-engineer edge case handling)
- Coverage improvement is progressive goal - each milestone should improve metrics

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 19-test-suite--and--validation*
*Context gathered: 2026-02-08*
