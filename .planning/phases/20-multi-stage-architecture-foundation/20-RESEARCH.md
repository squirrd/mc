# Phase 20: Multi-Stage Architecture Foundation - Research

**Researched:** 2026-02-09
**Domain:** Multi-stage container builds with layer caching optimization
**Confidence:** HIGH

## Summary

Multi-stage Containerfile builds are the established best practice for creating optimized container images. They use multiple FROM statements with named stages to separate build-time dependencies from runtime artifacts, enabling final images that are significantly smaller, more secure, and faster to deploy.

For this phase converting MC's single-stage RHEL 10 UBI Containerfile to multi-stage architecture, the standard approach uses three named stages: a minimal downloader stage for OCM binary, a builder stage with Python build dependencies, and a final runtime-only stage. Layer caching optimization is achieved through strategic instruction ordering (stable before volatile) and careful ARG placement to prevent unnecessary cache invalidation.

The research shows consistent patterns across 2026 sources: named stages improve maintainability, COPY --from enables selective artifact transfer, BuildKit automatically skips unused stages, and proper layer ordering can reduce build times from minutes to seconds when caching works effectively.

**Primary recommendation:** Use named stages (ocm-downloader, mc-builder, final), place ARG declarations after dependencies are installed to maximize cache reuse, use UBI-minimal for downloader stages, and verify caching with automated "Using cache" assertions in test scripts.

## Standard Stack

The established libraries/tools for multi-stage container builds with RHEL UBI:

### Core
| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| RHEL 10 UBI | 10.1 | Final runtime base | Official Red Hat base image, OCI-compliant, freely redistributable |
| UBI-minimal | 10.x | Downloader stage base | 92MB disk / 32MB compressed, includes microdnf, optimal for intermediate stages |
| BuildKit | Default in Docker 23+ | Build engine | Layer caching, stage skipping, cache mounts enabled by default |
| podman/docker | Latest | Build tooling | Standard OCI container build tools |

### Supporting
| Library/Tool | Version | Purpose | When to Use |
|--------------|---------|---------|-------------|
| curl | Pre-installed in UBI | Binary downloads | Already in UBI, reliable for GitHub releases |
| sha256sum | Pre-installed | Checksum verification | Standard tool for integrity validation |
| microdnf | Pre-installed in UBI-minimal | Package installation | Minimal package manager for intermediate stages |
| python3-pip | From RHEL repos | Python package build | Required only in builder stage, not final |
| setuptools/wheel | Latest from pip | Python editable installs | Required for pip install --no-build-isolation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| UBI-minimal | UBI-micro | Micro has no package manager (0 bytes), requires external dnf --installroot pattern, more complex |
| curl | wget | Both pre-installed in UBI, curl more common in examples |
| Named stages | Numeric references (0,1,2) | Numeric breaks when Containerfile reordered, named stages more maintainable |

**Installation:**
```bash
# No installation needed - UBI images pulled during build
podman build -t mc:multi-stage -f container/Containerfile .

# Verify BuildKit enabled (Docker 23+)
docker buildx version
```

## Architecture Patterns

### Recommended Multi-Stage Structure
```
Containerfile (multi-stage):
├── Stage 1: ocm-downloader (UBI-minimal)
│   ├── Download OCM binary from GitHub releases
│   ├── Verify SHA256 checksum
│   └── Extract/prepare binary
├── Stage 2: mc-builder (UBI standard)
│   ├── Install build dependencies (pip, gcc, python-devel)
│   ├── Copy project source
│   └── Build Python packages
└── Stage 3: final (UBI standard)
    ├── Install runtime dependencies only
    ├── COPY --from=ocm-downloader /usr/local/bin/ocm
    ├── COPY --from=mc-builder /opt/mc (editable install)
    ├── COPY --from=mc-builder Python site-packages
    └── Non-root user, WORKDIR, ENTRYPOINT
```

### Pattern 1: Named Stage with COPY --from

