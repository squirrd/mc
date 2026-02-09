# Phase 22: Build Automation Core - Research

**Researched:** 2026-02-09
**Domain:** Shell script automation for container builds
**Confidence:** HIGH

## Summary

Build automation for containerized applications in 2026 relies on proven shell scripting patterns combined with specialized tooling. The standard approach uses bash scripts with yq for YAML parsing, podman build with --build-arg for version injection, and established error handling patterns (set -euo pipefail). Modern build scripts follow fail-fast principles with preflight validation, dry-run capabilities for safe previews, and CI-friendly output.

The research validated that all required capabilities exist in standard tooling: yq is the de facto YAML parser for shell scripts, podman build natively supports build arguments and multi-architecture builds, and bash provides robust mechanisms for option parsing, error handling, and command validation. Container tagging best practices recommend both versioned tags (for production immutability) and :latest tags (for development convenience).

**Primary recommendation:** Use bash script with manual while-loop argument parsing for long flags (--dry-run, --verbose), yq for YAML extraction, command -v for dependency checks, set -euo pipefail for fail-fast error handling, and podman build with multiple --build-arg flags for version injection.

## Standard Stack

The established libraries/tools for build automation scripts:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| bash | 4.0+ | Shell scripting runtime | Universal on Linux/macOS, built-in error handling, POSIX-compatible |
| yq | 4.x | YAML parsing for shell scripts | Lightweight, portable, jq-like syntax, handles nested YAML natively |
| podman | 4.0+ | Container build engine | Daemonless, rootless, Docker-compatible CLI, native multi-arch support |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ShellCheck | latest | Static analysis for shell scripts | Development/CI linting to catch common mistakes |
| jq | 1.6+ | JSON parsing | When podman outputs JSON (machine inspect, etc.) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yq | jq + yq Python wrapper | Python yq wraps jq, Go yq is faster and single binary |
| Manual parsing | getopt (external) | getopt handles complex option parsing but requires external dependency |
| Manual parsing | getopts (builtin) | getopts is builtin but only supports short options (-v), not long (--verbose) |

**Installation:**
```bash
# yq (mikefarah/yq - Go version, recommended)
# macOS
brew install yq

# Linux - download binary from GitHub releases
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/bin/yq
chmod +x /usr/bin/yq

# podman - typically already installed for container development
# ShellCheck - for development linting
brew install shellcheck  # macOS
dnf install ShellCheck   # RHEL/Fedora
```

## Architecture Patterns

### Recommended Project Structure
```
container/
├── build-container.sh   # Build automation script (this phase)
├── versions.yaml        # Version definitions (Phase 21)
├── Containerfile        # Multi-stage container definition (Phase 20)
└── entrypoint.sh        # Container entrypoint (Phase 20)
```

### Pattern 1: Manual While-Loop Argument Parsing
**What:** Parse long-form flags (--dry-run, --verbose, --help) using while loop with case statement
**When to use:** When you need long option names that getopts (builtin) cannot handle
**Example:**
```bash
# Source: Manual parsing pattern from bash argument parsing best practices
# https://medium.com/@wujido20/handling-flags-in-bash-scripts-4b06b4d0ed04

DRY_RUN=false
VERBOSE=false

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
      exit 1
      ;;
  esac
done
```

### Pattern 2: Fail-Fast Error Handling
**What:** Use set -euo pipefail to exit immediately on errors, undefined variables, or pipeline failures
**When to use:** All build automation scripts where failures should halt execution immediately
**Example:**
```bash
# Source: Bash error handling best practices
# https://www.howtogeek.com/bash-error-handling-patterns-i-use-in-every-script/

#!/usr/bin/env bash
set -euo pipefail

# set -e: Exit on any command failure
# set -u: Exit on undefined variable usage
# set -o pipefail: Pipeline fails if ANY command fails (not just last)
```

