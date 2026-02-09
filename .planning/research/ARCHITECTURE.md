# Architecture Research: Multi-Stage Container Builds and Version Management

**Domain:** Container build tooling with automated versioning for containerized development environments
**Researched:** 2026-02-09
**Confidence:** HIGH

## Executive Summary

Multi-stage container builds integrate cleanly with MC's existing Podman-based workflow by separating build-time dependencies from runtime artifacts, enabling efficient layer caching and independent version management. The architecture introduces three new components in the `container/` directory: a multi-stage Containerfile, a versions.yaml config, and a build-container.sh automation script. These additions require minimal changes to existing Python container management code, preserving the established pull-then-create workflow while adding intelligent build capabilities.


## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Build-Time Components                             │
│  (container/ directory - new and modified files)                     │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────────────────┐    │
│  │ versions.yaml│  │build-container│  │ Containerfile (multi-   │    │
│  │  - image: x.y│  │    .sh       │  │  stage with 3+ stages)  │    │
│  │  - mc: x.y.z │──│ reads config │──│  1. mc-builder          │    │
│  │  - tools:    │  │ queries quay │  │  2. ocm-downloader      │    │
│  │    ocm: x.y  │  │ auto-bumps   │  │  3. final (runtime)     │    │
│  └──────────────┘  └──────────────┘  └─────────────────────────┘    │
│                           │                      │                   │
│                           ↓                      ↓                   │
│                  ┌────────────────────────────────────┐              │
│                  │   Podman build (layer caching)     │              │
│                  └────────────────────────────────────┘              │
├─────────────────────────────────────────────────────────────────────┤
│                    Registry Storage                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  quay.io/rhn_support_dsquirre/mc-container                    │   │
│  │  - :latest (rolling tag)                                      │   │
│  │  - :1.0.0, :1.0.1, :1.1.0 (semver versioned tags)            │   │
│  └──────────────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────────────┤
│                    Runtime Components                                │
│  (src/mc/container/ - NO changes needed)                             │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  ContainerManager._ensure_image()                             │   │
│  │  1. Check local: mc-rhel10:latest exists?                     │   │
│  │  2. If not: Pull from quay.io/rhn_support_dsquirre/...        │   │
│  │  3. Tag as mc-rhel10:latest                                   │   │
│  │  4. Create container with workspace mount                     │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Multi-Stage Containerfile Architecture

### Stage Structure and Responsibilities

| Stage | Base Image | Responsibility | Artifacts Produced | Layer Caching Benefit |
|-------|------------|----------------|-------------------|----------------------|
| **mc-builder** | registry.access.redhat.com/ubi10/ubi:10.1 | Install build dependencies, copy MC source, install MC in editable mode | Installed MC CLI at /opt/mc | Cached unless MC source or pyproject.toml changes |
| **ocm-downloader** | registry.access.redhat.com/ubi10/ubi-minimal:10.1 | Download versioned OCM binary from GitHub releases | /tmp/ocm binary | Cached unless OCM version in versions.yaml changes |
| **final (runtime)** | registry.access.redhat.com/ubi10/ubi:10.1 | Copy MC from builder, copy OCM from downloader, install runtime dependencies, configure user | Complete runtime image (mc-rhel10:latest) | Only rebuilds when earlier stages change or runtime config changes |

### Containerfile Pattern

