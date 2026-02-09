# Feature Research: Multi-Stage Container Builds & Automated Versioning

**Domain:** Container build automation, multi-stage architecture, and tool version management
**Researched:** 2026-02-09
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Layer caching with multi-stage builds** | Standard Docker/Podman behavior - users expect only changed layers rebuild | LOW | BuildKit automatically caches stages; ordering instructions properly is key |
| **Named build stages** | Required to reference stages in `COPY --from=` and `--target` | LOW | Using `FROM base AS stage-name` syntax is standard |
| **Explicit version tags (no :latest)** | Production requirement - :latest causes tracking/rollback problems | LOW | Semantic versioning (x.y.z) is industry standard |
| **Build stage targeting** | `podman build --target stage-name` to build specific stages | LOW | Built-in feature; users expect it for dev/test workflows |
| **ARG-based version control** | `ARG TOOL_VERSION=1.2.3` pattern for configurable builds | LOW | Standard Dockerfile pattern for version pinning |
| **Registry push capability** | `--push` flag to build and publish in one command | LOW | Native podman/docker feature users rely on |
| **Semantic version bumping** | Auto-increment patch, manual minor/major control | MEDIUM | Must detect tool version changes to trigger auto-bump |
| **Build reproducibility** | Same input = same output; pinned versions required | MEDIUM | Requires version locking for all dependencies |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Query registry for current version** | Auto-detect if local version is stale vs quay.io | MEDIUM | Quay.io REST API: GET /api/v1/repository/{ns}/{repo}/tag/ |
| **versions.yaml single source of truth** | Centralized tool versions prevent drift across stages | LOW | YAML parsing + ARG injection pattern |
| **Tool version change detection** | Git diff on versions.yaml triggers auto patch bump | MEDIUM | Compares versions.yaml HEAD vs previous commit |
| **Stage-level caching strategy** | `--cache-from` with per-stage tags for CI/CD | HIGH | Requires pushing intermediate stages to registry |
| **Inline cache metadata** | BuildKit `--build-arg BUILDKIT_INLINE_CACHE=1` | MEDIUM | Enables remote cache reuse without separate cache images |
| **Dry-run mode** | Show what would be built/pushed without executing | LOW | Safety feature for automation scripts |
| **Version validation** | Check versions.yaml format and semver validity | LOW | Prevents broken builds from malformed config |
| **POC with single tool (OCM)** | Prove pattern works before scaling to all tools | LOW | Validates architecture before full implementation |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-push on every build** | Convenience - no manual push step | Pollutes registry with dev/test builds; no review gate | Require explicit `--push` flag; default to local-only |
| **:latest tag in production** | "Always get newest version" sounds convenient | Makes rollback impossible; tracking issues; K8s pulls different versions per node | Always use explicit semver tags; :latest only for dev |
| **Complex version schemes** | "We need date-based + git hash + branch name" | Breaks semantic versioning tools; hard to compare versions | Use semver tags (x.y.z); add git hash as label if needed |
| **Automatic major version bumps** | "Automate everything" | Major bumps signal breaking changes - must be intentional | Only auto-bump patch; require manual minor/major decisions |
| **Rebuild all stages always** | "Ensure everything is fresh" | Wastes time; defeats multi-stage caching benefits | Trust layer cache; use `--no-cache` only when debugging |
| **Version config in Containerfile** | "Keep versions with build logic" | Can't query versions without parsing Dockerfile; no single source of truth | Use versions.yaml; inject via ARG at build time |
| **Running multiple tools per stage** | "Consolidate to reduce stages" | Breaks stage-level caching; if one tool changes, all rebuild | One stage per tool/layer; optimize for cache reuse |

## Feature Dependencies