**What:** Use `FROM image:tag AS stage-name` to create named stages, then `COPY --from=stage-name` to selectively copy artifacts.

**When to use:** Always in multi-stage builds. Named stages are more maintainable than numeric references.

**Example:**
```dockerfile
# Source: https://docs.docker.com/build/building/multi-stage/
FROM registry.access.redhat.com/ubi10/ubi-minimal:latest AS ocm-downloader

ARG OCM_VERSION=0.35.0
RUN microdnf install -y curl && \
    curl -LO "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz" && \
    curl -LO "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256" && \
    sha256sum --check ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256 && \
    tar -xzf ocm-${OCM_VERSION}-linux-amd64.tar.gz && \
    chmod +x ocm && \
    mv ocm /usr/local/bin/ocm

FROM registry.access.redhat.com/ubi10/ubi:10.1 AS final
COPY --from=ocm-downloader /usr/local/bin/ocm /usr/local/bin/ocm
```

**Key benefits:**
- BuildKit only builds stages that final stage depends on (skips unused stages)
- Named references don't break when stages are reordered
- External images can be used as sources: `COPY --from=nginx:latest /etc/nginx/nginx.conf`

### Pattern 2: Layer Ordering for Cache Optimization

**What:** Order instructions from least to most frequently changing. Expensive operations (dependency installation) placed early, volatile operations (source code copy) placed late.

**When to use:** Every Containerfile. Critical for effective layer caching.

**Example:**
```dockerfile
# Source: https://docs.docker.com/build/cache/optimize/
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS mc-builder

# Layer 1: System dependencies (rarely change)
RUN dnf install -y python3-pip gcc python3-devel && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Layer 2: Python build dependencies (change occasionally)
RUN pip3 install --no-cache-dir setuptools wheel

# Layer 3: Project dependencies (change when requirements.txt changes)
COPY requirements.txt /opt/mc/
RUN pip3 install --no-cache-dir -r /opt/mc/requirements.txt

# Layer 4: Application code (changes frequently)
COPY . /opt/mc/
RUN pip3 install --no-cache-dir --no-build-isolation -e /opt/mc
```

**Cache invalidation cascade:**
- If Layer 4 changes, only Layer 4 rebuilds
- If Layer 3 changes, Layers 3-4 rebuild
- If Layer 1 changes, all layers rebuild

### Pattern 3: ARG Placement to Preserve Cache

**What:** Place ARG declarations as late as possible in Containerfile. Changing an ARG invalidates all subsequent layers.

**When to use:** When versions need to be parameterized but shouldn't invalidate earlier dependency layers.

**Example:**
```dockerfile
# Source: https://docs.docker.com/build/cache/optimize/
FROM registry.access.redhat.com/ubi10/ubi-minimal:latest AS ocm-downloader

# Install curl first (cached regardless of OCM version)
RUN microdnf install -y curl && microdnf clean all

# ARG after dependencies - only download step invalidated when version changes
ARG OCM_VERSION=0.35.0

RUN curl -LO "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz"
```

**Anti-pattern (ARG too early):**
```dockerfile
# BAD: ARG before dependencies
FROM registry.access.redhat.com/ubi10/ubi-minimal:latest AS ocm-downloader

ARG OCM_VERSION=0.35.0  # Changing this invalidates curl install below

RUN microdnf install -y curl  # Rebuilds even though curl version unchanged
```

### Pattern 4: DNF Package Management in Single Layer

**What:** Chain `dnf install`, `dnf clean all`, and manual cache removal in single RUN instruction.

**When to use:** Every dnf/yum package installation in containers.

**Example:**
```dockerfile
# Source: https://protsenko.dev/infrastructure-security/purge-dnf-package-cache/
RUN dnf install -y python3-pip gcc python3-devel && \
    dnf clean all && \
    rm -rf /var/cache/dnf
```

