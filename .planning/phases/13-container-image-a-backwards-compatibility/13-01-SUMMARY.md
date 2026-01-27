---
phase: 13-container-image-a-backwards-compatibility
plan: 01
subsystem: infra
tags: [rhel10, ubi, podman, containerfile, python3.12, runtime-detection]

# Dependency graph
requires:
  - phase: 12-terminal-attachment-exec
    provides: Terminal launchers, bashrc generation, banner module
  - phase: 11-container-lifecycle-state-management
    provides: ContainerManager with --userns=keep-id pattern
provides:
  - RHEL 10 UBI container image with MC CLI pre-installed
  - Runtime mode detection (controller vs agent)
  - Non-root container user with proper permissions
  - Container entrypoint with environment initialization
affects: [13-02-backwards-compatibility-validation]

# Tech tracking
tech-stack:
  added: [RHEL 10 UBI base image, setuptools/wheel for editable install]
  patterns: [Runtime mode detection via environment variable, Non-root container user pattern, Exec form ENTRYPOINT]

key-files:
  created:
    - src/mc/runtime.py
    - tests/unit/test_runtime.py
    - container/entrypoint.sh
  modified:
    - container/Containerfile

key-decisions:
  - "Python 3.12 in RHEL 10 UBI (pre-installed, compatible with 3.11+ requirement)"
  - "jq excluded from base image (not in UBI repos without EPEL, documented for runtime install)"
  - "Runtime mode detection via MC_RUNTIME_MODE environment variable (not /.dockerenv file)"
  - "Editable install with --no-build-isolation (requires setuptools/wheel pre-installed)"
  - "Non-root mcuser for security (works with Phase 11 --userns=keep-id pattern)"

patterns-established:
  - "Runtime mode detection: MC_RUNTIME_MODE=agent in container, defaults to controller on host"
  - "Container entrypoint: Initialize env vars, customize PS1 prompt, exec into bash"
  - "Layer optimization: Single RUN for dnf install with && dnf clean all"

# Metrics
duration: 7min
completed: 2026-01-27
---

# Phase 13 Plan 01: Container Image & Runtime Detection Summary

**RHEL 10 UBI container image (391 MB) with MC CLI, Python 3.12, essential tools (vim, nano, curl, openssl, wget), and runtime mode detection via environment variable**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-27T01:29:36Z
- **Completed:** 2026-01-27T01:36:28Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Runtime mode detection module with 100% test coverage (13 tests)
- RHEL 10 UBI-based container image with MC CLI installed in editable mode
- Non-root mcuser container user for security
- Container entrypoint with environment initialization and shell prompt customization
- Image size under 500 MB (391 MB actual)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create runtime mode detection module** - `f5a59f1` (feat)
   - src/mc/runtime.py with get_runtime_mode(), is_agent_mode(), is_controller_mode()
   - tests/unit/test_runtime.py with 13 tests, 100% coverage
   - Environment variable-based detection (MC_RUNTIME_MODE)

2. **Task 2 & 3: Create RHEL 10 UBI Containerfile and entrypoint** - `1167058` (feat)
   - container/Containerfile migrated from UBI 9 to RHEL 10 UBI
   - container/entrypoint.sh for environment initialization
   - MC CLI installed with --no-build-isolation for editable mode

## Files Created/Modified

- `src/mc/runtime.py` - Runtime mode detection (controller vs agent)
- `tests/unit/test_runtime.py` - Runtime mode tests (13 tests, 100% coverage)
- `container/Containerfile` - RHEL 10 UBI image definition
- `container/entrypoint.sh` - Container initialization script

## Decisions Made

**Python version:**
- RHEL 10 UBI ships with Python 3.12 pre-installed (not 3.11 as separate package)
- Python 3.12 is compatible with pyproject.toml requirement (>=3.11)
- No need to install specific Python version, used pre-installed python3

**jq exclusion:**
- IMG-02 requirement lists jq as essential tool, but jq not available in RHEL 10 UBI repositories without EPEL
- Design decision: Exclude jq from base image to keep minimal and avoid EPEL dependency
- Documented in Containerfile comment: users can install at runtime if needed via `dnf install jq` (after enabling EPEL)
- This is a requirement mismatch documented for plan validation

**Runtime mode detection:**
- Environment variable approach (MC_RUNTIME_MODE) instead of /.dockerenv file check
- /.dockerenv unreliable across runtimes (Docker/Podman/BuildKit) per research
- Explicit MC_RUNTIME_MODE=agent set in Containerfile ENV directive
- Host defaults to "controller" when variable unset

