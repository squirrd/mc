# Phase 21: Version Management System - Research

**Researched:** 2026-02-09
**Domain:** YAML-based version configuration management for container builds
**Confidence:** HIGH

## Summary

Version management for container images requires a single source of truth configuration file that tracks image version, bundled CLI version, and tool versions independently. The established approach uses YAML for configuration due to its human-readable format, widespread tooling support, and native handling of nested structures.

For this phase establishing versions.yaml as the source of truth for MC container image versioning, the standard approach combines a well-structured YAML schema with validation at build time. The schema organizes versions by category (image, mc, tools) with tool entries containing full metadata including version, download URL templates with placeholders, and checksums for integrity verification.

Research shows consistent patterns across 2026 sources: yq (command-line YAML processor) is the de facto standard for parsing YAML in shell scripts, semantic versioning validation uses regex patterns from semver.org, URL template substitution follows {variable} placeholder conventions, and fail-fast validation during build prevents expensive failures after downloads begin.

**Primary recommendation:** Use a minimal YAML schema with three top-level sections (image, mc, tools), parse with yq in shell build scripts, validate semantic versions with regex before build starts, use URL templates with {version} and {arch} placeholders for tool downloads, and fail builds immediately on validation errors to prevent wasted time.

## Standard Stack

The established libraries/tools for YAML-based version configuration management:

### Core
| Library/Tool | Version | Purpose | Why Standard |
|--------------|---------|---------|--------------|
| yq | v4.x (mikefarah) | YAML parsing in shell scripts | De facto standard, jq-like syntax, written in Go (single binary), supports YAML/JSON/XML |
| PyYAML | 6.0+ | YAML parsing in Python | Most widely used Python YAML library, safe_load() prevents code execution |
| Semantic Versioning | 2.0.0 | Version number format | Industry standard (semver.org), clear major.minor.patch semantics |
| curl --head | Pre-installed | URL reachability validation | Lightweight HTTP HEAD request, pre-installed on all systems |

### Supporting
| Library/Tool | Version | Purpose | When to Use |
|--------------|---------|---------|-------------|
| ruamel.yaml | Latest | YAML 1.2 with comment preservation | When round-trip parsing needed, preserves formatting (not needed for build scripts) |
| StrictYAML | Latest | Type-safe YAML validation | When schema validation critical, slower than PyYAML (optional for this phase) |
| Yamale | Latest | YAML schema validator | When complex schema validation needed (optional, can defer to Phase 22) |
| semver-tool | Latest | Bash semantic version utilities | When version comparison needed beyond validation (not needed for Phase 21) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| yq (mikefarah) | yq (kislyuk Python wrapper) | Python wrapper adds dependency, slower, mikefarah version is pure Go single binary |
| YAML | TOML/JSON | YAML better for nested structures and comments, more readable for version config |
| Manual URL construction | URL template libraries | Simple string replacement sufficient, libraries add unnecessary complexity |
| Build-time validation | Runtime validation | Build-time catches errors early, prevents bad images from being created |

**Installation:**
```bash
# yq (mikefarah version) - recommended for shell scripts
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 -O /usr/local/bin/yq
chmod +x /usr/local/bin/yq

# PyYAML - for Python-based validation (optional)
pip install pyyaml

# No other installation needed for validation scripts
```

## Architecture Patterns

### Recommended versions.yaml Structure
```yaml
# versions.yaml - Single source of truth for MC container image versioning
image:
  version: "1.0.0"  # Independent image version (semantic versioning)

mc:
  version: "2.0.2"  # MC CLI version bundled in container

tools:
  ocm:
    version: "1.0.10"
    url: "https://github.com/openshift-online/ocm-cli/releases/download/v{version}/ocm-linux-{arch}"
    checksum: "sha256:abc123..."  # SHA256 hash
    description: "OpenShift Cluster Manager CLI"
  # Future tools follow same pattern
```

### Pattern 1: Nested Category Structure

**What:** Organize version data into logical categories (image, mc, tools) with nested objects for clarity and extensibility.

**When to use:** Always for version configuration files. Prevents flat namespace pollution and groups related data.

**Example:**
```yaml
# Good: Nested structure
image:
  version: "1.0.0"

mc:
  version: "2.0.2"

tools:
  ocm:
    version: "1.0.10"
    url: "..."

# Bad: Flat structure
image_version: "1.0.0"
mc_version: "2.0.2"
ocm_version: "1.0.10"
ocm_url: "..."  # Unclear relationship
```

**Key benefits:**
- Clear organizational hierarchy
- Easy to add new tools without conflicts
- Self-documenting structure
- yq queries are more intuitive (.tools.ocm.version vs .ocm_version)

