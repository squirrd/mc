# Phase 25: Registry Publishing & OCM Verification - Research

**Researched:** 2026-02-10
**Domain:** Container registry publishing, authentication, and CLI tool integration testing
**Confidence:** HIGH

## Summary

This phase implements registry publishing to quay.io and verifies OCM CLI tool integration. The standard approach uses Podman's push command with token-based authentication stored in auth.json files. OCM binaries are downloaded from GitHub releases with SHA256 verification in multi-stage Containerfile builds. Integration testing validates the OCM version matches versions.yaml.

**Key findings:**
- Podman lacks atomic multi-tag push - requires sequential push operations for version tag and :latest
- Token-based authentication via podman login with auth.json storage (base64-encoded credentials)
- OCM releases provide separate .sha256 files for verification (single hash, no filename)
- OCM version command outputs structured Go format with GitVersion field matching semantic version
- Pre-flight credential validation recommended via podman login --get-login
- Built-in retry mechanism in Podman (3 retries with exponential backoff) for network failures

**Primary recommendation:** Use sequential podman push operations wrapped in bash script that validates credentials before building, pushes version tag first, then :latest tag, and fails the entire build if either push fails (non-zero exit code).

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| podman | 5.1+ | Container building and registry operations | Industry standard OCI-compliant container tool, official Quay.io support |
| curl | system | Binary downloads from GitHub releases | Universal HTTP client, available in all base images |
| sha256sum | GNU coreutils | Checksum verification | Standard UNIX utility for SHA256 validation |
| OCM CLI | 0.35.0+ | Open Component Model tooling | Official Open Component Model command-line interface |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| skopeo | latest | Registry inspection (inherited from Phase 24) | Already used for digest comparison |
| yq | 4.x | YAML parsing (inherited from Phase 24) | Already used for versions.yaml reading |
| container-structure-test | 1.x+ | Container integration testing | Optional: validates binary version in container |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| podman push | buildah push | Buildah has same retry mechanism, but podman already in use |
| curl | wget | Wget equally viable, curl more common in containers |
| container-structure-test | Custom bash test | container-structure-test is declarative but adds dependency |

**Installation:**

OCM CLI installed during container build (Containerfile downloader stage):
```bash
# In Containerfile downloader stage
ARG OCM_VERSION
ARG TARGETARCH
RUN curl -sL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz" -o ocm.tar.gz && \
    curl -sL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256" -o ocm.sha256 && \
    echo "$(cat ocm.sha256)  ocm.tar.gz" | sha256sum -c - && \
    tar -xzf ocm.tar.gz
```

## Architecture Patterns

### Recommended Project Structure
```
container/
├── build                          # Build script with --push flag
├── Containerfile                  # Multi-stage build
│   ├── downloader stage          # Downloads OCM binary, verifies SHA256
│   ├── builder stage             # Builds mc-cli binary
│   └── final stage               # Copies OCM to /usr/local/bin/ocm
├── test-integration              # Integration test for OCM version
└── versions.yaml                 # Single source of truth (existing)

.registry-auth                     # Token config file (gitignored, MC base dir)
```

### Pattern 1: Token-Based Registry Authentication
**What:** Store registry credentials in auth.json using podman login, reference via --authfile flag
**When to use:** All registry push operations requiring authentication
**Example:**
```bash
# Source: https://docs.podman.io/en/latest/markdown/podman-login.1.html
# Login with token (one-time setup)
echo "${QUAY_TOKEN}" | podman login quay.io \
  --username="${QUAY_USER}" \
  --password-stdin \
  --authfile="${MC_BASE}/.registry-auth/auth.json"

# Push using stored credentials
podman push \
  --authfile="${MC_BASE}/.registry-auth/auth.json" \
  localhost/mc-cli:1.2.18 \
  quay.io/mc-project/mc-cli:1.2.18
```

