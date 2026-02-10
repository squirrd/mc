# Phase 24: Auto-Versioning Logic - Research

**Researched:** 2026-02-10
**Domain:** Semantic version bumping, YAML manipulation, digest-based change detection, version conflict prevention
**Confidence:** HIGH

## Summary

Auto-versioning for container images requires three core capabilities: semantic version parsing and incrementing (x.y.z format), YAML file manipulation to update version fields, and digest-based change detection to determine when bumping is necessary. The standard approach uses yq for YAML updates (already available from Phase 22), bash regex or sort -V for version comparison, and skopeo digest comparison (established in Phase 23) as the trigger mechanism.

The critical design decision is the versioning model: versions.yaml stores only the minor version ("x.y"), while the patch number is calculated at build time by querying the registry for the latest "x.y.*" tag and incrementing. This makes the registry the source of truth for patch versions, preventing conflicts when multiple developers build simultaneously. The build flow is: extract minor version → query registry for latest x.y.* → build image → compare digests → if different, auto-bump to x.y.(z+1) and push.

Version validation must follow Semantic Versioning 2.0.0 specification, which requires non-negative integers without leading zeros in the format X.Y.Z. The official regex pattern ensures compliance, catching invalid formats like "01.2.3" (leading zeros) or "1.2" (missing patch).

**Primary recommendation:** Use yq for YAML updates (already installed), implement bash regex for version parsing and increment, validate against semver 2.0 spec, and make digest comparison (not file change) the bump trigger. Store only x.y in versions.yaml, calculate patch from registry state.

## Standard Stack

The established libraries/tools for this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| yq | 4.52+ | YAML file manipulation | Official mikefarah/yq project, in-place editing with -i flag, environment variable support via strenv() |
| bash regex | POSIX ERE | Version string parsing and validation | Built-in to bash 3.0+, BASH_REMATCH array for capture groups, no dependencies |
| sort -V | coreutils 8.30+ | Semantic version comparison | Built-in version-aware sort, handles 1.0.9 vs 1.0.10 correctly, no external tools |
| skopeo | 1.17+ | Registry digest queries | Already required from Phase 23, provides digest comparison for change detection |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| semver-tool | 3.4.0 | Semantic version operations | Optional alternative to hand-rolled bash, provides `semver bump patch` and `semver compare` |
| jq | 1.8+ | JSON parsing for skopeo output | Already required from Phase 23, used for parsing registry responses |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yq | sed/awk YAML editing | yq is safer (validates YAML structure), already installed from Phase 22 |
| bash regex | semver-tool | semver-tool adds dependency, but handles edge cases (pre-release versions) more robustly |
| sort -V | semver compare | sort -V is built-in, semver-tool provides clearer semantics for version comparison |
| Manual increment | Git tag-based versioning | Git tags decouple from image content, digest-based approach ensures content-driven versioning |

**Installation:**
```bash
# yq (already installed in Phase 22)
# macOS
brew install yq

# Linux
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq
chmod +x /usr/local/bin/yq

# semver-tool (optional)
wget -O /usr/local/bin/semver https://raw.githubusercontent.com/fsaintjacques/semver-tool/master/src/semver
chmod +x /usr/local/bin/semver
```

## Architecture Patterns

### Recommended Versioning Model
```
versions.yaml stores:
  image.version: "1.2"    # Minor version only (x.y)

Build-time calculation:
  1. Read image.version → "1.2"
  2. Query registry → latest tag matching "1.2.*" → "1.2.17"
  3. Build image locally
  4. Compare digest: local vs registry "1.2.17"
  5. If same → no-op (skip bump, skip push)
  6. If different → bump to "1.2.18", tag, auto-push

Registry as source of truth:
  - Patch version determined by registry state (not local files)
  - Prevents conflicts when multiple developers build
  - No stored patch version means no merge conflicts
```

### Pattern 1: Extract Minor Version from versions.yaml
**What:** Read x.y value from YAML, parse into major/minor components
**When to use:** At start of build to determine version prefix
**Example:**
```bash
# Source: https://github.com/mikefarah/yq (v4.52 syntax)
# Extract minor version from versions.yaml
MINOR_VERSION=$(yq '.image.version' container/versions.yaml)
# Returns: "1.2"

# Parse into components using IFS
IFS='.' read -r MAJOR MINOR <<< "$MINOR_VERSION"
# MAJOR=1, MINOR=2
```

