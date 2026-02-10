#!/usr/bin/env bash
#
# build-container.sh - Automated container build with version injection
#
# Reads versions.yaml, validates all version numbers, and builds the MC container
# image with proper version injection via --build-arg flags.
#
# Usage: ./build-container.sh [OPTIONS]
#   --dry-run    Preview build without executing
#   --verbose    Show detailed build output
#   --help       Display usage information

set -euo pipefail

# Global flags
DRY_RUN=false
VERBOSE=false
JSON_OUTPUT=false

# File paths
VERSIONS_FILE="container/versions.yaml"
SEMVER_REGEX='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$'
MINOR_VERSION_REGEX='^[0-9]+\.[0-9]+$'

# Registry configuration
REGISTRY_REPO="${REGISTRY_REPO:-quay.io/dsquirre/mc-rhel10}"

# Version variables (populated by extraction function)
IMAGE_VERSION=""        # Full semantic version (x.y.z) calculated at build time
MINOR_VERSION=""        # Minor version (x.y) from versions.yaml
MC_VERSION=""
declare -A TOOL_VERSIONS

#------------------------------------------------------------------------------
# Usage/Help Function
#------------------------------------------------------------------------------
show_usage() {
  cat << 'EOF'
Usage: build-container.sh [OPTIONS]

Build MC container image with version injection from versions.yaml

OPTIONS:
  --dry-run           Preview build without executing (validation only)
  --verbose           Show detailed build output
  --json              Output results in JSON format for CI/CD
  --registry REPO     Override registry repository (default: quay.io/dsquirre/mc-rhel10)
  --help              Display this help message

EXAMPLES:
  # Normal build
  ./build-container.sh

  # Preview build without executing
  ./build-container.sh --dry-run

  # Build with detailed output
  ./build-container.sh --verbose

  # Query different registry
  ./build-container.sh --registry quay.io/myorg/myimage --dry-run

  # Machine-readable JSON output
  ./build-container.sh --json

REQUIREMENTS:
  - podman (running machine on macOS/Windows)
  - yq (mikefarah/yq Go version)
  - skopeo (for registry queries)
  - jq (for JSON parsing)
  - container/versions.yaml file

OUTPUT:
  Creates two image tags:
  - mc-rhel10:<version> (from versions.yaml)
  - mc-rhel10:latest
EOF
}

#------------------------------------------------------------------------------
# Semantic Version Validation
#------------------------------------------------------------------------------
validate_semver() {
  local version="$1"

  # Semver 2.0.0 specification regex:
  # - (0|[1-9][0-9]*) = 0 or non-zero integer without leading zeros
  # - Must have all three components: major.minor.patch
  if [[ "$version" =~ $SEMVER_REGEX ]]; then
    return 0  # valid
  else
    return 1  # invalid
  fi
}

#------------------------------------------------------------------------------
# Preflight Validation
#------------------------------------------------------------------------------
preflight_checks() {
  local failed=false

  # Check yq (mikefarah/yq - Go version required)
  if ! command -v yq &> /dev/null; then
    echo "Error: yq is not installed" >&2
    echo "Install from: https://github.com/mikefarah/yq" >&2
    failed=true
  else
    # Verify correct yq version (Go, not Python)
    YQ_VERSION=$(yq --version 2>&1)
    if [[ ! "$YQ_VERSION" =~ "mikefarah/yq" ]]; then
      echo "Error: Wrong yq version (need mikefarah/yq, found $YQ_VERSION)" >&2
      echo "Install from: https://github.com/mikefarah/yq" >&2
      failed=true
    fi
  fi

  # Check skopeo
  if ! command -v skopeo &> /dev/null; then
    echo "Error: skopeo is not installed" >&2
    echo "Install from: https://github.com/containers/skopeo" >&2
    echo "  macOS: brew install skopeo" >&2
    echo "  Linux: dnf install skopeo (RHEL/Fedora) or apt install skopeo (Debian/Ubuntu)" >&2
    failed=true
  fi

  # Check jq
  if ! command -v jq &> /dev/null; then
    echo "Error: jq is not installed" >&2
    echo "Install from: https://jqlang.org" >&2
    echo "  macOS: brew install jq" >&2
    echo "  Linux: dnf install jq or apt install jq" >&2
    failed=true
  fi

  # Check podman
  if ! command -v podman &> /dev/null; then
    echo "Error: podman is not installed" >&2
    failed=true
  fi

  # Check podman machine status (macOS only)
  if [[ "$(uname)" == "Darwin" ]]; then
    MACHINE_STATE=$(podman machine inspect --format '{{.State}}' 2>/dev/null || echo "none")
    if [[ "$MACHINE_STATE" != "running" ]]; then
      echo "Error: Podman machine is not running" >&2
      echo "Start it with: podman machine start" >&2
      failed=true
    fi
  fi

  # Check versions.yaml exists
  if [[ ! -f "$VERSIONS_FILE" ]]; then
    echo "Error: $VERSIONS_FILE not found" >&2
    failed=true
  fi

  if [[ "$failed" == "true" ]]; then
    exit 1
  fi
}

