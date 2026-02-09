# Requirements: MC v2.0.3 Container Tools

**Defined:** 2026-02-09
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently

## v2.0.3 Requirements

Requirements for multi-stage container architecture with efficient layer caching and versioned tool management.

### Multi-Stage Build Architecture

- [ ] **MULTI-01**: Containerfile uses named stages (mc-builder, ocm-downloader, final) for explicit dependencies
- [ ] **MULTI-02**: Containerfile accepts ARG parameters for version injection from build script
- [ ] **MULTI-03**: Final stage uses COPY --from=stage pattern to copy only runtime artifacts
- [ ] **MULTI-04**: Building image twice (no changes) shows "Using cache" for all stages (layer caching works)
- [ ] **MULTI-05**: Downloader stages use minimal base images (RHEL minimal) for faster builds
- [ ] **MULTI-06**: Final stage contains only runtime dependencies (no build tools like pip, gcc)
- [ ] **MULTI-07**: Final stage uses RHEL 10 UBI as base image

### Version Management

- [x] **VER-01**: versions.yaml config file exists with image/mc/tools structure
- [x] **VER-02**: Image version uses semantic versioning (x.y.z) independent from MC CLI version
- [x] **VER-03**: versions.yaml tracks MC CLI version to bundle
- [x] **VER-04**: versions.yaml tracks OCM tool version and other tools when they are added
- [x] **VER-05**: Build script can query quay.io registry API for latest published image tag
- [ ] **VER-06**: Build script auto-increments patch version when building new image (1.0.5 → 1.0.6)
- [ ] **VER-07**: User manually updates minor version in versions.yaml when adding new tools (y in x.y.z)

### Build Automation

- [ ] **BUILD-01**: build-container.sh script exists in container/ directory
- [ ] **BUILD-02**: Build script reads versions.yaml and extracts all version numbers
- [ ] **BUILD-03**: Build script calls podman build with --build-arg flags for each version
- [ ] **BUILD-04**: Build script tags image with semantic version (mc-rhel10:1.0.0)
- [ ] **BUILD-05**: Build script also tags image as :latest (mc-rhel10:latest)
- [ ] **BUILD-06**: Build script supports --push flag to publish to quay.io registry
- [x] **BUILD-07**: Build script queries quay.io for latest tag before building
- [ ] **BUILD-08**: Build script auto-bumps patch version from quay.io latest (1.0.5 becomes 1.0.6)
- [ ] **BUILD-09**: Build script supports --dry-run flag showing actions without building
- [ ] **BUILD-10**: Build is architecture aware and can build for different architectures (limit to amd64 for v2.0.3)

### Tool Packaging (OCM POC)

- [ ] **TOOL-01**: OCM downloader stage fetches ocm-linux-amd64 binary from GitHub releases
- [ ] **TOOL-02**: OCM downloader stage uses ARG OCM_VERSION from versions.yaml
- [ ] **TOOL-03**: OCM binary copied to /usr/local/bin/ocm in final stage
- [ ] **TOOL-04**: Running `ocm version` in container returns version matching versions.yaml
- [ ] **TOOL-05**: OCM downloader stage supports TARGETARCH for amd64 vs arm64 selection
- [ ] **TOOL-06**: OCM download includes SHA256 checksum verification
- [ ] **TOOL-07**: Build fails if OCM checksum doesn't match expected value

## Future Requirements

Deferred to future milestones.

### Build Enhancements

- **BUILD-11**: Post-build validation (docker inspect confirms tags match versions.yaml)
- **BUILD-12**: Build target selection (--target flag) for testing individual stages
- **VER-08**: Version relationship policy enforcement (automated governance rules)

### Tool Packaging Expansion

- **TOOL-08**: Runtime dependency verification (ldd check for missing libs)
- **TOOL-09**: oc CLI tool integration (prove pattern scales)
- **TOOL-10**: aws CLI tool integration (Python package vs binary pattern)
- **TOOL-11**: backplane CLI tool integration
- **TOOL-12**: osdctl tool integration
- **TOOL-13**: rh-aws-saml-login tool integration
- **TOOL-14**: Claude Code tool integration

## Out of Scope

Explicitly excluded from this milestone.

| Feature | Reason |
|---------|--------|
| Automated version discovery | Too complex - requires GitHub/quay.io webhooks, CI integration; manual version updates sufficient for v2.0.3 |
| Full tool suite (all 7 tools) | OCM as POC first - validate pattern works before scaling complexity |
| Tool runtime configuration mounting | Focus on packaging, not configuration - OCM binary works but not authenticated; defer to future milestone |
| Multi-platform manifest building | Single platform sufficient - user's dev platform matches production; defer until multi-platform need validated |
| Stage-level cache pushing | Advanced optimization - requires intermediate stage publishing; defer until base pattern proven |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| MULTI-01 | Phase 20 | Complete |
| MULTI-02 | Phase 20 | Complete |
| MULTI-03 | Phase 20 | Complete |
| MULTI-04 | Phase 20 | Complete |
| MULTI-05 | Phase 20 | Complete |
| MULTI-06 | Phase 20 | Complete |
| MULTI-07 | Phase 20 | Complete |
| VER-01 | Phase 21 | Pending |
| VER-02 | Phase 21 | Pending |
| VER-03 | Phase 21 | Pending |
| VER-04 | Phase 21 | Pending |
| VER-05 | Phase 23 | Complete |
| VER-06 | Phase 24 | Pending |
| VER-07 | Phase 24 | Pending |
| BUILD-01 | Phase 22 | Complete |
| BUILD-02 | Phase 22 | Complete |
| BUILD-03 | Phase 22 | Complete |
| BUILD-04 | Phase 22 | Complete |
| BUILD-05 | Phase 22 | Complete |
| BUILD-06 | Phase 25 | Pending |
| BUILD-07 | Phase 23 | Complete |
| BUILD-08 | Phase 24 | Pending |
| BUILD-09 | Phase 22 | Complete |
| BUILD-10 | Phase 22 | Complete |
| TOOL-01 | Phase 25 | Pending |
| TOOL-02 | Phase 25 | Pending |
| TOOL-03 | Phase 25 | Pending |
| TOOL-04 | Phase 25 | Pending |
| TOOL-05 | Phase 25 | Pending |
| TOOL-06 | Phase 25 | Pending |
| TOOL-07 | Phase 25 | Pending |

**Coverage:**
- v2.0.3 requirements: 28 total
- Mapped to phases: 28/28 (100% coverage)
- Unmapped: 0

**Coverage by phase:**
- Phase 20 (Multi-Stage Architecture Foundation): 7 requirements
- Phase 21 (Version Management System): 4 requirements
- Phase 22 (Build Automation Core): 7 requirements
- Phase 23 (Quay.io Integration): 2 requirements
- Phase 24 (Auto-Versioning Logic): 3 requirements
- Phase 25 (Registry Publishing & OCM Verification): 7 requirements

---
*Requirements defined: 2026-02-09*
*Last updated: 2026-02-09 after roadmap creation (100% coverage validated)*