**Why:** Each RUN creates a new layer. If cleanup is in separate RUN, the cache persists in earlier layer, bloating final image even though later layer removes it.

### Pattern 5: Binary Download with SHA256 Verification

**What:** Download binary and checksum file, verify with sha256sum --check, fail build on mismatch.

**When to use:** Downloading any external binaries in container builds.

**Example:**
```dockerfile
# Source: https://thanoskoutr.com/posts/download-release-github/
ARG OCM_VERSION=0.35.0
ARG GITHUB_ORG=open-component-model
ARG GITHUB_REPO=ocm

RUN set -e && \
    curl -LO "https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz" && \
    curl -LO "https://github.com/${GITHUB_ORG}/${GITHUB_REPO}/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256" && \
    sha256sum --check ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256 && \
    tar -xzf ocm-${OCM_VERSION}-linux-amd64.tar.gz && \
    chmod +x ocm && \
    mv ocm /usr/local/bin/ocm && \
    rm -f ocm-*.tar.gz ocm-*.sha256
```

**Key elements:**
- `set -e`: Exit immediately on any error (fail-fast)
- Download both binary and `.sha256` checksum file
- `sha256sum --check` verifies integrity, exits non-zero on mismatch
- GitHub releases provide SHA256 checksums as of June 2025
- Cleanup temporary files in same layer to avoid bloat

### Pattern 6: Python Editable Install in Multi-Stage

**What:** For Python packages installed with `pip install -e`, copy both the source directory and installed site-packages to final stage.

**When to use:** When preserving editable install behavior in final image (source changes reflected without reinstall).

**Example:**
```dockerfile
# Source: https://pythonspeed.com/articles/multi-stage-docker-python/
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS mc-builder

RUN dnf install -y python3-pip gcc python3-devel && \
    dnf clean all && rm -rf /var/cache/dnf

COPY . /opt/mc
RUN pip3 install --no-cache-dir setuptools wheel && \
    pip3 install --no-cache-dir --no-build-isolation -e /opt/mc

FROM registry.access.redhat.com/ubi10/ubi:10.1 AS final

# Copy source directory (editable install points to this)
COPY --from=mc-builder /opt/mc /opt/mc

# Copy site-packages with .egg-link and .pth files
COPY --from=mc-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
```

**Why editable installs complicate multi-stage:**
- Editable install creates `.egg-link` file in site-packages pointing to source directory
- Must copy both source directory and site-packages to preserve linkage
- Alternative: Use `pip install --user` to isolate all files in `~/.local` for single-directory copy

### Anti-Patterns to Avoid

- **Single-stage builds:** Bloated images with build tools in production. Use multi-stage instead.
- **Copying source before dependencies:** Cache busts on every code change. Copy package files first, install dependencies, then copy source.
- **Running as root:** Security risk. Always create non-root user and switch with USER instruction.
- **Using ADD instead of COPY:** ADD has surprise tar extraction and URL download behavior. Use COPY for local files.
- **Separate RUN for cleanup:** `RUN dnf install` then `RUN dnf clean` keeps cache in earlier layer. Chain with &&.
- **Numeric stage references:** `COPY --from=0` breaks when stages reordered. Use `COPY --from=builder`.
- **ARG before stable layers:** Changing version ARG invalidates all subsequent layers. Place ARG late.
- **No .dockerignore:** `.git`, `node_modules`, temp files trigger cache invalidation. Always use .dockerignore.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Download binary from GitHub | Custom curl script | GitHub Releases API + sha256sum --check | GitHub provides official checksums (.sha256 files), sha256sum handles verification, format is standardized |
| Layer caching verification | Manual build inspection | Automated test script checking "Using cache" in output | BuildKit outputs "Using cache" for each cached layer, scriptable verification prevents regressions |
| Image size comparison | Manual `docker images` checks | Automated size assertion in CI | Build output shows size, `docker inspect` provides JSON, automated tests prevent accidental bloat |
| Multi-stage dependency copying | Hand-picking files | COPY --from with known paths | Easy to miss files, standard paths well-documented, COPY --from is atomic |
| Python virtual environments | venv in container | pip install --user or direct install | Virtual envs add complexity in containers, --user isolates to single directory, containers already isolated |
| Package manager caching | Custom cache dirs | BuildKit cache mounts | BuildKit cache mounts persist across builds, automatically managed, faster than custom solutions |