### Pattern 2: Find Latest Patch Version on Registry
**What:** Query registry for all tags matching x.y.* pattern, sort, take highest
**When to use:** Before building to determine current patch number
**Example:**
```bash
# Source: Phase 23 research (skopeo list-tags + sort -V)
# Find latest tag matching minor version prefix
find_latest_patch() {
  local image_repo="$1"     # "quay.io/namespace/mc-rhel10"
  local minor_version="$2"  # "1.2"

  # List all tags, filter to x.y.z matching our minor version
  skopeo list-tags "docker://${image_repo}" 2>/dev/null | \
    jq -r '.Tags[]' | \
    grep -E "^${minor_version}\.[0-9]+$" | \
    sort -V | \
    tail -1
}

# Usage
LATEST_TAG=$(find_latest_patch "quay.io/namespace/mc-rhel10" "1.2")
# Returns: "1.2.17" (or empty if no matching tags exist)

# Extract patch number
if [[ -n "$LATEST_TAG" ]]; then
  IFS='.' read -r _ _ CURRENT_PATCH <<< "$LATEST_TAG"
  # CURRENT_PATCH=17
else
  CURRENT_PATCH="-1"  # No existing tags, will start at 0
fi
```

### Pattern 3: Increment Patch Version
**What:** Add 1 to current patch number, construct new semantic version
**When to use:** After digest comparison confirms image changed
**Example:**
```bash
# Source: Bash arithmetic expansion
# Increment patch and construct new version
increment_patch() {
  local major="$1"
  local minor="$2"
  local current_patch="$3"  # -1 if no existing version

  # Increment (handles -1 → 0 for first build)
  local new_patch=$((current_patch + 1))

  echo "${major}.${minor}.${new_patch}"
}

# Usage
NEW_VERSION=$(increment_patch 1 2 17)
# Returns: "1.2.18"

# First build case
NEW_VERSION=$(increment_patch 1 2 -1)
# Returns: "1.2.0"
```

### Pattern 4: Validate Semantic Version Format
**What:** Check version string against semver 2.0 specification
**When to use:** Before any version operation (bump, tag, push)
**Example:**
```bash
# Source: https://semver.org/ official regex, bash-compatible variant
# Validate semantic version format
validate_semver() {
  local version="$1"

  # Semver 2.0 regex: major.minor.patch (no leading zeros, integers only)
  local semver_regex='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'

  if [[ "$version" =~ $semver_regex ]]; then
    return 0  # valid
  else
    return 1  # invalid
  fi
}

# Usage
if validate_semver "1.2.18"; then
  echo "Valid version"
fi

# Invalid cases
validate_semver "1.2"        # Missing patch (returns 1)
validate_semver "01.2.3"     # Leading zero (returns 1)
validate_semver "1.2.3-beta" # Pre-release (returns 1, out of scope)
```

### Pattern 5: Digest-Based Bump Decision
**What:** Compare local image digest with registry digest to determine if bump needed
**When to use:** After building image, before tagging/pushing
**Example:**
```bash
# Source: Phase 23 research (skopeo inspect for digest comparison)
# Decide whether to bump version based on digest comparison
should_bump_version() {
  local image_repo="$1"        # "quay.io/namespace/mc-rhel10"
  local existing_version="$2"  # "1.2.17" (latest on registry)
  local local_image="$3"       # "mc-rhel10:latest" (just built)

  # Get registry digest (empty if version doesn't exist)
  local registry_digest
  registry_digest=$(skopeo inspect "docker://${image_repo}:${existing_version}" 2>/dev/null | \
    jq -r '.Digest // empty')

  # Get local digest
  local local_digest
  local_digest=$(podman inspect "$local_image" 2>/dev/null | jq -r '.[0].Digest')

  # If no registry version, always bump (first build)
  if [[ -z "$registry_digest" ]]; then
    return 0  # bump needed
  fi

  # Compare digests
  if [[ "$local_digest" != "$registry_digest" ]]; then
    return 0  # bump needed (content changed)
  else
    return 1  # no bump (identical content)
  fi
}

# Usage
if should_bump_version "quay.io/namespace/mc-rhel10" "1.2.17" "mc-rhel10:latest"; then
  echo "Image changed, bumping to 1.2.18"
else
  echo "Image unchanged, skipping bump"
fi
```

