# Phase 23: Quay.io Integration - Research

**Researched:** 2026-02-10
**Domain:** Container registry API integration, image digest comparison, version staleness detection
**Confidence:** HIGH

## Summary

Quay.io integration requires querying the registry API to list tags, retrieve manifest digests, and compare them with locally built images. The standard approach uses either the Quay.io-specific API (`/api/v1/`) for tag listing or the OCI/Docker Registry v2 API (`/v2/`) for manifest inspection. Authentication leverages existing podman login credentials, with graceful fallback to anonymous access for public repositories.

The critical challenge is digest comparison: locally built images have different digest representations than registry manifests due to compression, multi-architecture manifests, and registry-specific encoding. The reliable approach is to use skopeo for registry inspection (which handles OCI standards correctly) and compare specific manifest fields rather than attempting to match podman's local digest directly.

**Primary recommendation:** Use skopeo inspect for registry queries (battle-tested, handles auth/digests correctly), implement change-based version bumping (build first, compare digests, then bump), and fail-fast on all errors for CI/CD reliability.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| skopeo | 1.17+ | Registry inspection without pulling images | Official containers/skopeo project, handles OCI standards correctly, avoids digest comparison pitfalls |
| jq | 1.8+ | JSON parsing for API responses | Ubiquitous in shell scripts, handles malformed JSON gracefully with -e flag |
| curl | 7.76+ | HTTP API calls with retry logic | Native to all Linux/macOS, supports --retry-connrefused and exponential backoff |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| semver-tool | bash implementation | Semantic version comparison and incrementing | Alternative to hand-rolled version parsing, provides `semver bump patch` and `semver compare` |
| podman | 4.0+ | Credential integration via auth.json | Already required for building, provides authentication for skopeo/curl |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| skopeo | Direct curl to /v2/ API | More control but must handle digest formats, multi-arch manifests, auth token exchange manually |
| semver-tool | Hand-rolled bash version parsing | Simpler dependencies but error-prone for edge cases (pre-release versions, comparisons) |
| skopeo | Quay.io /api/v1/ endpoint | Quay-specific, simpler response format, but non-standard (locks to Quay.io, won't work with other registries) |

**Installation:**
```bash
# skopeo (most Linux distros)
dnf install skopeo  # RHEL/Fedora
apt install skopeo  # Ubuntu/Debian

# macOS (via Homebrew)
brew install skopeo jq

# semver-tool (optional)
curl -o /usr/local/bin/semver https://raw.githubusercontent.com/fsaintjacques/semver-tool/master/src/semver
chmod +x /usr/local/bin/semver
```

## Architecture Patterns

### Recommended Integration Flow
```
1. Build image (using current versions.yaml)
2. Get local image digest (podman inspect)
3. Query registry for latest semantic version tag
4. Query registry for current version's manifest digest
5. Compare digests
6. If different → auto-bump patch version in versions.yaml
7. If same → skip (no publish needed)
```

### Pattern 1: Skopeo Registry Inspection
**What:** Use skopeo inspect to query registry metadata without pulling images
**When to use:** Any registry query (tags, digests, manifests)
**Example:**
```bash
# Source: https://github.com/containers/skopeo/blob/main/docs/skopeo-inspect.1.md
# Get manifest digest for a specific tag
skopeo inspect docker://quay.io/namespace/mc-rhel10:1.0.5 | jq -r '.Digest'

# Output: sha256:abc123...

# List all tags (using OCI registry API)
skopeo list-tags docker://quay.io/namespace/mc-rhel10 | jq -r '.Tags[]'
```

### Pattern 2: Credential Reuse from Podman Login
**What:** Read existing auth.json created by podman login
**When to use:** Authenticating to registries without prompting user
**Example:**
```bash
# Source: https://docs.podman.io/en/v5.1.0/markdown/podman-login.1.html
# Check for credentials (macOS/Windows persistent location)
AUTH_FILE="${HOME}/.config/containers/auth.json"

# Linux ephemeral location (lost on reboot)
# AUTH_FILE="${XDG_RUNTIME_DIR}/containers/auth.json"

# skopeo automatically uses these credentials
if [[ -f "$AUTH_FILE" ]]; then
  skopeo inspect docker://quay.io/private/repo:tag
else
  # Try anonymous access (public images)
  skopeo inspect docker://quay.io/public/repo:tag
fi
```

### Pattern 3: Semantic Version Sorting from Registry Tags
**What:** Find highest semantic version from registry tag list
**When to use:** Determining "latest published version" (ignoring :latest tag)
**Example:**
```bash
# Get all tags, filter to semver format, sort, take highest
skopeo list-tags docker://quay.io/namespace/mc-rhel10 | \
  jq -r '.Tags[]' | \
  grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | \
  sort -V | \
  tail -1
# Output: 1.0.5
```

### Pattern 4: Exponential Backoff for Rate Limiting
**What:** Retry with increasing delays on HTTP 429
**When to use:** All registry API calls
**Example:**
```bash
# Source: Best practices from https://blog.postman.com/http-error-429/
# Exponential backoff with jitter
retry_api_call() {
  local max_attempts=5
  local base_delay=1
  local attempt=1

  while [[ $attempt -le $max_attempts ]]; do
    # Make API call
    response=$(curl -s -w "%{http_code}" -o /tmp/response.json "$@")
    http_code="${response: -3}"

    if [[ "$http_code" == "200" ]]; then
      cat /tmp/response.json
      return 0
    elif [[ "$http_code" == "429" ]]; then
      # Calculate delay: base_delay * 2^(attempt-1) + jitter
      delay=$((base_delay * (1 << (attempt - 1))))
      jitter=$((RANDOM % (delay / 2)))
      total_delay=$((delay + jitter))

      echo "Rate limited, retrying in ${total_delay}s..." >&2
      sleep "$total_delay"
      ((attempt++))
    else
      echo "Request failed with HTTP $http_code" >&2
      return 1
    fi
  done

  echo "Max retries exceeded" >&2
  return 1
}
```

### Pattern 5: Digest-Based Change Detection
**What:** Build image first, then compare digest with registry to determine if version bump needed
**When to use:** Auto-versioning workflow
**Example:**
```bash
# Build image with current versions.yaml
podman build -t mc-rhel10:1.0.5 ...

# Get local image digest (use RepoDigests after push, or calculate from config)
LOCAL_DIGEST=$(podman inspect mc-rhel10:1.0.5 | jq -r '.[0].Digest')

# Get registry digest for same version (if exists)
REGISTRY_DIGEST=$(skopeo inspect docker://quay.io/namespace/mc-rhel10:1.0.5 2>/dev/null | jq -r '.Digest')

# Compare
if [[ "$LOCAL_DIGEST" != "$REGISTRY_DIGEST" ]]; then
  echo "Image changed, version bump required"
  # Auto-increment patch version
fi
```

### Anti-Patterns to Avoid
- **Pulling images to compare:** Bandwidth-intensive, slow, unnecessary (skopeo provides digests without pull)
- **Comparing local Digest to registry RepoDigests:** Digest formats differ (compressed vs uncompressed, multi-arch manifests)
- **Caching registry responses:** Stale data defeats purpose of version staleness detection
- **Silent auth failures:** Degrades security, use explicit anonymous access or fail loudly

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic version comparison | String split and integer compare | `semver compare` or `sort -V` | Pre-release versions, build metadata, lexical vs numeric sorting edge cases |
| Semantic version increment | Regex replace on patch number | `semver bump patch` | Handles 1.0.9 → 1.0.10 correctly, validates format, preserves metadata |
| Registry manifest inspection | curl + JSON parsing + auth token exchange | skopeo inspect | Handles multi-arch manifests, compressed digests, OCI spec compliance, auth integration |
| HTTP retry logic | Manual sleep loops | curl --retry --retry-connrefused | Built-in exponential backoff, handles transient errors correctly |
| JSON parsing with error handling | grep/sed on JSON | jq with -e flag | Handles malformed JSON, provides exit codes, validates structure |

**Key insight:** Container registry APIs have subtle complexity (multi-arch manifests, digest calculation differences, auth token exchange). Use battle-tested tools (skopeo) that handle OCI standards correctly rather than reimplementing.

## Common Pitfalls

### Pitfall 1: Digest Mismatch Between Local and Registry
**What goes wrong:** Local `podman inspect` digest doesn't match registry manifest digest after push
**Why it happens:** Compression differences, multi-arch manifest wrapping, registry re-encoding
**How to avoid:**
- Don't compare `podman inspect .[0].Digest` directly to registry digest
- Use RepoDigests field (post-push) or build → push → query registry flow
- Alternative: Compare specific manifest fields (layers, config) instead of top-level digest
**Warning signs:** Same image shows different SHA256 hashes locally vs on quay.io

**Source:** [Podman digest SHA locally does not match remote digest](https://github.com/containers/podman/issues/14779), [Image digest different for local vs pushed](https://github.com/containers/podman/discussions/15803)

### Pitfall 2: Compressed vs Uncompressed Layer Digests
**What goes wrong:** Layer digests in manifest reference compressed tar.gzip, but local runtime tracks uncompressed
**Why it happens:** Registry manifests store compressed digest, containerd/podman track uncompressed digest separately
**How to avoid:**
- Always compare manifest-level digest, not individual layer digests
- If comparing layers, ensure both sides use same compression state
**Warning signs:** Digest comparison fails even though image content is identical

**Source:** [Layer digests shown in manifests are different from uncompressed](https://www.digitalocean.com/blog/inside-container-registry-mechanics-of-push-pull)

### Pitfall 3: RepoDigests Array for Multi-Arch Images
**What goes wrong:** RepoDigests contains multiple digests for multi-arch images (manifest list + platform-specific)
**Why it happens:** Multi-arch images have both a "fat manifest" digest and per-architecture image digests
**How to avoid:**
- Specify architecture when querying: `skopeo inspect --override-arch amd64 docker://...`
- Compare manifest list digest for multi-arch, or platform-specific digest for single-arch
**Warning signs:** RepoDigests array has 2+ entries, digests differ based on how you query

**Source:** [Digest inconsistent for multi-arch images](https://github.com/containers/podman/issues/24858)

### Pitfall 4: Assuming Global Podman Credentials
**What goes wrong:** Script can't authenticate because auth.json is in ephemeral location (Linux /run)
**Why it happens:** Default Linux location is `${XDG_RUNTIME_DIR}/containers/auth.json` which is lost on reboot
**How to avoid:**
- Check both persistent (`$HOME/.config/containers/auth.json`) and ephemeral locations
- Document that users should `podman login --authfile ~/.config/containers/auth.json` for persistence
- Fall back to anonymous access for public repos
**Warning signs:** Authentication works after `podman login` but fails after reboot

**Source:** [Podman registry credentials removed after reboot](https://access.redhat.com/solutions/7002142)

### Pitfall 5: Not Handling HTTP 429 Rate Limits
**What goes wrong:** Script fails on busy networks or CI environments with many parallel builds
**Why it happens:** Quay.io and other registries enforce rate limits, respond with HTTP 429
**How to avoid:**
- Check for Retry-After header first (respect server's guidance)
- Implement exponential backoff with jitter (prevent thundering herd)
- Set max retry limit (5-7 attempts) to avoid infinite loops
- Use curl --retry 5 --retry-connrefused for built-in retry logic
**Warning signs:** Intermittent failures in CI, works locally but fails in GitHub Actions

**Source:** [Best practices for handling 429 errors](https://help.docebo.com/hc/en-us/articles/31803763436946-Best-practices-for-handling-API-rate-limits-and-429-errors), [HTTP Error 429 explained](https://blog.postman.com/http-error-429/)

### Pitfall 6: Version Comparison with Non-Numeric Patch Numbers
**What goes wrong:** String comparison treats "1.0.9" > "1.0.10" (lexical vs numeric)
**Why it happens:** Bash string comparison is lexical, not numeric-aware
**How to avoid:**
- Use `sort -V` (version sort) for comparing semantic versions
- Or use dedicated semver tool: `semver compare 1.0.9 1.0.10` returns -1 (first is older)
- Never use `[[ "1.0.9" > "1.0.10" ]]` for version comparison
**Warning signs:** Script thinks 1.0.9 is newer than 1.0.10

**Source:** [Semantic version comparison in bash](https://github.com/fsaintjacques/semver-tool)

### Pitfall 7: Ignoring Network Errors
**What goes wrong:** Script continues after registry query fails, leading to incorrect decisions
**Why it happens:** curl succeeds (HTTP 200) but content is error JSON, or network timeout is silent
**How to avoid:**
- Check curl exit code: `curl --fail` returns non-zero on HTTP 4xx/5xx
- Validate JSON response with jq -e: `jq -e '.Digest' || exit 1`
- Set connection timeout: `curl --connect-timeout 10 --max-time 30`
- Use `set -euo pipefail` to fail on any command error
**Warning signs:** Script reports "no version published" when network is down

**Source:** [curl timeout error handling](https://gist.github.com/yidas/467968d25cd7424cb5ea98500300680f), [How to handle timeouts in curl](https://www.simplified.guide/curl/timeout-handle)

## Code Examples

Verified patterns from official sources:

### Query Registry for Latest Semantic Version Tag
```bash
# Source: https://github.com/containers/skopeo (skopeo list-tags)
# Get highest semantic version from registry, ignoring :latest and pre-release tags

get_latest_registry_version() {
  local image_repo="$1"  # e.g., "quay.io/namespace/mc-rhel10"

  # List tags, filter to x.y.z format, sort, take highest
  skopeo list-tags "docker://${image_repo}" | \
    jq -r '.Tags[]' | \
    grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | \
    sort -V | \
    tail -1
}

# Usage
LATEST_VERSION=$(get_latest_registry_version "quay.io/namespace/mc-rhel10")
echo "Latest published: $LATEST_VERSION"
```

### Check if Specific Version Exists on Registry
```bash
# Source: https://github.com/containers/skopeo (skopeo inspect)
# Returns 0 if version exists, 1 if not found

version_exists_on_registry() {
  local image_repo="$1"  # e.g., "quay.io/namespace/mc-rhel10"
  local version="$2"     # e.g., "1.0.5"

  # skopeo inspect returns non-zero if tag doesn't exist
  if skopeo inspect "docker://${image_repo}:${version}" &>/dev/null; then
    return 0  # exists
  else
    return 1  # not found
  fi
}

# Usage
if version_exists_on_registry "quay.io/namespace/mc-rhel10" "1.0.5"; then
  echo "Version 1.0.5 already published"
else
  echo "Version 1.0.5 not found on registry"
fi
```

### Get Manifest Digest from Registry
```bash
# Source: https://github.com/containers/skopeo (skopeo inspect)
# Returns digest or empty string if tag doesn't exist

get_registry_digest() {
  local image_repo="$1"  # e.g., "quay.io/namespace/mc-rhel10"
  local version="$2"     # e.g., "1.0.5"

  skopeo inspect "docker://${image_repo}:${version}" 2>/dev/null | \
    jq -r '.Digest // empty'
}

# Usage
REGISTRY_DIGEST=$(get_registry_digest "quay.io/namespace/mc-rhel10" "1.0.5")
if [[ -n "$REGISTRY_DIGEST" ]]; then
  echo "Registry digest: $REGISTRY_DIGEST"
else
  echo "Version not found on registry"
fi
```

### Auto-Increment Patch Version in versions.yaml
```bash
# Source: https://github.com/fsaintjacques/semver-tool (semver bump)
# Increments patch version (1.0.5 → 1.0.6)

bump_patch_version() {
  local versions_file="$1"  # Path to versions.yaml

  # Read current version
  current_version=$(yq '.image.version' "$versions_file")

  # Increment patch (using semver-tool)
  new_version=$(semver bump patch "$current_version")

  # Update versions.yaml
  yq -i ".image.version = \"$new_version\"" "$versions_file"

  echo "Version bumped: $current_version → $new_version"
}

# Alternative: Hand-rolled increment (if semver-tool not available)
bump_patch_version_manual() {
  local versions_file="$1"

  current_version=$(yq '.image.version' "$versions_file")

  # Split version into parts
  IFS='.' read -r major minor patch <<< "$current_version"

  # Increment patch
  new_patch=$((patch + 1))
  new_version="${major}.${minor}.${new_patch}"

  # Update versions.yaml
  yq -i ".image.version = \"$new_version\"" "$versions_file"

  echo "Version bumped: $current_version → $new_version"
}
```

### Exponential Backoff with Retry-After Header
```bash
# Source: https://blog.postman.com/http-error-429/ (HTTP 429 best practices)
# Respects Retry-After header, falls back to exponential backoff

retry_with_backoff() {
  local url="$1"
  local max_attempts=5
  local base_delay=1
  local attempt=1

  while [[ $attempt -le $max_attempts ]]; do
    # Make request, capture headers and body
    response=$(curl -s -i -w "\n%{http_code}" "$url")
    http_code=$(echo "$response" | tail -1)
    headers=$(echo "$response" | sed -n '1,/^$/p')
    body=$(echo "$response" | sed '1,/^$/d' | head -n -1)

    if [[ "$http_code" == "200" ]]; then
      echo "$body"
      return 0
    elif [[ "$http_code" == "429" ]]; then
      # Check for Retry-After header
      retry_after=$(echo "$headers" | grep -i "Retry-After:" | awk '{print $2}' | tr -d '\r')

      if [[ -n "$retry_after" ]]; then
        # Use server-provided delay
        echo "Rate limited, retrying after ${retry_after}s (server-specified)..." >&2
        sleep "$retry_after"
      else
        # Exponential backoff with jitter
        delay=$((base_delay * (1 << (attempt - 1))))
        jitter=$((RANDOM % (delay / 2)))
        total_delay=$((delay + jitter))

        echo "Rate limited, retrying in ${total_delay}s (attempt $attempt/$max_attempts)..." >&2
        sleep "$total_delay"
      fi

      ((attempt++))
    else
      echo "Request failed with HTTP $http_code" >&2
      return 1
    fi
  done

  echo "Max retries exceeded" >&2
  return 1
}
```

### Safe JSON Parsing with Error Handling
```bash
# Source: https://jqlang.org/manual/ (jq -e flag for exit status)
# Validates JSON structure and provides error handling

parse_registry_response() {
  local json_response="$1"
  local field="$2"  # e.g., ".Digest"

  # Use -e flag to exit with error if field doesn't exist
  # Use -r for raw output (no quotes)
  echo "$json_response" | jq -e -r "$field" 2>/dev/null

  # jq -e returns:
  # - 0 if field exists and is not null/false
  # - 1 if field is null/false
  # - 2-3 for parsing errors
  local exit_code=$?

  if [[ $exit_code -ne 0 ]]; then
    echo "Error: Failed to parse JSON field '$field'" >&2
    return 1
  fi
}

# Usage
response=$(skopeo inspect docker://quay.io/namespace/mc-rhel10:1.0.5)
digest=$(parse_registry_response "$response" ".Digest") || {
  echo "Failed to get digest"
  exit 1
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Pull image to compare | skopeo inspect (no pull) | 2019+ (skopeo matured) | 100x faster, no disk usage, works in CI |
| Quay.io-specific /api/v1/ | OCI Registry v2 /v2/ API | 2021+ (OCI standard adoption) | Portable across registries (Docker Hub, GitHub, Quay.io) |
| Manual curl + auth token exchange | skopeo with podman auth.json | 2020+ (containers/image library) | Automatic credential reuse, no token management |
| String comparison for versions | sort -V or semver tools | 2018+ (coreutils 8.30) | Correct semantic version ordering |
| Manual retry loops | curl --retry with exponential backoff | 2022+ (curl 7.76) | Built-in transient error handling |

**Deprecated/outdated:**
- **Docker Registry v1 API**: Removed 2018, use v2 API (/v2/ endpoints)
- **Anonymous Quay.io tag listing**: Now requires auth even for public repos (changed 2023), use skopeo with credentials
- **Podman .Digest field for registry comparison**: Unreliable for multi-arch images, use RepoDigests or skopeo

## Open Questions

Things that couldn't be fully resolved:

1. **Quay.io Rate Limits**
   - What we know: HTTP 429 returned on rate limit, Retry-After header may be provided
   - What's unclear: Exact rate limit thresholds (requests per minute/hour), whether limits differ for authenticated vs anonymous
   - Recommendation: Implement retry logic, monitor in CI for actual limits, contact Quay.io support if limits too restrictive

2. **Multi-Architecture Digest Behavior**
   - What we know: Multi-arch images have both manifest list digest and per-platform digests, RepoDigests can contain multiple entries
   - What's unclear: Whether comparing manifest list digest is sufficient for change detection, or if need platform-specific comparison
   - Recommendation: Start with manifest list digest comparison (simpler), validate in testing with multi-arch builds

3. **Podman vs Skopeo Digest Differences**
   - What we know: Podman inspect and skopeo inspect sometimes report different digests for same image
   - What's unclear: Root cause (compression, manifest format, local vs registry encoding), when they align
   - Recommendation: Use skopeo as source of truth for registry comparisons, avoid podman digest for registry comparison

## Sources

### Primary (HIGH confidence)
- [OCI Distribution Spec](https://github.com/opencontainers/distribution-spec/blob/main/spec.md) - Registry v2 API standard
- [Skopeo Documentation](https://github.com/containers/skopeo) - Registry inspection tool
- [Podman Login Documentation](https://docs.podman.io/en/v5.1.0/markdown/podman-login.1.html) - Authentication file locations
- [semver-tool](https://github.com/fsaintjacques/semver-tool) - Semantic version operations
- [jq Manual](https://jqlang.org/manual/) - JSON parsing

### Secondary (MEDIUM confidence)
- [Best practices for handling API rate limits](https://help.docebo.com/hc/en-us/articles/31803763436946-Best-practices-for-handling-API-rate-limits-and-429-errors) - HTTP 429 handling patterns
- [HTTP Error 429 explained](https://blog.postman.com/http-error-429/) - Rate limiting and exponential backoff
- [Inside a container registry](https://www.digitalocean.com/blog/inside-container-registry-mechanics-of-push-pull) - Digest mechanics
- [Quay.io API Documentation](https://docs.quay.io/api/) - Registry-specific API
- [Project Quay API Guide](https://docs.projectquay.io/api_quay.html) - Authentication and bearer tokens

### Tertiary (LOW confidence - validation needed)
- [Podman digest mismatch issues](https://github.com/containers/podman/issues/14779) - Known digest comparison problems
- [Multi-arch digest inconsistencies](https://github.com/containers/podman/issues/24858) - Platform-specific digest behavior
- [Quay.io authentication failures](https://docs.quay.io/issues/auth-failure.html) - Common auth problems

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - skopeo, jq, curl are widely adopted, official tools with stable APIs
- Architecture: HIGH - OCI Registry v2 API is standard, skopeo patterns verified in documentation
- Pitfalls: MEDIUM - Based on GitHub issues and community reports, but validated against official docs
- Change detection workflow: MEDIUM - Build-first approach is logical but digest comparison has known edge cases

**Research date:** 2026-02-10
**Valid until:** 2026-04-10 (60 days - container ecosystem is relatively stable)

**Key uncertainties requiring validation during planning:**
- Exact Quay.io rate limit thresholds (may need testing or contact with Quay.io)
- Multi-arch digest comparison strategy (may need experimentation with actual multi-arch builds)
- Whether to use semver-tool or hand-rolled version parsing (dependency vs simplicity tradeoff)