```dockerfile
# Stage 1: mc-builder - Build MC CLI from source
FROM registry.access.redhat.com/ubi10/ubi:10.1 AS mc-builder
RUN dnf install -y python3-pip && dnf clean all
RUN pip3 install --no-cache-dir setuptools wheel
COPY . /opt/mc
RUN pip3 install --no-cache-dir --no-build-isolation -e /opt/mc

# Stage 2: ocm-downloader - Fetch versioned OCM tool
FROM registry.access.redhat.com/ubi10/ubi-minimal:10.1 AS ocm-downloader
ARG OCM_VERSION=0.1.71
RUN microdnf install -y tar gzip && microdnf clean all
RUN curl -L "https://github.com/openshift-online/ocm-cli/releases/download/v${OCM_VERSION}/ocm-linux-amd64" \
    -o /tmp/ocm && chmod +x /tmp/ocm

# Stage 3: final - Assemble runtime image
FROM registry.access.redhat.com/ubi10/ubi:10.1
# Install runtime dependencies (no build tools)
RUN dnf install -y python3-pip vim nano wget openssl && dnf clean all
# Copy MC from builder stage
COPY --from=mc-builder /opt/mc /opt/mc
COPY --from=mc-builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=mc-builder /usr/local/bin/mc /usr/local/bin/mc
# Copy OCM from downloader stage
COPY --from=ocm-downloader /tmp/ocm /usr/local/bin/ocm
# User setup, workspace, entrypoint (unchanged from current Containerfile)
RUN groupadd --system mcuser && useradd --system --gid mcuser --home-dir /home/mcuser --create-home mcuser
RUN mkdir -p /case && chown mcuser:mcuser /case
COPY --chmod=755 container/entrypoint.sh /usr/local/bin/entrypoint.sh
ENV MC_RUNTIME_MODE=agent
USER mcuser
WORKDIR /case
ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/bin/bash"]
```

### Layer Caching Optimization

**Key Principle:** Order instructions from least-frequently-changed to most-frequently-changed.

**Caching Behavior:**
1. **mc-builder stage:** Rebuilds when `COPY . /opt/mc` detects source changes or when pyproject.toml dependencies change
2. **ocm-downloader stage:** Rebuilds only when OCM_VERSION ARG changes (version bump in versions.yaml)
3. **final stage:** COPY --from instructions invalidate cache only when source stages rebuild

**Build Speed Benefits:**
- First build: Full build time (~3-5 minutes for all stages)
- MC source change: Rebuilds mc-builder + final (~2-3 minutes), ocm-downloader cached
- OCM version change: Rebuilds ocm-downloader + final (~1 minute), mc-builder cached
- Containerfile-only change (labels, env): Rebuilds final only (~30 seconds)

## Version Management Architecture

### versions.yaml Schema

```yaml
# Image version (independent semver, NOT tied to MC CLI version)
image:
  version: "1.0.0"  # x.y.z semver
  description: "RHEL 10 UBI container with MC CLI and essential tools"

# MC CLI version (for reference, read from pyproject.toml)
mc:
  version: "2.0.3"  # Read from pyproject.toml, not modified by build script
  source: "pyproject.toml"

# Tool versions (triggers auto-patch-bump when changed)
tools:
  ocm:
    version: "0.1.71"
    url: "https://github.com/openshift-online/ocm-cli/releases/download/v{VERSION}/ocm-linux-amd64"
    description: "OpenShift Cluster Manager CLI"
  # Future tools:
  # oc:
  #   version: "4.15.0"
  #   url: "https://mirror.openshift.com/pub/openshift-v4/clients/oc/{VERSION}/linux/oc.tar.gz"
```

**Schema Rationale:**
- **image.version:** Independent from MC CLI version allows container updates (new tools, base image updates) without MC code changes
- **mc.version:** Reference only, proves which MC version is in the image
- **tools:** Each tool as key with version + URL pattern, making it easy to add new tools

### Version Bumping Logic

**Automatic (patch):**
- Trigger: Any version change in `tools:` section
- Logic: Increment `image.version` patch (1.0.0 → 1.0.1)
- Rationale: New tool version = new image build needed, but API-compatible change

**Manual (minor):**
- Trigger: New tool added to `tools:` section (developer runs `build-container.sh --minor`)
- Logic: Increment `image.version` minor (1.0.1 → 1.1.0)
- Rationale: New capability added, feature release

**Manual (major):**
- Trigger: Breaking change (base image upgrade RHEL 10 → 11, MC incompatible change)
- Logic: Increment `image.version` major (1.1.0 → 2.0.0)
- Rationale: Signals incompatibility to users


## build-container.sh Responsibilities

### Core Workflow