### Pattern 3: Preflight Validation
**What:** Check all dependencies and preconditions before starting main logic
**When to use:** Build scripts that depend on external tools (podman, yq) or running services
**Example:**
```bash
# Source: Command existence checking best practices
# https://www.baeldung.com/linux/bash-script-check-program-exists

# Check if command exists using command -v (most portable)
if ! command -v podman &> /dev/null; then
  echo "Error: podman is not installed" >&2
  exit 1
fi

# Check podman machine status (macOS/Windows specific)
if [[ "$(uname)" == "Darwin" ]]; then
  PODMAN_STATUS=$(podman machine inspect --format '{{.State}}' 2>/dev/null || echo "none")
  if [[ "$PODMAN_STATUS" != "running" ]]; then
    echo "Error: Podman machine is not running. Start with: podman machine start" >&2
    exit 1
  fi
fi
```

### Pattern 4: YAML Parsing with yq
**What:** Extract nested YAML values using jq-like syntax with yq
**When to use:** Reading structured configuration from YAML files in shell scripts
**Example:**
```bash
# Source: yq official documentation
# https://mikefarah.gitbook.io/yq

VERSIONS_FILE="container/versions.yaml"

# Extract simple values using dot notation
IMAGE_VERSION=$(yq '.image.version' "$VERSIONS_FILE")
MC_VERSION=$(yq '.mc.version' "$VERSIONS_FILE")

# Extract nested tool version
OCM_VERSION=$(yq '.tools.ocm.version' "$VERSIONS_FILE")

# Validate extraction succeeded (yq returns "null" if key missing)
if [[ "$IMAGE_VERSION" == "null" ]] || [[ -z "$IMAGE_VERSION" ]]; then
  echo "Error: Could not read image.version from $VERSIONS_FILE" >&2
  exit 1
fi
```

### Pattern 5: Dry-Run Mode Implementation
**What:** Preview actions without executing them using conditional execution based on flag
**When to use:** Scripts that modify state (builds, deployments) where users need safe preview
**Example:**
```bash
# Source: Bash dry-run patterns
# https://wozniak.ca/blog/drafts/bash-metaprogramming.html

DRY_RUN=false

# Function to execute or preview commands
run_cmd() {
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] Would execute: $*"
  else
    "$@"
  fi
}

# Usage
run_cmd podman build --tag "mc-rhel10:${IMAGE_VERSION}" .
```

### Pattern 6: Build Time Measurement
**What:** Track and report script execution time using bash SECONDS variable
**When to use:** Build scripts where execution time is valuable feedback
**Example:**
```bash
# Source: Bash time measurement patterns
# https://www.baeldung.com/linux/bash-calculate-time-elapsed

# Reset SECONDS at start
SECONDS=0

# ... build operations ...

# Report elapsed time
ELAPSED=$SECONDS
echo "Build completed in ${ELAPSED}s"
```

### Pattern 7: Podman Build with Multiple Build Args
**What:** Pass multiple version variables to podman build using --build-arg flags
**When to use:** Container builds that need version injection from external configuration
**Example:**
```bash
# Source: podman build official documentation
# https://docs.podman.io/en/latest/markdown/podman-build.1.html

# Extract versions from YAML
OCM_VERSION=$(yq '.tools.ocm.version' versions.yaml)

# Build with version injection
podman build \
  --file container/Containerfile \
  --build-arg "OCM_VERSION=${OCM_VERSION}" \
  --tag "mc-rhel10:${IMAGE_VERSION}" \
  --tag "mc-rhel10:latest" \
  .
```

### Pattern 8: Multi-Tag Container Images
**What:** Tag built image with both semantic version and :latest tag
**When to use:** All container builds - versioned for production, :latest for convenience
**Example:**
```bash
# Source: Container image tagging best practices
# https://container-registry.com/posts/container-image-versioning/

# Build with primary version tag
podman build --tag "mc-rhel10:${IMAGE_VERSION}" .

# Add :latest tag to same image (no rebuild)
podman tag "mc-rhel10:${IMAGE_VERSION}" "mc-rhel10:latest"

# Alternative: Multi-tag in single build (podman supports multiple --tag flags)
podman build \
  --tag "mc-rhel10:${IMAGE_VERSION}" \
  --tag "mc-rhel10:latest" \
  .
```