### Pattern 6: Update Minor Version in YAML (Manual)
**What:** User manually updates image.version when adding new tools
**When to use:** When adding new tool to container (manual step, not automated)
**Example:**
```bash
# Source: https://github.com/mikefarah/yq (update operator with strenv)
# Manually update minor version in versions.yaml
update_minor_version() {
  local new_version="$1"  # "1.3" (user decides to bump minor)

  # Update versions.yaml in-place
  yq -i ".image.version = \"$new_version\"" container/versions.yaml

  echo "Minor version updated to $new_version"
  echo "Next build will create ${new_version}.0"
}

# Usage (manual workflow)
# User adds new tool (e.g., oc CLI) to container
# User runs: update_minor_version "1.3"
# Next build creates 1.3.0 (registry has no 1.3.* tags yet)
# Subsequent builds create 1.3.1, 1.3.2, etc.
```

### Pattern 7: Version Conflict Detection
**What:** Check if calculated next version already exists on registry
**When to use:** After incrementing, before tagging (safety check)
**Example:**
```bash
# Source: Phase 23 research (skopeo inspect for existence check)
# Check if version already exists on registry
version_exists_on_registry() {
  local image_repo="$1"  # "quay.io/namespace/mc-rhel10"
  local version="$2"     # "1.2.18"

  # skopeo inspect returns non-zero if tag doesn't exist
  if skopeo inspect "docker://${image_repo}:${version}" &>/dev/null; then
    return 0  # exists
  else
    return 1  # not found
  fi
}

# Usage
NEW_VERSION="1.2.18"
if version_exists_on_registry "quay.io/namespace/mc-rhel10" "$NEW_VERSION"; then
  echo "ERROR: Version $NEW_VERSION already exists on registry"
  echo "This indicates a race condition or registry query failure"
  exit 1
fi
```

### Integration Flow
```
Build script workflow:

1. Preflight checks
   - Validate yq, skopeo, jq, podman available
   - Validate versions.yaml exists and is valid YAML

2. Version extraction
   - Read image.version from versions.yaml → "1.2"
   - Parse into MAJOR, MINOR components

3. Registry query
   - Query latest tag matching "1.2.*" → "1.2.17"
   - Extract CURRENT_PATCH → 17
   - If no tags found → CURRENT_PATCH=-1

4. Image build
   - Build image with podman (mc-rhel10:temp)
   - Get local digest

5. Digest comparison
   - Get registry digest for "1.2.17" (if exists)
   - Compare local vs registry digest

6. Decision point
   A. Digests match (or registry query failed earlier)
      - Log "Image unchanged, skipping publish"
      - Exit 0 (no-op)

   B. Digests differ (or first build)
      - Calculate NEW_VERSION → "1.2.18"
      - Validate semver format
      - Check conflict (version already exists)
      - Tag image: mc-rhel10:1.2.18 and mc-rhel10:latest
      - Auto-push to registry
      - Log "Published 1.2.18"
```

### Anti-Patterns to Avoid
- **Storing patch version in versions.yaml:** Causes merge conflicts, race conditions when multiple developers build
- **File-based change detection:** Dockerfile changes don't always mean image changes (comments, whitespace), digest is authoritative
- **Manual version bumping:** Error-prone, defeats purpose of automation, use digest-based trigger instead
- **Comparing versions with string operators:** "1.0.9" > "1.0.10" lexically, use sort -V or semver compare
- **Allowing version conflicts:** If calculated version exists on registry, fail hard (indicates logic error or race)

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Semantic version validation | Custom regex without anchors | Official semver regex with ^ and $ | Edge cases: leading zeros (01.2.3), missing components (1.2), non-integers (1.a.3) |
| YAML field updates | sed with line matching | yq with field path | YAML formatting (indentation, quotes), nested structures, arrays, type preservation |
| Version comparison | String comparison | sort -V or semver compare | Lexical vs numeric (1.0.9 vs 1.0.10), pre-release versions (-alpha), build metadata (+build) |
| Registry tag listing | curl + jq to registry API | skopeo list-tags | Authentication, multi-arch manifests, pagination, rate limiting, error handling |
| Patch increment | Regex find/replace | Arithmetic $((patch + 1)) | Handles 9→10 transition, validates input is integer, -1→0 for first build |