```
1. Read versions.yaml
   ├─ Parse current image.version
   ├─ Extract tool versions (OCM_VERSION, etc.)
   └─ Validate schema

2. Query Quay.io for latest published tag
   ├─ API: GET https://quay.io/api/v1/repository/rhn_support_dsquirre/mc-container/tag/
   ├─ Parse JSON response for tags
   └─ Find highest semver tag (ignore "latest")

3. Compare versions and decide bump
   ├─ If tools versions changed since last Quay.io tag: auto-bump patch
   ├─ If --minor flag: bump minor
   ├─ If --major flag: bump major
   └─ Update versions.yaml with new image.version

4. Build image with Podman
   ├─ Pass tool versions as build args (--build-arg OCM_VERSION=0.1.71)
   ├─ Tag with new semver: mc-rhel10:1.0.1
   └─ Tag with latest: mc-rhel10:latest

5. Push to Quay.io (if --push flag)
   ├─ podman push quay.io/rhn_support_dsquirre/mc-container:1.0.1
   └─ podman push quay.io/rhn_support_dsquirre/mc-container:latest
```

### Script Interface

```bash
# Usage patterns
./container/build-container.sh                    # Build locally, auto-bump patch if tools changed
./container/build-container.sh --minor            # Force minor version bump
./container/build-container.sh --push             # Build and push to quay.io
./container/build-container.sh --no-bump          # Build without version change (testing)
./container/build-container.sh --check-only       # Dry-run: show what version would be assigned
```

### Quay.io API Integration

**Endpoint:** `GET https://quay.io/api/v1/repository/{namespace}/{repo}/tag/`

**Authentication:**
- Public repos: No auth needed for tag listing
- Private repos: Use Bearer token from environment (`QUAY_TOKEN`)

**Response Parsing:**
```json
{
  "tags": [
    {
      "name": "latest",
      "manifest_digest": "sha256:abc123...",
      "last_modified": "Sat, 08 Feb 2026 12:34:56 -0000"
    },
    {
      "name": "1.0.0",
      "manifest_digest": "sha256:def456...",
      "last_modified": "Fri, 07 Feb 2026 10:20:30 -0000"
    }
  ]
}
```

**Querying Latest Semver:**
1. Filter tags to semver format only (regex: `^[0-9]+\.[0-9]+\.[0-9]+$`)
2. Sort by semver rules (use `sort -V` or semver-tool)
3. Return highest version

**Error Handling:**
- Network failure: Warn, default to manual version from versions.yaml
- Empty repository: Default to 1.0.0 for first image
- Auth failure: Exit with clear error message

## Integration with Existing Container Management

### ContainerManager._ensure_image() - NO CHANGES NEEDED

**Current behavior (preserved):**
```python
def _ensure_image(self, image_name: str, registry_image: str) -> None:
    # 1. Check if image exists locally first (fast path)
    try:
        self.podman.client.images.get(image_name)  # mc-rhel10:latest
        return  # Image exists, use it
    except Exception:
        pass  # Image not found locally

    # 2. Try pulling from registry
    try:
        self.podman.client.images.pull(registry_image)  # quay.io/.../mc-container:latest
        pulled_image = self.podman.client.images.get(registry_image)
        pulled_image.tag("mc-rhel10", "latest")  # Tag as mc-rhel10:latest
    except Exception as pull_error:
        raise RuntimeError(f"Image not available. Build locally: podman build...")
```

**Why no changes needed:**
- Always pulls `:latest` tag from registry (gets newest image automatically)
- Multi-stage build is transparent to runtime - final image has same structure
- Local tag `mc-rhel10:latest` remains consistent naming convention
- OCM tool just appears at `/usr/local/bin/ocm` in the container

### Image Pull Workflow Impact

**Before (v2.0.2 - single stage):**
1. User runs `mc case 12345678`
2. ContainerManager.create() calls _ensure_image()
3. Pulls `quay.io/rhn_support_dsquirre/mc-container:latest` (549 MB)
4. Tags as `mc-rhel10:latest`
5. Creates container from `mc-rhel10:latest`

**After (v2.0.3 - multi-stage):**
1. User runs `mc case 12345678`
2. ContainerManager.create() calls _ensure_image()
3. Pulls `quay.io/rhn_support_dsquirre/mc-container:latest` (final stage only, ~540 MB)
4. Tags as `mc-rhel10:latest`
5. Creates container from `mc-rhel10:latest` (now includes OCM at /usr/local/bin/ocm)