#------------------------------------------------------------------------------
# Version Extraction and Validation
#------------------------------------------------------------------------------
extract_and_validate_versions() {
  # Extract minor version from versions.yaml (x.y format)
  MINOR_VERSION=$(yq '.image.version' "$VERSIONS_FILE")
  MC_VERSION=$(yq '.mc.version' "$VERSIONS_FILE")

  # Validate minor version extraction
  if [[ -z "$MINOR_VERSION" ]] || [[ "$MINOR_VERSION" == "null" ]]; then
    echo "Error: Could not read image.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  # Validate MC version extraction
  if [[ -z "$MC_VERSION" ]] || [[ "$MC_VERSION" == "null" ]]; then
    echo "Error: Could not read mc.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  # Validate minor version format (x.y)
  if [[ ! "$MINOR_VERSION" =~ $MINOR_VERSION_REGEX ]]; then
    echo "Error: Invalid image version format: $MINOR_VERSION (expected x.y, not x.y.z)" >&2
    echo "Note: Patch version is auto-calculated from registry state" >&2
    exit 1
  fi

  # Validate MC version format (full semantic version)
  if [[ ! "$MC_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "Error: Invalid MC version format: $MC_VERSION (expected x.y.z)" >&2
    exit 1
  fi

  # Extract all tool versions
  # Get all tool names under .tools
  TOOL_NAMES=$(yq '.tools | keys | .[]' "$VERSIONS_FILE")

  # For each tool, extract version and validate
  while IFS= read -r tool_name; do
    # Extract version for this tool
    tool_version=$(yq ".tools.${tool_name}.version" "$VERSIONS_FILE")

    if [[ -z "$tool_version" ]] || [[ "$tool_version" == "null" ]]; then
      echo "Error: No version found for tool: $tool_name" >&2
      exit 1
    fi

    # Validate tool version format
    if [[ ! "$tool_version" =~ $SEMVER_REGEX ]]; then
      echo "Error: Invalid ${tool_name} version format: $tool_version (expected x.y.z)" >&2
      exit 1
    fi

    # Store in associative array
    TOOL_VERSIONS["$tool_name"]="$tool_version"
  done <<< "$TOOL_NAMES"
}

#------------------------------------------------------------------------------
# Registry Query Functions
#------------------------------------------------------------------------------

# Query registry for latest semantic version tag
# Returns: highest semantic version, or empty string if no versions published
query_latest_registry_version() {
  local max_attempts=5
  local base_delay=1
  local attempt=1

  while [[ $attempt -le $max_attempts ]]; do
    # Try to list tags from registry
    local response
    local exit_code

    response=$(skopeo list-tags "docker://${REGISTRY_REPO}" 2>&1) || exit_code=$?

    if [[ -z "${exit_code:-}" ]]; then
      # Success - parse tags
      local latest_version
      latest_version=$(echo "$response" | \
        jq -r '.Tags[]' 2>/dev/null | \
        grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | \
        sort -V | \
        tail -1)

      echo "${latest_version:-}"
      return 0

    elif [[ "$response" =~ "429" ]] || [[ "$response" =~ "Too Many Requests" ]]; then
      # Rate limited - check for retry-after header or use exponential backoff
      local delay=$((base_delay * (1 << (attempt - 1))))
      local jitter=$((RANDOM % (delay / 2 + 1)))
      local total_delay=$((delay + jitter))

      if [[ "$VERBOSE" == "true" ]]; then
        echo "Rate limited by registry, retrying in ${total_delay}s (attempt $attempt/$max_attempts)..." >&2
      fi

      sleep "$total_delay"
      ((attempt++))

    elif [[ "$response" =~ "unauthorized" ]] || [[ "$response" =~ "authentication required" ]]; then
      # Authentication failure - fail immediately
      echo "Error: Authentication failed for registry $REGISTRY_REPO" >&2
      echo "Run: podman login quay.io" >&2
      return 1

    else
      # Other error - fail
      echo "Error: Failed to query registry: $response" >&2
      return 1
    fi
  done

  # Max retries exceeded
  echo "Error: Max retries exceeded querying registry" >&2
  return 1
}

# Check if specific version exists on registry
# Args: version (e.g., "1.0.5")
# Returns: 0 if exists, 1 if not found
check_version_exists() {
  local version="$1"

  if skopeo inspect "docker://${REGISTRY_REPO}:${version}" &>/dev/null; then
    return 0
  else
    return 1
  fi
}

# Get manifest digest for specific version
# Args: version (e.g., "1.0.5")
# Returns: digest string (sha256:...) or empty if version not found
get_registry_digest() {
  local version="$1"

  local digest
  digest=$(skopeo inspect "docker://${REGISTRY_REPO}:${version}" 2>/dev/null | \
    jq -r '.Digest // empty')

  echo "${digest:-}"
}

# Compare local build with registry
# Returns: 0 if match, 1 if differ
compare_with_registry() {
  local version="$1"
  local local_digest="$2"

  # Get registry digest
  local registry_digest
  registry_digest=$(get_registry_digest "$version")

  if [[ -z "$registry_digest" ]]; then
    # Version not found on registry
    return 1
  fi

  # Compare digests
  if [[ "$local_digest" == "$registry_digest" ]]; then
    return 0
  else
    return 1
  fi
}

# Find latest patch version for given minor version
# Args: minor_version (e.g., "1.0")
# Returns: patch number (e.g., 17) or -1 if no tags found
find_latest_patch() {
  local minor_version="$1"

  # Query registry for all tags matching x.y.z pattern with our minor version
  local latest_tag
  latest_tag=$(skopeo list-tags "docker://${REGISTRY_REPO}" 2>/dev/null | \
    jq -r '.Tags[]' 2>/dev/null | \
    grep -E "^${minor_version}\.[0-9]+$" | \
    sort -V | \
    tail -1)

  if [[ -n "$latest_tag" ]]; then
    # Extract patch number from x.y.z
    local patch
    IFS='.' read -r _ _ patch <<< "$latest_tag"
    echo "$patch"
  else
    # No tags found for this minor version
    echo "-1"
  fi
}

#------------------------------------------------------------------------------
# Architecture Detection
#------------------------------------------------------------------------------
detect_architecture() {
  local arch
  arch=$(uname -m)

  case "$arch" in
    x86_64)
      ARCH="amd64"
      ;;
    aarch64|arm64)
      ARCH="arm64"
      ;;
    *)
      echo "Error: Unsupported architecture: $arch" >&2
      exit 1
      ;;
  esac

  # Architecture detected and mapped for build
  # Both amd64 and arm64 are supported by the Containerfile
}

