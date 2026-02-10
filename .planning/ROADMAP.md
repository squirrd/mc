# Roadmap: MC CLI Hardening Project

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- ✅ **v2.0 Containerization + Distribution** - Phases 9-14.1 (shipped 2026-02-01)
- ✅ **v2.0.1 Cleanup & Hardening** - Batch-based (shipped 2026-02-02)
- ✅ **v2.0.2 Window Tracking** - Phases 15-19 (shipped 2026-02-08)
- 🚧 **v2.0.3 Container Tools** - Phases 20-25 (in progress)

## Phases

<details>
<summary>✅ v1.0 Hardening (Phases 1-8) - SHIPPED 2026-01-22</summary>

### Phase 1: Test Infrastructure Setup
**Goal**: Establish pytest testing framework
**Plans**: 3 plans
**Status**: Complete

### Phase 2: Critical Path Testing
**Goal**: Test auth, API client, and workspace manager
**Plans**: 3 plans
**Status**: Complete

### Phase 3: Tech Debt Resolution
**Goal**: Fix hardcoded paths and configuration issues
**Plans**: 3 plans
**Status**: Complete

### Phase 4: Bug Fixes
**Goal**: Fix LDAP and typo issues
**Plans**: 2 plans
**Status**: Complete

### Phase 5: Security Hardening
**Goal**: Add validation, caching, and security features
**Plans**: 3 plans
**Status**: Complete

### Phase 6: Performance Optimization
**Goal**: Parallel downloads and caching
**Plans**: 3 plans
**Status**: Complete

### Phase 7: Type Safety
**Goal**: Full type hints and mypy validation
**Plans**: 2 plans
**Status**: Complete

### Phase 8: Logging Infrastructure
**Goal**: Structured logging with redaction
**Plans**: 2 plans
**Status**: Complete

</details>

<details>
<summary>✅ v2.0 Containerization + Distribution (Phases 9-14.1) - SHIPPED 2026-02-01</summary>

### Phase 9: Platform Detection & Container Runtime
**Goal**: Detect platform and establish Podman connection
**Plans**: 3 plans
**Status**: Complete

### Phase 10: Container Lifecycle Management
**Goal**: Create, list, stop, delete containers with state persistence
**Plans**: 3 plans
**Status**: Complete

### Phase 11: Salesforce Integration
**Goal**: Query case metadata and resolve workspace paths
**Plans**: 3 plans
**Status**: Complete

### Phase 12: Terminal Automation
**Goal**: Automatic terminal window attachment
**Plans**: 4 plans
**Status**: Complete

### Phase 13: Container Image
**Goal**: RHEL 10 UBI image with MC CLI and tools
**Plans**: 3 plans
**Status**: Complete

### Phase 14: Distribution Infrastructure
**Goal**: Modern distribution via uv tool
**Plans**: 3 plans
**Status**: Complete

### Phase 14.1: UAT Fixes (INSERTED)
**Goal**: Fix critical bugs blocking UAT
**Plans**: 5 plans
**Status**: Complete

</details>

<details>
<summary>✅ v2.0.2 Window Tracking (Phases 15-19) - SHIPPED 2026-02-08</summary>

### Phase 15: Window Registry Foundation
**Goal**: SQLite-backed window ID persistence
**Plans**: 2 plans
**Status**: Complete

### Phase 16: macOS Duplicate Prevention
**Goal**: Window tracking for iTerm2 and Terminal.app
**Plans**: 2 plans
**Status**: Complete

### Phase 17: Self-Healing Registry
**Goal**: Automatic cleanup and reconciliation
**Plans**: 2 plans
**Status**: Complete

### Phase 18: Linux X11 Support
**Goal**: Window tracking for Linux terminals
**Plans**: 2 plans
**Status**: Complete

### Phase 19: Test Suite & Validation
**Goal**: Comprehensive testing for window tracking
**Plans**: 2 plans
**Status**: Complete

</details>

## 🚧 v2.0.3 Container Tools (In Progress)

**Milestone Goal:** Multi-stage container architecture with efficient layer caching and versioned tool management

### Phase 20: Multi-Stage Architecture Foundation
**Goal**: Convert single-stage Containerfile to multi-stage pattern with verified layer caching
**Depends on**: Nothing (first phase of milestone)
**Requirements**: MULTI-01, MULTI-02, MULTI-03, MULTI-04, MULTI-05, MULTI-06, MULTI-07
**Success Criteria** (what must be TRUE):
  1. Containerfile uses named stages (mc-builder, ocm-downloader, final) with explicit FROM...AS syntax
  2. Building image twice with no changes shows "Using cache" for all stages
  3. Final stage contains only runtime artifacts (no pip, gcc, or other build tools)
  4. Final stage image is smaller than original single-stage image
  5. OCM binary exists at /usr/local/bin/ocm in final image
**Plans**: 2 plans
**Status**: Complete

Plans:
- [x] 20-01-PLAN.md — Multi-stage Containerfile with OCM integration and cache verification
- [x] 20-02-PLAN.md — Fix OCM repository (gap closure: wrong tool integrated)

### Phase 21: Version Management System
**Goal**: Establish versions.yaml as single source of truth with independent image versioning
**Depends on**: Phase 20
**Requirements**: VER-01, VER-02, VER-03, VER-04
**Success Criteria** (what must be TRUE):
  1. versions.yaml config file exists with image/mc/tools structure and valid YAML syntax
  2. Image version uses semantic versioning (x.y.z) independent from MC CLI version
  3. versions.yaml tracks MC CLI version bundled in container
  4. versions.yaml tracks OCM tool version with URL pattern
  5. Manual build can inject version ARGs from versions.yaml into Containerfile
**Plans**: 1 plan
**Status**: Complete