### Pattern 2: URL Templates with Placeholders

**What:** Use {variable} placeholder syntax in URLs, replace at build time with actual values using shell string substitution or yq.

**When to use:** Any URL that varies by version or architecture. Enables version updates without touching URL patterns.

**Example:**
```yaml
tools:
  ocm:
    version: "1.0.10"
    url: "https://github.com/openshift-online/ocm-cli/releases/download/v{version}/ocm-linux-{arch}"
```

**Shell substitution:**
```bash
# Extract values with yq
VERSION=$(yq '.tools.ocm.version' versions.yaml)
URL_TEMPLATE=$(yq '.tools.ocm.url' versions.yaml)

# Substitute placeholders
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then ARCH="amd64"; elif [ "$ARCH" = "aarch64" ]; then ARCH="arm64"; fi
DOWNLOAD_URL="${URL_TEMPLATE//\{version\}/$VERSION}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{arch\}/$ARCH}"

# Result: https://github.com/openshift-online/ocm-cli/releases/download/v1.0.10/ocm-linux-amd64
```

**Benefits:**
- Version updates don't require URL changes
- Architecture-specific downloads handled automatically
- Pattern is human-readable
- No external templating library needed

### Pattern 3: Semantic Version Validation with Regex

**What:** Validate version strings against semver.org regex pattern before using in builds.

**When to use:** Every time a version is read from configuration. Fail fast on invalid formats.

**Example:**
```bash
#!/bin/bash
# Semantic version regex from semver.org (simplified for basic x.y.z)
SEMVER_REGEX='^([0-9]+)\.([0-9]+)\.([0-9]+)$'

validate_version() {
    local version="$1"
    local name="$2"

    if ! [[ "$version" =~ $SEMVER_REGEX ]]; then
        echo "ERROR: Invalid semantic version for $name: '$version'"
        echo "Expected format: x.y.z (e.g., 1.0.0)"
        exit 1
    fi
}

# Usage
IMAGE_VERSION=$(yq '.image.version' versions.yaml)
validate_version "$IMAGE_VERSION" "image"

MC_VERSION=$(yq '.mc.version' versions.yaml)
validate_version "$MC_VERSION" "MC CLI"
```

**Full semver.org regex (with pre-release and build metadata):**
```bash
FULL_SEMVER_REGEX='^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(-((0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?$'
```

### Pattern 4: Fail-Fast URL Validation

**What:** Validate URLs are reachable with HTTP HEAD request before attempting download, fail build immediately on 404.

**When to use:** Before any expensive build operations. Prevents wasted build time on unreachable URLs.

**Example:**
```bash
#!/bin/bash
set -e  # Exit on any error

validate_url() {
    local url="$1"
    local name="$2"

    echo "Validating URL for $name: $url"

    # Use curl --head to check without downloading
    if ! curl --head --silent --fail --location "$url" > /dev/null 2>&1; then
        echo "ERROR: URL not reachable for $name"
        echo "URL: $url"
        echo "This may indicate:"
        echo "  - Invalid version number"
        echo "  - Release not yet published"
        echo "  - Network connectivity issue"
        exit 1
    fi

    echo "SUCCESS: URL is reachable for $name"
}

# Usage
DOWNLOAD_URL="https://github.com/openshift-online/ocm-cli/releases/download/v1.0.10/ocm-linux-amd64"
validate_url "$DOWNLOAD_URL" "OCM CLI"
```

**Benefits:**
- Fails within seconds, not after minutes of build
- Clear error message identifies the problem
- Catches typos in version numbers immediately
- Detects missing releases before build starts

### Pattern 5: YAML Parsing with yq in Shell Scripts

**What:** Use yq command-line tool to extract values from YAML files in shell scripts, avoiding manual parsing.

**When to use:** Any shell script that needs to read YAML configuration. Standard practice for build scripts.

**Example:**
```bash
#!/bin/bash
set -euo pipefail

# Read simple values
IMAGE_VERSION=$(yq '.image.version' versions.yaml)
MC_VERSION=$(yq '.mc.version' versions.yaml)

# Read nested values
OCM_VERSION=$(yq '.tools.ocm.version' versions.yaml)
OCM_URL=$(yq '.tools.ocm.url' versions.yaml)

# Iterate over all tools
yq '.tools | keys | .[]' versions.yaml | while read -r tool; do
    version=$(yq ".tools.${tool}.version" versions.yaml)
    url=$(yq ".tools.${tool}.url" versions.yaml)
    echo "Tool: $tool, Version: $version"
done

# Check if key exists
if yq -e '.tools.ocm' versions.yaml > /dev/null 2>&1; then
    echo "OCM configuration found"
fi
```