**Key insight:** Version bumping seems simple (just add 1) but has subtle requirements: semver validation, YAML structure preservation, digest-based trigger logic, and registry conflict detection. Use battle-tested tools (yq, skopeo) and follow semver 2.0 spec strictly.

## Common Pitfalls

### Pitfall 1: Storing Patch Version in versions.yaml
**What goes wrong:** Multiple developers building simultaneously create merge conflicts, versions diverge
**Why it happens:** Git tracks versions.yaml, two builds increment patch simultaneously, both commit "1.2.18"
**How to avoid:**
- Store only minor version (x.y) in versions.yaml
- Calculate patch at build time from registry state (source of truth)
- Registry's linear tag history prevents conflicts
**Warning signs:** Frequent merge conflicts in versions.yaml, version numbers skipped on registry (1.2.5 → 1.2.7)

**Source:** Decision from Phase 24 CONTEXT.md, pattern used by Chainguard and other image builders

### Pitfall 2: Leading Zeros in Version Numbers
**What goes wrong:** Version "01.2.3" or "1.02.3" violates semver spec, breaks version comparison
**Why it happens:** Zero-padding for visual alignment, copying from other systems that allow it
**How to avoid:**
- Validate with semver regex: `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`
- Reject versions with leading zeros (0 is valid, 00 or 01 are not)
- Test: validate_semver "01.2.3" should return false
**Warning signs:** Version comparison fails unexpectedly, registry rejects push with "invalid tag"