**Key difference:** Pulled image is slightly smaller (no build dependencies) and includes OCM tool. No code changes to ContainerManager.

## File Organization

### container/ Directory Structure (New and Modified)

```
container/
├── Containerfile              # MODIFIED: Convert to multi-stage (mc-builder, ocm-downloader, final)
├── versions.yaml              # NEW: Version config (image: 1.0.0, mc: 2.0.3, tools: ocm: 0.1.71)
├── build-container.sh         # NEW: Automation script (reads versions.yaml, queries quay.io, builds)
├── build.sh                   # EXISTING: Simple build script (keep for backward compat, or deprecate)
├── entrypoint.sh              # UNCHANGED: Runtime entrypoint
└── run.sh                     # UNCHANGED: Local container run helper
```

**File Ownership:**
- `Containerfile`: Build instructions, owned by container architecture
- `versions.yaml`: Single source of truth for versions, owned by release process
- `build-container.sh`: Build automation, owned by container tooling
- `build.sh`: Legacy/simple build, consider deprecating or updating to call build-container.sh
- `entrypoint.sh`: Runtime behavior, unchanged
- `run.sh`: Local testing helper, unchanged

### src/mc/container/ Python Code - NO CHANGES

**Modules remain unchanged:**
- `manager.py`: ContainerManager class, _ensure_image() preserved
- `models.py`: ContainerMetadata dataclass
- `state.py`: StateDatabase for container registry
- `__init__.py`: Package exports

**Rationale:** Multi-stage build is a build-time concern, not a runtime concern. Python code manages running containers, not building images.

## Build vs Runtime Separation

### Build-Time Concerns (container/ directory)

**Components:**
- Multi-stage Containerfile
- versions.yaml config
- build-container.sh script
- Podman build execution

**Responsibilities:**
- Fetch dependencies (pip, curl)
- Compile/package MC CLI
- Download tool binaries
- Assemble final image
- Tag and push to registry

**Environment:** Developer machine or CI/CD pipeline

### Runtime Concerns (src/mc/container/ Python code)

**Components:**
- ContainerManager class
- PodmanClient wrapper
- StateDatabase
- Terminal automation

**Responsibilities:**
- Pull image from registry
- Create container instances
- Mount workspace volumes
- Execute commands in containers
- Track container state

**Environment:** User's host machine running MC CLI

### Clean Separation Benefits

1. **Testability:** Build scripts tested independently from container runtime logic
2. **Iteration Speed:** Change build process without touching Python code (and vice versa)
3. **Responsibility:** Build team owns container/, runtime team owns src/mc/container/
4. **Debugging:** Build failures vs runtime failures have different troubleshooting paths


## Architectural Patterns

### Pattern 1: Builder-Downloader-Final

**What:** Three-stage pattern where builder compiles code, downloader fetches binaries, final assembles runtime image

**When to use:**
- Application needs compilation (Python, Go, Java)
- Multiple external binaries needed
- Want to minimize final image size

**Trade-offs:**
- **Pros:** Small final image, clear separation, efficient caching
- **Cons:** More complex Containerfile, longer initial build time

**Example (from above):**
```dockerfile
FROM ubi AS mc-builder    # Compiles MC CLI
FROM ubi-minimal AS ocm-downloader  # Downloads OCM binary
FROM ubi AS final         # Assembles runtime
COPY --from=mc-builder ...
COPY --from=ocm-downloader ...
```

### Pattern 2: ARG-Based Version Injection

**What:** Pass versions as build arguments, allowing same Containerfile to build different versions

**When to use:**
- Tool versions change frequently
- Want to track versions in config file
- Need reproducible builds

**Trade-offs:**
- **Pros:** Version controlled in YAML, easy to audit, no Containerfile edits
- **Cons:** Must pass ARGs correctly, ARG changes invalidate cache

**Example:**
```dockerfile
ARG OCM_VERSION=0.1.71  # Default, overridden by build-container.sh
RUN curl -L "https://github.com/.../v${OCM_VERSION}/ocm-linux-amd64" ...
```

