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
SEMVER_REGEX='^[0-9]+\.[0-9]+\.[0-9]+$'

# Registry configuration
REGISTRY_REPO="${REGISTRY_REPO:-quay.io/dsquirre/mc-rhel10}"

# Version variables (populated by extraction function)
IMAGE_VERSION=""
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
  # Extract image and MC versions
  IMAGE_VERSION=$(yq '.image.version' "$VERSIONS_FILE")
  MC_VERSION=$(yq '.mc.version' "$VERSIONS_FILE")

  # Validate image version extraction
  if [[ -z "$IMAGE_VERSION" ]] || [[ "$IMAGE_VERSION" == "null" ]]; then
    echo "Error: Could not read image.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  # Validate MC version extraction
  if [[ -z "$MC_VERSION" ]] || [[ "$MC_VERSION" == "null" ]]; then
    echo "Error: Could not read mc.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  # Validate image version format
  if [[ ! "$IMAGE_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "Error: Invalid image version format: $IMAGE_VERSION (expected x.y.z)" >&2
    exit 1
  fi

  # Validate MC version format
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
# Build Orchestration
#------------------------------------------------------------------------------
perform_build() {
  # Reset timer
  SECONDS=0

  # Define image tags
  local image_tag="mc-rhel10:${IMAGE_VERSION}"
  local latest_tag="mc-rhel10:latest"

  # Build command array
  local build_cmd=(
    podman build
    --file container/Containerfile
    --tag "$image_tag"
    --tag "$latest_tag"
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
    echo "[DRY-RUN] Would execute:"
    printf '%s ' "${build_cmd[@]}"
    printf '\n'
    echo ""
    echo "[DRY-RUN] Parsed versions:"
    echo "  Image version: $IMAGE_VERSION"
    echo "  MC CLI version: $MC_VERSION"
    for tool_name in "${!TOOL_VERSIONS[@]}"; do
      echo "  ${tool_name} version: ${TOOL_VERSIONS[$tool_name]}"
    done
    echo ""
    echo "[DRY-RUN] Would create tags:"
    echo "  - $image_tag"
    echo "  - $latest_tag"
    exit 0
  else
    # Execute build
    "${build_cmd[@]}"

    # Calculate elapsed time
    local elapsed=$SECONDS

    # Success message
    echo "Build completed successfully in ${elapsed}s"
    echo "Created tags:"
    echo "  - $image_tag"
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
echo "Reading versions.yaml..."
extract_and_validate_versions

# Detect architecture
detect_architecture

# Show build info
echo "Starting build..."
echo "  Image version: $IMAGE_VERSION"
echo "  MC CLI version: $MC_VERSION"

# Perform build
perform_build