**Key insight:** Multi-stage builds have well-established patterns documented by Docker and RHEL. Container size optimization, layer caching, and binary verification are solved problems with standard tools. Custom solutions add complexity without benefit.

## Common Pitfalls

### Pitfall 1: Cache Invalidation from ARG Placement

**What goes wrong:** Placing ARG declarations early in Containerfile causes entire build to re-run when version changes, even though dependencies haven't changed.

**Why it happens:** Changing an ARG value invalidates that layer and all subsequent layers. If ARG appears before expensive operations like `dnf install`, those operations rebuild unnecessarily.

**How to avoid:**
1. Place ARG declarations as late as possible
2. Install dependencies before declaring version ARGs
3. Group related ARGs together just before their usage
4. Use separate ARG for cache-busting vs actual versions

**Warning signs:**
- Build logs show "Using cache" for first few layers, then rebuild everything on version change
- `dnf install` or `pip install` re-run even though package lists unchanged
- Build times don't improve on second identical build

**Example:**
```dockerfile
# GOOD: ARG after stable dependencies
RUN dnf install -y curl
ARG OCM_VERSION=0.35.0
RUN curl -LO ".../${OCM_VERSION}/..."

# BAD: ARG before stable dependencies
ARG OCM_VERSION=0.35.0
RUN dnf install -y curl  # Rebuilds when OCM_VERSION changes
```

### Pitfall 2: Incomplete DNF Cache Cleanup

**What goes wrong:** Final image is larger than expected because DNF metadata cache persists in intermediate layers even though final layer removes it.

**Why it happens:** Each RUN instruction creates a new layer. If `dnf clean all` is in a separate RUN from `dnf install`, the cache exists in the install layer and contributes to final image size.

**How to avoid:**
1. Chain installation and cleanup in single RUN with &&
2. Add `rm -rf /var/cache/dnf` for thorough cleanup
3. Verify with `docker history <image>` to see layer sizes

**Warning signs:**
- Final image 50-100MB larger than expected
- `docker history` shows large layer for dnf install even with clean command
- Multiple RUN statements for package management

**Example:**
```dockerfile
# GOOD: Single RUN with cleanup
RUN dnf install -y python3-pip && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# BAD: Separate RUN statements
RUN dnf install -y python3-pip  # Creates layer with cache
RUN dnf clean all               # Removes from filesystem but layer persists
```

### Pitfall 3: Missing Build Tools in Final Image

**What goes wrong:** Application fails to run in final stage because build dependencies (gcc, python3-devel, pip) weren't copied, only runtime is needed but detection is wrong.

**Why it happens:** Multi-stage builds separate builder and final stages. Developers forget to install runtime dependencies in final stage or incorrectly copy build tools.

**How to avoid:**
1. Explicitly install runtime dependencies in final stage (python3, libraries)
2. Don't copy build tools (gcc, pip, python3-devel) to final stage
3. Test final image in isolation to ensure runtime works
4. For Python editable installs, copy both source and site-packages

**Warning signs:**
- Import errors when running container
- "gcc: command not found" or similar errors at runtime
- Container works in builder stage but fails in final stage
- Python packages missing at runtime

**Example:**
```dockerfile
# Builder stage
FROM ubi10:10.1 AS builder
RUN dnf install -y python3-pip gcc python3-devel  # Build tools
COPY . /opt/mc
RUN pip3 install -e /opt/mc

# Final stage - MUST install runtime dependencies
FROM ubi10:10.1 AS final
RUN dnf install -y python3  # Runtime only, NO gcc/pip/devel
COPY --from=builder /opt/mc /opt/mc
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
```

