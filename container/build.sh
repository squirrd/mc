#!/bin/bash
# Build the mc-rhel10 container image
# Run this script from the project root directory

set -e

IMAGE_NAME="${IMAGE_NAME:-mc-rhel10}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

# Ensure we're in project root (one level up from this script)
cd "$(dirname "$0")/.."

echo "Building container image: ${IMAGE_NAME}:${IMAGE_TAG}"
podman build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f container/Containerfile .

echo "Build complete!"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
echo ""
echo "Verify with: podman images | grep ${IMAGE_NAME}"