### Pattern 3: Registry-Queried Auto-Versioning

**What:** Query registry for latest published version, auto-increment if changes detected

**When to use:**
- Continuous delivery pipeline
- Prevent version conflicts
- Automate release tagging

**Trade-offs:**
- **Pros:** No manual version management, prevents duplicates
- **Cons:** Requires network access to registry, more complex build script

**Example (from build-container.sh):**
```bash
LATEST_TAG=$(curl -s https://quay.io/api/v1/repository/.../tag/ | jq -r '.tags[].name' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -1)
NEXT_VERSION=$(increment_patch "$LATEST_TAG")  # 1.0.0 → 1.0.1
```

## Data Flow

### Build Flow (Developer/CI Pipeline)

```
Developer edits versions.yaml (bump OCM version)
    ↓
Run: ./container/build-container.sh
    ↓
build-container.sh reads versions.yaml
    ↓
Query Quay.io API for latest tag (e.g., 1.0.0)
    ↓
Detect tool version change → auto-bump patch (1.0.0 → 1.0.1)
    ↓
Update versions.yaml with new image.version
    ↓
Podman build with multi-stage Containerfile
    │
    ├─ Stage 1 (mc-builder): Install MC CLI
    ├─ Stage 2 (ocm-downloader): Download OCM v0.1.71
    └─ Stage 3 (final): Copy artifacts, configure runtime
    ↓
Tag image: mc-rhel10:latest, mc-rhel10:1.0.1
    ↓
(Optional) Push to Quay.io: quay.io/.../mc-container:1.0.1 and :latest
```

### Runtime Flow (End User)

```
User runs: mc case 12345678
    ↓
ContainerManager.create() called
    ↓
_ensure_image() checks for local image: mc-rhel10:latest
    ↓ (not found)
Pull from registry: quay.io/.../mc-container:latest
    ↓
Podman pulls final stage only (no builder/downloader stages)
    ↓
Tag as: mc-rhel10:latest
    ↓
Create container with workspace mount
    ↓
User inside container: ocm version (works! /usr/local/bin/ocm exists)
```

## Scaling Considerations

### Adding More Tools (e.g., oc, kubectl, rosa)

**Current (1 tool - OCM):**
- 1 downloader stage
- 1 COPY --from in final stage
- 1 entry in versions.yaml

**Scaling to 5 tools:**

**Option A: Separate stage per tool (recommended)**
```dockerfile
FROM ubi-minimal AS ocm-downloader
ARG OCM_VERSION
RUN curl -L ... -o /tmp/ocm

FROM ubi-minimal AS oc-downloader
ARG OC_VERSION
RUN curl -L ... -o /tmp/oc

FROM ubi-minimal AS kubectl-downloader
ARG KUBECTL_VERSION
RUN curl -L ... -o /tmp/kubectl

FROM ubi AS final
COPY --from=ocm-downloader /tmp/ocm /usr/local/bin/
COPY --from=oc-downloader /tmp/oc /usr/local/bin/
COPY --from=kubectl-downloader /tmp/kubectl /usr/local/bin/
```

**Pros:**
- Independent caching per tool
- Parallel downloads during build
- Easy to debug failures

**Cons:**
- More stages (not a real problem, Podman handles this well)

**Option B: Single downloader stage for all tools**
```dockerfile
FROM ubi-minimal AS tool-downloader
ARG OCM_VERSION
ARG OC_VERSION
RUN curl -L ... -o /tmp/ocm && \
    curl -L ... -o /tmp/oc && \
    ...
```

**Pros:**
- Fewer stages
- Simpler Containerfile

**Cons:**
- Cache invalidated if ANY tool version changes
- Sequential downloads (slower)
- Harder to isolate failures

**Recommendation:** Use Option A (separate stages) for better caching and parallel builds.

### versions.yaml Scaling