**Source:** [Semantic Versioning 2.0.0 Specification](https://semver.org/) Item 2: "A normal version number MUST take the form X.Y.Z where X, Y, and Z are non-negative integers, and MUST NOT contain leading zeroes."

### Pitfall 3: Lexical vs Numeric Version Comparison
**What goes wrong:** Bash string comparison treats "1.0.9" > "1.0.10" (lexically '9' > '1')
**Why it happens:** `[[ "1.0.9" > "1.0.10" ]]` uses string comparison, not version-aware logic
**How to avoid:**
- Use `sort -V` for version sorting (coreutils 8.30+)
- Or use `semver compare` from semver-tool
- Never use `>`, `<`, `==` string operators for versions
**Warning signs:** Script finds "1.0.9" when "1.0.10" is newer, version order reversed in output

**Source:** [Baeldung: Compare Dot-Separated Version Strings](https://www.baeldung.com/linux/compare-dot-separated-version-string), [bash-semver GitHub](https://github.com/fmahnke/shell-semver)

### Pitfall 4: File Change vs Content Change Detection
**What goes wrong:** Dockerfile changes trigger version bump, but image content unchanged (comment edit)
**Why it happens:** Watching git diff instead of image digest, assumptions about layer caching
**How to avoid:**
- Always build first, then compare digest (not file timestamps)
- Use skopeo inspect digest as authoritative change signal
- Digest includes all layers and config, immune to comment/whitespace changes
**Warning signs:** Version bumps when nothing functionally changed, registry bloat with identical images

**Source:** [Container Image Versioning Best Practices](https://container-registry.com/posts/container-image-versioning/), [Red Hat: How to Name and Version Container Images](https://developers.redhat.com/articles/2025/01/28/how-name-version-and-reference-container-images)

### Pitfall 5: Version Conflict Race Conditions
**What goes wrong:** Two builds query registry, both see "1.2.17", both try to push "1.2.18"
**Why it happens:** Time gap between query and push, no atomic increment operation
**How to avoid:**
- Check version exists before push (version_exists_on_registry)
- If exists, fail hard with error (indicates race or logic bug)
- To retry: manual minor bump (1.2→1.3) or fix race condition source
**Warning signs:** "Image already exists" error from registry, builds succeed locally but push fails

**Source:** [Quay.io Image Already Exists](https://docs.quay.io/issues/image-exists.html), Phase 24 CONTEXT.md (fail-fast on conflict)

### Pitfall 6: Missing Patch Component Validation
**What goes wrong:** Script accepts "1.2" as valid version, tries to push, registry rejects
**Why it happens:** Incomplete semver regex or skipping validation step
**How to avoid:**
- Always validate with full regex: `^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$`
- Require all three components (major.minor.patch)
- Test edge cases: "1.2" (missing), "1" (missing), "1.2.3.4" (extra)
**Warning signs:** Registry push fails with "invalid tag format", error only appears in CI

**Source:** [Semver 2.0 Regex Validation](https://github.com/semver/semver/issues/232), [iHateRegex: Semantic Versioning](https://ihateregex.io/expr/semver/)

### Pitfall 7: Registry Query Failures Silently Ignored
**What goes wrong:** skopeo fails (network down, auth expired), script continues with stale data or defaults
**Why it happens:** Using `|| true` or not checking exit codes, assuming network always works
**How to avoid:**
- Fail fast on registry query errors (Phase 23 decision)
- Check skopeo exit code: `skopeo list-tags ... || exit 1`
- Don't fall back to local version or default values
- Require network connectivity for build (registry is source of truth)
**Warning signs:** Build succeeds offline, creates version 1.2.0 when 1.2.17 exists on registry

**Source:** Phase 23 research Common Pitfalls, Phase 24 CONTEXT.md (fail-fast on registry failure)

### Pitfall 8: YAML Structure Corruption
**What goes wrong:** Using sed/awk to update version field breaks YAML formatting, indentation lost
**Why it happens:** sed matches line pattern but doesn't understand YAML structure (nested objects, quotes)
**How to avoid:**
- Always use yq for YAML updates (validates structure, preserves formatting)
- Use field path syntax: `.image.version = "1.3"`
- Test: verify YAML still parses after update
**Warning signs:** Build fails with "invalid YAML", versions.yaml has broken indentation, values unquoted

**Source:** [yq Documentation](https://github.com/mikefarah/yq), [Processing YAML with yq](https://www.baeldung.com/linux/yq-utility-processing-yaml)

## Code Examples

Verified patterns from official sources:

### Complete Auto-Versioning Function
```bash
# Source: Synthesis of Phase 23 research + semver spec + yq docs
# Implements full auto-versioning workflow with digest-based bumping

auto_version_image() {
  local versions_file="$1"     # container/versions.yaml
  local image_repo="$2"        # quay.io/namespace/mc-rhel10
  local local_image="$3"       # mc-rhel10:latest (just built)

  # 1. Extract minor version from versions.yaml
  local minor_version
  minor_version=$(yq '.image.version' "$versions_file") || {
    echo "ERROR: Failed to read image.version from $versions_file"
    return 1
  }

  # Validate minor version format (x.y)
  if [[ ! "$minor_version" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid minor version format: $minor_version (expected x.y)"
    return 1
  fi

  # Parse components
  IFS='.' read -r major minor <<< "$minor_version"

  # 2. Query registry for latest patch version
  local latest_tag
  latest_tag=$(skopeo list-tags "docker://${image_repo}" 2>/dev/null | \
    jq -r '.Tags[]' | \
    grep -E "^${minor_version}\.[0-9]+$" | \
    sort -V | \
    tail -1)

  local current_patch=-1
  if [[ -n "$latest_tag" ]]; then
    IFS='.' read -r _ _ current_patch <<< "$latest_tag"
  fi

  echo "Current registry state: ${latest_tag:-none} (patch=$current_patch)"

  # 3. Compare digests (if registry version exists)
  if [[ "$current_patch" -ge 0 ]]; then
    local registry_digest local_digest

    registry_digest=$(skopeo inspect "docker://${image_repo}:${latest_tag}" 2>/dev/null | \
      jq -r '.Digest // empty')

    local_digest=$(podman inspect "$local_image" 2>/dev/null | jq -r '.[0].Digest')

    if [[ "$registry_digest" == "$local_digest" ]]; then
      echo "Image unchanged (digest match), skipping bump"
      return 0  # No bump needed
    fi

    echo "Image changed (digest mismatch), bumping required"
  else
    echo "No existing tags, first build"
  fi

  # 4. Calculate new version
  local new_patch=$((current_patch + 1))
  local new_version="${major}.${minor}.${new_patch}"

  # Validate semantic version format
  if [[ ! "$new_version" =~ ^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$ ]]; then
    echo "ERROR: Generated invalid version: $new_version"
    return 1
  fi

  # 5. Check for version conflict
  if skopeo inspect "docker://${image_repo}:${new_version}" &>/dev/null; then
    echo "ERROR: Version $new_version already exists on registry"
    echo "This indicates a race condition or logic error"
    return 1
  fi

  # 6. Return new version for tagging
  echo "$new_version"
  return 0
}

# Usage in build script
NEW_VERSION=$(auto_version_image "container/versions.yaml" \
  "quay.io/namespace/mc-rhel10" "mc-rhel10:latest")

if [[ $? -eq 0 && -n "$NEW_VERSION" ]]; then
  echo "Tagging and pushing: $NEW_VERSION"
  podman tag mc-rhel10:latest "mc-rhel10:${NEW_VERSION}"
  podman push "mc-rhel10:${NEW_VERSION}" "docker://quay.io/namespace/mc-rhel10:${NEW_VERSION}"
fi
```

### Validate Semantic Version Format
```bash
# Source: https://semver.org/ official regex, bash-compatible
# Validates version against semver 2.0.0 specification

validate_semver() {
  local version="$1"

  # Semver 2.0 regex components:
  # - (0|[1-9][0-9]*) = 0 or non-zero integer (no leading zeros)
  # - \. = literal dot
  # - $ = end anchor (no extra characters)
  local semver_regex='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'

  if [[ "$version" =~ $semver_regex ]]; then
    # Optional: extract components using BASH_REMATCH
    local major="${BASH_REMATCH[1]}"
    local minor="${BASH_REMATCH[2]}"
    local patch="${BASH_REMATCH[3]}"
    echo "Valid: $major.$minor.$patch"
    return 0
  else
    echo "Invalid semver format: $version"
    return 1
  fi
}

# Test cases
validate_semver "1.2.3"      # Valid
validate_semver "0.0.0"      # Valid (zero is allowed)
validate_semver "1.2"        # Invalid (missing patch)
validate_semver "01.2.3"     # Invalid (leading zero)
validate_semver "1.2.3.4"    # Invalid (extra component)
validate_semver "1.a.3"      # Invalid (non-integer)
validate_semver "1.2.3-beta" # Invalid (pre-release not supported)
```

### Update Minor Version (Manual User Action)
```bash
# Source: https://github.com/mikefarah/yq v4.52 docs
# User manually bumps minor version when adding new tools

update_minor_version() {
  local versions_file="${1:-container/versions.yaml}"
  local new_minor="$2"  # e.g., "1.3"

  # Validate input format
  if [[ ! "$new_minor" =~ ^[0-9]+\.[0-9]+$ ]]; then
    echo "ERROR: Invalid minor version format: $new_minor (expected x.y)"
    return 1
  fi

  # Read current version
  local current_version
  current_version=$(yq '.image.version' "$versions_file")

  echo "Updating minor version: $current_version → $new_minor"
  echo "Next build will create ${new_minor}.0"

  # Update in-place
  yq -i ".image.version = \"$new_minor\"" "$versions_file"

  # Verify update
  local updated_version
  updated_version=$(yq '.image.version' "$versions_file")

  if [[ "$updated_version" == "$new_minor" ]]; then
    echo "✓ versions.yaml updated successfully"
    return 0
  else
    echo "ERROR: Update failed, versions.yaml shows: $updated_version"
    return 1
  fi
}

# Manual workflow example
# 1. User adds new tool (oc CLI) to Containerfile
# 2. User updates minor version: update_minor_version "container/versions.yaml" "1.3"
# 3. User commits versions.yaml change
# 4. Next build creates 1.3.0 (patch starts at 0 for new minor version)
```

### Find Next Patch Version from Registry
```bash
# Source: Phase 23 research (skopeo + sort -V)
# Returns next patch number, handles first build case

get_next_patch() {
  local image_repo="$1"        # quay.io/namespace/mc-rhel10
  local minor_version="$2"     # 1.2

  # Query registry for tags matching minor version
  local latest_tag
  latest_tag=$(skopeo list-tags "docker://${image_repo}" 2>/dev/null | \
    jq -r '.Tags[]' | \
    grep -E "^${minor_version}\.[0-9]+$" | \
    sort -V | \
    tail -1)

  if [[ -n "$latest_tag" ]]; then
    # Extract patch number
    IFS='.' read -r _ _ current_patch <<< "$latest_tag"
    local next_patch=$((current_patch + 1))
    echo "$next_patch"
  else
    # No tags found, start at 0
    echo "0"
  fi
}

# Usage
NEXT_PATCH=$(get_next_patch "quay.io/namespace/mc-rhel10" "1.2")
NEW_VERSION="1.2.${NEXT_PATCH}"
echo "Next version: $NEW_VERSION"

# Examples:
# Registry has: 1.2.17 → Returns: 18 → NEW_VERSION=1.2.18
# Registry has: 1.2.0  → Returns: 1  → NEW_VERSION=1.2.1
# Registry has: (none) → Returns: 0  → NEW_VERSION=1.2.0
```

### Check Version Conflict Before Push
```bash
# Source: Phase 23 research (skopeo inspect for existence)
# Prevents pushing version that already exists

check_version_conflict() {
  local image_repo="$1"  # quay.io/namespace/mc-rhel10
  local version="$2"     # 1.2.18

  echo "Checking for version conflict: $version"

  if skopeo inspect "docker://${image_repo}:${version}" &>/dev/null; then
    echo "ERROR: Version $version already exists on registry"
    echo "Possible causes:"
    echo "  - Race condition (another build pushed this version)"
    echo "  - Registry query failure (stale local state)"
    echo "  - Logic error (version calculation incorrect)"
    return 1  # Conflict detected
  else
    echo "✓ Version $version available for push"
    return 0  # No conflict
  fi
}

# Usage before push
NEW_VERSION="1.2.18"
if check_version_conflict "quay.io/namespace/mc-rhel10" "$NEW_VERSION"; then
  podman tag mc-rhel10:latest "mc-rhel10:${NEW_VERSION}"
  podman push "mc-rhel10:${NEW_VERSION}" "docker://quay.io/namespace/mc-rhel10:${NEW_VERSION}"
else
  echo "Push aborted due to version conflict"
  exit 1
fi
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Store full version (x.y.z) in config | Store minor (x.y), calculate patch from registry | 2024+ (GitOps adoption) | Eliminates merge conflicts, registry as source of truth |
| Git tag-based versioning | Digest-based change detection | 2023+ (reproducibility focus) | Content-driven versions, immune to comment changes |
| Manual version bumps | Automated bumping on digest diff | 2022+ (CI/CD maturity) | Prevents human error, enforces bump-on-change |
| sed/awk for YAML updates | yq with schema validation | 2020+ (yq v4 release) | Safe structure preservation, type handling |
| String comparison for versions | sort -V or semver tools | 2018+ (coreutils 8.30) | Correct 1.0.9 vs 1.0.10 ordering |

**Deprecated/outdated:**
- **Storing patch version in git:** Causes merge conflicts, use registry state instead
- **`[[ "$v1" > "$v2" ]]` for version comparison:** Lexical vs numeric, use sort -V
- **Manually incrementing version files:** Error-prone, use digest-based automation
- **Assuming file change = image change:** Layer caching makes this unreliable, use digest

**Emerging patterns (2025-2026):**
- **Renovate/Dependabot for digest updates:** Automated PRs when base image digests change
- **Semantic version + commit SHA tags:** e.g., v1.2.3-abc123f for traceability
- **Immutable tag policies:** Registry-enforced prevention of tag overwrites
- **Sigstore/Cosign integration:** Sign digest, not tag (tags are mutable)

## Open Questions

Things that couldn't be fully resolved:

1. **Race Condition Window**
   - What we know: Time gap between registry query and push allows simultaneous builds to conflict
   - What's unclear: Whether quay.io has atomic tag creation API, how often this occurs in practice
   - Recommendation: Detect conflict with check before push, fail fast, rely on developers coordinating (or CI queue serialization)

2. **Registry Query Failure Recovery**
   - What we know: Phase 24 CONTEXT.md specifies "fail hard" on registry query failure
   - What's unclear: Whether to retry on specific error types (timeout vs auth), how many retries
   - Recommendation: Use Phase 23 exponential backoff for transient errors, fail fast on auth/permission errors

3. **Minor Version Bump Enforcement**
   - What we know: VER-07 requires manual minor bump when adding tools, but no enforcement mechanism
   - What's unclear: Whether to add validation (e.g., detect new tools in versions.yaml, require minor bump)
   - Recommendation: Trust developer workflow for v2.0.3, consider validation in future milestone if issues arise

4. **Multi-Arch Version Synchronization**
   - What we know: Phase 22 is architecture-aware (amd64 for v2.0.3), Phase 25 may publish multi-arch
   - What's unclear: Whether to version amd64/arm64 separately (1.2.3-amd64) or unified (1.2.3 with manifest list)
   - Recommendation: Plan for unified versioning (1.2.3 points to manifest list), research in Phase 25

## Sources

### Primary (HIGH confidence)
- [Semantic Versioning 2.0.0 Specification](https://semver.org/) - Official spec for version format rules
- [yq Documentation](https://github.com/mikefarah/yq) - YAML manipulation tool (v4.52.2)
- [semver-tool](https://github.com/fsaintjacques/semver-tool) - Bash semver implementation (v3.4.0)
- [GNU Coreutils sort -V](https://www.gnu.org/software/coreutils/manual/html_node/Version-sort.html) - Version-aware sorting
- Phase 23 Research (skopeo, jq, registry query patterns) - Already verified in Phase 23

### Secondary (MEDIUM confidence)
- [Baeldung: Processing YAML with yq](https://www.baeldung.com/linux/yq-utility-processing-yaml) - yq usage patterns
- [Container Image Versioning Best Practices](https://container-registry.com/posts/container-image-versioning/) - Digest-based workflows
- [Red Hat: How to Name, Version, and Reference Container Images](https://developers.redhat.com/articles/2025/01/28/how-name-version-and-reference-container-images) - 2025 best practices
- [Chainguard: Considerations for Keeping Containers Up to Date](https://edu.chainguard.dev/chainguard/chainguard-images/staying-secure/updating-images/considerations-for-image-updates/) - Digest-based automation
- [Microsoft: Image Tag Best Practices](https://learn.microsoft.com/en-us/azure/container-registry/container-registry-image-tag-version) - Version conflict prevention

### Tertiary (LOW confidence - validation needed)
- [Automating Docker Image Versioning with GitHub Actions](https://dev.to/msrabon/automating-docker-image-versioning-build-push-and-scanning-using-github-actions-388n) - CI/CD patterns
- [GitLab Semantic Versioning](https://github.com/mrooding/gitlab-semantic-versioning) - Label-based bumping
- [Quay.io Image Already Exists](https://docs.quay.io/issues/image-exists.html) - Conflict error handling

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - yq, bash regex, sort -V are mature, stable tools with official documentation
- Architecture (versioning model): HIGH - Registry-as-source-of-truth pattern is industry standard (Chainguard, Red Hat)
- Pitfalls: HIGH - Semver spec is authoritative, Phase 23 research validated registry patterns
- Integration flow: MEDIUM - Digest-based bump logic is sound, but race condition handling needs testing

**Research date:** 2026-02-10
**Valid until:** 2026-04-10 (60 days - semver and tooling are stable, container practices evolve slowly)

**Key uncertainties requiring validation during planning:**
- Race condition frequency and mitigation (conflict detection sufficient vs need distributed lock)
- Whether to implement semver-tool or hand-rolled bash (dependency vs simplicity tradeoff)
- Exponential backoff for registry queries (reuse Phase 23 retry logic vs separate implementation)
- Error message verbosity (how much diagnostic info for version conflict failures)