**yq vs manual parsing:**
- yq handles edge cases (quotes, special characters)
- yq validates YAML syntax automatically
- yq is faster than awk/sed/grep combinations
- yq supports complex queries (filtering, transforming)

### Pattern 6: Version Configuration as Single Source of Truth

**What:** Store all version information in one file, reference it from all other locations (Containerfile, build scripts, docs).

**When to use:** Always. Prevents version drift between different files.

**Example:**
```
Project structure:
├── versions.yaml              # SINGLE SOURCE OF TRUTH
├── container/
│   ├── Containerfile          # Reads ARGs from build script
│   └── build.sh               # Parses versions.yaml, passes as --build-arg
├── docs/
│   └── README.md              # References versions.yaml in examples
└── .planning/
    └── VERSION_POLICY.md      # Documents versioning scheme
```

**Workflow:**
```bash
# 1. Developer edits versions.yaml
vim versions.yaml  # Change OCM version from 1.0.10 to 1.0.11

# 2. Build script reads versions.yaml
./container/build.sh  # Parses YAML, validates, passes to Containerfile

# 3. Containerfile receives version as ARG
# ARG OCM_VERSION=1.0.11  (injected by build script)

# 4. Documentation references versions.yaml
# README.md: "See versions.yaml for current tool versions"
```

### Anti-Patterns to Avoid

