---
phase: 24-auto-versioning-logic
plan: 01
subsystem: infra
tags: [container, versioning, semver, registry, digest, automation]

# Dependency graph
requires:
  - phase: 23-quay.io-integration
    provides: Registry query with skopeo, digest comparison, exponential backoff retry logic
  - phase: 22-build-automation
    provides: Build script with yq version extraction and podman build orchestration
  - phase: 21-version-management
    provides: versions.yaml schema with image and tool version tracking

provides:
  - Intelligent patch version auto-bumping based on digest comparison
  - Registry-as-source-of-truth for current patch versions
  - No-op behavior when image unchanged (digest match)
  - Version conflict detection before push
  - Semantic version validation against semver 2.0.0 spec
  - Auto-push new versions with versioned and latest tags

affects: [25-registry-publishing, future-multi-arch-builds, container-ci-cd]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Minor version (x.y) in versions.yaml, patch auto-calculated from registry"
    - "Digest comparison as bump trigger (not file changes)"
    - "Registry query → build → compare → bump decision → push workflow"
    - "Fail-fast on version conflicts (race condition detection)"
    - "Temporary tag during build, retag after version calculation"

key-files:
  created: []
  modified:
    - container/versions.yaml
    - container/build-container.sh

key-decisions:
  - "Store only minor version (x.y) in versions.yaml to prevent merge conflicts"
  - "Registry determines current patch version, preventing conflicts when multiple developers build"
  - "Digest comparison triggers bump (not file changes or timestamps)"
  - "No --push flag: auto-push on digest differ is always behavior"
  - "Build with temp tag, compare digest, then retag and push if needed"
  - "Fail fast on version conflict (version already exists when shouldn't)"

patterns-established:
  - "validate_semver() uses official semver 2.0.0 regex: ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$"
  - "find_latest_patch() queries registry with grep -E and sort -V for version-aware sorting"
  - "auto_version_and_push() orchestrates: query → build → compare → bump → validate → push"
  - "No-op return when digest matches (skip bump and push)"
  - "check_version_exists() before push prevents race conditions"

# Metrics
duration: 4min
completed: 2026-02-10
---

# Phase 24 Plan 01: Auto-Versioning Logic Summary

**Intelligent patch version bumping with digest-based change detection, registry-as-source-of-truth, and automatic publishing to quay.io**

## Performance

- **Duration:** 4 min
- **Started:** 2026-02-10T00:20:58Z
- **Completed:** 2026-02-10T00:25:50Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Minor version (x.y) stored in versions.yaml, patch auto-calculated from registry state
- Digest-based bump decision: compares local vs registry digest to determine if push needed
- No-op behavior when image unchanged (digest match): skips bump and push
- Version conflict detection before push: fails if calculated version already exists
- Auto-push new versions with both versioned tag (x.y.z) and latest tag
- Semantic version validation against semver 2.0.0 specification (rejects leading zeros, missing components)

## Task Commits

Each task was committed atomically:

1. **Task 1: Update versions.yaml schema to minor version format** - `1265a38` (refactor)
2. **Task 2: Implement auto-versioning logic with digest-based bumping** - `4ea22d7` (feat)

## Files Created/Modified

- `container/versions.yaml` - Changed image.version from "1.0.0" to "1.0" (x.y format), added comment explaining patch auto-calculation
- `container/build-container.sh` - Added validate_semver(), find_latest_patch(), auto_version_and_push() functions; replaced perform_build() workflow; updated extract_and_validate_versions() for minor version format; modified output_json() for bumped/pushed status

## Decisions Made

**1. Minor version format in versions.yaml**
- Store only x.y (not x.y.z) to prevent merge conflicts when multiple developers build
- Registry tag list becomes source of truth for current patch number
- Aligns with CONTEXT.md decision: "versions.yaml contains `image.version: "x.y"` (e.g., "1.2") — manually managed minor version"

**2. Digest comparison as bump trigger**
- Build image first (always), then compare digest with registry
- Digest comparison is authoritative (not file timestamps or git diff)
- Immune to comment/whitespace changes that don't affect image content
- No --force-bump override: digest match = skip push (no-op)

**3. Registry as source of truth**
- find_latest_patch() queries registry for latest x.y.* tag matching minor version
- Returns -1 if no tags found (first build creates x.y.0)
- Prevents version conflicts when multiple builds occur simultaneously
- Fail-fast if calculated version already exists (race condition detection)

**4. Auto-push on digest differ**
- No --push flag required: content change automatically triggers publish
- Tags both versioned (x.y.z) and :latest before pushing
- Follows CONTEXT.md decision: "When digest differs: automatically push to quay.io after tagging"

**5. Semantic version validation**
- validate_semver() uses official semver 2.0.0 regex
- Rejects leading zeros (01.2.3), missing components (1.2), non-integers (1.a.3)
- Applied before tagging and pushing to ensure registry compliance

**6. Temporary tag during build**
- Build with mc-rhel10:temp tag (not :latest)
- Extract digest from temp tag
- Compare with registry digest
- Only tag as versioned and :latest after bump decision
- Prevents pollution of :latest tag when digest matches

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - implementation followed RESEARCH.md patterns and CONTEXT.md workflow specification.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 25 (Registry Publishing):**
- Auto-versioning system complete with digest-based bumping
- Registry query established with exponential backoff retry
- Version conflict detection prevents race conditions
- Auto-push capability proven with quay.io integration

**Notes for Phase 25:**
- Current implementation builds and pushes amd64 only (Phase 22 decision)
- Phase 25 may add multi-arch manifest creation (amd64 + arm64)
- Auto-versioning logic already supports this: digest comparison works regardless of architecture
- May need to enhance find_latest_patch() to handle manifest list digests

**Blockers/Concerns:**
None - all success criteria met, dry-run tested, validation logic proven.

---
*Phase: 24-auto-versioning-logic*
*Completed: 2026-02-10*
