# Phase 20: Multi-Stage Architecture Foundation - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Convert single-stage Containerfile to multi-stage build pattern with layer caching optimization and minimal runtime-only final image. This phase establishes the architectural foundation for efficient container builds.

</domain>

<decisions>
## Implementation Decisions

### Stage naming & organization
- Use descriptive stage names: `ocm-downloader`, `mc-builder`, `final`
- Stage order: Downloader → Builder → Final
- Strict separation: each stage contains only its required dependencies
  - ocm-downloader: curl and download tools only
  - mc-builder: pip, gcc, python-devel for building MC CLI
  - final: runtime dependencies only (no build tools)
- Moderate commenting: between minimal and detailed, less verbose than current Containerfile

### Cache optimization strategy
- Version changes trigger cache invalidation (ARG version changes force rebuild)
- Automated test script to validate caching (build twice, assert cache hits)
- Optimize for both local development and CI/CD equally

### OCM integration approach
- SHA256 checksum verification during download (fail build immediately on mismatch)
- Fail fast error handling (no retries, build stops immediately on download failure)
- OCM binary placed at `/usr/local/bin/ocm` (standard PATH location per success criteria)

### Final image composition
- MC CLI: copy everything required for MC functionality from mc-builder
- OCM: minimal binary only at /usr/local/bin/ocm (configuration deferred to future phase)
- Runtime dependencies: minimal set, preserve existing tools from original Containerfile where needed for requirements/integration tests
- Aggressive size optimization: target <500MB final image
- Permissions: preserve existing features from original container where part of requirements or integration testing

### Claude's Discretion
- Layer ordering within stages for maximum cache efficiency
- Download mechanism for OCM binary (GitHub releases API approach)
- Exact runtime dependencies beyond Python interpreter
- Permission/ownership details following container security best practices
- Specific cache verification script implementation

</decisions>

<specifics>
## Specific Ideas

- Success criteria explicitly requires final stage smaller than original single-stage image
- Success criteria requires "Using cache" validation on unchanged rebuild
- Success criteria requires OCM binary at /usr/local/bin/ocm specifically
- Existing Containerfile has too much detail in comments - reduce verbosity
- Original container has features needed for requirements/integration tests - preserve these

</specifics>

<deferred>
## Deferred Ideas

- OCM configuration and setup (deferred to future phase)

</deferred>

---

*Phase: 20-multi-stage-architecture-foundation*
*Context gathered: 2026-02-09*