### Pattern 9: Semantic Version Validation
**What:** Validate version strings match x.y.z format using bash regex
**When to use:** Scripts that consume version numbers from external sources
**Example:**
```bash
# Source: Semantic versioning regex patterns
# https://ihateregex.io/expr/semver/

# Simple semver validation (x.y.z only, no prerelease/metadata)
SEMVER_REGEX='^[0-9]+\.[0-9]+\.[0-9]+$'

validate_semver() {
  local version=$1
  if [[ ! "$version" =~ $SEMVER_REGEX ]]; then
    echo "Error: Invalid semantic version: $version (expected x.y.z)" >&2
    return 1
  fi
}

# Usage
validate_semver "$IMAGE_VERSION" || exit 1
```

### Pattern 10: CI-Friendly Output
**What:** Avoid ANSI color codes and special characters for clean CI/CD logs
**When to use:** Scripts that will run in CI pipelines or be redirected to files
**Example:**
```bash
# Source: NO_COLOR standard
# https://no-color.org/

# Respect NO_COLOR environment variable (CI often sets this)
# Don't use tput colors, ANSI escape codes, or Unicode box characters

# Good: Plain text output
echo "Building container image mc-rhel10:${IMAGE_VERSION}"
echo "Build completed successfully"

# Avoid: Color codes (unless NO_COLOR is unset and terminal detected)
# echo -e "\033[32mBuild completed\033[0m"
```

### Anti-Patterns to Avoid

- **Using :latest only:** Production deployments need immutable version tags, not mutable :latest
- **Ignoring podman machine status:** On macOS/Windows, podman requires the VM to be running
- **Using getopts for long options:** getopts only handles short flags (-v), not long (--verbose)
- **Using which for command detection:** Prefer command -v (builtin, more reliable, POSIX)
- **Shell variable escaping in yq queries:** Use yq's strenv() function instead of shell variable interpolation
- **Relying only on set -e:** Explicitly check critical commands; set -e has edge cases
- **Hardcoding versions in build script:** Defeats purpose of versions.yaml single source of truth

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom awk/sed/grep patterns | yq (mikefarah/yq) | YAML has complex edge cases (multiline, quotes, anchors); yq handles all correctly |
| Long option parsing | Custom string manipulation | Manual while-loop with case | Well-established pattern; getopt has portability issues |
| Container tagging | Build twice for two tags | Multiple --tag flags or podman tag | Podman supports multi-tag natively; rebuilding wastes time |
| Version validation | String splitting logic | Regex pattern matching | Regex is declarative, handles edge cases (leading zeros, etc.) |
| Command existence | Parsing PATH manually | command -v builtin | Handles aliases, functions, builtins; command -v is POSIX standard |
| Exit code handling | Manual $? checks everywhere | set -euo pipefail + explicit checks | Fail-fast by default prevents cascading failures |
| Build time tracking | date arithmetic | SECONDS builtin variable | Automatic, no subprocess overhead, perfect for second-level precision |

**Key insight:** Shell scripting has 30+ years of established patterns. Modern tools (yq, ShellCheck) address historical pain points. Don't reinvent - use standard solutions and focus on domain logic.

## Common Pitfalls

### Pitfall 1: Podman Machine Not Running (macOS/Windows)
**What goes wrong:** Script fails with cryptic "cannot connect to podman socket" error
**Why it happens:** Podman on macOS/Windows requires a Linux VM (podman machine) to be running; unlike Docker Desktop, it doesn't auto-start
**How to avoid:** Add preflight check that verifies podman machine state before attempting build
**Warning signs:**
- Error: "unable to connect to Podman socket"
- Running on macOS or Windows
- podman machine ls shows machine in "stopped" state