### Pattern 2: Sequential Multi-Tag Push with Atomic Semantics
**What:** Push version tag first, then :latest tag, fail entire build if either fails
**When to use:** When both tags must exist together in registry (atomic requirement)
**Example:**
```bash
# Source: Podman documentation pattern, adapted for atomic requirement
set -e  # Exit on first failure

VERSION="1.2.18"
IMAGE="quay.io/mc-project/mc-cli"

# Push version tag first
podman push --authfile="${AUTH_FILE}" "localhost/mc-cli:${VERSION}" "${IMAGE}:${VERSION}"

# Push :latest tag (only if version tag succeeded)
podman push --authfile="${AUTH_FILE}" "localhost/mc-cli:${VERSION}" "${IMAGE}:latest"

echo "Successfully pushed ${IMAGE}:${VERSION} and ${IMAGE}:latest"
```

### Pattern 3: Multi-Stage Build with SHA256 Verification
**What:** Download binary in downloader stage, verify checksum, fail build on mismatch
**When to use:** All external binary downloads requiring integrity verification
**Example:**
```bash
# Source: https://adrianhesketh.com/2022/01/26/verifying-download-hashes-during-docker-build/
# Containerfile downloader stage
FROM alpine:latest AS downloader
ARG OCM_VERSION
ARG TARGETARCH

RUN apk add --no-cache curl

# Download binary and checksum
RUN curl -sL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz" \
    -o ocm.tar.gz && \
    curl -sL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256" \
    -o ocm.sha256

# Verify checksum (build fails if mismatch)
RUN echo "$(cat ocm.sha256)  ocm.tar.gz" | sha256sum -c -

# Extract binary
RUN tar -xzf ocm.tar.gz -C /usr/local/bin

# Final stage copies verified binary
FROM fedora:latest
COPY --from=downloader /usr/local/bin/ocm /usr/local/bin/ocm
```

### Pattern 4: Pre-Flight Credential Validation
**What:** Verify registry credentials exist and are valid before building
**When to use:** All build scripts that push to registries (avoid wasted build time)
**Example:**
```bash
# Source: https://oneuptime.com/blog/post/2026-01-27-podman-registry/view
# Pre-flight check in build script
validate_registry_auth() {
  local registry="$1"
  local authfile="$2"

  # Check if credentials exist for registry
  if ! podman login --authfile="${authfile}" --get-login "${registry}" >/dev/null 2>&1; then
    echo "ERROR: No valid credentials found for ${registry}"
    echo "Run: podman login ${registry} --authfile=${authfile}"
    exit 1
  fi

  echo "✓ Registry credentials validated for ${registry}"
}

# Usage in build script
validate_registry_auth "quay.io" "${MC_BASE}/.registry-auth/auth.json"
```

### Pattern 5: Integration Testing for Binary Version Verification
**What:** Run binary in container, compare version output to versions.yaml
**When to use:** Verify binary installation and version correctness
**Example:**
```bash
# Source: https://github.com/GoogleContainerTools/container-structure-test patterns
# Integration test script
#!/bin/bash
set -e

EXPECTED_VERSION=$(yq eval '.ocm' versions.yaml)
IMAGE="localhost/mc-cli:${VERSION}"

# Run ocm version in container
ACTUAL_VERSION=$(podman run --rm "${IMAGE}" ocm version | grep -oP 'GitVersion:"v\K[^"]+')

if [[ "${ACTUAL_VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "ERROR: Version mismatch!"
  echo "Expected: ${EXPECTED_VERSION}"
  echo "Actual: ${ACTUAL_VERSION}"
  exit 1
fi

echo "✓ OCM version verified: ${ACTUAL_VERSION}"
```

