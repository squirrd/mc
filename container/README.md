# MC Container Image Build System

Multi-stage container build with automated versioning and registry publishing.

## Quick Start

### 1. Authenticate with Quay.io

First-time setup (credentials persist):

```bash
podman login quay.io --authfile=.registry-auth/auth.json
```

**For robot accounts** (recommended):
- Username: `<org>+<robot-name>` (e.g., `dsquirre+mc_builder`)
- Password: Robot token from [Quay.io dashboard](https://quay.io/organization/dsquirre?tab=robots)

**For personal accounts:**
- Username: Your quay.io username
- Password: Your quay.io password

### 2. Build and Push

```bash
cd container
./build-container.sh
```

That's it! The script handles:
- Version extraction from `versions.yaml`
- Multi-stage build with layer caching
- Registry query for latest version
- Digest comparison to detect changes
- Auto-versioning and push if content changed

## How Auto-Versioning Works

The system uses **intelligent patch bumping** based on image content:

1. **Build image** with versions from `versions.yaml`
2. **Query registry** for latest published tag
3. **Compare digests** between local build and registry
4. **If digest differs** → Auto-bump patch version and push
5. **If digest matches** → Skip push (no-op)

### Version Format

`versions.yaml` stores the **minor version** (x.y):

```yaml
image:
  version: "1.0"  # Minor version only
```

The build script calculates the **patch version** from registry:
- Registry has `1.0.5` → Build creates `1.0.6`
- Registry has no `1.0.*` tags → Build creates `1.0.0`

This prevents version conflicts when multiple builds occur.

## Updating Tool Versions

### Update Existing Tool

Edit `versions.yaml`:

```yaml
tools:
  ocm:
    version: "1.0.11"  # Changed from 1.0.10
```

Run build:

```bash
./build-container.sh
```

**Result:**
- Digest differs (OCM binary changed)
- Auto-bumps patch: `1.0.5` → `1.0.6`
- Pushes `mc-rhel10:1.0.6` and `mc-rhel10:latest`

### Add New Tool (Minor Version Bump)

When adding a new tool, **manually bump the minor version**:

```yaml
image:
  version: "1.1"  # Changed from 1.0
```

Then add tool downloader stage to `Containerfile` (follow OCM pattern):

```dockerfile
# New tool downloader stage
FROM registry.access.redhat.com/ubi9/ubi-minimal:latest AS oc-downloader
ARG OC_VERSION
RUN microdnf install -y curl && \
    curl -sL https://mirror.openshift.com/pub/openshift-v4/clients/ocp/${OC_VERSION}/openshift-client-linux.tar.gz -o oc.tar.gz && \
    tar -xzf oc.tar.gz && \
    chmod +x oc

# Copy to final stage
COPY --from=oc-downloader --chown=mcuser:mcuser /oc /usr/local/bin/oc
```

Add to `versions.yaml`:

```yaml
tools:
  oc:
    version: "4.14.0"
    url: "https://mirror.openshift.com/pub/openshift-v4/clients/ocp/{version}/openshift-client-linux.tar.gz"
    description: "OpenShift CLI"
```

**Result:**
- First build creates `1.1.0`
- Subsequent tool updates bump patch: `1.1.0` → `1.1.1` → `1.1.2`

## Build Script Options

```bash
# Preview without building
./build-container.sh --dry-run

# Show detailed build output
./build-container.sh --verbose

# Machine-readable JSON output (for CI/CD)
./build-container.sh --json

# Query different registry
./build-container.sh --registry quay.io/myorg/myimage

# Show help
./build-container.sh --help
```

## Verifying Published Images

### List tags on registry:

```bash
skopeo list-tags docker://quay.io/dsquirre/mc-rhel10
```

### Inspect image:

```bash
podman pull quay.io/dsquirre/mc-rhel10:latest
podman run --rm quay.io/dsquirre/mc-rhel10:latest ocm version
```

## Testing

### Integration Test

Verify OCM tool integration:

```bash
./test-integration
```

**Checks:**
- OCM version in container matches `versions.yaml`
- OCM binary is functional (`--help` works)

### Cache Verification

Verify layer caching works:

```bash
./verify-cache.sh
```

**Expected:** 12+ cache hits on second build

## File Structure

```
container/
├── Containerfile          # Multi-stage build definition
├── versions.yaml          # Version configuration (single source of truth)
├── build-container.sh     # Build automation script
├── test-integration       # OCM integration test
├── verify-cache.sh        # Layer caching verification
└── README.md              # This file
```

## Architecture

### Multi-Stage Build

Three stages optimize image size and build time:

1. **ocm-downloader** (UBI-minimal)
   - Downloads OCM binary from GitHub releases
   - Verifies SHA256 checksum
   - Supports amd64/arm64 architectures

2. **mc-builder** (UBI 10.1)
   - Installs MC CLI from source
   - Builds Python dependencies

3. **final** (UBI 10.1)
   - Runtime-only image (no build tools)
   - Copies artifacts from previous stages
   - 565MB final size

### Layer Caching

Stages rebuild only when inputs change:
- ARG changes invalidate downstream layers
- OCM version change → only ocm-downloader rebuilds
- MC version change → only mc-builder rebuilds
- Achieves 12-layer cache reuse on unchanged builds

## Troubleshooting

### Authentication Failed

```
Error: Registry authentication required
```

**Fix:** Run `podman login quay.io --authfile=.registry-auth/auth.json`

### yq Version Mismatch

```
Error: yq version check failed
```

**Fix:** Install mikefarah/yq (Go version), not Python yq:
```bash
brew install yq  # macOS
```

### Podman Machine Not Running (macOS)

```
Error: Podman machine not running
```

**Fix:**
```bash
podman machine start
```

### Version Already Exists

```
Error: Version 1.0.5 already exists on registry
```

**Cause:** Race condition - another build pushed same version

**Fix:** Re-run build (will bump to 1.0.6)

## Requirements

- **podman** - Container runtime (with machine on macOS/Windows)
- **yq** - YAML parser (mikefarah/yq Go version)
- **skopeo** - Registry query tool
- **jq** - JSON parser

Install on macOS:
```bash
brew install podman yq skopeo jq
```

Install on Linux:
```bash
# RHEL/Fedora
sudo dnf install podman skopeo jq

# Install yq from GitHub releases
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq
chmod +x /usr/local/bin/yq
```

## CI/CD Integration

Use `--json` mode for machine-readable output:

```bash
./build-container.sh --json
```

**Output:**
```json
{
  "image_version": "1.0.5",
  "mc_version": "2.0.2",
  "ocm_version": "1.0.10",
  "registry_latest": "1.0.4",
  "digest_match": false,
  "version_bumped": true,
  "pushed": true,
  "tags": ["mc-rhel10:1.0.5", "mc-rhel10:latest"]
}
```

## Design Decisions

**Why minor version in versions.yaml?**
- Prevents merge conflicts when multiple developers build
- Registry becomes source of truth for patch versions
- Automatic conflict prevention

**Why digest comparison?**
- Immune to comment/whitespace changes
- Only pushes when actual content changes
- Prevents unnecessary registry pushes

**Why auto-push on digest differ?**
- Simplifies workflow (no manual push step)
- Ensures registry stays in sync with builds
- Fail-fast on version conflicts

---

**For more details, see:**
- Phase 20-25 summaries in `.planning/phases/`
- Milestone archive: `.planning/milestones/v2.0.3-ROADMAP.md`