```bash
# Detection and helpful error
if [[ "$(uname)" == "Darwin" ]] || [[ "$(uname)" =~ MINGW|MSYS ]]; then
  MACHINE_STATE=$(podman machine inspect --format '{{.State}}' 2>/dev/null || echo "none")
  if [[ "$MACHINE_STATE" != "running" ]]; then
    echo "Error: Podman machine is not running" >&2
    echo "Start it with: podman machine start" >&2
    exit 1
  fi
fi
```

### Pitfall 2: yq Version Confusion (Python vs Go)
**What goes wrong:** yq commands fail with syntax errors despite correct syntax
**Why it happens:** Two different tools named "yq" exist - Python wrapper around jq (kislyuk/yq) and standalone Go tool (mikefarah/yq) with incompatible syntax
**How to avoid:** Explicitly use mikefarah/yq (Go version), verify with yq --version (should show "mikefarah/yq version X.Y.Z")
**Warning signs:**
- yq command errors with "parse error" for valid syntax
- yq --version shows "jq-X.Y" instead of "mikefarah/yq version"
- Installing via pip instead of direct binary

```bash
# Verify correct yq version in preflight
YQ_VERSION=$(yq --version 2>&1)
if [[ ! "$YQ_VERSION" =~ "mikefarah/yq" ]]; then
  echo "Error: Wrong yq version detected" >&2
  echo "Expected: mikefarah/yq (Go implementation)" >&2
  echo "Found: $YQ_VERSION" >&2
  echo "Install from: https://github.com/mikefarah/yq" >&2
  exit 1
fi
```

### Pitfall 3: Unquoted Variable Expansion
**What goes wrong:** Variables with spaces or special characters cause word splitting, leading to incorrect command execution
**Why it happens:** Bash performs word splitting on unquoted variables; VERSION="1.0.0 alpha" becomes two arguments
**How to avoid:** Always quote variable expansions: "$VARIABLE" not $VARIABLE
**Warning signs:**
- Script works with simple versions but breaks with prerelease versions (1.0.0-beta)
- ShellCheck warnings: SC2086 "Double quote to prevent globbing and word splitting"

```bash
# Wrong - will break with spaces
podman build --tag mc-rhel10:$IMAGE_VERSION .

# Correct - quotes prevent word splitting
podman build --tag "mc-rhel10:${IMAGE_VERSION}" .
```

### Pitfall 4: Ignoring Pipeline Failures
**What goes wrong:** Critical errors in piped commands are silently ignored (yq parsing failure, grep no match)
**Why it happens:** By default, bash only checks exit code of last command in pipeline
**How to avoid:** Use set -o pipefail to fail on any pipeline command failure
**Warning signs:**
- Variables contain empty strings despite appearing to run successfully
- yq or grep failures don't stop script execution

```bash
# Without pipefail - failure in yq is ignored, INVALID_VAR is empty
INVALID_VAR=$(cat versions.yaml | yq '.nonexistent.key')
echo "Got: $INVALID_VAR"  # Prints empty string, no error

# With pipefail - script exits on yq failure
set -o pipefail
INVALID_VAR=$(cat versions.yaml | yq '.nonexistent.key')  # Exits here
```

### Pitfall 5: Missing versions.yaml Validation
**What goes wrong:** Build fails deep into process when podman tries to use invalid version
**Why it happens:** Script doesn't validate YAML parsing succeeded before using values
**How to avoid:** Check that extracted values are non-empty and match expected format immediately after extraction
**Warning signs:**
- yq returns "null" string for missing keys
- Build fails with cryptic error about invalid build argument
- Error appears in podman build output, not script validation