#------------------------------------------------------------------------------
# Output Formatting
#------------------------------------------------------------------------------

# Output results in JSON format
output_json() {
  local new_version="$1"
  local bumped="$2"
  local pushed="$3"
  local latest_registry="$4"

  cat <<EOF
{
  "minor_version": "$MINOR_VERSION",
  "new_version": ${new_version:+"\"$new_version\""}${new_version:-null},
  "bumped": $bumped,
  "pushed": $pushed,
  "latest_registry_version": ${latest_registry:+"\"$latest_registry\""}${latest_registry:-null},
  "mc_version": "$MC_VERSION",
  "tools": {
$(for tool_name in "${!TOOL_VERSIONS[@]}"; do
    echo "    \"$tool_name\": \"${TOOL_VERSIONS[$tool_name]}\""
  done | paste -sd ',' -)
  }
}
EOF
}

#------------------------------------------------------------------------------
# Build Orchestration
#------------------------------------------------------------------------------
auto_version_and_push() {
  # Reset timer
  SECONDS=0

  # Parse minor version into components
  IFS='.' read -r MAJOR MINOR <<< "$MINOR_VERSION"

  # Query registry for latest patch version (skip in dry-run)
  local current_patch=-1
  local latest_registry_tag=""

  if [[ "$DRY_RUN" != "true" ]]; then
    if [[ "$JSON_OUTPUT" != "true" ]]; then
      echo "Querying registry for latest ${MINOR_VERSION}.* version..."
    fi

    current_patch=$(find_latest_patch "$MINOR_VERSION")

    if [[ "$current_patch" -ge 0 ]]; then
      latest_registry_tag="${MINOR_VERSION}.${current_patch}"
      if [[ "$JSON_OUTPUT" != "true" ]]; then
        echo "  Latest on registry: $latest_registry_tag"
      fi
    else
      if [[ "$JSON_OUTPUT" != "true" ]]; then
        echo "  Latest on registry: No ${MINOR_VERSION}.* tags found (first build)"
      fi
    fi
  fi

  # Build image with temporary tag
  local temp_tag="mc-rhel10:temp"

  if [[ "$JSON_OUTPUT" != "true" ]]; then
    echo "Building image..."
  fi

  # Build command array
  local build_cmd=(
    podman build
    --file container/Containerfile
    --tag "$temp_tag"
  )

  # Add MC_VERSION build arg
  build_cmd+=("--build-arg" "MC_VERSION=$MC_VERSION")

  # Add tool version build args
  for tool_name in "${!TOOL_VERSIONS[@]}"; do
    # Convert tool name to uppercase for ARG name (ocm -> OCM_VERSION)
    local arg_name
    arg_name=$(echo "${tool_name}" | tr '[:lower:]' '[:upper:]')_VERSION
    build_cmd+=("--build-arg" "${arg_name}=${TOOL_VERSIONS[$tool_name]}")
  done

  # Add context path
  build_cmd+=(.)

  # Control verbosity
  if [[ "$VERBOSE" != "true" ]]; then
    build_cmd+=(--quiet)
  fi

  # Dry-run or execute
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] Would query registry for latest ${MINOR_VERSION}.* version"
    echo ""
    echo "[DRY-RUN] Would execute build:"
    printf '%s ' "${build_cmd[@]}"
    printf '\n'
    echo ""
    echo "[DRY-RUN] Parsed versions:"
    echo "  Minor version: $MINOR_VERSION"
    echo "  MC CLI version: $MC_VERSION"
    for tool_name in "${!TOOL_VERSIONS[@]}"; do
      echo "  ${tool_name} version: ${TOOL_VERSIONS[$tool_name]}"
    done
    echo ""
    echo "[DRY-RUN] Would compare digest with registry"
    echo "[DRY-RUN] If digest differs:"
    echo "  Would bump to: ${MINOR_VERSION}.<patch+1>"
    echo "  Would tag: mc-rhel10:${MINOR_VERSION}.<patch+1> and mc-rhel10:latest"
    echo "  Would push to: $REGISTRY_REPO"
    exit 0
  fi

  # Execute build
  "${build_cmd[@]}"

  # Get local image digest
  local local_digest
  local_digest=$(podman inspect "$temp_tag" 2>/dev/null | jq -r '.[0].Digest')

  if [[ -z "$local_digest" ]]; then
    echo "Error: Failed to get digest for built image" >&2
    exit 1
  fi

  # Compare digests if registry version exists
  local bumped=false
  local pushed=false

  if [[ "$current_patch" -ge 0 ]]; then
    # Get registry digest for comparison
    local registry_digest
    registry_digest=$(get_registry_digest "$latest_registry_tag")

    if [[ "$local_digest" == "$registry_digest" ]]; then
      # Digests match - no-op
      local elapsed=$SECONDS

      if [[ "$JSON_OUTPUT" == "true" ]]; then
        output_json "" false false "$latest_registry_tag"
      else
        echo "Image unchanged (digest match), skipping bump and push"
        echo "Build completed in ${elapsed}s (no-op)"
      fi
      return 0
    fi

    if [[ "$JSON_OUTPUT" != "true" ]]; then
      echo "Image changed (digest mismatch), bumping version..."
    fi
  else
    if [[ "$JSON_OUTPUT" != "true" ]]; then
      echo "First build for ${MINOR_VERSION}.*, creating initial version..."
    fi
  fi

  # Calculate new version
  local new_patch=$((current_patch + 1))
  IMAGE_VERSION="${MAJOR}.${MINOR}.${new_patch}"

  # Validate semantic version format
  if ! validate_semver "$IMAGE_VERSION"; then
    echo "Error: Generated invalid version: $IMAGE_VERSION" >&2
    exit 1
  fi

  # Check for version conflict
  if check_version_exists "$IMAGE_VERSION"; then
    echo "Error: Version $IMAGE_VERSION already exists on registry" >&2
    echo "This indicates a race condition or logic error" >&2
    exit 1
  fi

  # Tag image with version and latest
  local version_tag="mc-rhel10:${IMAGE_VERSION}"
  local latest_tag="mc-rhel10:latest"

  podman tag "$temp_tag" "$version_tag"
  podman tag "$temp_tag" "$latest_tag"

  bumped=true

  # Push to registry
  if [[ "$JSON_OUTPUT" != "true" ]]; then
    echo "Pushing $IMAGE_VERSION to registry..."
  fi

  podman push "$version_tag" "docker://${REGISTRY_REPO}:${IMAGE_VERSION}"
  podman push "$latest_tag" "docker://${REGISTRY_REPO}:latest"

  pushed=true

  # Calculate elapsed time
  local elapsed=$SECONDS

  # Output results
  if [[ "$JSON_OUTPUT" == "true" ]]; then
    output_json "$IMAGE_VERSION" true true "$latest_registry_tag"
  else
    echo "Published $IMAGE_VERSION to $REGISTRY_REPO"
    echo "Build and push completed in ${elapsed}s"
    echo "Created tags:"
    echo "  - $version_tag"
    echo "  - $latest_tag"
  fi
}

#------------------------------------------------------------------------------
# Argument Parsing
#------------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case $1 in
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
      shift
      ;;
    --registry)
      if [[ -z "${2:-}" ]]; then
        echo "Error: --registry requires a value" >&2
        exit 1
      fi
      REGISTRY_REPO="$2"
      shift 2
      ;;
    --help)
      show_usage
      exit 0
      ;;
    *)
      echo "Error: Unknown option: $1" >&2
      echo "Run with --help for usage information" >&2
      exit 1
      ;;
  esac
done

#------------------------------------------------------------------------------
# Main Execution
#------------------------------------------------------------------------------

# Preflight checks
preflight_checks

# Read and validate versions
if [[ "$JSON_OUTPUT" != "true" ]]; then
  echo "Reading versions.yaml..."
fi
extract_and_validate_versions

# Detect architecture
detect_architecture

# Execute auto-versioning build and push workflow
auto_version_and_push
