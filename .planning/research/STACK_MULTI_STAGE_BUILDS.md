# Stack Research: Multi-Stage Container Builds & Tool Versioning

**Domain:** Container image build automation and versioning
**Researched:** 2026-02-09
**Confidence:** HIGH

## Executive Summary

This research covers stack additions needed to evolve MC CLI's container strategy from single-stage builds to multi-stage architecture with automated versioning. The focus is on tooling for:

1. Multi-stage Containerfile builds (builder + tool-downloaders + final)
2. Independent image versioning (semver x.y.z)
3. Build automation that queries quay.io and auto-bumps versions
4. OCM CLI packaging as proof-of-concept for tool downloads

**Key Finding:** Use Bash for build orchestration scripts with existing tools (skopeo, curl) rather than adding Python dependencies. YAML parsing needed for versions.yaml management - PyYAML is sufficient despite ruamel.yaml's advantages.

## Recommended Stack Additions

### Multi-Stage Build Support

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Podman | 5.7.0+ (existing) | Multi-stage builds with --target flag | Already in pyproject.toml dependencies; supports multi-stage builds natively with `AS stageName` and `COPY --from=stage` syntax; compatible with existing workflow |
| Containerfile | OCI spec | Multi-stage build definition | Standard format supported by both podman and buildah; no additional tooling needed; uses `FROM ... AS stageName` pattern for named stages |

**No new dependencies required.** Podman 5.7.0+ fully supports multi-stage builds through standard Containerfile syntax.

### Registry API & Version Querying

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| skopeo | 1.21.0+ | Image tag inspection and listing | Already available on host (1.21.0 verified); provides `skopeo list-tags` for remote registries without pulling images; faster than API calls for simple tag queries |
| curl | (system) | Quay.io REST API access | Pre-installed in RHEL 10 UBI base image; needed for API queries when skopeo is insufficient (pagination, filtering); quay.io API at `https://quay.io/api/v1/` requires no auth for public repos |
| jq | latest | JSON parsing in build scripts | Not in UBI repos without EPEL; use Python json module in scripts instead or enable EPEL at build time; avoid adding build-time dependency if Python alternative works |

**Recommendation:** Use skopeo as primary tool for tag queries. Use curl + Python json parsing for complex API queries (avoid jq dependency).

### YAML Configuration Management

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | 6.0.2+ | Parse and update versions.yaml | Simple read/write of version mapping file; widely used, stable, minimal dependencies; adequate for structure like `tools: ocm-cli: version: "1.0.10"` |
| tomli-w | 1.0.0+ (existing) | TOML writing for pyproject.toml | Already in dependencies for version bumping in pyproject.toml; use for semver updates to Python package version |

**Note:** ruamel.yaml (0.18.x) would preserve comments in versions.yaml but adds complexity. PyYAML is sufficient since versions.yaml is machine-managed.

### Semantic Versioning

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| semver | 3.0.4 | Semantic version parsing and bumping | Parse current version from versions.yaml or quay.io tags; implement bump logic (patch/minor/major); validate version strings; simpler API than semantic-version library |

**Example usage:**
```python
import semver
current = semver.Version.parse("2.0.1")
bumped = current.bump_patch()  # "2.0.2"
```

### Build Automation Scripting

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Bash | 5.x+ | Build orchestration scripts | RHEL 10 UBI includes bash; simpler than Python for command sequencing; can call skopeo, podman, curl directly; easier to read for container build workflows |
| Python | 3.11+ (existing) | Complex version logic and YAML updates | Use when Bash is insufficient (YAML parsing, semver bumping, complex conditionals); leverage existing project dependencies (semver, PyYAML) |

**Pattern:** Bash for build orchestration (build.sh), Python for version management (version-bump.py).

### OCM CLI Packaging

| Component | Version | Purpose | Installation Method |
|-----------|---------|---------|---------------------|
| OCM CLI | 1.0.10+ | OpenShift Cluster Manager CLI tool | Download from GitHub releases at `https://github.com/openshift-online/ocm-cli/releases`; binaries available for linux-amd64, linux-arm64; verify with SHA256 checksum |