```bash
# Always validate immediately after extraction
IMAGE_VERSION=$(yq '.image.version' versions.yaml)
if [[ -z "$IMAGE_VERSION" ]] || [[ "$IMAGE_VERSION" == "null" ]]; then
  echo "Error: Could not read image.version from versions.yaml" >&2
  exit 1
fi

# Validate format
SEMVER_REGEX='^[0-9]+\.[0-9]+\.[0-9]+$'
if [[ ! "$IMAGE_VERSION" =~ $SEMVER_REGEX ]]; then
  echo "Error: Invalid version format: $IMAGE_VERSION (expected x.y.z)" >&2
  exit 1
fi
```

### Pitfall 6: Incorrect Architecture Detection
**What goes wrong:** Architecture mapping fails; script uses "x86_64" where podman/GitHub expect "amd64"
**Why it happens:** Different tools use different architecture naming conventions (x86_64 vs amd64, aarch64 vs arm64)
**How to avoid:** Map uname -m output to standardized names (amd64, arm64)
**Warning signs:**
- Downloads fail with 404 for URLs containing "x86_64"
- Container builds work locally but fail on different architectures

```bash
# Map uname output to standard names
ARCH=$(uname -m)
case "$ARCH" in
  x86_64)
    ARCH="amd64"
    ;;
  aarch64)
    ARCH="arm64"
    ;;
  *)
    echo "Error: Unsupported architecture: $ARCH" >&2
    exit 1
    ;;
esac
```

### Pitfall 7: Verbose Output Overload
**What goes wrong:** Default output is overwhelming (podman prints 50+ lines), making CI logs unreadable
**Why it happens:** podman build is verbose by default, showing every Containerfile step
**How to avoid:** Suppress podman output by default, show only with --verbose flag using --quiet or output redirection
**Warning signs:**
- CI logs are thousands of lines for simple build
- Important messages (version info, final tags) are buried in podman output

```bash
# Control verbosity
if [[ "$VERBOSE" == "true" ]]; then
  podman build --tag "mc-rhel10:${IMAGE_VERSION}" .
else
  # Suppress podman build output, show only errors
  podman build --quiet --tag "mc-rhel10:${IMAGE_VERSION}" . || {
    echo "Build failed. Re-run with --verbose for details" >&2
    exit 1
  }
fi
```

## Code Examples

Verified patterns from official sources and best practices:

### Complete Preflight Validation Function
```bash
# Source: Combined from multiple best practices sources
# Command validation: https://www.baeldung.com/linux/bash-script-check-program-exists
# Podman machine: https://docs.podman.io/en/latest/markdown/podman-machine-inspect.1.html

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
      failed=true
    fi
  fi

  # Check podman
  if ! command -v podman &> /dev/null; then
    echo "Error: podman is not installed" >&2
    failed=true
  fi

  # Check podman machine status (macOS/Windows only)
  if [[ "$(uname)" == "Darwin" ]]; then
    MACHINE_STATE=$(podman machine inspect --format '{{.State}}' 2>/dev/null || echo "none")
    if [[ "$MACHINE_STATE" != "running" ]]; then
      echo "Error: Podman machine is not running" >&2
      echo "Start it with: podman machine start" >&2
      failed=true
    fi
  fi

  # Check versions.yaml exists
  if [[ ! -f "container/versions.yaml" ]]; then
    echo "Error: container/versions.yaml not found" >&2
    failed=true
  fi

  if [[ "$failed" == "true" ]]; then
    exit 1
  fi
}
```

