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

# File paths
VERSIONS_FILE="container/versions.yaml"
SEMVER_REGEX='^[0-9]+\.[0-9]+\.[0-9]+$'

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
  --dry-run     Preview build without executing (validation only)
  --verbose     Show detailed build output
  --help        Display this help message

EXAMPLES:
  # Normal build
  ./build-container.sh

  # Preview build without executing
  ./build-container.sh --dry-run

  # Build with detailed output
  ./build-container.sh --verbose

REQUIREMENTS:
  - podman (running machine on macOS/Windows)
  - yq (mikefarah/yq Go version)
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
