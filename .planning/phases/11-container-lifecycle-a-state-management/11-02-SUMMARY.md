---
phase: 11-container-lifecycle-a-state-management
plan: 02
subsystem: infra
tags: [podman, containers, sqlite, orchestration, rootless]

# Dependency graph
requires:
  - phase: 09-container-architecture---podman-integration
    provides: PodmanClient with lazy connection and retry logic
  - phase: 11-container-lifecycle-a-state-management
    plan: 01
    provides: StateDatabase with WAL mode and reconciliation

provides:
  - ContainerManager with create() orchestration
  - Auto-restart pattern for stopped/exited containers
  - Reconciliation before operations to detect external deletions
  - Workspace directory auto-creation before mount
  - Error handling with container cleanup on failures

affects: [11-03, container-operations, cli-commands]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "State-First Container Operations: reconcile before create, check state before Podman"
    - "Auto-restart pattern: transparently restart stopped/exited containers"
    - "Workspace auto-creation: makedirs before volume mount prevents failures"
    - "Cleanup on failure: stop and remove container if state persistence fails"

key-files:
  created:
    - src/mc/container/manager.py
    - tests/unit/test_container_manager_create.py
    - tests/integration/test_container_create_integration.py
  modified: []

key-decisions:
  - "Auto-restart pattern: Existing stopped/exited containers restart instead of creating duplicates (prevents container proliferation)"
  - "Workspace auto-creation: Create workspace directory before mount with exist_ok=True (prevents mount failures when directory missing)"
  - "Non-fatal reconciliation: Reconciliation failures print warning but don't block operations (degraded mode for offline scenarios)"
  - "Cleanup on state failure: If state persistence fails, stop and remove container to prevent orphaned containers (all-or-nothing consistency)"
  - "Exception handling pattern: Wrap podman-py exceptions in RuntimeError with helpful messages (consistent error interface)"

patterns-established:
  - "Pattern 1 - State-First Operations: Always reconcile before operations, check state before Podman API calls"
  - "Pattern 2 - Auto-restart transparency: Check container.status in (stopped, exited) and call container.start()"
  - "Pattern 3 - Error propagation: Catch podman-py exceptions, wrap in RuntimeError with context about case number and operation"

# Metrics
duration: 7min
completed: 2026-01-26
---

# Phase 11 Plan 02: Container Creation Orchestration Summary

**ContainerManager with auto-restart for stopped containers, workspace auto-creation, userns_mode=keep-id for rootless permissions, and state reconciliation**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-26T06:22:29Z
- **Completed:** 2026-01-26T06:29:38Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- ContainerManager.create() orchestrates Podman container creation with StateDatabase persistence
- Auto-restart pattern: stopped/exited containers restart transparently instead of creating duplicates
- Workspace directory created automatically before mount (prevents "directory does not exist" mount failures)
- userns_mode=keep-id configured for rootless volume permissions (host user UID/GID match container)
- Reconciliation before operations detects externally deleted containers (via 'podman rm')
- 12 unit tests with 85%+ coverage on create() and _reconcile() methods
- 2 integration tests verify end-to-end flow with real Podman (skip gracefully when unavailable)

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement ContainerManager with create operation** - `9eceae4` (feat)
   - ContainerManager class with Podman and StateDatabase integration
   - create() method with auto-restart, reconciliation, state persistence
   - _reconcile() helper to detect external deletions
   - Workspace directory creation, error handling with cleanup

2. **Task 2: Create unit tests for container creation** - `d5b204a` (test)
   - 12 comprehensive tests covering all scenarios
   - Mock-based tests for fast execution
   - Verify userns_mode=keep-id, volume configuration, auto-restart
   - Error handling and reconciliation tests

3. **Task 3: Integration smoke test** - `a9f2712` (test)
   - End-to-end tests with real Podman
   - Verify userns_mode and volume mount in actual container
   - Test auto-restart with stopped container
   - Test reconciliation with externally deleted containers
   - Marked @pytest.mark.integration, skip when Podman unavailable

## Files Created/Modified

- `src/mc/container/manager.py` - ContainerManager orchestration class (259 lines)
- `tests/unit/test_container_manager_create.py` - Unit tests for create() (425 lines, 12 tests)
- `tests/integration/test_container_create_integration.py` - Integration tests with real Podman (162 lines, 2 tests)

## Decisions Made

**1. Auto-restart pattern implementation**
- Rationale: Prevents container proliferation when user runs `mc create` multiple times
- Implementation: Check state first, if exists get from Podman, restart if stopped/exited
- Benefit: Transparent to user, container state persists across restarts

**2. Workspace directory auto-creation**
- Rationale: Prevents common failure mode when workspace path doesn't exist yet
- Implementation: `os.makedirs(workspace_path, exist_ok=True)` before container creation
- Benefit: Robust handling of fresh installations and manual directory deletion

**3. Non-fatal reconciliation failures**
- Rationale: Podman connection errors shouldn't prevent all container operations
- Implementation: Wrap _reconcile() in try/except, print warning, continue operation
- Benefit: Degraded mode works offline or when Podman temporarily unavailable

**4. Cleanup on state persistence failure**
- Rationale: Prevent orphaned containers (in Podman but not in state)
- Implementation: If state.add_container() fails, stop and remove container
- Benefit: All-or-nothing consistency, no partial state

**5. Exception wrapping pattern**
- Rationale: Consistent error interface across application
- Implementation: Catch podman-py exceptions, wrap in RuntimeError with context
- Benefit: Error messages include case number and operation for debugging

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation proceeded smoothly following RESEARCH.md patterns.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for 11-03 (Container list, stop, delete operations):**
- ContainerManager foundation complete with state-first pattern
- _reconcile() helper available for all operations
- Error handling pattern established
- Integration test framework in place

**No blockers or concerns.**

---
*Phase: 11-container-lifecycle-a-state-management*
*Completed: 2026-01-26*
