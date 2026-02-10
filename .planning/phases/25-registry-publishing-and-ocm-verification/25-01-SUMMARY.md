---
phase: 25-registry-publishing-and-ocm-verification
plan: 01
subsystem: infra
tags: [podman, registry, quay.io, authentication, credentials]

# Dependency graph
requires:
  - phase: 24-auto-versioning-logic
    provides: Auto-versioning build script with registry integration
provides:
  - Persistent registry authentication infrastructure
  - Pre-flight credential validation before builds
  - Gitignored auth.json for secure credential storage
affects: [25-02, container-publishing, registry-operations]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Persistent auth.json in MC base directory (not container/)"
    - "Pre-flight credential validation with podman login --get-login"
    - "Helpful error messages with exact podman login commands"

key-files:
  created:
    - .registry-auth/auth.json
  modified:
    - .gitignore
    - container/build-container.sh

key-decisions:
  - "Auth.json in MC base directory (not container/) for sharing with future mc-cli registry operations"
  - "Pre-flight validation prevents wasted 2-5 minute build cycles on auth failures"
  - "Gitignored .registry-auth/ directory prevents credential leaks"

patterns-established:
  - "Pattern: MC_BASE variable for repository root detection in build scripts"
  - "Pattern: --authfile flag on all podman push operations for explicit credential control"
  - "Pattern: Fail-fast validation before expensive operations (build, push)"

# Metrics
duration: 3min
completed: 2026-02-10
---

# Phase 25 Plan 01: Registry Authentication Infrastructure Summary

**Persistent registry credentials with pre-flight validation preventing wasted build time on auth failures**

## Performance

- **Duration:** 3 min
- **Started:** 2026-02-10T01:19:28Z
- **Completed:** 2026-02-10T01:22:30Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Registry auth infrastructure at .registry-auth/auth.json with template structure
- Pre-flight credential validation in build script before builds
- Helpful error messages with exact podman login commands
- Credentials persist across reboots (unlike ${XDG_RUNTIME_DIR})

## Task Commits

Each task was committed atomically:

1. **Task 1: Create registry auth config infrastructure** - `c510b7f` (feat)
2. **Task 2: Add pre-flight credential validation to build script** - `629b7dc` (feat)

## Files Created/Modified
- `.registry-auth/auth.json` - Template for persistent registry credentials (gitignored)
- `.gitignore` - Added .registry-auth/ to prevent credential commits
- `container/build-container.sh` - Added MC_BASE detection, validate_registry_auth() function, pre-flight validation, --authfile flags on push commands

## Decisions Made

**1. Auth.json location: MC base directory (not container/)**
- Rationale: Shared location for future mc-cli registry operations, persists across reboots
- Per CONTEXT.md: "Registry configuration fixed location in config file under MC base directory"

**2. Pre-flight validation with podman login --get-login**
- Rationale: Prevents wasted 2-5 minute build cycles that fail at push time
- Fail-fast with helpful error messages showing exact podman login command

**3. File permissions 600 (owner read/write only)**
- Rationale: Auth field contains base64-encoded credentials (not encrypted), security-sensitive

**4. Gitignore .registry-auth/ directory**
- Rationale: Prevents accidental credential commits to version control

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - straightforward implementation following RESEARCH.md patterns.

## User Setup Required

**Registry authentication required for automated builds.**

Before using `container/build-container.sh`, authenticate with Quay.io:

```bash
# For Quay.io robot accounts:
podman login quay.io --authfile=.registry-auth/auth.json
# Username: <org>+<robot-name>
# Password: Robot token from Quay.io dashboard

# For personal accounts:
podman login quay.io --authfile=.registry-auth/auth.json
```

**Verification:**
```bash
# Dry-run will validate credentials
./container/build-container.sh --dry-run
# Expected: "✓ Registry credentials validated for quay.io/..."
```

## Next Phase Readiness

**Ready for registry publishing (Plan 02):**
- ✓ Auth infrastructure in place
- ✓ Pre-flight validation prevents build failures
- ✓ Helpful error messages guide users to fix auth issues
- ✓ Credentials persist across reboots

**Blockers:** None - user must authenticate before first build (documented above)

---
*Phase: 25-registry-publishing-and-ocm-verification*
*Completed: 2026-02-10*