Plans:
- [x] 21-01-PLAN.md — Create versions.yaml config and validate manual build workflow

### Phase 22: Build Automation Core
**Goal**: Automate container builds with version extraction and orchestration
**Depends on**: Phase 21
**Requirements**: BUILD-01, BUILD-02, BUILD-03, BUILD-04, BUILD-05, BUILD-09, BUILD-10
**Success Criteria** (what must be TRUE):
  1. build-container.sh script exists in container/ directory and is executable
  2. Build script reads versions.yaml and extracts all version numbers
  3. Build script calls podman build with --build-arg flags for each version
  4. Build script tags image with semantic version (mc-rhel10:1.0.0) and :latest
  5. Build script supports --dry-run flag showing actions without building
  6. Build is architecture-aware for amd64 (foundation for future multi-arch)
**Plans**: 1 plan
**Status**: Complete

Plans:
- [x] 22-01-PLAN.md — Build automation with version extraction, validation, and orchestration

### Phase 23: Quay.io Integration
**Goal**: Query registry for latest tags and detect version staleness
**Depends on**: Phase 22
**Requirements**: VER-05, BUILD-07
**Success Criteria** (what must be TRUE):
  1. Build script can query quay.io registry API for latest published image tag
  2. Build script detects if local versions.yaml version already exists on quay.io
  3. Build script provides clear feedback about version comparison results
  4. Query failures (network, rate limit) degrade gracefully without blocking builds
**Plans**: 1 plan
**Status**: Complete

Plans:
- [x] 23-01-PLAN.md — Registry query and digest comparison with skopeo integration

### Phase 24: Auto-Versioning Logic
**Goal**: Implement intelligent patch version bumping based on digest comparison
**Depends on**: Phase 23
**Requirements**: VER-06, VER-07, BUILD-08
**Success Criteria** (what must be TRUE):
  1. Build script auto-increments patch version when building new image (1.0.5 becomes 1.0.6)
  2. Build script detects tool version changes in versions.yaml to trigger auto-bump
  3. User can manually update minor version in versions.yaml when adding new tools
  4. Build script validates version numbers follow semantic versioning format
  5. Build script prevents version conflicts (local version already exists on registry)
**Plans**: 2 plans
**Status**: Complete

Plans:
- [x] 24-01-PLAN.md — Auto-versioning logic with digest-based bumping and auto-push
- [x] 24-02-PLAN.md — Fix semver validation to reject leading zeros (gap closure)

### Phase 25: Registry Publishing & OCM Verification
**Goal**: Publish versioned images to quay.io and verify OCM tool integration end-to-end
**Depends on**: Phase 24
**Requirements**: BUILD-06, TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07
**Success Criteria** (what must be TRUE):
  1. Build script validates registry credentials before building (pre-flight check)
  2. Registry authentication stored persistently in MC base directory
  3. Published image has both versioned tag (1.0.0) and :latest tag
  4. OCM downloader stage fetches ocm-linux-amd64 binary from GitHub releases using ARG OCM_VERSION
  5. Running `ocm version` in container returns version matching versions.yaml
  6. OCM download includes SHA256 checksum verification that fails build on mismatch
  7. OCM binary is executable and functional (not just present)
**Plans**: 2 plans

Plans:
- [ ] 25-01-PLAN.md — Registry authentication and pre-flight credential validation
- [ ] 25-02-PLAN.md — OCM integration testing and version verification

## Progress

**Execution Order:**
Phases execute in numeric order: 20 → 21 → 22 → 23 → 24 → 25

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Test Infrastructure Setup | v1.0 | 3/3 | Complete | 2026-01-22 |
| 2. Critical Path Testing | v1.0 | 3/3 | Complete | 2026-01-22 |
| 3. Tech Debt Resolution | v1.0 | 3/3 | Complete | 2026-01-22 |
| 4. Bug Fixes | v1.0 | 2/2 | Complete | 2026-01-22 |
| 5. Security Hardening | v1.0 | 3/3 | Complete | 2026-01-22 |
| 6. Performance Optimization | v1.0 | 3/3 | Complete | 2026-01-22 |
| 7. Type Safety | v1.0 | 2/2 | Complete | 2026-01-22 |
| 8. Logging Infrastructure | v1.0 | 2/2 | Complete | 2026-01-22 |
| 9. Platform Detection & Container Runtime | v2.0 | 3/3 | Complete | 2026-02-01 |
| 10. Container Lifecycle Management | v2.0 | 3/3 | Complete | 2026-02-01 |
| 11. Salesforce Integration | v2.0 | 3/3 | Complete | 2026-02-01 |
| 12. Terminal Automation | v2.0 | 4/4 | Complete | 2026-02-01 |
| 13. Container Image | v2.0 | 3/3 | Complete | 2026-02-01 |
| 14. Distribution Infrastructure | v2.0 | 3/3 | Complete | 2026-02-01 |
| 14.1. UAT Fixes | v2.0 | 5/5 | Complete | 2026-02-01 |
| 15. Window Registry Foundation | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 16. macOS Duplicate Prevention | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 17. Self-Healing Registry | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 18. Linux X11 Support | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 19. Test Suite & Validation | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 20. Multi-Stage Architecture Foundation | v2.0.3 | 2/2 | Complete | 2026-02-09 |
| 21. Version Management System | v2.0.3 | 1/1 | Complete | 2026-02-09 |
| 22. Build Automation Core | v2.0.3 | 1/1 | Complete | 2026-02-10 |
| 23. Quay.io Integration | v2.0.3 | 1/1 | Complete | 2026-02-10 |
| 24. Auto-Versioning Logic | v2.0.3 | 2/2 | Complete | 2026-02-10 |
| 25. Registry Publishing & OCM Verification | v2.0.3 | 0/2 | Not started | - |