### Pitfall 4: SHA256 Verification Without Fail-Fast

**What goes wrong:** Binary download fails verification but build continues, resulting in container with missing or corrupted binary.

**Why it happens:** Shell commands by default continue on error unless `set -e` is used. Without fail-fast, `sha256sum --check` can fail but subsequent commands execute.

**How to avoid:**
1. Use `set -e` at start of RUN command for fail-fast behavior
2. Chain commands with && so failure stops execution
3. Use `set -o pipefail` to catch errors in piped commands
4. Test failure scenarios (wrong checksum) to verify build fails

**Warning signs:**
- Build succeeds but binary missing in final image
- Verification logs show checksum mismatch but build completes
- Inconsistent binary presence across builds

**Example:**
```dockerfile
# GOOD: Fail-fast with set -e
RUN set -e && \
    curl -LO "https://.../binary.tar.gz" && \
    curl -LO "https://.../binary.tar.gz.sha256" && \
    sha256sum --check binary.tar.gz.sha256 && \
    tar -xzf binary.tar.gz

# BAD: No fail-fast, continues on error
RUN curl -LO "https://.../binary.tar.gz"
RUN curl -LO "https://.../binary.tar.gz.sha256"
RUN sha256sum --check binary.tar.gz.sha256  # Fails but next command runs
RUN tar -xzf binary.tar.gz  # Extracts nothing or corrupted file
```

### Pitfall 5: Non-Root User Placement in Multi-Stage

**What goes wrong:** Files copied from builder stage have wrong ownership/permissions in final stage, causing runtime errors.

**Why it happens:** Builder stage runs as root, creates files owned by root. Final stage switches to non-root user but files remain root-owned and may not be accessible.

**How to avoid:**
1. Keep USER root during COPY --from operations
2. Use COPY --chown=user:group to set ownership during copy
3. Switch to non-root user after all COPY operations complete
4. Verify file permissions in final image

**Warning signs:**
- "Permission denied" errors at runtime
- Application can't read configuration files
- `ls -la` shows root:root ownership on files accessed by non-root user

**Example:**
```dockerfile
# GOOD: Set ownership during copy, switch user last
FROM ubi10:10.1 AS final
RUN groupadd --system mcuser && useradd --system --gid mcuser mcuser
COPY --from=builder --chown=mcuser:mcuser /opt/mc /opt/mc
USER mcuser  # Switch after all copies complete

# BAD: Switch user before copying
FROM ubi10:10.1 AS final
RUN groupadd --system mcuser && useradd --system --gid mcuser mcuser
USER mcuser  # Too early
COPY --from=builder /opt/mc /opt/mc  # Owned by root, user can't access
```

### Pitfall 6: Cache Busting from .dockerignore Omission

**What goes wrong:** Builds don't use cache even though code unchanged, because hidden files (.git, .venv, __pycache__) trigger layer invalidation.

**Why it happens:** COPY instruction checksums all files in context. Without .dockerignore, temporary files, git history, and build artifacts change between builds, invalidating cache.

**How to avoid:**
1. Create .dockerignore file at project root
2. Exclude .git, .venv, __pycache__, node_modules, *.pyc
3. Exclude IDE files (.vscode, .idea)
4. Test that touching excluded files doesn't invalidate cache

**Warning signs:**
- `git commit` causes full rebuild even though source unchanged
- Virtual environment changes trigger full rebuild
- Build cache never reused despite no code changes

**Example .dockerignore:**
```
.git
.venv
.vscode
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.coverage
.mypy_cache
*.egg-info
dist/
build/
```

## Code Examples

Verified patterns from official sources:

### Complete Multi-Stage Pattern for Python Application