### Version Extraction and Validation
```bash
# Source: yq documentation + semver validation patterns
# https://mikefarah.gitbook.io/yq
# https://ihateregex.io/expr/semver/

VERSIONS_FILE="container/versions.yaml"
SEMVER_REGEX='^[0-9]+\.[0-9]+\.[0-9]+$'

extract_and_validate_versions() {
  # Extract versions
  IMAGE_VERSION=$(yq '.image.version' "$VERSIONS_FILE")
  MC_VERSION=$(yq '.mc.version' "$VERSIONS_FILE")

  # Validate extraction succeeded
  if [[ -z "$IMAGE_VERSION" ]] || [[ "$IMAGE_VERSION" == "null" ]]; then
    echo "Error: Could not read image.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  if [[ -z "$MC_VERSION" ]] || [[ "$MC_VERSION" == "null" ]]; then
    echo "Error: Could not read mc.version from $VERSIONS_FILE" >&2
    exit 1
  fi

  # Validate semantic versioning format
  if [[ ! "$IMAGE_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "Error: Invalid image version format: $IMAGE_VERSION (expected x.y.z)" >&2
    exit 1
  fi

  if [[ ! "$MC_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "Error: Invalid MC version format: $MC_VERSION (expected x.y.z)" >&2
    exit 1
  fi

  # Export for use in script
  export IMAGE_VERSION MC_VERSION
}
```

### Extract All Tool Versions from YAML
```bash
# Source: yq documentation on iterating nested structures
# https://mikefarah.gitbook.io/yq/usage/tips-and-tricks

# Extract all tool versions and build --build-arg flags
build_args=()

# Get all tool names under .tools
TOOL_NAMES=$(yq '.tools | keys | .[]' "$VERSIONS_FILE")

# For each tool, extract version and create build arg
while IFS= read -r tool_name; do
  # Extract version for this tool
  tool_version=$(yq ".tools.${tool_name}.version" "$VERSIONS_FILE")

  if [[ -z "$tool_version" ]] || [[ "$tool_version" == "null" ]]; then
    echo "Warning: No version found for tool: $tool_name" >&2
    continue
  fi

  # Convert to uppercase for ARG name (ocm -> OCM_VERSION)
  ARG_NAME=$(echo "${tool_name}" | tr '[:lower:]' '[:upper:]')_VERSION

  # Add to build args array
  build_args+=("--build-arg" "${ARG_NAME}=${tool_version}")
done <<< "$TOOL_NAMES"
```

### Complete Build Command with Dry-Run
```bash
# Source: Combining podman build patterns with dry-run implementation
# https://docs.podman.io/en/latest/markdown/podman-build.1.html
# https://wozniak.ca/blog/drafts/bash-metaprogramming.html

perform_build() {
  local image_tag="mc-rhel10:${IMAGE_VERSION}"
  local latest_tag="mc-rhel10:latest"

  # Build command with all arguments
  local build_cmd=(
    podman build
    --file container/Containerfile
    --tag "$image_tag"
    --tag "$latest_tag"
  )

  # Add all build args
  build_cmd+=("${build_args[@]}")

  # Add context path
  build_cmd+=(.)

  # Suppress output unless verbose
  if [[ "$VERBOSE" != "true" ]]; then
    build_cmd+=(--quiet)
  fi

  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY-RUN] Would execute:"
    printf '%s ' "${build_cmd[@]}"
    printf '\n'
    echo ""
    echo "[DRY-RUN] Would create tags:"
    echo "  - $image_tag"
    echo "  - $latest_tag"
  else
    # Execute build
    "${build_cmd[@]}"
  fi
}
```