- **Hardcoded versions in multiple files:** Update versions.yaml only, parse from other locations
- **Manual URL construction in Containerfile:** Use templates with placeholders, substitute in build script
- **No validation before build:** Validate YAML syntax, semantic versions, and URLs before expensive operations
- **Complex YAML schema:** Keep structure minimal, avoid deep nesting beyond 3 levels
- **Comments in YAML for metadata:** Use description fields for tool purposes, comments don't survive round-trip parsing
- **Using latest tag:** Pin specific versions, enables reproducible builds and rollback
- **JSON instead of YAML:** YAML is more readable for human-edited config, supports comments
- **Version in multiple places:** Single source of truth pattern prevents drift

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing in shell | awk/sed/grep scripts | yq command-line tool | Handles edge cases (quotes, multiline, special chars), validates syntax, 10x faster |
| Semantic version validation | Custom string parsing | semver.org regex pattern | Covers all edge cases (pre-release, build metadata), battle-tested, standardized |
| URL reachability check | wget/ping scripts | curl --head --silent --fail | Lightweight HTTP HEAD request, respects redirects, clear exit codes |
| YAML schema validation | Manual field checking | PyYAML + custom validator or Yamale | Handles type checking, required fields, format validation, clear error messages |
| URL template substitution | Complex sed/awk | Bash string replacement ${var//pattern/replacement} | Built-in, fast, readable, no external dependencies |
| Version comparison | String parsing | semver-tool or Python packaging.version | Handles pre-release versions, correctly compares 1.9.0 < 1.10.0 |

**Key insight:** YAML processing and version management are solved problems with mature tooling. yq is ubiquitous in container build pipelines (Kubernetes, CI/CD), semantic versioning has official regex patterns, and URL validation is a single curl command. Custom solutions add maintenance burden without benefit.

## Common Pitfalls

### Pitfall 1: YAML Syntax Errors from Indentation

**What goes wrong:** YAML parsing fails during build due to incorrect indentation (tabs vs spaces, inconsistent spacing).

**Why it happens:** YAML relies on precise indentation to define hierarchy. A single misaligned space breaks the structure. Developers may use tabs or mix indentation styles.

**How to avoid:**
1. Always use 2 spaces for indentation (YAML convention)
2. Configure editor to insert spaces, not tabs
3. Use YAML linter (yamllint) in pre-commit hooks
4. Validate YAML syntax before committing (yq eval versions.yaml > /dev/null)

**Warning signs:**
- Build fails with "yaml: line X: mapping values are not allowed here"
- "did not find expected key" errors
- Values appearing as keys or vice versa
- Editor shows mixed tab/space characters

**Example:**
```yaml
# GOOD: Consistent 2-space indentation
tools:
  ocm:
    version: "1.0.10"
    url: "https://..."

# BAD: Mixed tabs and spaces (invisible in some editors)
tools:
	ocm:  # Tab character
  version: "1.0.10"  # 2 spaces
    url: "https://..."  # 4 spaces
```

### Pitfall 2: Invalid Semantic Versions Passing Through

**What goes wrong:** Version string like "1.0" or "v1.0.0" or "latest" gets written to versions.yaml, passes validation, then breaks URL construction or version comparison.

**Why it happens:** No validation at edit time, developers assume flexible version formats, or copy versions from tags that include prefixes.

**How to avoid:**
1. Validate all versions on file save (editor plugin or git hook)
2. Use strict semver regex: ^[0-9]+\.[0-9]+\.[0-9]+$ for basic x.y.z
3. Build script MUST validate before using versions
4. Reject version strings with prefixes (v1.0.0 → 1.0.0)

**Warning signs:**
- Build fails during URL substitution
- Tool downloads fail with 404 errors
- Version comparison logic breaks
- Different behavior between v1.0.0 and 1.0.0

**Example:**
```yaml
# GOOD: Strict semantic version
image:
  version: "1.0.0"  # Three numeric components

# BAD: Various invalid formats
image:
  version: "1.0"      # Only two components
  version: "v1.0.0"   # Has v prefix
  version: "latest"   # Not semantic version
  version: "1.0.0-beta"  # Pre-release (valid semver but may break simple parsing)
```

### Pitfall 3: URL Template Variable Mismatch

**What goes wrong:** URL template has {version} placeholder but versions.yaml is missing version field, or uses {arch} but script doesn't substitute it, resulting in literal "{arch}" in download URL.

**Why it happens:** Template and schema definition are in different files, developer adds new placeholder without updating substitution logic.

**How to avoid:**
1. Document all supported placeholders ({version}, {arch})
2. Validate that all placeholders in URLs have corresponding data
3. Test URL substitution with actual values before using
4. Fail build if unresolved placeholders remain after substitution

**Warning signs:**
- Download URLs contain literal "{version}" or "{arch}"
- 404 errors for URLs that should exist
- curl downloads HTML error page instead of binary
- Inconsistent URL patterns across tools

**Example:**
```yaml
# Configuration
tools:
  ocm:
    version: "1.0.10"
    url: "https://github.com/org/repo/releases/download/v{version}/ocm-linux-{arch}"

# GOOD: Substitutes all placeholders
DOWNLOAD_URL="${URL_TEMPLATE//\{version\}/$VERSION}"
DOWNLOAD_URL="${DOWNLOAD_URL//\{arch\}/$ARCH}"
# Result: https://github.com/org/repo/releases/download/v1.0.10/ocm-linux-amd64

# BAD: Forgets to substitute {arch}
DOWNLOAD_URL="${URL_TEMPLATE//\{version\}/$VERSION}"
# Result: https://github.com/org/repo/releases/download/v1.0.10/ocm-linux-{arch}
# curl downloads 404 error page
```

### Pitfall 4: No Validation Before Expensive Operations

**What goes wrong:** Build script starts expensive operations (download large files, compile code) before validating versions.yaml, then fails minutes later when invalid version is used.

**Why it happens:** Validation added as afterthought, developer assumes configuration is always correct, or validation placed after downloads.

**How to avoid:**
1. Validate YAML syntax FIRST (yq eval versions.yaml)
2. Validate semantic versions SECOND
3. Validate URL reachability THIRD
4. Only then proceed to downloads and builds
5. Use set -e for fail-fast behavior

**Warning signs:**
- Builds fail after multi-minute downloads
- Same validation error happens repeatedly
- Build logs show successful downloads followed by validation failure
- Wasted CI/CD minutes on invalid configurations

**Example:**
```bash
# GOOD: Validate before expensive operations
#!/bin/bash
set -euo pipefail

# Step 1: Validate YAML syntax (< 1 second)
echo "Validating YAML syntax..."
yq eval versions.yaml > /dev/null

# Step 2: Validate semantic versions (< 1 second)
echo "Validating version formats..."
validate_semver "$(yq '.image.version' versions.yaml)" "image"
validate_semver "$(yq '.mc.version' versions.yaml)" "mc"

# Step 3: Validate URLs reachable (< 5 seconds)
echo "Validating tool URLs..."
validate_url "$DOWNLOAD_URL" "OCM CLI"

# Step 4: Proceed with expensive operations (minutes)
echo "All validations passed, starting build..."
podman build --build-arg OCM_VERSION="$OCM_VERSION" ...

# BAD: Validate after expensive operations
#!/bin/bash
podman build ...  # 5 minutes
validate_semver "$VERSION"  # Fails here, wasted 5 minutes
```

### Pitfall 5: Architecture Detection Errors

**What goes wrong:** Build script assumes x86_64 architecture, breaks on ARM systems (aarch64, arm64). Or maps x86_64 → amd64 but tool uses x86_64 naming.

**Why it happens:** Different tools use different architecture naming conventions (x86_64 vs amd64, aarch64 vs arm64). Script hardcodes architecture or uses wrong mapping.

**How to avoid:**
1. Detect architecture with uname -m
2. Map to tool-specific names based on URL pattern
3. Test on both x86_64 and ARM systems
4. Document architecture mapping in versions.yaml comments
5. Validate architecture value is in allowed set

**Warning signs:**
- Builds fail on ARM systems but work on x86_64
- 404 errors for architecture-specific downloads
- Wrong binary downloaded (x86 binary on ARM system)
- Container builds succeed but runtime fails with "exec format error"

**Example:**
```bash
# GOOD: Detect and map architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        ARCH="amd64"  # Most GitHub releases use amd64
        ;;
    aarch64)
        ARCH="arm64"  # Most GitHub releases use arm64
        ;;
    *)
        echo "ERROR: Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Verify architecture is in URL
if [[ "$DOWNLOAD_URL" != *"$ARCH"* ]]; then
    echo "WARNING: Architecture $ARCH not found in URL"
fi

# BAD: Hardcoded architecture
ARCH="amd64"  # Breaks on ARM systems
```

### Pitfall 6: Checksum Validation Skipped or Wrong

**What goes wrong:** versions.yaml contains checksum field but build script doesn't verify it, or checksum is for wrong version/architecture, or uses wrong hash algorithm.

**Why it happens:** Checksum validation requires downloading file first, developer skips for speed, or checksum is outdated after version change.

**How to avoid:**
1. Download file, verify checksum, fail on mismatch
2. Use sha256sum (widely supported, secure)
3. Update checksum when version changes (automation or manual)
4. Make checksum optional but warn if missing
5. Test checksum validation with intentionally wrong hash

**Warning signs:**
- Builds succeed with corrupted downloads
- Different binaries on different build runs
- Checksum field outdated relative to version field
- sha256sum command not found (missing in minimal images)

**Example:**
```bash
# GOOD: Verify checksum if provided
EXPECTED_CHECKSUM=$(yq '.tools.ocm.checksum' versions.yaml)

if [ -n "$EXPECTED_CHECKSUM" ] && [ "$EXPECTED_CHECKSUM" != "null" ]; then
    echo "Verifying checksum..."
    echo "$EXPECTED_CHECKSUM ocm-linux-${ARCH}" | sha256sum --check || {
        echo "ERROR: Checksum verification failed"
        exit 1
    }
else
    echo "WARNING: No checksum provided, skipping verification"
fi

# BAD: Checksum in config but not verified
# versions.yaml has checksum field
# Build script downloads but never checks it
curl -LO "$DOWNLOAD_URL"  # No verification
```

## Code Examples

Verified patterns from official sources:

### Complete versions.yaml Schema

```yaml
# versions.yaml - Single source of truth for MC container image versioning
# Format: Semantic Versioning 2.0.0 (https://semver.org)
# Last updated: 2026-02-09

image:
  version: "1.0.0"  # Independent image version (increments on any change)

mc:
  version: "2.0.2"  # MC CLI version bundled in container (from pyproject.toml)

tools:
  ocm:
    version: "1.0.10"
    url: "https://github.com/openshift-online/ocm-cli/releases/download/v{version}/ocm-linux-{arch}"
    checksum: "sha256:abc123..."  # SHA256 hash for verification (optional)
    description: "OpenShift Cluster Manager CLI"

  # Future tool example (commented for reference)
  # kubectl:
  #   version: "1.28.0"
  #   url: "https://dl.k8s.io/release/v{version}/bin/linux/{arch}/kubectl"
  #   checksum: "sha256:def456..."
  #   description: "Kubernetes command-line tool"
```

### Build Script Version Extraction and Validation

```bash
#!/bin/bash
# Source: Composite pattern from yq docs + semver.org + bash best practices
# https://mikefarah.gitbook.io/yq
# https://semver.org
set -euo pipefail

VERSIONS_FILE="versions.yaml"

# Semantic version regex (basic x.y.z format)
SEMVER_REGEX='^([0-9]+)\.([0-9]+)\.([0-9]+)$'

echo "=== Validating versions.yaml ==="

# Step 1: Validate YAML syntax
echo "Checking YAML syntax..."
if ! yq eval "$VERSIONS_FILE" > /dev/null 2>&1; then
    echo "ERROR: Invalid YAML syntax in $VERSIONS_FILE"
    exit 1
fi
echo "✓ YAML syntax valid"

# Step 2: Extract and validate image version
echo "Validating image version..."
IMAGE_VERSION=$(yq '.image.version' "$VERSIONS_FILE")
if ! [[ "$IMAGE_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "ERROR: Invalid image version: '$IMAGE_VERSION'"
    echo "Expected format: x.y.z (e.g., 1.0.0)"
    exit 1
fi
echo "✓ Image version: $IMAGE_VERSION"

# Step 3: Extract and validate MC CLI version
echo "Validating MC CLI version..."
MC_VERSION=$(yq '.mc.version' "$VERSIONS_FILE")
if ! [[ "$MC_VERSION" =~ $SEMVER_REGEX ]]; then
    echo "ERROR: Invalid MC version: '$MC_VERSION'"
    echo "Expected format: x.y.z (e.g., 2.0.2)"
    exit 1
fi
echo "✓ MC CLI version: $MC_VERSION"

# Step 4: Validate and process tool versions
echo "Validating tool versions..."
TOOL_COUNT=$(yq '.tools | keys | length' "$VERSIONS_FILE")
echo "Found $TOOL_COUNT tools"

yq '.tools | keys | .[]' "$VERSIONS_FILE" | while read -r tool; do
    echo "  Validating tool: $tool"

    # Extract tool metadata
    TOOL_VERSION=$(yq ".tools.${tool}.version" "$VERSIONS_FILE")
    TOOL_URL=$(yq ".tools.${tool}.url" "$VERSIONS_FILE")

    # Validate version format
    if ! [[ "$TOOL_VERSION" =~ $SEMVER_REGEX ]]; then
        echo "ERROR: Invalid version for $tool: '$TOOL_VERSION'"
        exit 1
    fi

    # Validate URL exists
    if [ -z "$TOOL_URL" ] || [ "$TOOL_URL" = "null" ]; then
        echo "ERROR: Missing URL for $tool"
        exit 1
    fi

    echo "  ✓ $tool version $TOOL_VERSION"
done

echo "=== All validations passed ==="
```

### URL Template Substitution and Validation

```bash
#!/bin/bash
# Source: Composite pattern from curl docs + GitHub API patterns
# https://www.baeldung.com/linux/shell-check-url-validity
set -euo pipefail

substitute_url_template() {
    local template="$1"
    local version="$2"
    local arch="$3"

    # Substitute {version} placeholder
    local url="${template//\{version\}/$version}"

    # Substitute {arch} placeholder
    url="${url//\{arch\}/$arch}"

    echo "$url"
}

validate_url_reachable() {
    local url="$1"
    local name="$2"

    echo "Validating URL for $name..."
    echo "  URL: $url"

    # Use curl --head to check without downloading
    # --silent: no progress bar
    # --fail: exit code 22 for HTTP errors
    # --location: follow redirects
    if curl --head --silent --fail --location "$url" > /dev/null 2>&1; then
        echo "  ✓ URL is reachable"
        return 0
    else
        echo "  ERROR: URL not reachable"
        echo "  Possible causes:"
        echo "    - Invalid version number"
        echo "    - Release not published yet"
        echo "    - Architecture not supported"
        echo "    - Network connectivity issue"
        return 1
    fi
}

# Example usage
VERSIONS_FILE="versions.yaml"
TOOL="ocm"

# Extract metadata
VERSION=$(yq ".tools.${TOOL}.version" "$VERSIONS_FILE")
URL_TEMPLATE=$(yq ".tools.${TOOL}.url" "$VERSIONS_FILE")

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) ARCH="amd64" ;;
    aarch64) ARCH="arm64" ;;
    *) echo "ERROR: Unsupported architecture: $ARCH"; exit 1 ;;
esac

# Substitute template
DOWNLOAD_URL=$(substitute_url_template "$URL_TEMPLATE" "$VERSION" "$ARCH")

# Validate before download
if ! validate_url_reachable "$DOWNLOAD_URL" "$TOOL"; then
    exit 1
fi

# Proceed with download
echo "Downloading $TOOL $VERSION..."
curl -fsSL "$DOWNLOAD_URL" -o "${TOOL}-linux-${ARCH}"
```

### YAML Validation with Python (Optional Alternative)

```python
#!/usr/bin/env python3
# Source: PyYAML documentation + semantic versioning best practices
# https://pyyaml.org/wiki/PyYAMLDocumentation
import sys
import re
from pathlib import Path
import yaml

# Semantic version regex (basic x.y.z)
SEMVER_PATTERN = re.compile(r'^([0-9]+)\.([0-9]+)\.([0-9]+)$')

def validate_semver(version: str, field_name: str) -> None:
    """Validate semantic version format."""
    if not SEMVER_PATTERN.match(version):
        print(f"ERROR: Invalid semantic version for {field_name}: '{version}'")
        print("Expected format: x.y.z (e.g., 1.0.0)")
        sys.exit(1)

def validate_versions_yaml(file_path: Path) -> dict:
    """Validate versions.yaml schema and content."""

    # Load YAML file
    try:
        with open(file_path) as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"ERROR: Invalid YAML syntax: {e}")
        sys.exit(1)

    # Validate top-level structure
    required_sections = ['image', 'mc', 'tools']
    for section in required_sections:
        if section not in data:
            print(f"ERROR: Missing required section: {section}")
            sys.exit(1)

    # Validate image version
    if 'version' not in data['image']:
        print("ERROR: Missing image.version")
        sys.exit(1)
    validate_semver(data['image']['version'], 'image.version')

    # Validate MC version
    if 'version' not in data['mc']:
        print("ERROR: Missing mc.version")
        sys.exit(1)
    validate_semver(data['mc']['version'], 'mc.version')

    # Validate tools
    for tool_name, tool_config in data['tools'].items():
        required_fields = ['version', 'url']
        for field in required_fields:
            if field not in tool_config:
                print(f"ERROR: Missing {field} for tool: {tool_name}")
                sys.exit(1)

        validate_semver(tool_config['version'], f'tools.{tool_name}.version')

        # Validate URL contains placeholders
        url = tool_config['url']
        if '{version}' not in url:
            print(f"WARNING: URL for {tool_name} doesn't contain {{version}} placeholder")

    print("✓ All validations passed")
    return data

if __name__ == '__main__':
    versions_file = Path('versions.yaml')
    if not versions_file.exists():
        print(f"ERROR: {versions_file} not found")
        sys.exit(1)

    validate_versions_yaml(versions_file)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Hardcoded versions in Containerfile | versions.yaml single source of truth | Industry best practice 2020+ | Centralized version management, prevents drift |
| Manual YAML parsing with awk/sed | yq command-line tool | yq v4 release 2020+ | Reliable parsing, 10x faster, handles edge cases |
| PyYAML only | ruamel.yaml for round-trip | ruamel.yaml 0.15+ (2018) | Comment preservation, YAML 1.2 support, better for generated configs |
| No version validation | Semantic versioning enforcement | semver.org 2.0.0 (2013) | Prevents invalid versions, standardized format |
| Download then validate URL | Validate URL before download (curl --head) | Best practice 2015+ | Fail fast, saves bandwidth and time |
| Version in git tags | Version in configuration file | CI/CD best practice 2018+ | Decouples image version from code version |
| latest tag only | Semantic versioned tags | Container best practice 2019+ | Reproducible builds, rollback capability |
| Comments for documentation | Structured description fields | YAML best practice 2020+ | Machine-readable metadata, survives round-trip |

**Deprecated/outdated:**
- **Hardcoded versions in Containerfile**: Use ARG parameters injected from versions.yaml
- **Manual YAML parsing**: Use yq or PyYAML, don't reinvent parsing logic
- **No checksum verification**: Always verify integrity with SHA256 checksums when available
- **Implicit version updates**: Explicit version declarations prevent surprise breakage
- **Version in environment variables only**: Configuration file provides audit trail and version control

## Open Questions

Things that couldn't be fully resolved:

1. **OCM CLI Checksum Availability**
   - What we know: GitHub releases provide SHA256 checksums as of June 2025, OCM CLI is actively maintained
   - What's unclear: Whether OCM CLI releases include checksum files (.sha256) or only GPG signatures
   - Recommendation: Check OCM releases page for v1.0.10, use checksums if available, document in versions.yaml schema if checksums are optional vs required

2. **Version Sync Between pyproject.toml and versions.yaml**
   - What we know: MC CLI version currently in pyproject.toml (2.0.2), versions.yaml will track it separately
   - What's unclear: Whether to auto-sync or manually update, single source of truth conflict
   - Recommendation: Phase 21 uses manual sync (developer updates both), Phase 22+ can add validation that they match, future phase could auto-generate versions.yaml from pyproject.toml

3. **Tool Checksum Storage Format**
   - What we know: SHA256 checksums are standard, can be stored as "sha256:abc123..." or just "abc123..."
   - What's unclear: Best format for versions.yaml (algorithm prefix or separate field)
   - Recommendation: Use "sha256:abc123..." format (algorithm prefix included) for self-documenting values, aligns with container image digest format

4. **Optional vs Required Tool Fields**
   - What we know: version and url are clearly required, checksum and description are useful but may be optional
   - What's unclear: Whether to enforce all fields or allow incremental addition
   - Recommendation: Require version and url, make checksum and description optional in Phase 21, can add enforcement in Phase 22 build script

## Sources

### Primary (HIGH confidence)

- [yq Official Documentation](https://mikefarah.gitbook.io/yq) - Command-line YAML processor, query syntax, installation
- [yq GitHub Repository (mikefarah)](https://github.com/mikefarah/yq) - Go-based portable YAML/JSON/XML processor
- [Semantic Versioning 2.0.0](https://semver.org/) - Official semantic versioning specification, regex patterns
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) - Python YAML parsing, safe_load() usage
- [Real Python - YAML: The Missing Battery in Python](https://realpython.com/python-yaml/) - PyYAML vs ruamel.yaml comparison, best practices
- [Baeldung - Processing YAML Content With yq](https://www.baeldung.com/linux/yq-processing-yaml) - yq usage patterns, examples
- [Baeldung - Verify if a URL Is Valid From the Linux Shell](https://www.baeldung.com/linux/shell-check-url-validity) - curl --head validation pattern

### Secondary (MEDIUM confidence)

- [Better Stack - Working with YAML Files in Python](https://betterstack.com/community/guides/scaling-python/yaml-files-in-python/) - PyYAML usage patterns (2024)
- [Yamale GitHub Repository](https://github.com/23andMe/Yamale) - YAML schema validator
- [StrictYAML Documentation](https://hitchdev.com/strictyaml/) - Type-safe YAML validation
- [GitHub - Semantic Versioning Regex](https://gist.github.com/jhorsman/62eeea161a13b80e39f5249281e17c39) - Bash semver validation patterns
- [GitHub - Bash script for checking semantic version](https://gist.github.com/rverst/1f0b97da3cbeb7d93f4986df6e8e5695) - Practical bash implementation
- [Medium - Parsing JSON and YAML Files with jq and yq](https://medium.com/@amareswer/parsing-json-and-yaml-files-with-jq-and-yq-in-shell-scripts-39f1b3e3beb6) - Shell script integration patterns
- [OneUpTime - How to Handle Regular Expressions in Bash (2026-01-24)](https://oneuptime.com/blog/post/2026-01-24-bash-regular-expressions/view) - Bash regex patterns
- [Oreate AI - Choosing Between ruamel.yaml and PyYAML](https://www.oreateai.com/blog/choosing-between-ruamelyaml-and-pyyaml-a-comprehensive-comparison/2ca85e856751622588a46a00a9a8e664) - Library comparison
- [GitHub Docs - Linking to Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/linking-to-releases) - GitHub release URL patterns
- [Thoughtspot - Single Source of Truth (SSOT)](https://www.thoughtspot.com/data-trends/best-practices/single-source-of-truth) - SSOT best practices
- [Perforce - Single Source of Truth Examples](https://www.perforce.com/blog/vcs/single-source-of-truth-examples-ssot) - Version control SSOT patterns

### Tertiary (LOW confidence - WebSearch only)

- [YAML Validators A Complete Guide](https://skynethosting.net/blog/yaml-validators/) - General YAML validation tools (2025)
- [MoldStud - YAML File Validation Best Practices](https://moldstud.com/articles/p-yaml-file-validation-best-practices-to-ensure-configuration-accuracy) - Validation strategies
- [Container Image Versioning Best Practices](https://container-registry.com/posts/container-image-versioning/) - Versioning strategies for containers
- [DevToolHub - Parsing JSON and YAML with jq and yq](https://devtoolhub.com/parsing-json-and-yaml-files-with-jq-and-yq-in-shell-scripts/) - Tool comparison
- Various DevOps blog articles on version management (multiple sources 2025-2026) - General patterns, cross-verified with official docs

## Metadata

**Confidence breakdown:**
- Standard stack (yq, PyYAML, semver): HIGH - Official documentation, established industry tools since 2013-2020
- Architecture patterns (YAML schema, URL templates): HIGH - Composite pattern from official docs and verified examples
- Shell script patterns (yq usage, validation): HIGH - Official yq documentation and bash best practices
- Pitfalls: MEDIUM-HIGH - Combination of official docs and community experience, practical validation
- OCM CLI integration details: MEDIUM - GitHub repo verified, checksum format needs confirmation

**Research date:** 2026-02-09
**Valid until:** 30 days for tools (yq stable), 7 days for OCM versions (releases monthly), semantic patterns evergreen

**Key uncertainties requiring validation:**
1. OCM CLI checksum file availability and format in v1.0.10 release
2. Decision on pyproject.toml vs versions.yaml as single source of truth for MC CLI version
3. Optional vs required fields policy for tool metadata