**Containerfile pattern for OCM CLI:**
```dockerfile
# Download stage
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS ocm-downloader
ARG OCM_VERSION=1.0.10
ARG TARGETARCH
RUN curl -L -o /tmp/ocm \
    https://github.com/openshift-online/ocm-cli/releases/download/v${OCM_VERSION}/ocm-linux-${TARGETARCH} \
    && chmod +x /tmp/ocm

# Final stage
FROM registry.access.redhat.com/ubi10/ubi:10.1
COPY --from=ocm-downloader /tmp/ocm /usr/local/bin/ocm
```

**Note:** Use ARG for version parameterization; `TARGETARCH` auto-populated by buildah/podman for multi-arch builds.

## Installation

### New Python Dependencies

```bash
# Core versioning (add to pyproject.toml)
pip install semver>=3.0.4
pip install pyyaml>=6.0.2

# tomli-w already present for TOML writing
```

### System Tools (Verification)

```bash
# Verify existing tools (no installation needed)
skopeo --version    # Should be 1.21.0+
podman --version    # Should be 5.7.0+
curl --version      # Pre-installed in UBI
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Bash build scripts | Python build scripts | When build logic requires complex data structures, API parsing, or error handling beyond shell capabilities; for projects already using Python-based build tools |
| PyYAML | ruamel.yaml | When versions.yaml needs comment preservation for human editing; when roundtrip parsing is critical; adds 3x parse time but maintains formatting |
| skopeo list-tags | Quay.io REST API | When pagination needed (>100 tags); when filtering by date/labels required; when querying private repos with auth tokens |
| semver library | semantic-version | When NPM-style version ranges needed (SimpleSpec/NpmSpec); when version coercion from non-semver strings required; both are maintained but semver has simpler API |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| jq in Containerfile | Not available in UBI repos without EPEL; adds build dependency; Python json module in scripts is simpler | Python json module or enable EPEL only if unavoidable |
| Docker BuildKit | Podman uses buildah backend; BuildKit is Docker-specific; MC CLI standardized on Podman for rootless support | Podman native multi-stage builds with buildah backend |
| go get for OCM CLI | Unsupported by OCM CLI maintainers; requires Go toolchain in build stage; binary releases are preferred distribution method | Download pre-built binaries from GitHub releases |
| rpm packages for tools | OCM CLI RPM only in Fedora Copr, not UBI repos; adds repository configuration complexity; harder to version-pin | Direct binary download from GitHub releases with SHA256 verification |

## Stack Patterns by Build Stage

### Pattern 1: Tool Downloader Stage

**When:** Adding downloadable CLI tools (ocm-cli, rosa-cli, etc.)

**Structure:**
```dockerfile
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS tool-downloader
ARG TOOL_VERSION
ARG TARGETARCH
RUN curl -L -o /tmp/tool https://releases.example.com/v${TOOL_VERSION}/tool-${TARGETARCH} \
    && curl -L -o /tmp/tool.sha256 https://releases.example.com/v${TOOL_VERSION}/tool-${TARGETARCH}.sha256 \
    && sha256sum -c /tmp/tool.sha256 \
    && chmod +x /tmp/tool
```

**Use because:** Isolates download + verification; can run parallel to other stages; discards curl and verification artifacts from final image.

### Pattern 2: MC Builder Stage

**When:** Building MC CLI from source in container

**Structure:**
```dockerfile
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS mc-builder
RUN dnf install -y python3-pip python3-devel gcc
COPY . /build
RUN pip install --no-cache-dir --target=/opt/mc /build
```

**Use because:** Separates build dependencies (gcc, python3-devel) from runtime; produces clean /opt/mc tree for final stage; enables caching of build dependencies.

### Pattern 3: Final Runtime Stage

**When:** Assembling minimal runtime image

**Structure:**
```dockerfile
FROM registry.access.redhat.com/ubi10/ubi:10.1
COPY --from=mc-builder /opt/mc /opt/mc
COPY --from=ocm-downloader /tmp/ocm /usr/local/bin/ocm
COPY --from=rosa-downloader /tmp/rosa /usr/local/bin/rosa
# Runtime dependencies only
RUN dnf install -y python3 vim nano wget && dnf clean all
```

**Use because:** Minimal final image with only runtime deps; all tools assembled from previous stages; one RUN layer for dnf operations.

## Version Bumping Workflow

### Automated Version Detection

**Build script checks:**
1. Query quay.io for latest mc-rhel10 tag via `skopeo list-tags docker://quay.io/namespace/mc-rhel10`
2. Parse latest version using semver library
3. Read versions.yaml to get tool versions (OCM CLI, etc.)
4. Compare against upstream (GitHub releases API)

