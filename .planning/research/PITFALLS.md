# Pitfalls Research: Multi-Stage Builds & Version Management

**Domain:** Container build automation with multi-stage architecture and versioned tool management
**Researched:** 2026-02-09
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Layer Cache Invalidation from Stage Dependencies

**What goes wrong:**
When converting a single-stage Containerfile to multi-stage with `COPY --from=builder`, Docker/Podman incorrectly invalidates cache for downstream stages even when upstream stage was cached. Result: Every build rebuilds all stages, defeating the primary benefit of multi-stage builds (fast incremental rebuilds).

**Why it happens:**
Build tools (buildah/BuildKit) calculate cache checksums by examining file metadata in `COPY --from=` instructions. If the source stage was rebuilt (even from cache), the cache key changes, invalidating all downstream stages. This is a known bug in both Docker (moby/buildkit#2120) and Podman (containers/podman#20229).

**How to avoid:**
- Use named stages explicitly: `FROM base AS mc-builder` not just `FROM base`
- Order stages from least-frequently-changed to most-frequently-changed
- Place tool downloader stages BEFORE mc-builder stage (tools change less than code)
- Test cache behavior: `podman build` twice in a row should show "Using cache" for unchanged stages
- Never use `--squash-all` with multi-stage builds (completely breaks layer caching per containers/podman#14712)

**Warning signs:**
- Build times don't improve on second run
- Console shows "Step X/Y" rebuilding instead of "Using cache"
- `podman build` output never shows cached layer reuse

**Phase to address:**
Phase 1 (Multi-stage Architecture Design) - Verify cache behavior in acceptance criteria before proceeding to Phase 2

---

### Pitfall 2: Version Conflict Between Image Version and MC CLI Version

**What goes wrong:**
Image version (1.0.0) and MC CLI version (2.0.3) drift out of sync. Users pull image tagged `mc-rhel10:latest`, expect MC 2.0.3 inside, but get MC 2.0.2 because image wasn't rebuilt. Or worse: auto-bumping patch version on every tool change causes version.yaml to show image 1.0.47 when nothing meaningful changed.

**Why it happens:**
Three separate version numbers exist (image semver, MC CLI version in pyproject.toml, tool versions in versions.yaml) with no enforcement of their relationship. Common mistakes:
- Forgetting to rebuild image after MC version bump
- Auto-bumping image patch for tool version changes that don't warrant a release
- Tagging both `:latest` and `:1.0.0` without checking if versions.yaml matches

**How to avoid:**
- Declare version relationship policy in versions.yaml header comment:
  ```yaml
  # Image version: Independent semver (x.y.z)
  # - Patch bump: Tool version changes only (OCM 1.2.3 -> 1.2.4)
  # - Minor bump: New tool added OR MC CLI minor version bump
  # - Major bump: Breaking changes to container interface
  ```
- build-container.sh reads MC CLI version from pyproject.toml and validates compatibility
- Add version mismatch detection: `mc --version` inside container vs. image tag
- Never auto-bump on tool version changes - require manual decision
- Phase acceptance: Verify version.yaml → image tag → `mc --version` consistency

**Warning signs:**
- Image tag 1.0.5 but `mc --version` shows 2.0.2
- versions.yaml shows OCM 1.2.3 but `ocm version` returns 1.2.1
- Quay.io shows 12 patch versions in 1 day (over-aggressive auto-bumping)

**Phase to address:**
Phase 2 (Version Management System) - Define and implement version relationship policy before automation

---

### Pitfall 3: Architecture Mismatch in Tool Binaries

**What goes wrong:**
Containerfile downloads `ocm-linux-amd64` binary, builds successfully on amd64 build host, pushes to quay.io. Users on ARM64 (Apple Silicon, AWS Graviton) pull image, run container, `ocm` command fails with "Exec format error" because binary is wrong architecture.

**Why it happens:**
Tool downloader stage hardcodes architecture instead of using `TARGETARCH` build argument:
```dockerfile
# WRONG - hardcoded architecture
RUN curl -L https://github.com/.../ocm-linux-amd64 -o /usr/local/bin/ocm

# RIGHT - dynamic architecture
ARG TARGETARCH
RUN curl -L https://github.com/.../ocm-linux-${TARGETARCH} -o /usr/local/bin/ocm
```

OCM CLI provides separate binaries for amd64, arm64, and ppc64le. Without TARGETARCH substitution, image only works on build host's architecture.

**How to avoid:**
- Every tool downloader stage MUST declare `ARG TARGETARCH` before RUN instructions
- Substitute `${TARGETARCH}` in download URLs: `ocm-linux-${TARGETARCH}`
- Test on multiple architectures: Build on amd64, verify on arm64 (or vice versa)
- Use `podman build --platform linux/amd64,linux/arm64` to create multi-arch manifest
- Add architecture to versions.yaml: `architectures: [amd64, arm64]`
- Acceptance test: Pull image on different architecture and verify `ocm version` succeeds

**Warning signs:**
- `ocm` command works on build machine but fails on different architecture
- "Exec format error" or "cannot execute binary file" in container
- Image size differs significantly between architectures (missing binary)

**Phase to address:**
Phase 3 (OCM Tool Integration POC) - Verify multi-architecture support before declaring pattern proven

---

### Pitfall 4: Quay.io API Rate Limiting and Authentication Failures

**What goes wrong:**
build-container.sh queries quay.io API to get latest image tag. During rapid iteration (10+ builds in 30 minutes), API returns 429 "Too many requests". Script fails, can't determine next version, refuses to build. Or: API requires authentication but script uses unauthenticated requests, gets 401 on private repos.

**Why it happens:**
Quay.io rate limits requests to "tens of requests per second from same IP" (per docs.quay.io/issues/429). Build automation makes sequential API calls (list tags, get manifest, check exists) without backoff. Additionally, quay.io API requires OAuth2 tokens for private repos, not username/password - using basic auth returns "invalid_token" error.

**How to avoid:**
- Implement exponential backoff for API requests (1s, 2s, 4s, 8s delays)
- Cache API responses locally: Write latest tag to `.cache/quay-latest-tag.txt`, TTL 5 minutes
- Provide `--version X.Y.Z` override flag to skip API query entirely
- For private repos: Generate OAuth2 token via quay.io UI → Settings → Robot Accounts
- Add `--offline` mode: Use local `podman images` to determine version, never call API
- Graceful degradation: If API fails after retries, fall back to manual version specification

**Warning signs:**
- Build script fails with "Too many requests" during rapid iteration
- "invalid_token" errors when accessing private repos
- Script hangs for 30+ seconds waiting for API response
- Rate limit errors during CI/CD runs (multiple builds from same runner IP)

**Phase to address:**
Phase 2 (Version Management System) - Implement API client with retry/caching before integrating with build script

---

### Pitfall 5: Breaking Existing Single-Stage Build Workflow

**What goes wrong:**
After converting to multi-stage Containerfile, existing `container/build.sh` script stops working. Users who had `alias build-mc='cd ~/mc && ./container/build.sh'` in their shell config suddenly get errors. Worse: Documentation still references old single-stage build commands, causing confusion.

**Why it happens:**
Migration changes file structure, script arguments, or dependencies without maintaining backward compatibility:
- Containerfile now requires BuildKit features not available in older podman versions
- build.sh renamed to build-container.sh without symlink
- New script requires versions.yaml which doesn't exist in older checkouts
- Build time increases from 45s to 3m on first run (multi-stage overhead)

**How to avoid:**
- Keep `container/build.sh` as wrapper calling new build-container.sh (backward compat)
- Validate podman version: `podman version | grep "^Version:" | awk '{print $2}'` >= 4.0
- Add feature detection: Test for BuildKit support before using multi-stage syntax
- Document migration in MIGRATION.md: "If upgrading from v2.0.2, run X first"
- Preserve single-stage Containerfile as `Containerfile.single` for comparison
- Add `--legacy` flag to build-container.sh that uses single-stage for emergencies

**Warning signs:**
- Users report "build.sh not found" after git pull
- Build errors about "unknown instruction" (BuildKit syntax on old podman)
- GitHub issues titled "Builds broken after upgrading to v2.0.3"
- CI/CD pipeline failures in environments still using podman 3.x

**Phase to address:**
Phase 1 (Multi-stage Architecture Design) - Plan backward compatibility strategy before implementation

---

### Pitfall 6: versions.yaml Parsing Failures from Manual Edits

**What goes wrong:**
Developer manually edits versions.yaml to bump OCM version. Introduces subtle YAML syntax error (tabs instead of spaces, incorrect indentation, unquoted version number starting with 0). build-container.sh parses YAML, encounters error, crashes with cryptic "mapping values are not allowed here" message. Build system is dead until YAML fixed.

**Why it happens:**
YAML is whitespace-sensitive and error-intolerant. Common mistakes:
- Mixing tabs and spaces (YAML spec forbids tabs)
- Version numbers like `1.0` parsed as float 1.0, not string "1.0" (loses trailing zero)
- Unquoted strings like `ocm: v1.2.3` parsed as object if colon in value
- Copy-paste from docs introduces UTF-16 encoding breaking UTF-8 parser

**How to avoid:**
- Add YAML schema validation: `yamllint versions.yaml` in pre-commit hook
- Provide editor config: `.editorconfig` enforces spaces, not tabs
- Quote all version strings: `version: "1.2.3"` not `version: 1.2.3`
- build-container.sh validates YAML before parsing:
  ```bash
  if ! python3 -c "import yaml; yaml.safe_load(open('versions.yaml'))" 2>/dev/null; then
    echo "ERROR: versions.yaml has syntax errors"
    exit 1
  fi
  ```
- Provide version-bump command: `./build-container.sh --bump-tool ocm 1.2.4` edits YAML safely
- Example versions.yaml with comments showing correct syntax

**Warning signs:**
- Build script fails with "YAML parsing error" but file looks correct
- Version numbers lose precision (1.10 becomes 1.1)
- Builds work locally but fail in CI (encoding differences)
- `yamllint` shows errors that human eye doesn't catch

**Phase to address:**
Phase 2 (Version Management System) - Add YAML validation before relying on manual edits

---

### Pitfall 7: Missing Dependencies in Final Stage

**What goes wrong:**
Multi-stage build copies OCM binary from downloader stage to final stage. Binary runs, tries to make HTTPS calls, crashes with "error loading shared libraries: libssl.so.3". Or: OCM binary expects `/etc/ssl/certs` directory populated, but final stage is minimal Alpine without CA certificates. Result: Tool installed but non-functional.

**Why it happens:**
Tool binaries have runtime dependencies not obvious from documentation:
- Dynamically linked libraries (libssl, libcrypto, libc)
- CA certificate bundles for HTTPS
- Timezone data in /usr/share/zoneinfo
- User/group databases (/etc/passwd, /etc/group)

OCM CLI is distributed as statically-linked binary, but developer assumes all binaries are static. Future tools (helm, kubectl) may be dynamically linked.

**How to avoid:**
- Test binaries standalone: `ldd /usr/local/bin/ocm` shows shared library dependencies
- Use base image with common dependencies: RHEL 10 UBI has libssl, CA certs pre-installed
- Document dependency inspection process in architecture docs
- For each new tool, verify in isolated container:
  ```bash
  podman run --rm -it registry.access.redhat.com/ubi10/ubi:10.1 /bin/bash
  # Upload binary, test functionality
  ```
- Add smoke test to Containerfile: `RUN ocm version` fails build if dependencies missing
- Consider static binaries: `CGO_ENABLED=0` for Go tools eliminates shared lib deps

**Warning signs:**
- `ldd` output shows "not found" for shared libraries
- Binary runs on RHEL but fails on Alpine or Debian-based images
- Tools work locally but fail inside container
- Errors mention "libssl.so", "libcrypto.so", "libc.so"

**Phase to address:**
Phase 3 (OCM Tool Integration POC) - Verify runtime dependencies before declaring success

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode tool versions in Containerfile instead of versions.yaml | Skip YAML parsing complexity | Manual updates required in multiple files, versions drift out of sync | Never - versions.yaml is foundational |
| Skip quay.io API, manually specify `--tag 1.0.5` every build | Avoid API rate limits and auth complexity | Developer forgets to bump version, overwrites tags | Development only - CI must use automation |
| Use `:latest` tag only, skip semver tagging | Simpler tagging logic | Can't rollback to previous version, no version history | Never - semver is requirement |
| Download tools at runtime instead of baking into image | Faster image builds (smaller layers) | Slower container startup, network dependency, version drift | Never - defeats purpose of versioned tools |
| Copy entire /opt/mc to final stage instead of selective COPY | Simpler Containerfile (one COPY line) | Image bloat (includes .git, tests, docs), 200MB+ wasted | Early prototyping only - optimize before merge |
| Build single-arch image (amd64 only) | Simpler build script, faster builds | ARM64 users can't use the tool | Only if 100% of users on amd64 (unlikely) |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Quay.io API | Using basic auth (username/password) for private repos | Generate OAuth2 token via Robot Accounts in quay.io UI |
| Quay.io API | Making 10+ API calls in rapid succession | Implement exponential backoff + local caching (5min TTL) |
| Podman build | Using `--squash-all` with multi-stage builds | Never use --squash-all (breaks layer caching per podman#14712) |
| YAML parsing | Using shell tools (sed/awk) to edit versions.yaml | Use `yq` or Python's yaml library for safe editing |
| Git tagging | Pushing version tag before build succeeds | Build + test + push image, THEN tag git (rollback if push fails) |
| CI/CD | Triggering new pipeline on tag push | Add `only: branches` filter to prevent infinite tag-push loops |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Rebuilding unchanged stages | Multi-stage build takes 3min on every run | Order stages least-to-most frequently changed; test cache with double-build | Every build after first |
| Downloading tools on every build | Network I/O dominates build time | Use Containerfile `COPY --from` to cache downloads in layers | Every build |
| Parsing versions.yaml in tight loop | build-container.sh slow (5+ seconds) | Parse once, cache results in shell variables | Not noticeable until <1s matters |
| Querying quay.io API serially | 3-5 seconds per API call x 3 calls = 15s overhead | Parallel API requests with `&` and `wait` in bash | When build speed matters |
| Full image rebuild on patch bump | Change versions.yaml → rebuild entire 549MB image | Layer versions.yaml COPY late in Containerfile | Every version bump |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Downloading binaries over HTTP instead of HTTPS | Man-in-the-middle attack injects malicious binary | Always use HTTPS URLs for tool downloads |
| Not verifying SHA256 checksums | Corrupted or tampered binary silently included | Download `.sha256` file, verify before COPY |
| Hardcoding OAuth tokens in build script | Token leaks in git history, never expires | Use environment variables + .gitignore, document token generation |
| Running build stage as root unnecessarily | Privilege escalation if build compromised | Use `USER mcuser` in stages that don't need root |
| Including secrets in ARG instructions | Secrets visible in image history via `docker history` | Use BuildKit secret mounts: `RUN --mount=type=secret,id=token` |
| Building from untrusted base images | Supply chain attack via compromised base | Use official Red Hat UBI images with signature verification |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Cryptic YAML parsing errors | Developer wastes 20min debugging "mapping values not allowed" | Validate YAML with yamllint, show exact line number + helpful message |
| build-container.sh fails silently | Build appears to succeed but image not pushed | Always `set -e` in bash, exit on any error, print clear success/failure message |
| Version auto-bump without confirmation | Unexpected version 1.0.23 pushed, developer confused | Show diff: "OCM 1.2.3 → 1.2.4 detected, bumping image 1.0.5 → 1.0.6. Continue? (y/N)" |
| No progress indication during tool downloads | User thinks build hung, kills process | Use `curl --progress-bar` or podman build `--progress=plain` |
| Breaking changes without migration guide | Users upgrade, builds fail, no clear path forward | Provide MIGRATION.md with step-by-step upgrade instructions |

## "Looks Done But Isn't" Checklist

- [ ] **Multi-stage build:** Verify cache works - build twice, second build should be <30s
- [ ] **Architecture support:** Test on both amd64 and arm64, verify `ocm version` succeeds
- [ ] **Version automation:** Verify image tag matches versions.yaml matches `mc --version` inside container
- [ ] **Quay.io integration:** Test with rate limiting (10 builds in 5min), verify graceful degradation
- [ ] **YAML validation:** Introduce syntax error in versions.yaml, verify build fails with helpful message
- [ ] **Backward compatibility:** Checkout v2.0.2, run new build script, verify graceful error or success
- [ ] **Tool functionality:** Not just `ocm version` but actual `ocm login` + `ocm cluster list` works
- [ ] **Error messages:** Break each integration (no internet, wrong token, bad YAML), verify helpful errors
- [ ] **Documentation:** README shows both quick start AND migration from single-stage

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cache invalidation breaks builds | LOW | Add `podman build --no-cache` flag to documentation, accept slower builds short-term |
| Version conflict (image vs MC CLI) | MEDIUM | Tag new image with corrected version, update quay.io latest tag manually |
| Architecture mismatch shipped to production | HIGH | Build multi-arch manifest, push to quay.io, users `podman pull --platform` to force re-pull |
| Quay.io rate limit in CI/CD | LOW | Add exponential backoff, or cache API responses in CI cache (30min TTL) |
| Breaking backward compatibility | MEDIUM | Release v2.0.3.1 patch with backward-compat wrapper scripts |
| YAML parsing fails on version bump | LOW | Validate YAML in pre-commit hook, provide `make validate` target |
| Missing dependencies in final stage | MEDIUM | Add dependencies to Containerfile, rebuild + re-push, bump patch version |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Layer cache invalidation | Phase 1 (Architecture) | Build twice, verify second build <30s with cache |
| Version conflict | Phase 2 (Version Mgmt) | Compare versions.yaml, image tag, `mc --version` output |
| Architecture mismatch | Phase 3 (OCM POC) | Test on arm64 AND amd64, verify `ocm version` |
| Quay.io rate limiting | Phase 2 (Version Mgmt) | Run 10 builds in 5min, verify backoff prevents failure |
| Breaking existing builds | Phase 1 (Architecture) | Test v2.0.2 checkout with new scripts, verify graceful behavior |
| YAML parsing failures | Phase 2 (Version Mgmt) | Introduce syntax error, verify helpful error message |
| Missing dependencies | Phase 3 (OCM POC) | Run `ldd` on binaries, test in isolated container |

## Sources

**Multi-stage build pitfalls:**
- [Docker Multi-stage Build Documentation](https://docs.docker.com/build/building/multi-stage/)
- [Docker Best Practices](https://docs.docker.com/build/building/best-practices/)
- [Understanding Docker Multistage Builds - Earthly Blog](https://earthly.dev/blog/docker-multistage/)
- [Best Practices for Building Docker Images - Better Stack](https://betterstack.com/community/guides/scaling-docker/docker-build-best-practices/)

**Podman layer caching issues:**
- [Layer caching does not work with --squash-all --layers - Podman Issue #20229](https://github.com/containers/podman/issues/20229)
- [buildah doesn't use cached layers with multi-stage build and --label - Issue #4950](https://github.com/containers/buildah/issues/4950)
- [podman build --squash always rebuilds every layer - Issue #14712](https://github.com/containers/podman/issues/14712)
- [Optimize container build speed with Podman on Windows](https://medium.com/@jeroenverhaeghe/tips-to-optimize-container-build-speed-02e4622d8bae)

**Container image versioning:**
- [Docker Best Practices: Using Tags and Labels - Docker Blog](https://www.docker.com/blog/docker-best-practices-using-tags-and-labels-to-manage-docker-image-sprawl/)
- [Semantic Versioning for Containers - Inedo Documentation](https://docs.inedo.com/docs/proget/docker/semantic-versioning)
- [Container Image Versioning](https://container-registry.com/posts/container-image-versioning/)
- [Using Semver for Docker Image Tags - Medium](https://medium.com/@mccode/using-semantic-versioning-for-docker-image-tags-dfde8be06699)

**Quay.io API integration:**
- [Quay.io rate limiting - Red Hat Customer Portal](https://access.redhat.com/solutions/6218921)
- [Quay.io returning 429 due to rate limits - Sonatype Support](https://support.sonatype.com/hc/en-us/articles/32093607704723-DockerHub-and-Quay-io-returning-429-due-to-rate-limits)
- [Quay Documentation - 429 Errors](https://docs.quay.io/issues/429.html)
- [Quay.io API Documentation](https://docs.quay.io/api/)

**Cache invalidation with COPY --from:**
- [How to Fix Docker Build Cache Issues - OneUpTime](https://oneuptime.com/blog/post/2026-01-25-fix-docker-build-cache-issues/view)
- [Build cache invalidation - Docker Docs](https://docs.docker.com/build/cache/invalidation/)
- [cache-from and COPY invalidates all layers - BuildKit Issue #2120](https://github.com/moby/buildkit/issues/2120)
- [How to Build Docker Images with Cache Busting - OneUpTime](https://oneuptime.com/blog/post/2026-01-30-docker-cache-busting/view)

**Binary compatibility across architectures:**
- [WARNING: Platform linux/amd64 does not match linux/arm64 - Collabnix](https://collabnix.com/warning-the-requested-images-platform-linux-amd64-does-not-match-the-detected-host-platform-linux-arm64-v8/)
- [Multi-platform - Docker Docs](https://docs.docker.com/build/building/multi-platform)
- [How to Build Multi-Architecture Docker Images - OneUpTime](https://oneuptime.com/blog/post/2026-01-06-docker-multi-architecture-images/view)
- [Docker image platform compatibility with MAC Silicon - Medium](https://medium.com/@email.bajaj/docker-image-platform-compatibility-issue-with-mac-silicon-processors-m1-m2-ee2d5ea3ff0e)

**OCM CLI installation:**
- [OCM CLI GitHub Repository](https://github.com/openshift-online/ocm-cli)
- [OCM Container GitHub Repository](https://github.com/openshift/ocm-container)

**Version automation:**
- [How to Automate Version Bumping with GitHub Actions - OneUpTime](https://oneuptime.com/blog/post/2026-01-27-version-bumping-github-actions/view)
- [Bumping version tags with git](https://www.tobymackenzie.com/blog/2023/12/27/bumping-version-tags-with-git/)
- [Automate Git Tag Versioning Using Bash](https://reemus.dev/tldr/git-tag-versioning-script)
- [GitVersion - Version Incrementing](https://gitversion.net/docs/reference/version-increments)

**YAML parsing errors:**
- [How to resolve Kubernetes YAML parsing errors - LabEx](https://labex.io/tutorials/kubernetes-how-to-resolve-kubernetes-yaml-parsing-errors-418394)
- [Resolving YAML Parsing Errors in Azure DevOps](https://medium.com/@python-javascript-php-html-css/resolving-yaml-parsing-errors-in-azure-devops-tips-and-solutions-f73cf45d9bd)
- [How to Fix Errors in YAML Config Files - Shockbyte](https://shockbyte.com/billing/knowledgebase/45/How-to-Fix-Errors-in-YAML-YML-Config-Files.html)

**Docker ARG and build arguments:**
- [How to Use Docker Build Arguments - OneUpTime](https://oneuptime.com/blog/post/2026-01-25-docker-build-arguments/view)
- [Docker Best Practices: Using ARG and ENV - Docker Blog](https://www.docker.com/blog/docker-best-practices-using-arg-and-env-in-your-dockerfiles/)
- [Dockerfile reference - Docker Docs](https://docs.docker.com/reference/dockerfile/)

---
*Pitfalls research for: MC CLI v2.0.3 Container Tools milestone*
*Researched: 2026-02-09*