**Adding 5 tools:**
```yaml
tools:
  ocm:
    version: "0.1.71"
    url: "https://github.com/openshift-online/ocm-cli/releases/download/v{VERSION}/ocm-linux-amd64"
  oc:
    version: "4.15.0"
    url: "https://mirror.openshift.com/pub/openshift-v4/clients/oc/{VERSION}/linux/oc.tar.gz"
  kubectl:
    version: "1.29.1"
    url: "https://dl.k8s.io/release/v{VERSION}/bin/linux/amd64/kubectl"
  rosa:
    version: "1.2.35"
    url: "https://github.com/openshift/rosa/releases/download/v{VERSION}/rosa-linux-amd64"
  helm:
    version: "3.14.0"
    url: "https://get.helm.sh/helm-v{VERSION}-linux-amd64.tar.gz"
```

**Schema scales cleanly:** Each tool is a separate key with version + URL pattern. build-container.sh iterates over all tools to generate build args.

## Anti-Patterns

### Anti-Pattern 1: Version Coupling

**What people do:** Tie image version to MC CLI version (image: "2.0.3" == mc: "2.0.3")

**Why it's wrong:**
- Forces image rebuild for every MC code change
- Can't update tools without MC code change
- Version 2.0.3-with-OCM-0.1.71 vs 2.0.3-with-OCM-0.1.72 becomes impossible to track

**Do this instead:** Independent image semver (image: "1.0.1") tracks container changes, mc: "2.0.3" is reference only

### Anti-Pattern 2: Hardcoded Versions in Containerfile

**What people do:**
```dockerfile
RUN curl -L "https://github.com/.../v0.1.71/ocm-linux-amd64" -o /tmp/ocm
```

**Why it's wrong:**
- Must edit Containerfile to change version (error-prone)
- No single source of truth for versions
- Can't auto-bump or track changes

**Do this instead:** Use ARG + versions.yaml
```dockerfile
ARG OCM_VERSION=0.1.71
RUN curl -L "https://github.com/.../v${OCM_VERSION}/ocm-linux-amd64" -o /tmp/ocm
```

### Anti-Pattern 3: Installing Build Tools in Final Image

**What people do:**
```dockerfile
FROM ubi
RUN dnf install -y gcc make python3-devel  # Build dependencies
COPY . /opt/mc
RUN pip install /opt/mc
```

**Why it's wrong:**
- Final image bloated with unnecessary build tools
- Security risk (compilers in production image)
- Wastes registry bandwidth

**Do this instead:** Use builder stage, copy only artifacts to final
```dockerfile
FROM ubi AS builder
RUN dnf install -y gcc make python3-devel
RUN pip install /opt/mc

FROM ubi AS final
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
# No build tools in final image
```

### Anti-Pattern 4: Pulling Latest Tool Versions at Build Time

**What people do:**
```dockerfile
RUN curl -L "https://github.com/.../releases/latest/download/ocm-linux-amd64" -o /tmp/ocm
```

**Why it's wrong:**
- Non-reproducible builds (OCM version changes, image breaks)
- Can't audit what version is in an image
- No warning when tools update with breaking changes

**Do this instead:** Pin exact versions in versions.yaml, update explicitly
```yaml
tools:
  ocm:
    version: "0.1.71"  # Explicit version, auditable
```


## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Quay.io Registry | REST API (JSON) | GET /api/v1/repository/{namespace}/{repo}/tag/ for querying tags; authenticated push via podman login |
| GitHub Releases | HTTPS download | Direct binary download from releases URLs, checksum validation recommended but optional |
| Podman | CLI via subprocess | build-container.sh invokes `podman build`, `podman tag`, `podman push` commands |
| PyPI | pip install | mc-builder stage installs MC CLI dependencies, pinned in pyproject.toml |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| build-container.sh ↔ versions.yaml | File I/O (YAML parsing) | Read version config, write updated image.version after auto-bump |
| build-container.sh ↔ Quay.io API | HTTP GET (curl + jq) | Query latest tag, compare with local version |
| Containerfile ↔ build-container.sh | Build args | Pass OCM_VERSION, other tool versions as --build-arg flags |
| ContainerManager ↔ Podman registry | podman-py API | Pull image, tag image, no awareness of build process |

## Recommended Build Order

### Phase 1: Multi-Stage Containerfile (Foundational)

**Why first:** Validates build pattern works before adding automation complexity

