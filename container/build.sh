#!/bin/bash
# Build the mc-con container image

set -e

IMAGE_NAME="${IMAGE_NAME:-mc-con}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "Building container image: ${IMAGE_NAME}:${IMAGE_TAG}"
podman build -t "${IMAGE_NAME}:${IMAGE_TAG}" -f Containerfile .

echo "Build complete!"
echo "Image: ${IMAGE_NAME}:${IMAGE_TAG}"
