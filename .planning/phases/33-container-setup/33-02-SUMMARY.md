---
phase: 33-container-setup
plan: "02"
subsystem: container
tags: [podman, volumes, mounts, pre-flight, claude, config]

# Dependency graph
requires:
  - phase: 33-container-setup
    provides: Containerfile with mc CLI, OCM, and claude Code installed

provides:
  - get_mc_config_path() helper returning ~/mc/config
  - get_claude_config_path() helper returning ~/.claude
  - Pre-flight hard failure when ~/mc/config is absent from host
  - Warning-and-continue when ~/.claude is absent from host
  - ~/mc/config mounted read-only at /home/mcuser/mc/config in every container
  - ~/.claude mounted read-write at /home/mcuser/.claude when present on host
  - 6 unit tests covering all new mount and pre-flight scenarios
  - All existing container manager tests updated for isolation

affects:
  - 33-container-setup (33-03 if planned)
  - Any phase that calls ContainerManager.create()
  - Integration testing of container launch

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Pre-flight check pattern: validate host paths before any side effects in create()
    - Conditional volume mount pattern: check path.exists() before adding to volumes dict
    - Warning-vs-error distinction: hard fail for required paths, warn-and-continue for optional

key-files:
  created:
    - tests/unit/test_container_manager_mounts.py
  modified:
    - src/mc/container/manager.py
    - tests/unit/test_container_manager_create.py

key-decisions:
  - "~/mc/config is required (hard fail): without it the container cannot be configured"
  - "~/.claude is optional (warn-and-continue): claude auth is desirable but container is functional without it"
  - "mc/config mounted read-only (ro): container should not modify host config"
  - "claude dir mounted read-write (rw): claude needs to write session state inside the container"
  - "Pre-flight placed before os.makedirs to fail fast without any side effects"

patterns-established:
  - "Pre-flight pattern: validate host dependencies at top of create() before any filesystem changes"
  - "Conditional mount pattern: if path.exists(): add to volumes dict — used for OCM, claude, future mounts"

# Metrics
duration: 5min
completed: 2026-03-20
---

# Phase 33 Plan 02: Container Mount Configuration Summary

**Pre-flight validation and dual config mounts added to ContainerManager.create(): ~/mc/config (ro) and ~/.claude (rw) mounted into every case container**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-20T10:29:20Z
- **Completed:** 2026-03-20T10:34:49Z
- **Tasks:** 4
- **Files modified:** 3 (1 created, 2 updated)

## Accomplishments

- Added `get_mc_config_path()` and `get_claude_config_path()` module-level helpers alongside the existing `get_ocm_config_path()` pattern
- `create()` now hard-fails before any side effects when `~/mc/config` is absent, with a clear user-facing error message
- `~/mc/config` mounted read-only at `/home/mcuser/mc/config` in every container, making mc CLI configuration available inside
- `~/.claude` mounted read-write at `/home/mcuser/.claude` when present on the host, passing Claude Code authentication into the container
- 6 focused unit tests added covering all mount and pre-flight scenarios
- 9 existing `test_container_manager_create.py` tests updated to add explicit mocks for the new path helpers, ensuring full test isolation from the developer's actual filesystem

## Task Commits

Each task was committed atomically:

1. **Task 1: Add get_mc_config_path() and get_claude_config_path() helpers** - `9303d4b` (feat)
2. **Task 2: Add pre-flight checks and new mounts to create()** - `b2c9357` (feat)
3. **Task 3: Write unit tests for mount and pre-flight behavior** - `70c2b40` (test)
4. **Task 4: Verify existing container manager tests still pass** - `ca94b1f` (fix)

## Files Created/Modified

- `src/mc/container/manager.py` - Added two path helper functions; replaced volumes block with pre-flight checks + mc_config/claude_dir mounts; renumbered step comments
- `tests/unit/test_container_manager_mounts.py` - New: 6 unit tests for mount and pre-flight behavior across 3 test classes
- `tests/unit/test_container_manager_create.py` - Added `get_mc_config_path` and `get_claude_config_path` patches to all `create()`-calling tests; updated volumes assertion in `test_create_new_container`

## Decisions Made

- `~/mc/config` is a hard requirement: without it the in-container mc CLI has no configuration, so failing early (before workspace creation) is correct
- `~/.claude` is optional: containers are fully functional without it, so a warning is appropriate; users who have not set up Claude Code yet should not be blocked
- Read-only for mc config, read-write for claude: mc config is host-owned config that the container must not modify; claude needs read-write access for session state
- Pre-flight checks placed before `os.makedirs` to avoid creating workspace directories when the config path check would immediately fail

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test isolation: 9 existing tests lacked mocks for new path helpers**

- **Found during:** Task 4 (verify existing tests)
- **Issue:** `test_create_new_container` and `test_create_skips_ocm_config_volume_when_absent` failed because the real `~/mc/config` and `~/.claude` paths were resolved. Other tests passed incidentally because `~/mc/config` exists on this developer's machine, but they lacked deterministic mocks.
- **Fix:** Added `@patch('mc.container.manager.get_mc_config_path')` and `@patch('mc.container.manager.get_claude_config_path')` to all 9 tests that call `create()` with no pre-existing container in state. Updated volumes assertion in `test_create_new_container` and `test_create_skips_ocm_config_volume_when_absent` to reflect the new expected volumes dict.
- **Files modified:** `tests/unit/test_container_manager_create.py`
- **Verification:** `uv run pytest tests/unit/test_container_manager_create.py --no-cov` — 21 passed
- **Committed in:** `ca94b1f` (Task 4 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug in test isolation)
**Impact on plan:** Required fix for correctness. Test isolation is mandatory to prevent false positives/negatives based on developer filesystem state. No scope creep.

## Issues Encountered

None — tasks executed as specified.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ContainerManager.create() now mounts ~/mc/config and ~/.claude automatically
- Container environment is ready for OCM login passthrough (33-03 if planned) and Claude Code usage inside case containers
- All 77 container manager tests pass (71 existing + 6 new)

---
*Phase: 33-container-setup*
*Completed: 2026-03-20*