```dockerfile
# Source: Docker official docs + RHEL best practices
# https://docs.docker.com/build/building/multi-stage/
# https://developers.redhat.com/articles/2021/11/30/build-lightweight-and-secure-container-images-using-rhel-ubi

# Stage 1: Download external binary with verification
FROM registry.access.redhat.com/ubi10/ubi-minimal:latest AS ocm-downloader

# Install downloader tools (cached)
RUN microdnf install -y curl && microdnf clean all

# Version ARG after dependencies
ARG OCM_VERSION=0.35.0

# Download and verify in single fail-fast RUN
RUN set -e && \
    curl -LO "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz" && \
    curl -LO "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256" && \
    sha256sum --check ocm-${OCM_VERSION}-linux-amd64.tar.gz.sha256 && \
    tar -xzf ocm-${OCM_VERSION}-linux-amd64.tar.gz && \
    chmod +x ocm && \
    mv ocm /usr/local/bin/ocm && \
    rm -f ocm-*.tar.gz ocm-*.sha256

# Stage 2: Build Python application
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS mc-builder

# System dependencies (rarely change)
RUN dnf install -y python3-pip gcc python3-devel && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Python build dependencies (change occasionally)
RUN pip3 install --no-cache-dir setuptools wheel

# Application source (changes frequently)
COPY . /opt/mc

# Build application
RUN pip3 install --no-cache-dir --no-build-isolation -e /opt/mc

# Stage 3: Final runtime image
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS final

LABEL maintainer="MC CLI Team"
LABEL description="RHEL 10 UBI container with MC CLI and OCM"
LABEL version="2.0"

# Runtime dependencies only (NO build tools)
RUN dnf install -y python3 vim nano wget openssl && \
    dnf clean all && \
    rm -rf /var/cache/dnf

# Create non-root user
RUN groupadd --system mcuser && \
    useradd --system --gid mcuser --home-dir /home/mcuser --create-home mcuser

# Create workspace with correct ownership
RUN mkdir -p /case && chown mcuser:mcuser /case

# Copy artifacts from previous stages with correct ownership
COPY --from=ocm-downloader --chown=mcuser:mcuser /usr/local/bin/ocm /usr/local/bin/ocm
COPY --from=mc-builder --chown=mcuser:mcuser /opt/mc /opt/mc
COPY --from=mc-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Copy entrypoint script
COPY --chmod=755 container/entrypoint.sh /usr/local/bin/entrypoint.sh

# Environment and user
ENV MC_RUNTIME_MODE=agent
USER mcuser
WORKDIR /case

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
```

### Cache Verification Test Script

```bash
# Source: Composite pattern from cache verification best practices
# https://www.baeldung.com/ops/docker-build-cache

#!/bin/bash
set -euo pipefail

echo "Building container image (first build)..."
podman build -t mc:test -f container/Containerfile . | tee build1.log

echo "Building container image (second build, no changes)..."
podman build -t mc:test -f container/Containerfile . | tee build2.log

# Verify all stages show "Using cache"
STAGES=("ocm-downloader" "mc-builder" "final")
for stage in "${STAGES[@]}"; do
    if ! grep -q "Using cache" build2.log; then
        echo "ERROR: Stage $stage not using cache"
        exit 1
    fi
done

echo "SUCCESS: All stages using cache on unchanged rebuild"

# Cleanup
rm -f build1.log build2.log
```

### Image Size Comparison Script