```
[versions.yaml parsing]
    └──requires──> [ARG injection to Containerfile]
                       └──requires──> [Named build stages]

[Auto patch bump] ──requires──> [Git diff detection]
                  ──requires──> [versions.yaml parsing]

[Registry query] ──enhances──> [Version validation]

[Stage targeting] ──requires──> [Named build stages]
                  ──enhances──> [Layer caching]

[--push flag] ──conflicts──> [Auto-push on every build]

[POC with OCM] ──validates──> [versions.yaml pattern]
               ──proves──> [Multi-stage caching works]
```

### Dependency Notes

- **versions.yaml → ARG injection:** versions.yaml is parsed by build script, which passes `--build-arg TOOL_VERSION=x.y.z` to podman build
- **Auto patch bump requires git diff:** Compares versions.yaml between HEAD and HEAD~1 to detect tool updates
- **Stage targeting requires named stages:** Can't use `--target` without `FROM base AS stage-name` syntax
- **POC validates architecture:** OCM as single tool proves pattern scales before adding complexity
- **--push conflicts with auto-push:** Explicit flag prevents accidental registry pollution

## MVP Definition

### Launch With (v2.0.3)

Minimum viable product - what's needed to validate the concept.

- [x] **Multi-stage Containerfile with named stages** - Enables layer caching and targeted builds
- [x] **versions.yaml config file** - Single source of truth for tool versions
- [x] **build-container.sh script** - Orchestrates build with version injection
- [x] **ARG-based version control** - Pass versions from YAML to Containerfile
- [x] **Semantic versioning for image** - Independent x.y.z versioning (not tied to MC CLI version)
- [x] **--push flag support** - Explicit control over registry publishing
- [x] **Auto patch bump on tool version change** - Git diff triggers version increment
- [x] **OCM tool as POC** - Single tool proves multi-stage pattern works

### Add After Validation (v2.1.x)

Features to add once core is working.

- [ ] **Registry query for version comparison** - Check if quay.io has newer version than local
- [ ] **Inline cache metadata** - Enable `BUILDKIT_INLINE_CACHE=1` for CI/CD optimization
- [ ] **Dry-run mode** - `--dry-run` flag to preview actions without executing
- [ ] **Version validation** - Check semver format and YAML schema before build
- [ ] **Additional tools beyond OCM** - Scale pattern to jq, yq, oc, kubectl, etc.

### Future Consideration (v2.2+)

Features to defer until pattern is proven at scale.

- [ ] **Stage-level cache pushing** - Push intermediate stages with `--cache-from` tags
- [ ] **Multi-platform builds** - `--platform linux/amd64,linux/arm64` support
- [ ] **Automated dependency updates** - Dependabot/Renovate for tool version bumps
- [ ] **Build time optimization reports** - Analyze cache hit rates per stage
- [ ] **Tool manifest auto-generation** - Generate versions.yaml from installed binaries

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Multi-stage Containerfile | HIGH | LOW | P1 |
| versions.yaml config | HIGH | LOW | P1 |
| build-container.sh script | HIGH | MEDIUM | P1 |
| ARG-based version control | HIGH | LOW | P1 |
| Semantic versioning | HIGH | LOW | P1 |
| --push flag | HIGH | LOW | P1 |
| Auto patch bump | HIGH | MEDIUM | P1 |
| OCM tool POC | HIGH | MEDIUM | P1 |
| Registry query | MEDIUM | MEDIUM | P2 |
| Inline cache metadata | MEDIUM | LOW | P2 |
| Dry-run mode | MEDIUM | LOW | P2 |
| Version validation | MEDIUM | LOW | P2 |
| Stage cache pushing | LOW | HIGH | P3 |
| Multi-platform builds | LOW | MEDIUM | P3 |
| Dependency updates | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.0.3 launch
- P2: Should have, add in v2.1.x
- P3: Nice to have, consider for v2.2+

## Competitor/Industry Analysis

