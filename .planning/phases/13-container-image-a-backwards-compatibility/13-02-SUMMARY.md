---
phase: 13-container-image-a-backwards-compatibility
plan: 02
subsystem: infra
tags: [podman, containers, rhel10, ubi, environment-variables, integration-tests]

# Dependency graph
requires:
  - phase: 13-container-image-a-backwards-compatibility
    plan: 01
    provides: mc-rhel10:latest container image with MC CLI, Python 3.12, essential tools
  - phase: 11-container-lifecycle-a-state-management
    plan: 02
    provides: ContainerManager.create() with auto-restart pattern

provides:
  - ContainerManager.create() updated to use mc-rhel10:latest image
  - Environment variables (CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE=agent) set in containers
  - Image verification with helpful build instructions if missing
  - Comprehensive integration test suite for container image functionality (8 tests)

affects: [backwards-compatibility-validation, container-operations, runtime-testing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Image verification pattern: Check image exists before container creation with actionable error messages"
    - "Environment variable injection: Set case metadata and runtime mode via container environment dict"
    - "Integration test patterns: Skip gracefully when image not built or integration flag unset"

key-files:
  created:
    - tests/integration/test_container_image.py
  modified:
    - src/mc/container/manager.py
    - tests/unit/test_container_manager_create.py

key-decisions:
  - "Image verification before creation: Explicit check for mc-rhel10:latest with build command in error message (prevents cryptic Podman errors)"
  - "Environment variables over entrypoint args: Set CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE via environment dict (simpler than command args, accessible to all processes)"
  - "Integration test skip strategy: MC_TEST_INTEGRATION environment variable required (prevents false failures on systems without Podman/image)"

patterns-established:
  - "Pattern 1 - Image verification: Check image exists with client.images.get() before container creation, provide actionable error with build command"
  - "Pattern 2 - Environment injection: Use environment parameter dict in containers.create() for case metadata and runtime mode"
  - "Pattern 3 - Integration test skip: Use @pytest.mark.skipif with custom check functions for conditional skip messages"

# Metrics
duration: 5min
completed: 2026-01-27
---

# Phase 13 Plan 02: Backwards Compatibility Integration Summary

**ContainerManager updated to use mc-rhel10:latest image with environment variables (CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE=agent) and 8 integration tests validating end-to-end container functionality**

## Performance

- **Duration:** 5 min
- **Started:** 2026-01-27T01:39:53Z
- **Completed:** 2026-01-27T01:44:40Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- ContainerManager.create() now uses mc-rhel10:latest instead of UBI9 baseline image
- Image verification checks mc-rhel10:latest exists before creation with helpful error message
- Environment variables set in containers: CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE=agent
- 8 comprehensive integration tests covering image existence, container creation, environment setup, CLI accessibility, tools, and runtime mode detection
- All unit tests updated to verify new image reference and environment variables (13 tests passing)
- Integration tests skip gracefully when image not built or MC_TEST_INTEGRATION flag not set

## Task Commits

Each task was committed atomically:

1. **Task 1: Update ContainerManager to use mc-rhel10 image** - `544221f` (feat)
   - Changed image from registry.access.redhat.com/ubi9/ubi:latest to mc-rhel10:latest
   - Added image verification with podman_client.client.images.get("mc-rhel10:latest")
   - Added environment dict with CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE
   - Updated 13 unit tests to mock image check and verify environment variables
   - Added test for image not found error with build command in message

2. **Task 2: Create container image integration tests** - `0a6d13a` (test)
   - Created tests/integration/test_container_image.py with 8 comprehensive tests
   - Test image exists and has correct labels
   - Test container creation with mc-rhel10 image
   - Test environment variables propagate correctly
   - Test shell prompt format (PS1 from entrypoint.sh)
   - Test MC CLI importable and version accessible
   - Test essential tools available (vim, curl, openssl, wget)
   - Test runtime mode detection (agent mode)
   - Test config file readable in mounted workspace
   - All tests skip with helpful messages when image not built or integration flag unset

## Files Created/Modified

- `src/mc/container/manager.py` - Updated create() to use mc-rhel10:latest, added image verification, added environment variables
- `tests/unit/test_container_manager_create.py` - Updated 13 tests to mock image check and verify environment variables, added test for image not found error
- `tests/integration/test_container_image.py` - Created 8 integration tests for end-to-end container image validation (369 lines)

## Decisions Made

**1. Image verification before container creation**
- Rationale: Provide clear, actionable error message if image not built instead of cryptic Podman error
- Implementation: Check client.images.get("mc-rhel10:latest") before containers.create()
- Error message includes: "Run 'podman build -t mc-rhel10:latest -f container/Containerfile .' first"
- Benefit: Developers get immediate guidance on how to fix missing image issue

**2. Environment variables for case metadata**
- Rationale: Simpler than passing via command args, accessible to all processes in container
- Implementation: environment dict with CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH, MC_RUNTIME_MODE
- Coordination: MC_RUNTIME_MODE=agent works with Phase 13-01 runtime.py detection
- Benefit: Shell scripts and Python code can access metadata via standard env vars

**3. Integration test skip strategy**
- Rationale: Prevent false test failures on CI systems or developer machines without Podman/image
- Implementation: @pytest.mark.skipif checking MC_TEST_INTEGRATION env var and image existence
- Skip messages: Include exact command to build image or enable integration tests
- Benefit: Clear guidance for developers on how to run integration tests

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly with Phase 11 ContainerManager foundation and Phase 13-01 image.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for backwards compatibility validation:**
- mc-rhel10:latest image fully integrated into ContainerManager
- Environment variables propagate case metadata and runtime mode correctly
- Integration test framework in place for manual/automated validation
- Shell prompt customization working via entrypoint.sh
- MC CLI accessible inside containers with correct runtime mode detection

**No blockers or concerns.**

---
*Phase: 13-container-image-a-backwards-compatibility*
*Completed: 2026-01-27*