### Anti-Patterns to Avoid
- **Pushing :latest before version tag:** If :latest succeeds but version tag fails, registry is inconsistent (violates atomic requirement)
- **Using base64-encoded password in scripts:** Auth tokens should be provided via stdin or environment variables, never hardcoded
- **Skipping checksum verification:** Network corruption or man-in-the-middle attacks can provide malicious binaries
- **Manual retry logic:** Podman has built-in retry (3 attempts, exponential backoff) - don't duplicate
- **Using ${XDG_RUNTIME_DIR}/containers/auth.json for persistent credentials:** This directory is ephemeral and cleared on reboot

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic multi-tag push | Custom transaction logic | Sequential push with `set -e` | No native atomic push in Podman; sequential with fail-fast gives atomic semantics |
| Credential validation | Custom API calls | `podman login --get-login` | Already handles auth.json parsing, credential scope resolution |
| SHA256 checksum verification | Custom hash calculation | `sha256sum -c` | Standard UNIX utility, handles file format, reports errors clearly |
| Retry on network failures | Custom retry loops | Podman built-in retry (default 3x) | Exponential backoff already implemented, configurable via `--retry` flag |
| Container command testing | Custom docker exec scripts | container-structure-test | Declarative YAML, handles output parsing, regex matching, exit codes |
| Registry credential storage | Custom encryption | containers-auth.json format | Standard across Podman/Docker/Buildah, supports credential helpers |

**Key insight:** Registry operations have many edge cases (network failures, credential expiry, partial uploads). Use proven tools (podman, sha256sum) rather than custom scripts that may miss corner cases.

## Common Pitfalls

### Pitfall 1: Credentials Disappear After Reboot
**What goes wrong:** Registry credentials vanish after system restart, breaking builds
**Why it happens:** Default auth.json location is `${XDG_RUNTIME_DIR}/containers/auth.json`, which is ephemeral (`/run/user/<UID>`) and cleared on reboot
**How to avoid:** Use persistent location with `--authfile $HOME/.config/containers/auth.json` or custom path in MC base directory
**Warning signs:** Build succeeds locally but fails in CI/CD or after developer restarts machine

### Pitfall 2: Auth.json Contains Base64, Not Encryption
**What goes wrong:** Developers assume credentials are encrypted in auth.json, exposing secrets
**Why it happens:** Auth field contains base64-encoded `username:password`, which is trivially reversible
**How to avoid:** Treat auth.json as sensitive secret (gitignore, restrict permissions to 600), consider credential helpers for production
**Warning signs:** auth.json committed to git, world-readable permissions

### Pitfall 3: SHA256 File Contains Only Hash, Not Filename
**What goes wrong:** Checksum verification fails because developers expect `hash  filename` format
**Why it happens:** OCM GitHub releases provide .sha256 files with bare hash (e.g., `0d2105da920601f4d98...`), not standard format
**How to avoid:** Construct verification string manually: `echo "$(cat ocm.sha256)  ocm.tar.gz" | sha256sum -c -`
**Warning signs:** sha256sum reports "no properly formatted checksum lines found"

### Pitfall 4: TARGETARCH Not Available in Early Podman Versions
**What goes wrong:** `ARG TARGETARCH` is empty, download URLs malformed (e.g., `ocm-0.35.0-linux-.tar.gz`)
**Why it happens:** TARGETARCH support added in Buildah 1.36.0 (Podman 5.1+), older versions don't set this variable
**How to avoid:** Verify Podman 5.1+ or manually set TARGETARCH: `podman build --build-arg TARGETARCH=amd64`
**Warning signs:** Download failures with malformed URLs, missing architecture in filenames

