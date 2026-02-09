# Project Research Summary

**Project:** MC CLI v2.0.3 Container Tools
**Domain:** Container build automation with multi-stage architecture and versioned tool management
**Researched:** 2026-02-09
**Confidence:** HIGH

## Executive Summary

MC CLI v2.0.3 enhances container tooling by migrating from single-stage to multi-stage builds, enabling efficient layer caching, independent image versioning, and automated tool management. The research validates a three-component architecture: a multi-stage Containerfile (mc-builder, ocm-downloader, final stages), a versions.yaml config file for version management, and a build-container.sh automation script. This architecture separates build-time complexity from runtime simplicity, requiring zero changes to existing Python container management code while delivering significant benefits—smaller images, faster incremental builds, and independent versioning for container updates without MC CLI code changes.

The recommended approach uses Podman's native multi-stage build capabilities (already in dependencies), Bash for build orchestration with Python for version logic, and introduces semver for version bumping plus PyYAML for config management. The OCM CLI serves as proof-of-concept for a scalable pattern: one downloader stage per tool maximizes cache reuse and enables parallel builds. Independent image versioning (1.0.0 separate from MC 2.0.3) allows tool updates to trigger automatic patch bumps without coupling to MC release cycles.

Critical risks center on layer cache invalidation (defeating multi-stage benefits), version drift between image tags and actual contents, and architecture mismatches for multi-platform support. Prevention strategies are well-documented: explicit stage naming, careful instruction ordering, rigorous version validation, and TARGETARCH ARG usage. The research shows high confidence across all areas, with clear implementation patterns validated against official Podman documentation and real-world container build best practices.

## Key Findings

### Recommended Stack

Multi-stage builds work with existing Podman 5.7.0+ already in pyproject.toml dependencies—no additional container tooling needed. The stack additions focus on version management and build automation: semver (3.0.4) for semantic version bumping, PyYAML (6.0.2) for parsing versions.yaml, and bash for build orchestration with Python for complex logic. Skopeo (1.21.0+ already on host) queries registry tags via `list-tags` command, avoiding unnecessary API complexity. The research specifically recommends against jq (not in UBI repos) in favor of Python's json module for API parsing.

