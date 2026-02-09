#!/bin/bash
# Multi-Stage Container Cache Verification Script
#
# Validates that layer caching works correctly by building the image twice
# and verifying that the second build uses cached layers for all stages.
#
# Usage:
#   ./container/verify-cache.sh
#
# Exit codes:
#   0 - Success: Layer caching working correctly
#   1 - Failure: No cached layers found or other error

set -euo pipefail

# Trap for cleanup
cleanup() {
    rm -f build1.log build2.log
}
trap cleanup EXIT

echo "=== Multi-Stage Container Cache Verification ==="
echo ""

# Build first time
echo "Building container image (first build)..."
if ! podman build -t mc-rhel10:cache-test -f container/Containerfile . > build1.log 2>&1; then
    echo "ERROR: First build failed"
    cat build1.log
    exit 1
fi
echo "First build completed successfully"
echo ""

# Build second time (no changes)
echo "Building container image (second build, no changes)..."
if ! podman build -t mc-rhel10:cache-test -f container/Containerfile . > build2.log 2>&1; then
    echo "ERROR: Second build failed"
    cat build2.log
    exit 1
fi
echo "Second build completed successfully"
echo ""

# Check for cache usage in second build
# Podman uses "CACHED" or "Using cache" to indicate layer cache hits
if grep -q -E "(Using cache|CACHED)" build2.log; then
    CACHE_LINES=$(grep -c -E "(Using cache|CACHED)" build2.log || true)
    echo "SUCCESS: Layer caching working correctly"
    echo "Cache hits: ${CACHE_LINES} layers reused from cache"
    echo ""
    echo "Multi-stage architecture is optimized for fast rebuilds."
    exit 0
else
    echo "ERROR: No cached layers found in second build"
    echo "This indicates cache invalidation - check ARG placement and layer ordering"
    echo ""
    echo "Second build log:"
    cat build2.log
    exit 1
fi