**Tasks:**
1. Convert current Containerfile to 3-stage pattern (mc-builder, ocm-downloader, final)
2. Hardcode OCM version initially (ARG OCM_VERSION=0.1.71)
3. Build locally: `podman build -t mc-rhel10:test -f container/Containerfile .`
4. Verify: Run container, check `ocm version` works
5. Compare image sizes: current single-stage vs new multi-stage

**Success criteria:**
- Image builds successfully
- OCM tool present at /usr/local/bin/ocm
- Image size comparable or smaller than single-stage
- Layer caching works (rebuild after MC source change only rebuilds mc-builder + final)

### Phase 2: versions.yaml Config (Version Management)

**Why second:** Establishes single source of truth before automation

**Tasks:**
1. Create `container/versions.yaml` with initial schema (image: 1.0.0, mc: 2.0.3, tools: ocm: 0.1.71)
2. Update Containerfile to use ARG OCM_VERSION (no default, must be passed)
3. Manually build with: `podman build --build-arg OCM_VERSION=0.1.71 ...`
4. Verify versions.yaml is parseable (test with `yq` or Python YAML parser)

**Success criteria:**
- versions.yaml validates against schema
- Containerfile builds with --build-arg OCM_VERSION
- Image contains correct OCM version specified in YAML

### Phase 3: build-container.sh Script (Automation Core)

**Why third:** Automates what was proven manually in phases 1-2

**Tasks:**
1. Create `container/build-container.sh` with basic functionality:
   - Read versions.yaml (parse YAML in bash using `yq` or Python)
   - Extract tool versions (OCM_VERSION)
   - Run podman build with --build-arg flags
   - Tag image as mc-rhel10:latest
2. No version bumping yet, just automation of manual build
3. Test: `./container/build-container.sh` produces same image as manual build

**Success criteria:**
- Script runs without errors
- Produces correctly tagged image
- All build args passed correctly
- Image identical to manual build

### Phase 4: Quay.io Integration (Version Querying)

**Why fourth:** Adds external dependency, needs core automation working first

**Tasks:**
1. Add Quay.io API query to build-container.sh:
   - GET https://quay.io/api/v1/repository/rhn_support_dsquirre/mc-container/tag/
   - Parse JSON response (curl + jq)
   - Extract semver tags, find highest version
2. Add --check-only flag to show current vs latest version without building
3. Test against live Quay.io registry

**Success criteria:**
- Script successfully queries Quay.io API
- Correctly identifies latest semver tag
- Handles empty repository gracefully (defaults to 1.0.0)
- Reports network errors clearly

### Phase 5: Auto-Versioning Logic (Intelligent Bumping)

**Why fifth:** Most complex logic, needs all previous pieces working

**Tasks:**
1. Implement version comparison (local versions.yaml vs Quay.io latest)
2. Detect tool version changes (compare current OCM version vs version in last published image)
3. Auto-increment patch version if tool changes detected
4. Support manual --minor and --major flags
5. Write updated version back to versions.yaml

**Success criteria:**
- Detects tool version changes correctly
- Auto-bumps patch version (1.0.0 → 1.0.1)
- Manual bumps work (--minor: 1.0.1 → 1.1.0)
- versions.yaml updated with new image.version

### Phase 6: Registry Push (Publishing)

**Why last:** Only needed after build process is proven reliable

**Tasks:**
1. Add --push flag to build-container.sh
2. Tag image with both semver and latest
3. Push to Quay.io: `podman push quay.io/rhn_support_dsquirre/mc-container:1.0.1`
4. Push latest tag: `podman push quay.io/rhn_support_dsquirre/mc-container:latest`
5. Verify pushed image is pullable by ContainerManager

**Success criteria:**
- Images pushed successfully to Quay.io
- Both versioned and :latest tags present
- ContainerManager can pull new image
- User can run `mc case XXXXX` and get container with OCM tool

## Verification Strategy

### Build-Time Verification