### Usage/Help Display
```bash
# Source: Standard help pattern for command-line tools

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
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Docker build | Podman build | ~2020-2021 | Daemonless, rootless by default, better for CI/CD |
| Python yq (kislyuk) | Go yq (mikefarah) | ~2019-2020 | Single binary, faster, jq-like syntax, better shell integration |
| getopt external tool | Manual while-loop parsing | Ongoing | Avoids external dependency, better portability, handles long options |
| :latest only | Multi-tag (version + latest) | ~2018-2019 | Production immutability + dev convenience |
| echo debug output | ShellCheck linting | ~2015-present | Catch errors before runtime, enforce best practices |
| Manual $? checks | set -euo pipefail | ~2014-present | Fail-fast by default, fewer bugs from ignored errors |

**Deprecated/outdated:**
- **Python yq (kislyuk/yq):** Wrapper around jq with different syntax; mikefarah/yq is standalone and preferred for shell scripts
- **Using which for command detection:** Unreliable across platforms; command -v is POSIX standard and handles more cases
- **Docker-specific flags:** Some docker build flags don't exist in podman; use portable subset or check tool

## Open Questions

Things that couldn't be fully resolved:

1. **Podman build exit codes**
   - What we know: podman build returns non-zero on failure, zero on success
   - What's unclear: Specific exit codes for different failure types (missing file vs build error vs out of disk)
   - Recommendation: Rely on zero/non-zero only; parse stderr for specific error details if needed

2. **yq error handling for malformed YAML**
   - What we know: yq exits with non-zero code for parse errors; returns "null" string for missing keys
   - What's unclear: Whether yq distinguishes between malformed YAML vs missing keys in exit code
   - Recommendation: Use set -e to catch parse errors; explicitly check for "null" string for missing keys

3. **Optimal dry-run exit code**
   - What we know: Exit 0 (success) is simplest; some tools use specific codes for dry-run (e.g., 3)
   - What's unclear: Industry standard for dry-run mode exit codes in build scripts
   - Recommendation: Use exit 0 for successful dry-run (validation passed); matches user expectation

## Sources

### Primary (HIGH confidence)
- [yq official documentation (mikefarah/yq)](https://mikefarah.gitbook.io/yq) - YAML parsing syntax, usage patterns, tips and tricks
- [podman build official documentation](https://docs.podman.io/en/latest/markdown/podman-build.1.html) - Build arguments, tagging, multi-architecture support
- [podman machine inspect documentation](https://docs.podman.io/en/latest/markdown/podman-machine-inspect.1.html) - Machine status checking
- [Bash error handling patterns (HowToGeek)](https://www.howtogeek.com/bash-error-handling-patterns-i-use-in-every-script/) - set -euo pipefail, fail-fast patterns
- [Error handling in Bash scripts (Red Hat)](https://www.redhat.com/en/blog/error-handling-bash-scripting) - Official Red Hat guidance

### Secondary (MEDIUM confidence)
- [Container Image Versioning best practices](https://container-registry.com/posts/container-image-versioning/) - Multi-tagging strategy, version vs latest
- [Docker tagging best practices](https://www.docker.com/blog/docker-best-practices-using-tags-and-labels-to-manage-docker-image-sprawl/) - Verified with official docs
- [Semantic versioning regex (ihateregex.io)](https://ihateregex.io/expr/semver/) - Community resource, verified against semver.org
- [Bash argument parsing patterns (Medium)](https://medium.com/@wujido20/handling-flags-in-bash-scripts-4b06b4d0ed04) - Manual while-loop pattern
- [Bash time measurement (Baeldung)](https://www.baeldung.com/linux/bash-calculate-time-elapsed) - SECONDS variable usage
- [Command existence checking (Baeldung)](https://www.baeldung.com/linux/bash-script-check-program-exists) - command -v vs which vs type
- [ShellCheck official site](https://www.shellcheck.net/) - Static analysis tool

### Tertiary (LOW confidence, marked for validation)
- [NO_COLOR standard](https://no-color.org/) - Community standard for CI-friendly output (not official spec)
- [Bash dry-run metaprogramming](https://wozniak.ca/blog/drafts/bash-metaprogramming.html) - Draft article, pattern is sound
- [Podman machine automation (Medium)](https://medium.com/@guillem.riera/podman-machine-setup-for-x86-64-on-apple-silicon-run-docker-amd64-containers-on-m1-m2-m3-bf02bea38598) - User guide, verified against official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - yq and podman are industry standard for container builds with YAML config
- Architecture patterns: HIGH - All patterns verified against official documentation or established best practices
- Pitfalls: MEDIUM-HIGH - Based on common issues in shell scripting and container builds; some from direct documentation, others from community patterns

**Research date:** 2026-02-09
**Valid until:** 2026-04-09 (60 days - shell scripting patterns are stable; podman/yq evolve slowly)