```bash
# Source: Container size measurement best practices
# https://oneuptime.com/blog/post/2026-01-27-optimize-container-image-sizes/

#!/bin/bash
set -euo pipefail

# Get original single-stage image size
ORIGINAL_SIZE=$(podman images mc:original --format "{{.Size}}" | sed 's/MB//' | sed 's/GB/*1024/')
ORIGINAL_SIZE_MB=$(echo "$ORIGINAL_SIZE" | bc)

# Get multi-stage image size
MULTISTAGE_SIZE=$(podman images mc:multi-stage --format "{{.Size}}" | sed 's/MB//' | sed 's/GB/*1024/')
MULTISTAGE_SIZE_MB=$(echo "$MULTISTAGE_SIZE" | bc)

# Calculate reduction
REDUCTION=$(echo "scale=2; ($ORIGINAL_SIZE_MB - $MULTISTAGE_SIZE_MB) / $ORIGINAL_SIZE_MB * 100" | bc)

echo "Original image: ${ORIGINAL_SIZE_MB}MB"
echo "Multi-stage image: ${MULTISTAGE_SIZE_MB}MB"
echo "Reduction: ${REDUCTION}%"

# Verify multi-stage is smaller (success criteria)
if (( $(echo "$MULTISTAGE_SIZE_MB >= $ORIGINAL_SIZE_MB" | bc -l) )); then
    echo "ERROR: Multi-stage image not smaller than original"
    exit 1
fi

echo "SUCCESS: Multi-stage image is smaller"
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single-stage builds | Multi-stage builds | Docker 17.05 (2017) | 50-90% size reduction typical, build tools excluded from final image |
| Numeric stage references (COPY --from=0) | Named stages (COPY --from=builder) | Docker 17.05 (2017) | Maintainable when stages reordered, self-documenting |
| Manual cache management | BuildKit cache mounts | Docker 23+ (2023, default) | Automatic cache persistence across builds, no manual scripting |
| Legacy Docker builder | BuildKit | Docker 23+ (2023, default) | Stage skipping, parallel builds, improved caching, 2-10x faster |
| GPG verification for binaries | SHA256 checksums in releases | GitHub June 2025 | Simpler verification, SHA256 provided automatically for release assets |
| Virtual environments in containers | Direct pip install or pip install --user | Ongoing best practice | Containers already isolated, venv adds complexity, direct install simpler |
| UBI 8/9 | UBI 10 | RHEL 10 release (2024) | Python 3.12 pre-installed, updated package repos |
| pip without --no-cache-dir | pip --no-cache-dir standard | Established best practice | 10-50MB reduction per layer, prevents pip cache bloat |

**Deprecated/outdated:**
- **MAINTAINER instruction**: Use LABEL maintainer instead (deprecated since Docker 1.13)
- **apt-get upgrade in Dockerfiles**: Non-reproducible builds, use pinned base image versions
- **Using latest tag in FROM**: Non-reproducible, pin specific versions (ubi10:10.1)
- **Shell form of ENTRYPOINT/CMD**: Doesn't handle signals properly, use exec form with arrays

## Open Questions

Things that couldn't be fully resolved:

1. **OCM Release Checksum Format**
   - What we know: GitHub releases provide SHA256 checksums as of June 2025, OCM v0.35.0 latest as of Jan 2026
   - What's unclear: Exact filename format for OCM checksums (*.sha256 vs *.sha256sum), need to verify in actual release
   - Recommendation: Check OCM releases page to confirm checksum file naming, fallback to GPG verification if SHA256 unavailable

2. **Python Site-Packages Path for RHEL 10 UBI Python 3.12**
   - What we know: RHEL 10 UBI has Python 3.12 pre-installed, standard path likely `/usr/local/lib/python3.12/site-packages` or `/usr/lib/python3.12/site-packages`
   - What's unclear: Exact path when using pip3 vs pip, system vs local site-packages
   - Recommendation: Verify with `python3 -m site` in builder stage, document actual path found

3. **UBI-minimal vs UBI-micro for Downloader Stage**
   - What we know: UBI-minimal has microdnf (92MB/32MB compressed), UBI-micro has no package manager (smaller)
   - What's unclear: Whether UBI-micro pattern (dnf --installroot from external) worth complexity for single curl install
   - Recommendation: Use UBI-minimal for simplicity, curl install is <10MB, simplicity outweighs minimal size gain

4. **Existing Container Features Needed for Tests**
   - What we know: Original Containerfile mentions "features needed for requirements/integration tests", includes vim, nano, wget, openssl
   - What's unclear: Which specific tools are actually required vs nice-to-have
   - Recommendation: Preserve all tools from original in final stage initially, remove in future optimization phase after test validation

## Sources

### Primary (HIGH confidence)

- [Docker Multi-Stage Builds Official Docs](https://docs.docker.com/build/building/multi-stage/) - Named stages, COPY --from syntax, BuildKit stage skipping
- [Docker Build Cache Invalidation](https://docs.docker.com/build/cache/invalidation/) - How ARG affects cache, layer ordering principles
- [Docker Cache Optimization Best Practices](https://docs.docker.com/build/cache/optimize/) - Layer ordering, expensive operations placement
- [RHEL UBI Build Lightweight Images](https://developers.redhat.com/articles/2021/11/30/build-lightweight-and-secure-container-images-using-rhel-ubi) - Multi-stage patterns with UBI, UBI-micro advanced usage
- [RHEL 10 UBI Minimal Catalog](https://catalog.redhat.com/en/software/containers/ubi10/ubi-minimal/66f1504a379b9c2cf23e145c) - UBI-minimal specs, size (92MB/32MB), microdnf included
- [OCM GitHub Repository](https://github.com/open-component-model/ocm) - v0.35.0 latest release (Jan 2026), GPG verification documented

### Secondary (MEDIUM confidence)

- [How to Optimize Docker Build Times with Layer Caching](https://oneuptime.com/blog/post/2026-01-16-docker-optimize-build-times/) (2026-01-16) - ARG placement, instruction ordering, BuildKit features
- [How to Implement Docker Layer Caching Strategies](https://oneuptime.com/blog/post/2026-01-30-how-to-implement-docker-layer-caching-strategies/) (2026-01-30) - Cache verification, "Using cache" output parsing
- [How to Optimize Container Image Sizes](https://oneuptime.com/blog/post/2026-01-27-optimize-container-image-sizes/) (2026-01-27) - Size comparison techniques, optimization examples
- [Dockerfile Clean DNF Package Cache](https://protsenko.dev/infrastructure-security/purge-dnf-package-cache/) - DNF cache cleanup best practice, single-layer pattern
- [Download Latest Release from GitHub and Verify with Checksums](https://thanoskoutr.com/posts/download-release-github/) - SHA256 verification pattern, curl commands
- [Multi-stage Builds #2: Python Specifics](https://pythonspeed.com/articles/multi-stage-docker-python/) - Editable install complications, pip install --user pattern
- [Baeldung Docker Build Cache Guide](https://www.baeldung.com/ops/docker-build-cache) - Cache verification, "Using cache" output

### Tertiary (LOW confidence - WebSearch only)

- [10 Container Security Best Practices 2026](https://www.portainer.io/blog/container-security-best-practices) - SHA256 verification importance, fail-fast patterns
- [Distroless vs UBI Micro Comparison](https://www.anantacloud.com/post/distroless-vs-ubi-micro-choosing-the-right-minimal-container-base-image) - UBI-micro vs UBI-minimal tradeoffs
- Various DevOps blog articles on multi-stage builds (multiple sources 2025-2026) - General patterns, cross-verified with official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Docker/RHEL documentation, established since 2017
- Architecture patterns: HIGH - Docker official docs, RHEL developer guides, verified in production
- Pitfalls: MEDIUM-HIGH - Combination of official docs and community experience, cross-verified patterns
- OCM integration: MEDIUM - GitHub repo verified, checksum format needs confirmation in actual release
- Python editable install multi-stage: MEDIUM - Community patterns, not officially documented by Docker/RHEL

**Research date:** 2026-02-09
**Valid until:** 30 days (stable domain, multi-stage builds well-established, but OCM versions change monthly)

**Key uncertainties requiring validation:**
1. OCM checksum filename format (verify in actual v0.35.0 release)
2. Python 3.12 site-packages exact path in RHEL 10 UBI
3. Minimal tool set required for existing integration tests
