---
phase: 21-version-management-system
plan: 01
subsystem: infra
tags: [versioning, yaml, semantic-versioning, container-build, yq]

# Dependency graph
requires:
  - phase: 20-multi-stage-architecture-foundation
    provides: Multi-stage Containerfile with ARG injection architecture
provides:
  - versions.yaml single source of truth for image/MC/tool versions
  - Independent image versioning (1.0.0) decoupled from MC CLI version (2.0.2)
  - OCM tool metadata with URL template pattern ({version}, {arch} placeholders)
  - Validated manual build workflow demonstrating version extraction and injection
affects: [22-build-automation, 23-quay-container-registry, 24-auto-versioning-workflow, 25-container-publishing-pipeline]

# Tech tracking
tech-stack:
  added: [yq (YAML parsing)]
  patterns: [URL template substitution, semantic versioning validation, single source of truth configuration]

key-files:
  created: [container/versions.yaml]
  modified: []

key-decisions:
  - "Independent image versioning (1.0.0) decoupled from MC CLI version (2.0.2) enables tool updates without code releases"
  - "URL template pattern with {version} and {arch} placeholders enables version changes without URL modifications"
  - "Nested YAML schema: image/mc/tools sections for clear organization"
  - "yq command-line tool for YAML parsing in build scripts (standard practice for container builds)"

patterns-established:
  - "versions.yaml as single source of truth: Manual workflow: yq extract → podman build --build-arg → verify in container"
  - "Semantic versioning (x.y.z) enforced for all version fields"
  - "Tool metadata format: version, url (template), checksum, description"

# Metrics
duration: 2min
completed: 2026-02-09
---

# Phase 21 Plan 01: Version Management System Summary

**Independent image versioning (1.0.0) decoupled from MC CLI version (2.0.2) with versions.yaml single source of truth and validated manual build workflow**

## Performance

- **Duration:** 2 minutes 28 seconds
- **Started:** 2026-02-09T13:29:47Z
- **Completed:** 2026-02-09T13:32:15Z
- **Tasks:** 2
- **Files modified:** 1 created

## Accomplishments

- Created versions.yaml as single source of truth for container image, MC CLI, and tool versions
- Established independent image versioning (1.0.0) decoupled from MC CLI version (2.0.2)
- Implemented OCM tool metadata with URL template pattern using {version} and {arch} placeholders
- Validated manual build workflow: extracted OCM version from YAML, injected into container build, verified in running container
- Demonstrated version override flexibility by building with different OCM version (1.0.8)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create versions.yaml with nested schema and initial versions** - `0e645a0` (feat)
2. **Task 2: Validate manual build workflow with version injection** - `3d0124d` (test)

## Files Created/Modified

- `container/versions.yaml` - Single source of truth configuration with nested schema (image, mc, tools sections), semantic versioning for all components, OCM tool metadata with URL template pattern

## Decisions Made

**Schema structure:**
- Nested organization: image/mc/tools sections for clarity and extensibility
- Tool metadata format: version, url (template), checksum, description per tool
- URL templates with {version} and {arch} placeholders for flexibility

**Version numbering:**
- Independent image version (1.0.0) starting point separate from MC CLI version (2.0.2)
- Enables tool updates without requiring MC CLI code releases
- All versions use semantic versioning format (x.y.z)

**Build workflow:**
- Manual workflow pattern established: yq extract from YAML → inject via --build-arg → verify in container
- Proven that Phase 20 ARG injection architecture works seamlessly with versions.yaml
- Build automation (Phase 22) will replicate this exact pattern

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without problems.

## Validation Results

**YAML schema validation:**
- YAML syntax valid (yq parse successful)
- All three sections present (image, mc, tools)
- All version fields use semantic versioning (x.y.z)

**Version extraction validation:**
- Image version: 1.0.0 (extracted successfully)
- MC version: 2.0.2 (extracted successfully)
- OCM version: 1.0.10 (extracted successfully)
- OCM URL template contains {version} and {arch} placeholders

**Manual build workflow validation:**
- Container built successfully with OCM version extracted from versions.yaml (1.0.10)
- OCM binary version in running container matches versions.yaml specification
- Version override tested: Built with OCM 1.0.8, verified correct version in container
- ARG injection architecture from Phase 20 works end-to-end with versions.yaml

**Requirements coverage:**
- VER-01: versions.yaml exists with image/mc/tools structure ✓
- VER-02: Image version uses semantic versioning independent from MC CLI version ✓
- VER-03: versions.yaml tracks MC CLI version (2.0.2) ✓
- VER-04: versions.yaml tracks OCM tool version (1.0.10) ✓

## Next Phase Readiness

**Phase 22 (Build Automation) ready to proceed:**
- Single source of truth established for all version information
- yq parsing pattern proven functional for version extraction
- ARG injection mechanism validated end-to-end
- Manual workflow demonstrated in Task 2 can be directly replicated in build script
- URL template substitution pattern documented and tested
- Independent image versioning enables automated version bumping without MC CLI dependencies

**No blockers or concerns.**

---
*Phase: 21-version-management-system*
*Completed: 2026-02-09*