| Feature | Standard Docker Workflow | Our Approach | Rationale |
|---------|--------------------------|--------------|-----------|
| Multi-stage builds | Manual Dockerfile with stages | versions.yaml + script automation | Centralize version management outside Dockerfile |
| Versioning | Manual git tags or CI labels | Auto-bump patch on tool changes | Reduce human error; semantic versioning enforced |
| Build caching | Native BuildKit layer cache | Named stages + `--target` pattern | Optimize for tool-specific rebuilds |
| Registry publishing | Manual `docker push` command | `--push` flag in build script | Prevent accidental registry pollution |
| Tool installation | Hard-coded `RUN wget https://...` | ARG variables from versions.yaml | Single source of truth; easy updates |
| Version tracking | :latest tag or git commit hash | Semantic versioning (x.y.z) | Production-safe; supports rollback |

## Category Breakdown

### Multi-Stage Build Features

**Table Stakes:**
- Named build stages (`FROM base AS stage-name`)
- Stage targeting (`--target stage-name`)
- Layer caching (automatic with BuildKit)
- Stage-to-stage artifact copying (`COPY --from=builder`)

**Differentiators:**
- One stage per tool (maximize cache reuse)
- Base stage → tool stages → final stage pattern
- OCM POC validates architecture before scaling

**Anti-Features:**
- Monolithic single-stage builds (defeats caching)
- Multiple tools per stage (breaks granular caching)
- Always rebuild all stages (wastes time)

### Version Management Features

**Table Stakes:**
- Semantic versioning (x.y.z format)
- Explicit version tags (no :latest in production)
- Version pinning via ARG
- Reproducible builds (locked dependencies)

**Differentiators:**
- versions.yaml single source of truth
- Auto patch bump on tool version changes
- Git-based version change detection
- Independent image versioning (separate from MC CLI version)

**Anti-Features:**
- :latest tag reliance (breaks production)
- Manual version management (error-prone)
- Complex version schemes (breaks tooling)
- Auto major/minor bumps (hides breaking changes)

### Build Automation Features

**Table Stakes:**
- Build script orchestration
- `--push` flag for publishing
- ARG injection from config
- Exit on build failures

**Differentiators:**
- Dry-run mode (safety)
- Version validation (pre-build checks)
- Registry query (detect staleness)

**Anti-Features:**
- Auto-push on every build (pollutes registry)
- Silent failures (hide build errors)
- No build logs (debugging nightmare)

### Tool Packaging Features

**Table Stakes:**
- Pinned tool versions
- Download verification (checksums)
- Binary installation to standard paths
- Non-root user compatibility

**Differentiators:**
- OCM as POC (single tool validation)
- Scalable pattern for adding tools
- Centralized version management

**Anti-Features:**
- Unpinned "latest" tool downloads
- No checksum verification (security risk)
- Tools installed as root only
- Hard-coded URLs in Dockerfile

## Implementation Recommendations

### For v2.0.3 (Current Milestone)

Focus on proving the pattern works with minimal complexity:

1. **Start with OCM tool only** - Don't try to migrate all tools at once
2. **Use simple YAML format** - `tools: ocm: version: "0.1.73"` structure
3. **Manual minor/major bumps** - Only auto-bump patch version
4. **Local builds first** - Get caching working before adding registry complexity
5. **Explicit --push** - Require flag to prevent accidental publishing

### Success Criteria for POC