**Decision logic:**
- If MC CLI source changed (git diff) → bump MC image version
- If tool version in versions.yaml changed → rebuild without version bump (patch bump optional)
- If Containerfile changed → rebuild + version bump (minor)
- If base image digest changed → rebuild without version bump (security update)

### Version Bump Implementation

**Python script (version-bump.py):**
```python
import semver
import yaml

# Read current versions
with open("versions.yaml") as f:
    versions = yaml.safe_load(f)

# Bump version
current = semver.Version.parse(versions["mc-image"]["version"])
new_version = current.bump_patch()  # or bump_minor(), bump_major()

# Write back
versions["mc-image"]["version"] = str(new_version)
with open("versions.yaml", "w") as f:
    yaml.dump(versions, f)
```

**Bash script (build.sh) integration:**
```bash
#!/bin/bash
set -euo pipefail

# Bump version
python3 version-bump.py --bump patch

# Read new version
NEW_VERSION=$(python3 -c "import yaml; print(yaml.safe_load(open('versions.yaml'))['mc-image']['version'])")

# Build with version
podman build -t mc-rhel10:${NEW_VERSION} -f container/Containerfile .
podman tag mc-rhel10:${NEW_VERSION} quay.io/namespace/mc-rhel10:${NEW_VERSION}
podman tag mc-rhel10:${NEW_VERSION} quay.io/namespace/mc-rhel10:latest

# Push to registry
podman push quay.io/namespace/mc-rhel10:${NEW_VERSION}
podman push quay.io/namespace/mc-rhel10:latest
```

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| semver 3.0.4 | Python 3.7-3.14 | Works with existing Python 3.11+ requirement |
| PyYAML 6.0.2 | Python 3.8+ | Compatible with project's 3.11+ baseline |
| skopeo 1.21.0 | Podman 5.7.0+ | Both use same containers/image library; version alignment not critical but recommended |
| OCM CLI 1.0.10 | Any Linux kernel 4.x+ | Statically linked Go binary; no runtime dependencies |

**CRITICAL:** Podman Python library version (5.7.0) must stay aligned with host podman binary for API compatibility. Already specified in pyproject.toml.

## Sources

**Official Documentation:**
- [Podman Build Documentation](https://docs.podman.io/en/latest/markdown/podman-build.1.html) - Multi-stage build syntax and --target flag
- [Skopeo Documentation](https://github.com/containers/skopeo/blob/main/docs/skopeo-list-tags.1.md) - Tag listing for registries
- [Quay.io API Documentation](https://docs.quay.io/api/) - REST API for repository queries
- [OCM CLI Releases](https://github.com/openshift-online/ocm-cli/releases) - Latest version and binary downloads (v1.0.10 as of Dec 2025)
- [Semantic Versioning Spec](https://semver.org/) - Version format specification

**Python Libraries:**
- [python-semver PyPI](https://pypi.org/project/semver/) - Version 3.0.4, Python 3.7-3.14 support
- [PyYAML PyPI](https://pypi.org/project/pyyaml/) - Version 6.0.2+ for YAML parsing

**Research Sources:**
- [How to Build Images with Podman](https://oneuptime.com/blog/post/2026-01-27-podman-build/view) - Multi-stage best practices (2026)
- [Skopeo: The Unsung Hero](https://developers.redhat.com/articles/2025/09/24/skopeo-unsung-hero-linux-container-tools) - Registry inspection patterns
- [Python YAML Parser Guide](https://ioflood.com/blog/python-yaml-parser/) - PyYAML vs ruamel.yaml comparison
- [Quay.io API Guide](https://docs.projectquay.io/api_quay.html) - Tag listing endpoints

**Confidence Assessment:**
- Multi-stage builds: HIGH (verified with official podman docs, current as of 2026)
- Quay.io API: HIGH (official API documentation reviewed)
- OCM CLI: HIGH (GitHub releases page checked, v1.0.10 confirmed Dec 2025)
- YAML libraries: HIGH (PyPI verified, version compatibility confirmed)
- Build automation patterns: MEDIUM (based on community practices, not official guidelines)

---

*Stack research for: MC CLI Multi-Stage Container Builds*
*Researched: 2026-02-09*
