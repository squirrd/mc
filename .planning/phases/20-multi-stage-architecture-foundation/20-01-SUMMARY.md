---
phase: 20-multi-stage-architecture-foundation
plan: 01
subsystem: infra
tags: [podman, containerfile, multi-stage, ocm, layer-caching, rhel-ubi]

# Dependency graph
requires:
  - phase: 11-container-lifecycle
    provides: Container manager and build infrastructure
provides:
  - Multi-stage Containerfile with three named stages (ocm-downloader, mc-builder, final)
  - ARG parameter injection architecture for build script automation (Phase 22)
  - OCM binary integration with SHA256 verification
  - Automated cache verification testing
  - Optimized layer caching for fast rebuilds
affects: [21-version-management, 22-build-automation]

# Tech tracking
tech-stack:
  added: [ocm-cli-0.35.0]
  patterns:
    - "Multi-stage builds with ARG parameter injection for version control"
    - "SHA256 checksum verification for downloaded binaries"
    - "Layer ordering optimized for cache efficiency with version injection"

key-files:
  created:
    - container/verify-cache.sh
  modified:
    - container/Containerfile

key-decisions:
  - "ARG parameters placed BEFORE dependencies to accept build script injection (Phase 22)"
  - "OCM binary downloaded from GitHub releases with SHA256 verification"
  - "Three-stage separation: downloader (UBI-minimal), builder (UBI 10.1), final (UBI 10.1)"
  - "MC console script copied from builder stage to final stage"

patterns-established:
  - "ARG injection pattern: declare ARG before dependencies, accept via --build-arg at build time"
  - "Checksum verification: echo hash + filename format for sha256sum --check compatibility"
  - "Stage artifact copying: COPY --from=stage-name for cross-stage file transfer"

# Metrics
duration: 10min
completed: 2026-02-09
---

# Phase 20 Plan 01: Multi-Stage Architecture Foundation Summary

**Three-stage Containerfile with ARG injection architecture, OCM binary integration via SHA256-verified GitHub releases, and 12-layer cache optimization achieving fast rebuilds**

## Performance

- **Duration:** 10 min
- **Started:** 2026-02-09T11:42:45Z
- **Completed:** 2026-02-09T11:53:43Z
- **Tasks:** 3
- **Files modified:** 2

## Accomplishments
- Converted single-stage Containerfile to multi-stage build with three named stages
- Established ARG parameter injection architecture for Phase 22 build script automation
- Integrated OCM CLI v0.35.0 with SHA256 checksum verification from GitHub releases
- Achieved 12-layer cache optimization (verified via automated test)
- Created automated cache verification script
- Reduced build tool footprint in final image (no pip, gcc, python3-devel)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create multi-stage Containerfile with ARG parameter injection architecture** - `5c6fdeb` (feat)
2. **Task 2: Create automated cache verification test** - `8417a57` (test)
3. **Task 3: Verify ARG injection mechanism and layer caching** - (verification only, no commit)

## Files Created/Modified
- `container/Containerfile` - Multi-stage build with ocm-downloader, mc-builder, final stages. ARG OCM_VERSION for build script injection. SHA256-verified OCM binary download. Runtime-only final image.
- `container/verify-cache.sh` - Automated cache verification script. Builds twice, validates cache hits, reports layer count.

## Decisions Made

**ARG placement for Phase 22 build script automation:**
- Placed ARG OCM_VERSION BEFORE curl installation in ocm-downloader stage
- When build script injects new version via --build-arg, downstream layers are invalidated
- This is correct behavior: version changes require downloading new binary
- Preserves caching when version unchanged between builds

**OCM checksum verification:**
- GitHub releases provide hash-only file (no filename in checksum file)
- Solution: `echo "$(cat expected.sha256)  ocm.tar.gz" | sha256sum --check`
- Format matches sha256sum --check expectations (hash + two spaces + filename)

**MC console script copying:**
- Initial implementation missed /usr/local/bin/mc console script
- Auto-fixed (Rule 2): Added COPY --from=mc-builder for /usr/local/bin/mc
- Verified MC CLI functional via `mc --help` and `mc --version`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] MC console script not copied to final stage**
- **Found during:** Task 1 verification (MC CLI not working)
- **Issue:** Containerfile copied site-packages but not /usr/local/bin/mc console script created by pip install
- **Fix:** Added `COPY --from=mc-builder --chown=mcuser:mcuser /usr/local/bin/mc /usr/local/bin/mc`
- **Files modified:** container/Containerfile
- **Verification:** `podman run --rm mc-rhel10:multi-stage mc --help` succeeded
- **Committed in:** 5c6fdeb (Task 1 commit)

**2. [Rule 1 - Bug] SHA256 checksum file format incompatible with sha256sum --check**
- **Found during:** Task 1 initial build (checksum verification failed)
- **Issue:** GitHub releases provide hash-only file, sha256sum --check expects "hash  filename" format
- **Fix:** Changed verification to `echo "$(cat expected.sha256)  ocm.tar.gz" | sha256sum --check`
- **Files modified:** container/Containerfile
- **Verification:** Build succeeded with "ocm.tar.gz: OK" message
- **Committed in:** 5c6fdeb (Task 1 commit)

---

**Total deviations:** 2 auto-fixed (1 missing critical, 1 bug)
**Impact on plan:** Both auto-fixes necessary for correctness. MC console script required for CLI functionality. Checksum verification required for security. No scope creep.

## Issues Encountered
None - all issues auto-fixed via deviation rules.

## Verification Results

**Cache Verification:**
- Built image twice with no changes
- Second build showed cache hits for 12 layers
- Verification script: PASS

**ARG Injection (MULTI-02 architecture):**
- Built with `--build-arg OCM_VERSION=0.34.3`
- Verified injected version propagated via `ocm version` output
- Phase 22 build script architecture: Ready

**Size Comparison:**
- Original baseline: 549MB
- Multi-stage: 626MB
- Increase due to OCM binary addition (117MB)
- Size increase acceptable for added functionality

**OCM Binary:**
- Version: v0.35.0 (matches ARG default)
- Path: /usr/local/bin/ocm
- Functional: YES
- SHA256 verification: PASS

**Build Tools Exclusion:**
- pip3: Not found (expected)
- gcc: Not found (expected)
- python3-devel: Not installed (expected)
- Runtime-only final image: CONFIRMED

**Runtime Functionality:**
- MC CLI: mc 2.0.2 (working)
- Python: 3.12.12 (present)
- Essential tools: vim, nano, wget, openssl (all present)

## Next Phase Readiness

**Ready for Phase 21 (Version Management):**
- Multi-stage architecture established
- OCM binary integrated and functional
- ARG injection pattern proven (tested with multiple OCM versions)

**Ready for Phase 22 (Build Automation):**
- ARG OCM_VERSION parameter ready for build script injection
- Cache optimization verified (12-layer reuse on unchanged rebuild)
- Build script can inject versions via `--build-arg OCM_VERSION=X.Y.Z`

**No blockers or concerns.**

---
*Phase: 20-multi-stage-architecture-foundation*
*Completed: 2026-02-09*