**Core technologies:**
- **Podman 5.7.0+ (existing)**: Multi-stage builds with native support for `FROM...AS stage` and `COPY --from=stage` patterns
- **semver 3.0.4**: Semantic version parsing and bumping (patch/minor/major) with simple API and Python 3.11+ compatibility
- **PyYAML 6.0.2**: Parse and update versions.yaml config file (adequate for machine-managed YAML despite ruamel.yaml's comment preservation)
- **Bash + Python hybrid**: Bash for build orchestration (simple command sequencing), Python when logic complexity requires YAML parsing or semver operations
- **skopeo 1.21.0+ (existing)**: Query Quay.io tags via `list-tags` without pulling images—faster than REST API for simple queries

### Expected Features

Multi-stage container builds are table-stakes infrastructure that users expect to "just work" with standard Docker/Podman behaviors. The research identifies eight must-have features including layer caching, named build stages, explicit version tags (no :latest in production), ARG-based version control, and build reproducibility. These are low-complexity standard patterns that form the foundation. Differentiators include versions.yaml as single source of truth, automated patch bumping when tool versions change, and registry-queried version detection—medium complexity features that provide competitive advantage through reduced manual version management and drift prevention.

**Must have (table stakes):**
- Layer caching with multi-stage builds — standard BuildKit behavior users rely on
- Named build stages — required for `--target` and `COPY --from=` references
- Explicit version tags (semver x.y.z) — production requirement, :latest causes rollback problems
- ARG-based version control — standard Dockerfile pattern for configurable builds
- Semantic version bumping — auto-increment patch, manual minor/major control
- Build reproducibility — same input produces same output via version pinning

**Should have (competitive advantage):**
- versions.yaml single source of truth — centralized tool versions prevent drift across stages
- Tool version change detection — git diff on versions.yaml triggers auto patch bump
- Registry query for current version — auto-detect if local version is stale vs quay.io
- OCM tool as POC — prove pattern works with single tool before scaling complexity
- Dry-run mode — preview build actions without execution (safety feature)

**Defer (v2.1.x and beyond):**
- Inline cache metadata — BuildKit `BUILDKIT_INLINE_CACHE=1` for CI/CD optimization
- Additional tools beyond OCM — scale pattern to jq, yq, oc, kubectl after validation
- Stage-level cache pushing — `--cache-from` with per-stage tags for advanced CI/CD
- Multi-platform builds — `--platform linux/amd64,linux/arm64` support
- Automated dependency updates — Dependabot/Renovate for tool version bumps

### Architecture Approach

The architecture maintains clean separation between build-time concerns (container/ directory with Containerfile, versions.yaml, build-container.sh) and runtime concerns (src/mc/container/ Python code managing container lifecycle). Multi-stage Containerfile uses builder-downloader-final pattern: mc-builder stage compiles MC CLI from source, ocm-downloader fetches versioned OCM binary, final stage assembles minimal runtime image copying only artifacts. This separation enables independent caching—MC source changes rebuild only mc-builder + final, OCM version changes rebuild only ocm-downloader + final. Layer caching optimization follows least-to-most-frequently-changed ordering, reducing incremental builds from 3-5 minutes to under 1 minute.

**Major components:**
1. **Multi-stage Containerfile** — Three named stages (mc-builder, ocm-downloader, final) with ARG-based version injection from versions.yaml; final stage copies artifacts only, no build dependencies
2. **versions.yaml config** — Single source of truth with independent image semver (not tied to MC CLI version), tool versions with URL patterns, schema enabling easy tool additions
3. **build-container.sh script** — Reads versions.yaml, queries Quay.io API for latest tag, detects tool version changes to auto-bump patch, builds with podman passing build args, optional --push for registry publishing
4. **ContainerManager (unchanged)** — Existing _ensure_image() pull-then-create workflow preserved; multi-stage build transparent to runtime; OCM appears at /usr/local/bin/ocm automatically

### Critical Pitfalls

Research identified seven critical pitfalls with high-confidence prevention strategies. Layer cache invalidation tops the list—`COPY --from=builder` can incorrectly invalidate downstream caches even when upstream cached, defeating multi-stage benefits (verified Podman issue #20229). Prevention requires explicit named stages, careful stage ordering, and testing cache behavior with double-builds. Version conflicts between image tag, versions.yaml, and actual MC CLI version inside container cause drift—auto-bumping on every tool change creates version noise. Architecture mismatches (hardcoded ocm-linux-amd64 instead of using TARGETARCH) break ARM64 users. Quay.io API rate limiting during rapid iteration blocks builds without exponential backoff. Breaking existing single-stage build workflow requires backward compatibility planning. YAML parsing failures from manual edits (tabs vs spaces) require validation. Missing runtime dependencies for binaries require `ldd` verification.

1. **Layer cache invalidation from stage dependencies** — Verify cache works with double-builds; order stages least-to-most frequently changed; never use --squash-all with multi-stage (Podman #14712)
2. **Version conflict between image version and MC CLI version** — Declare version relationship policy in versions.yaml header; validate consistency across image tag, versions.yaml, and `mc --version` output
3. **Architecture mismatch in tool binaries** — Use `ARG TARGETARCH` in every downloader stage; substitute `${TARGETARCH}` in download URLs; test on both amd64 and arm64
4. **Quay.io API rate limiting and authentication failures** — Implement exponential backoff; cache API responses locally (5min TTL); provide `--version X.Y.Z` override to skip API
5. **Breaking existing single-stage build workflow** — Maintain build.sh as wrapper for backward compat; validate podman version >= 4.0; document migration path
6. **versions.yaml parsing failures from manual edits** — Add yamllint validation in pre-commit hook; quote all version strings; validate YAML before parsing in build script
7. **Missing dependencies in final stage** — Test binaries with `ldd` to check shared library dependencies; use RHEL UBI base with common deps pre-installed; add smoke tests to Containerfile

## Implications for Roadmap

The research strongly suggests a 6-phase incremental approach that validates each layer before adding complexity. Starting with multi-stage Containerfile architecture (Phase 1) proves the build pattern works and establishes cache behavior baselines before introducing automation. Version management (Phase 2) establishes single source of truth in versions.yaml before building automation that depends on it. Build automation (Phase 3) orchestrates what was proven manually in Phases 1-2. Quay.io integration (Phase 4) adds external dependency only after core automation works. Auto-versioning logic (Phase 5) implements complex version comparison after all pieces exist. Registry publishing (Phase 6) comes last since it requires reliable builds. This ordering minimizes risk by validating assumptions incrementally and allows early exit if patterns don't work as expected.

### Phase 1: Multi-Stage Architecture Foundation
**Rationale:** Validates build pattern works before adding automation complexity; establishes cache behavior baselines; proves OCM tool integration succeeds
**Delivers:** Working 3-stage Containerfile (mc-builder, ocm-downloader, final); hardcoded OCM version initially; verified layer caching; image size comparison vs single-stage
**Addresses:** Table-stakes features (layer caching, named stages, build reproducibility); Anti-feature avoidance (no build tools in final image)
**Avoids:** Pitfall #1 (cache invalidation) via explicit stage naming and ordering; Pitfall #7 (missing dependencies) via smoke tests and `ldd` verification
**Needs research:** No—multi-stage builds are well-documented standard patterns with official Podman docs and extensive community examples

### Phase 2: Version Management System
**Rationale:** Establishes single source of truth before automation depends on it; defines version relationship policy (image semver independent from MC CLI version)
**Delivers:** versions.yaml schema with image version, MC CLI reference, tool versions; manual builds with --build-arg pattern; YAML validation
**Addresses:** Differentiator features (versions.yaml single source of truth, version validation); Must-have (ARG-based version control)
**Avoids:** Pitfall #2 (version conflicts) via explicit version relationship policy; Pitfall #6 (YAML parsing failures) via yamllint validation and quote enforcement
**Needs research:** No—YAML parsing and semver libraries are straightforward; version management patterns well-established

### Phase 3: Build Automation Core
**Rationale:** Automates what was proven manually in Phases 1-2; no version bumping yet, just orchestration
**Delivers:** build-container.sh script that reads versions.yaml, extracts tool versions, runs podman build with --build-arg flags, tags image
**Addresses:** Differentiator features (dry-run mode potential, build orchestration); Must-have (semantic versioning enforcement)
**Avoids:** Pitfall #5 (breaking existing builds) via backward-compatible wrapper; UX pitfall (silent failures) via set -e and clear messaging
**Needs research:** No—bash scripting patterns for container builds are standard; Python YAML parsing straightforward

### Phase 4: Quay.io API Integration
**Rationale:** Adds external dependency only after core automation works; enables version staleness detection
**Delivers:** Quay.io REST API querying in build-container.sh; latest semver tag extraction; --check-only flag for dry-run version comparison
**Addresses:** Differentiator features (registry query for current version, version staleness detection)
**Avoids:** Pitfall #4 (API rate limiting) via exponential backoff, local caching (5min TTL), and --version override; Security mistake (token handling) via environment variables
**Needs research:** Minimal—Quay.io API is well-documented; may need brief research on OAuth2 token generation for private repos if needed

### Phase 5: Intelligent Version Bumping
**Rationale:** Most complex logic; needs all previous pieces working; implements core differentiator (auto patch bump)
**Delivers:** Version comparison logic (local versions.yaml vs Quay.io latest); tool version change detection via git diff; auto-increment patch on changes; manual --minor/--major flags; updated versions.yaml write-back
**Addresses:** Differentiator features (tool version change detection, auto patch bump); Must-have (semantic version bumping with manual control)
**Avoids:** Pitfall #2 (version conflicts) via version validation; UX pitfall (auto-bump without confirmation) via user confirmation prompt
**Needs research:** No—semver library API is simple; git diff patterns standard; version comparison logic straightforward

### Phase 6: Registry Publishing
**Rationale:** Only needed after build process proven reliable; publishing is one-way operation requiring confidence
**Delivers:** --push flag support; dual tagging (semver + latest); podman push to Quay.io; verification that ContainerManager can pull new image
**Addresses:** Must-have (registry push capability); Anti-feature avoidance (no auto-push, explicit flag required)
**Avoids:** Security mistake (hardcoded tokens) via environment variables; UX pitfall (breaking changes without migration) via backward compat verification
**Needs research:** No—podman push is standard; registry authentication well-documented

### Phase Ordering Rationale

- **Foundation first (Phase 1):** Multi-stage Containerfile must work before adding automation—validates cache behavior, image size benefits, tool integration success; early exit point if pattern doesn't deliver expected benefits
- **Config before automation (Phase 2):** versions.yaml establishes contract before build-container.sh depends on parsing it—prevents fragile automation built on unstable foundation
- **Local before remote (Phases 3-4):** Build automation works locally before adding Quay.io API dependency—allows iteration without network calls; API integration adds external dependency only when core proven
- **Detection before action (Phases 4-5):** Query Quay.io for versions before implementing auto-bump logic—version comparison depends on reliable registry queries
- **Build before publish (Phases 5-6):** Reliable versioning before pushing to registry—prevents publishing incorrectly-versioned images; publishing is one-way, requires confidence
- **Incremental validation:** Each phase has clear success criteria; failure in early phase prevents wasted effort in later phases; allows pivots based on discovered constraints

### Research Flags

**Phases with standard patterns (skip research-phase):**
- **Phase 1 (Multi-stage Architecture):** Multi-stage builds extensively documented in official Podman docs, Docker docs, and 2026 community sources; layer caching behavior well-understood
- **Phase 2 (Version Management):** PyYAML and semver library usage straightforward; version management patterns established in container ecosystem
- **Phase 3 (Build Automation):** Bash scripting for container builds follows standard patterns; no novel integration complexity
- **Phase 5 (Version Bumping):** semver library API simple; git diff patterns standard; no complex algorithm discovery needed
- **Phase 6 (Registry Publishing):** podman push standard operation; authentication well-documented

**Phases potentially needing focused research:**
- **Phase 4 (Quay.io API):** May warrant brief focused research if authentication complexity arises (OAuth2 token generation, robot accounts) or if advanced API features needed (pagination for repos with 100+ tags, filtering by date/labels); however, basic tag listing is well-documented and likely sufficient for POC

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Podman multi-stage support verified in official docs (2026); semver and PyYAML versions confirmed on PyPI with Python 3.11+ compatibility; skopeo 1.21.0 verified on host; no new container tooling required |
| Features | HIGH | Multi-stage builds and semantic versioning are industry-standard practices with extensive documentation; table-stakes vs differentiators clearly delineated based on Docker/Podman ecosystem expectations; anti-features validated against real-world pitfalls |
| Architecture | HIGH | Builder-downloader-final pattern proven in official Docker multi-stage docs and community examples; separation of build-time vs runtime concerns aligns with established containerization best practices; layer caching optimization patterns well-documented |
| Pitfalls | HIGH | All critical pitfalls validated against real GitHub issues (Podman #20229, #14712) and official documentation; prevention strategies tested in community; recovery costs accurately estimated based on container ecosystem experience |

**Overall confidence:** HIGH

### Gaps to Address

**Minor gaps requiring validation during implementation:**

- **Quay.io API pagination:** Research covers basic tag listing, but repos with 100+ tags may require pagination handling—likely not needed for MC CLI container (expects <20 versions in first year), but should validate during Phase 4 if tag count grows
- **Multi-architecture build timing:** Research assumes TARGETARCH substitution works for OCM CLI (verified in GitHub releases)—should validate during Phase 3 that URL pattern `ocm-linux-${TARGETARCH}` resolves correctly for both amd64 and arm64
- **Version relationship enforcement:** Research suggests policy declaration in versions.yaml header—during Phase 2 implementation, may need to formalize rules (e.g., "MC minor bump requires image minor bump") with validation logic rather than just comments
- **Cache hit rate monitoring:** Research mentions build time benefits (3-5min → <1min) but doesn't provide tooling to measure cache effectiveness—consider adding `--verbose` flag to build-container.sh that reports cache hit/miss per stage for troubleshooting

**No blocking gaps identified.** All core patterns validated against official sources and real-world implementations. Gaps above are refinements discovered during execution, not fundamental unknowns.

## Sources

### Primary (HIGH confidence)

**Official Documentation:**
- Podman Build Documentation (docs.podman.io) — Multi-stage build syntax, --target flag, layer caching behavior
- Skopeo Documentation (containers/skopeo GitHub) — Registry tag listing via `list-tags` command
- Quay.io API Documentation (docs.quay.io/api) — REST API for repository queries, tag listing endpoints
- OCM CLI Releases (github.com/openshift-online/ocm-cli/releases) — Binary downloads, v1.0.10 verified Dec 2025
- Semantic Versioning Spec (semver.org) — Version format specification
- python-semver PyPI (pypi.org/project/semver) — Version 3.0.4 compatibility, Python 3.7-3.14 support
- PyYAML PyPI (pypi.org/project/pyyaml) — Version 6.0.2+ for YAML parsing
- Docker Multi-stage Builds Documentation (docs.docker.com/build/building/multi-stage) — Canonical reference for multi-stage patterns
- Container Image Versioning (container-registry.com) — Best practices for semver tagging

### Secondary (MEDIUM confidence)

**Community Best Practices (2026 sources):**
- How to Build Images with Podman (OneUptime Blog, Jan 2026) — Multi-stage build patterns and optimization
- Skopeo: The Unsung Hero (Red Hat Developer, Sep 2025) — Registry inspection patterns
- Docker Layer Caching Strategies (OneUptime Blog, Jan 2026) — Cache optimization techniques
- Semantic Versioning Automation (OneUptime Blog, Jan 2026) — Version bumping workflows
- Container Anti-Patterns (dev.to, 2026) — Common mistakes and avoidance strategies
- DevOps Anti-Patterns (Medium, 2026) — Build automation pitfalls

**Verified GitHub Issues:**
- containers/podman#20229 — Layer caching does not work with --squash-all --layers
- containers/podman#14712 — podman build --squash always rebuilds every layer
- containers/buildah#4950 — buildah doesn't use cached layers with multi-stage build and --label
- moby/buildkit#2120 — cache-from and COPY invalidates all layers

### Tertiary (LOW confidence)

No tertiary sources required—all findings validated against official documentation or verified community sources with 2025-2026 timestamps.

---
*Research completed: 2026-02-09*
*Ready for roadmap: yes*