The OCM POC should validate:
- [ ] Multi-stage build with named stages works
- [ ] versions.yaml → ARG injection pattern works
- [ ] Only OCM stage rebuilds when OCM version changes
- [ ] Base stages are cached (don't rebuild unnecessarily)
- [ ] Image gets new patch version when OCM version changes
- [ ] `--push` flag publishes to quay.io successfully

### Anti-Pattern Warnings

**Don't:**
- Try to solve all tools at once (scope creep)
- Auto-push on every build (registry pollution)
- Use :latest tags anywhere (production risk)
- Skip version validation (broken builds)
- Rebuild everything always (defeats caching)

**Do:**
- Start with single tool POC
- Require explicit --push flag
- Use semver tags everywhere
- Validate versions.yaml before build
- Trust layer cache; use --no-cache sparingly

## Sources

### Multi-Stage Builds & Layer Caching
- [Multi-stage | Docker Docs](https://docs.docker.com/build/building/multi-stage/)
- [How to Optimize Docker Build Times with Layer Caching](https://oneuptime.com/blog/post/2026-01-16-docker-optimize-build-times/view)
- [How to Implement Docker Layer Caching Strategies](https://oneuptime.com/blog/post/2026-01-30-how-to-implement-docker-layer-caching-strategies/view)
- [Cache | Docker Docs](https://docs.docker.com/build/cache/)
- [Caching Docker layers on serverless build hosts with multi-stage builds, --target, and --cache-from](https://andrewlock.net/caching-docker-layers-on-serverless-build-hosts-with-multi-stage-builds---target,-and---cache-from/)
- [Multi-Stage Docker Builds: Smaller Images, Faster Deployments](https://www.cleanstart.com/guide/multi-stage-build)

### Semantic Versioning & Automation
- [Container Image Versioning](https://container-registry.com/posts/container-image-versioning/)
- [Semantic Versioning for Containers](https://docs.inedo.com/docs/proget/docker/semantic-versioning)
- [How to name, version, and reference container images | Red Hat Developer](https://developers.redhat.com/articles/2025/01/28/how-name-version-and-reference-container-images)
- [How to Implement Semantic Versioning Automation](https://oneuptime.com/blog/post/2026-01-25-semantic-versioning-automation/view)
- [How to Automate Version Bumping with GitHub Actions](https://oneuptime.com/blog/post/2026-01-27-version-bumping-github-actions/view)
- [Semantic Versioning 2.0.0](https://semver.org/)

### Registry APIs
- [Quay.io API](https://docs.quay.io/api/)
- [Project Quay API guide](https://docs.projectquay.io/api_quay.html)
- [Docker Registry API | Baeldung on Ops](https://www.baeldung.com/ops/docker-registry-api-list-images-tags)
- [HTTP API V2 | CNCF Distribution](https://distribution.github.io/distribution/spec/api/)

### Anti-Patterns & Best Practices
- [Container Anti-Patterns: Common Docker Mistakes and How to Avoid Them](https://dev.to/idsulik/container-anti-patterns-common-docker-mistakes-and-how-to-avoid-them-4129)
- [DevOps Roadmap: Common DevOps Mistakes, Anti-Patterns & How to Avoid Them (2026)](https://medium.com/@sainath.814/devops-roadmap-part-45-common-devops-mistakes-anti-patterns-how-to-avoid-them-based-on-real-de981419c7c4)
- [What's Wrong With The Docker :latest Tag?](https://vsupalov.com/docker-latest-tag/)
- [Docker Tip #18: Please Pin Your Docker Image Versions](https://nickjanetakis.com/blog/docker-tip-18-please-pin-your-docker-image-versions)

### Version Pinning & ARG Patterns
- [How to Pass Build Arguments and Environment Variables in Docker (2026)](https://oneuptime.com/blog/post/2026-01-06-docker-build-args-env-variables/view)
- [Pinning a Docker Image to a Specific Version](https://support.circleci.com/hc/en-us/articles/115015742147-Pinning-a-Docker-Image-to-a-Specific-Version)

### POC Best Practices
- [What Is Proof of Concept? POC Examples & Writing Guide [2026]](https://asana.com/resources/proof-of-concept)
- [What is PoC in Software Development? Guide to Proof of Concept [2026]](https://dbbsoftware.com/insights/what-is-proof-of-concept-in-software)
- [PoC vs Prototype and MVP: What's the Difference?](https://www.techmagic.co/blog/poc-vs-prototype-vs-mvp/)

---
*Feature research for: MC CLI Container Build System v2.0.3*
*Researched: 2026-02-09*
*Confidence: HIGH (verified with official documentation and current 2026 sources)*