### Pitfall 5: Podman Push Exits 125 on All Failures
**What goes wrong:** Cannot distinguish authentication failures from network failures (both exit 125)
**Why it happens:** Podman uses generic exit code 125 for container tool errors (unlike Docker's exit code 1)
**How to avoid:** Parse stderr for error messages ("unauthorized", "network unreachable") or use pre-flight checks
**Warning signs:** Builds fail with unhelpful "Error: exit status 125" messages

### Pitfall 6: OCM Version Output is Go Struct Format
**What goes wrong:** Simple grep for version number fails because output is Go struct: `version.Info{..., GitVersion:"v0.35.0", ...}`
**Why it happens:** OCM version command outputs Go-formatted struct, not plain text version
**How to avoid:** Parse with regex: `grep -oP 'GitVersion:"v\K[^"]+'` extracts version without 'v' prefix
**Warning signs:** Version comparison fails, grep returns entire line or nothing

### Pitfall 7: Registry Push Succeeds Locally but Fails in CI
**What goes wrong:** Push works on developer machine but fails in GitHub Actions/CI environment
**Why it happens:** CI has network restrictions, rate limits, or different auth.json location expectations
**How to avoid:** Test push in clean container with explicit --authfile path, verify CI has registry access
**Warning signs:** "connection refused", "unauthorized", "TLS handshake timeout" in CI logs

## Code Examples

Verified patterns from official sources:

### Podman Login with Token (Quay.io Robot Account)
```bash
# Source: https://docs.projectquay.io/use_quay.html
# For Quay.io robot accounts, username format: <org/username>+<robot-name>
echo "${QUAY_ROBOT_TOKEN}" | podman login quay.io \
  --username="mc-project+mc-cli-publisher" \
  --password-stdin \
  --authfile="${MC_BASE}/.registry-auth/auth.json"

# Verify login succeeded
podman login --authfile="${MC_BASE}/.registry-auth/auth.json" --get-login quay.io
```

### Sequential Multi-Tag Push with Error Handling
```bash
# Source: Podman documentation patterns, adapted for atomic semantics
#!/bin/bash
set -e  # Exit immediately on error

VERSION="1.2.18"
LOCAL_IMAGE="localhost/mc-cli:${VERSION}"
REMOTE_IMAGE="quay.io/mc-project/mc-cli"
AUTH_FILE="${MC_BASE}/.registry-auth/auth.json"

echo "=== Publishing ${VERSION} to ${REMOTE_IMAGE} ==="

# Pre-flight: Validate credentials
if ! podman login --authfile="${AUTH_FILE}" --get-login quay.io >/dev/null 2>&1; then
  echo "ERROR: No valid credentials for quay.io"
  exit 1
fi

# Push version tag first
echo "Pushing ${REMOTE_IMAGE}:${VERSION}..."
podman push --authfile="${AUTH_FILE}" "${LOCAL_IMAGE}" "${REMOTE_IMAGE}:${VERSION}"

# Push :latest tag (only if version tag succeeded due to set -e)
echo "Pushing ${REMOTE_IMAGE}:latest..."
podman push --authfile="${AUTH_FILE}" "${LOCAL_IMAGE}" "${REMOTE_IMAGE}:latest"

# Get image digest for verification
DIGEST=$(skopeo inspect --authfile="${AUTH_FILE}" "docker://${REMOTE_IMAGE}:${VERSION}" | yq eval '.Digest' -)

echo "✓ Successfully pushed:"
echo "  - ${REMOTE_IMAGE}:${VERSION}"
echo "  - ${REMOTE_IMAGE}:latest"
echo "  - Digest: ${DIGEST}"
```

### Containerfile: OCM Downloader Stage with SHA256 Verification
```dockerfile
# Source: https://github.com/open-component-model/ocm/releases patterns
# Downloader stage: Fetch and verify OCM binary
FROM alpine:latest AS ocm-downloader

ARG OCM_VERSION
ARG TARGETARCH

RUN apk add --no-cache curl

WORKDIR /tmp/ocm

# Download OCM binary and checksum
RUN curl -fsSL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz" \
    -o ocm.tar.gz && \
    curl -fsSL "https://github.com/open-component-model/ocm/releases/download/v${OCM_VERSION}/ocm-${OCM_VERSION}-linux-${TARGETARCH}.tar.gz.sha256" \
    -o ocm.sha256

# Verify SHA256 checksum (build fails if mismatch)
# OCM .sha256 files contain only the hash (no filename), so we construct the expected format
RUN echo "$(cat ocm.sha256)  ocm.tar.gz" | sha256sum -c - || \
    (echo "ERROR: SHA256 checksum verification failed for OCM ${OCM_VERSION}" && exit 1)

# Extract binary
RUN tar -xzf ocm.tar.gz && \
    chmod +x ocm

# Final stage: Copy verified binary
FROM fedora:latest
COPY --from=ocm-downloader /tmp/ocm/ocm /usr/local/bin/ocm

# Verify binary is executable and can report version
RUN ocm version || (echo "ERROR: OCM binary not functional" && exit 1)
```

### Integration Test: OCM Version Verification
```bash
# Source: Container-structure-test patterns, adapted for version matching
#!/bin/bash
# test-integration
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSIONS_FILE="${SCRIPT_DIR}/versions.yaml"
IMAGE="${1:-localhost/mc-cli:latest}"

echo "=== Integration Test: OCM Version Verification ==="

# Get expected version from versions.yaml
EXPECTED_VERSION=$(yq eval '.ocm' "${VERSIONS_FILE}")
echo "Expected OCM version: ${EXPECTED_VERSION}"

# Get actual version from container
# OCM version output format: version.Info{..., GitVersion:"v0.35.0", ...}
ACTUAL_OUTPUT=$(podman run --rm "${IMAGE}" ocm version)
echo "OCM version output: ${ACTUAL_OUTPUT}"

# Extract version from Go struct format
ACTUAL_VERSION=$(echo "${ACTUAL_OUTPUT}" | grep -oP 'GitVersion:"v\K[^"]+')
echo "Actual OCM version: ${ACTUAL_VERSION}"

# Compare versions (fail hard on mismatch)
if [[ "${ACTUAL_VERSION}" != "${EXPECTED_VERSION}" ]]; then
  echo "ERROR: OCM version mismatch!"
  echo "  Expected: ${EXPECTED_VERSION}"
  echo "  Actual:   ${ACTUAL_VERSION}"
  exit 1
fi

echo "✓ OCM version verified: ${ACTUAL_VERSION}"

# Verify binary is functional (not just present)
echo "=== Verifying OCM binary is functional ==="
podman run --rm "${IMAGE}" ocm --help >/dev/null
echo "✓ OCM binary is functional"
```

### Registry Auth Config File (.registry-auth/auth.json)
```json
# Source: https://man.archlinux.org/man/containers-auth.json.5
# Located in MC base directory: .registry-auth/auth.json
# Permissions: 600 (owner read/write only)
{
  "auths": {
    "quay.io": {
      "auth": "bWMtcHJvamVjdCttYy1jbGktcHVibGlzaGVyOjxST0JPVF9UT0tFTj4="
    }
  }
}
```

Note: The `auth` field is base64-encoded `username:password`. This is NOT encryption - treat file as sensitive secret.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Ephemeral credentials in ${XDG_RUNTIME_DIR} | Persistent auth.json in custom location | Podman 3.x+ | Credentials survive reboots, but require explicit --authfile |
| Docker-only auth format | containers-auth.json standard | Podman 2.x+ | Shared auth format across Podman/Docker/Buildah |
| Manual checksum verification | GitHub auto-generated SHA256 for assets | June 2025 | All release assets have immutable checksums via API |
| Long-lived robot tokens | Short-lived ephemeral tokens (1 hour) | Quay 3.16 (2026) | Enhanced security, requires OIDC integration for auto-refresh |
| TARGETARCH manual specification | Auto-set by --arch flag | Buildah 1.36.0 / Podman 5.1 (2024) | Multi-arch builds simpler, no manual ARG setting needed |
| Docker exit code 1 | Podman exit code 125 | Podman 1.x+ | Less granular error codes, need stderr parsing |
| --all-tags flag (feature request) | Sequential push per tag | Still no --all-tags in 2026 | Must push tags individually, no atomic operation |

**Deprecated/outdated:**
- **$HOME/.docker/config.json as primary location:** Still supported as fallback, but containers-auth.json is preferred
- **Password-based login via --password flag:** Still works but discouraged; use --password-stdin to avoid process exposure
- **Podman retry flag --retry <n>:** Available since Buildah 1.35, but default 3 retries is usually sufficient
- **Manual TARGETARCH setting:** Only needed for Podman < 5.1; modern versions set automatically

## Open Questions

Things that couldn't be fully resolved:

1. **OCM version output format stability**
   - What we know: Current format is Go struct `version.Info{..., GitVersion:"v0.35.0", ...}`
   - What's unclear: Whether this format is stable across OCM versions, or might change to JSON/plain text
   - Recommendation: Use regex parsing `grep -oP 'GitVersion:"v\K[^"]+'`, test on OCM upgrades, flag as potential breakage point

2. **Quay.io rate limiting and retry behavior**
   - What we know: Podman has 3-retry default with exponential backoff
   - What's unclear: Quay.io specific rate limits, whether retries count against quota
   - Recommendation: Use Podman defaults, monitor for 429 rate limit errors, document if limits encountered

3. **Short-lived token support in Quay.io free tier**
   - What we know: Quay 3.16 supports 1-hour ephemeral tokens via OIDC (Red Hat SSO or Azure AD)
   - What's unclear: Whether quay.io free tier (not self-hosted) supports this feature
   - Recommendation: Start with long-lived robot tokens, investigate ephemeral tokens if available

4. **Container-structure-test vs custom bash integration tests**
   - What we know: container-structure-test provides declarative YAML testing, but adds dependency
   - What's unclear: Whether declarative approach provides enough value to justify another tool
   - Recommendation: Start with custom bash test (simpler, no new dependency), migrate to container-structure-test if test complexity grows

## Sources

### Primary (HIGH confidence)
- [Podman Login Documentation](https://docs.podman.io/en/latest/markdown/podman-login.1.html) - Authentication file locations, credential storage
- [Podman Push Documentation](https://docs.podman.io/en/stable/markdown/podman-push.1.html) - Push operations, --authfile option
- [containers-auth.json Manual](https://man.archlinux.org/man/containers-auth.json.5) - Auth file format, base64 encoding, security considerations
- [OCM GitHub Releases v0.35.0](https://github.com/open-component-model/ocm/releases/tag/v0.35.0) - Asset naming, SHA256 files, download URLs
- [OCM CLI Reference](https://github.com/open-component-model/ocm/blob/main/docs/reference/ocm.md) - Version command, global flags
- [GitHub SHA256 Checksums Announcement](https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/) - Auto-generated checksums since June 2025

### Secondary (MEDIUM confidence)
- [Quay Robot Accounts Documentation](https://docs.projectquay.io/use_quay.html) - Token authentication, username format
- [Quay Ephemeral Tokens (v3.16)](https://docs.redhat.com/en/documentation/red_hat_quay/3.16/pdf/about_quay_io/Red_Hat_Quay-3.16-About_Quay_IO-en-US.pdf) - Short-lived tokens via OIDC
- [Buildah TARGETARCH Support](https://buildah.io/releases/) - TARGETARCH auto-setting in v1.36.0
- [Podman Multi-Tag Push Issue #2369](https://github.com/containers/podman/issues/2369) - No --all-tags flag discussion
- [OCM Version Output Example (Issue #368)](https://github.com/open-component-model/ocm/issues/368) - Go struct format example
- [Verifying Download Hashes During Docker Build](https://adrianhesketh.com/2022/01/26/verifying-download-hashes-during-docker-build/) - SHA256 verification pattern
- [How to Configure Podman Registry (2026)](https://oneuptime.com/blog/post/2026-01-27-podman-registry/view) - Pre-flight credential validation

### Tertiary (LOW confidence)
- [Container Structure Test](https://github.com/GoogleContainerTools/container-structure-test) - Testing framework patterns (not OCM-specific)
- [Podman Exit Code Discussion #3991](https://github.com/containers/podman/issues/3991) - Exit code 125 behavior (issue from 2019, may have changed)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official Podman/Quay documentation, verified GitHub releases
- Architecture patterns: HIGH - Verified with official documentation, tested curl commands for OCM downloads
- Pitfalls: MEDIUM/HIGH - Based on GitHub issues, documentation warnings, and community reports
- OCM version output: MEDIUM - Single example from GitHub issue (v0.3.0), format may have evolved

**Research date:** 2026-02-10
**Valid until:** 2026-03-12 (30 days - container tooling stable, but OCM releases frequent)