**Test Scenarios:**
1. **Clean build:** Delete all local images, run build-container.sh, verify image created
2. **Incremental build (MC change):** Edit MC source, rebuild, verify only mc-builder + final stages rebuild
3. **Incremental build (tool change):** Bump OCM version in versions.yaml, rebuild, verify only ocm-downloader + final stages rebuild
4. **Version auto-bump:** Change OCM version, run build-container.sh, verify image.version incremented from 1.0.0 to 1.0.1
5. **Registry push:** Run build-container.sh --push, verify both :1.0.1 and :latest tags on Quay.io

### Runtime Verification

**Test Scenarios:**
1. **Fresh pull:** Delete local mc-rhel10:latest, run `mc case 12345678`, verify image pulled from registry
2. **OCM tool present:** Inside container, run `ocm version`, verify correct version displayed
3. **MC CLI works:** Inside container, run `mc --version`, verify MC 2.0.3
4. **Workspace mount:** Verify /case directory mounted correctly with proper permissions
5. **Backward compatibility:** Existing v2.0.2 user workflow unchanged (no Python code changes)

### Integration Verification

**Test Scenarios:**
1. **Quay.io API query:** Run `build-container.sh --check-only`, verify latest version detected
2. **Build arg passing:** Verify OCM_VERSION passed correctly to Containerfile (check image labels or run `ocm version`)
3. **Layer caching:** Time builds with cache hit vs cache miss, verify speedup
4. **Multi-platform:** Build on macOS, push to registry, pull on Linux, verify works (both arm64 and amd64 if needed)

## Sources

**Multi-Stage Container Builds:**
- [Multi-stage builds - Docker Docs](https://docs.docker.com/build/building/multi-stage/)
- [How to Build Images with Podman - OneUptime Blog 2026](https://oneuptime.com/blog/post/2026-01-27-podman-build/view)
- [Advanced multi-stage build patterns - Medium](https://medium.com/@tonistiigi/advanced-multi-stage-build-patterns-6f741b852fae)
- [Understanding Multi-Stage Docker Builds - Blacksmith](https://www.blacksmith.sh/blog/understanding-multi-stage-docker-builds)

**Container Layer Caching with Podman:**
- [Optimize container build speed with Podman - Medium](https://medium.com/@jeroenverhaeghe/tips-to-optimize-container-build-speed-02e4622d8bae)
- [Deep Dive: Why Podman and containerd 2.0 are Replacing Docker in 2026 - DEV Community](https://dev.to/dataformathub/deep-dive-why-podman-and-containerd-20-are-replacing-docker-in-2026-32ak)
- [Understanding Podman Build: A Technical Deep Dive - Tao's Blog](https://www.ubitools.com/podman-build-technical-guide/)
- [Speeding Up Container Image Builds with Remote Cache - Martin Heinz](https://martinheinz.dev/blog/61)

**Version Management and Automation:**
- [Automating Docker Image Versioning with GitHub Actions - DEV Community](https://dev.to/msrabon/automating-docker-image-versioning-build-push-and-scanning-using-github-actions-388n)
- [Container Image Versioning - Container Registry](https://container-registry.com/posts/container-image-versioning/)
- [How to Implement ArgoCD Image Updater Automation - OneUptime 2026](https://oneuptime.com/blog/post/2026-01-27-argocd-image-updater/view)

**Semver Auto-Increment in Bash:**
- [semver-tool: semver bash implementation - GitHub](https://github.com/fsaintjacques/semver-tool)
- [Automate Git Tag Versioning Using Bash - reemus.dev](https://reemus.dev/tldr/git-tag-versioning-script)
- [shell-semver: Increment semantic versioning strings - GitHub](https://github.com/fmahnke/shell-semver)
- [Incrementing a Semantic Version String in Bash - Henry Schmale](https://www.henryschmale.org/2019/04/30/incr-semver.html)

**Quay.io API:**
- [Quay.io API Documentation](https://docs.quay.io/api/)
- [Get tags from a particular image in quay.io registry - OpenShift Tips](https://openshift.tips/images/)
- [Use Project Quay - Documentation](https://docs.projectquay.io/use_quay.html)
- [Working with tags - Red Hat Quay Documentation](https://docs.redhat.com/en/documentation/red_hat_quay/3.10/html/about_quay_io/working-with-tags)

---

*Architecture research for: Multi-stage container builds and version management*
*Researched: 2026-02-09*