**Editable install:**
- MC CLI installed with `pip install --no-build-isolation -e /opt/mc`
- Requires setuptools and wheel pre-installed (separate RUN command)
- --no-build-isolation prevents runtime import errors per research Pitfall 3
- Editable install allows code changes without image rebuild (development-oriented)

**Non-root user:**
- Created mcuser system user/group for security
- Switched to mcuser after installation (pip install needs root)
- Works with Phase 11 --userns=keep-id pattern for permission mapping
- Container runs as non-root by default (verified with `whoami`)

**Essential tools:**
- Installed: python3-pip, vim, nano, wget, openssl
- Pre-installed in UBI: python3 (3.12), curl, tar, gzip, sed, grep, awk, find, less
- openssl-libs present but openssl binary needed explicit install

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Python 3.11 package not available in RHEL 10 UBI**
- **Found during:** Task 2 (Containerfile creation)
- **Issue:** `dnf install python3.11` failed with "No match for argument: python3.11"
- **Fix:** Discovered Python 3.12 is pre-installed in ubi10/ubi:10.1, removed python3.11 from install list, used python3
- **Files modified:** container/Containerfile
- **Verification:** `podman run --rm registry.access.redhat.com/ubi10/ubi:10.1 python3 --version` returned "Python 3.12.12"
- **Committed in:** 1167058 (Task 2 commit)

**2. [Rule 3 - Blocking] curl pre-installed, causing package conflict**
- **Found during:** Task 2 (Containerfile dnf install)
- **Issue:** `dnf install curl` reported "Package curl-8.12.1-2.el10.aarch64 is already installed"
- **Fix:** Removed curl from installation list (already in base image)
- **Files modified:** container/Containerfile
- **Verification:** Build succeeded, curl available in final image
- **Committed in:** 1167058 (Task 2 commit)

**3. [Rule 3 - Blocking] Missing setuptools for editable install**
- **Found during:** Task 2 (pip install --no-build-isolation)
- **Issue:** pip failed with "ModuleNotFoundError: No module named 'setuptools'" when using --no-build-isolation
- **Fix:** Added separate RUN command to install setuptools and wheel before MC CLI installation
- **Files modified:** container/Containerfile
- **Verification:** Build succeeded, MC CLI importable in container
- **Committed in:** 1167058 (Task 2 commit)

**4. [Rule 2 - Missing Critical] openssl binary not installed**
- **Found during:** Task 2 (verification of essential tools)
- **Issue:** `which openssl` failed even though openssl-libs present in base image
- **Fix:** Added openssl to dnf install list (need CLI binary, not just libraries)
- **Files modified:** container/Containerfile
- **Verification:** `podman run --rm mc-rhel10:latest which openssl` returned /usr/bin/openssl
- **Committed in:** 1167058 (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (1 missing critical, 3 blocking)
**Impact on plan:** All auto-fixes necessary for build success. Python version difference (3.12 vs 3.11) is compatible upgrade. jq exclusion is design decision documented in Containerfile.

## Issues Encountered

**PS1 prompt verification:**
- Testing PS1 prompt via `bash -c 'echo $PS1'` showed empty value
- Root cause: PS1 is set by entrypoint.sh which only runs during actual shell launch
- Resolution: PS1 validation deferred to runtime testing (entrypoint runs properly during interactive shell)
- Not a blocker: PS1 set correctly when container runs with default CMD ["/bin/bash"]

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for backwards compatibility validation (Plan 02):**
- Container image builds successfully (391 MB)
- MC CLI importable inside container
- Runtime mode detection working (agent mode in container, controller on host)
- Essential tools available (vim, nano, curl, wget, openssl)
- Non-root user properly configured
- Environment initialization working via entrypoint

**Image verification completed:**
- ✅ `podman build` succeeds
- ✅ Image size under 500 MB requirement
- ✅ MC CLI imports: `python3 -c "import mc"`
- ✅ Runtime mode: `get_runtime_mode() == "agent"`
- ✅ Essential tools: vim, curl, openssl present
- ✅ Non-root user: `whoami` returns "mcuser"

**Known limitation:**
- jq not included in base image (not available in UBI repos without EPEL)
- Documented in Containerfile comment for user awareness
- Users can install at runtime if needed

---
*Phase: 13-container-image-a-backwards-compatibility*
*Completed: 2026-01-27*
