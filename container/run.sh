#!/bin/bash
# Run the mc-con container

set -e

CASE_ID="${1:-default}"
IMAGE_NAME="${IMAGE_NAME:-mc-con}"
IMAGE_TAG="${IMAGE_TAG:-latest}"

echo "Starting container for case: ${CASE_ID}"

podman run \
    --network host \
    -dt \
    --name "mc-${CASE_ID}" \
    -v ~/Library/Application\ Support/ocm/:/root/.config/ocm:rw \
    -v ~/.config/backplane:/root/.config/backplane:rw \
    -v ~/Cases:/root/Cases:rw \
    "${IMAGE_NAME}:${IMAGE_TAG}"

echo "Container mc-${CASE_ID} started"
