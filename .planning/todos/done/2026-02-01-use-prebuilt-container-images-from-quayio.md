---
created: 2026-02-01T21:52
title: Use pre-built container images from quay.io instead of local builds
area: containers
files:
  - src/mc/container/manager.py
  - src/mc/cli/commands/container.py
---

## Problem

Currently, users must build the MC container image locally on their machine using `podman build`. This creates several issues:

1. **Slow onboarding:** First-time users must wait for container build before using MC
2. **Inconsistent environments:** Each user builds from source, potential for drift
3. **Build dependencies:** Users need build tools and correct build context
4. **Wasted resources:** Every user rebuilds the same image instead of pulling once

The container image should be pre-built, versioned, and published to quay.io, allowing users to simply pull the latest image instead of building locally.

## Solution

**Strategy:**

1. **Publish to quay.io:** Set up automated builds that push to quay.io/[username]/mc-rhel10
2. **Version tagging:** Use semantic versioning (v2.0.0, v2.0.1) plus `latest` tag
3. **Pull-first logic:** Update MC to pull from quay.io before attempting local build
4. **Fallback support:** Keep local build option for development/customization

**Implementation areas:**

```python
# src/mc/container/manager.py
# Update create() to pull from registry first:
def _ensure_image(self, image_name: str) -> None:
    """Pull from quay.io or fall back to local build instructions."""
    registry_image = f"quay.io/{REGISTRY_USER}/{image_name}"
    
    try:
        # Try pulling from registry first
        self.podman.client.images.pull(registry_image)
        logger.info(f"Pulled {registry_image}")
    except PodmanError:
        # Fall back to checking local images
        if not self._image_exists_locally(image_name):
            raise ContainerError(
                f"Image {image_name} not found in registry or locally.",
                f"Pull failed. For local build: podman build -t {image_name} ..."
            )
```

**Configuration:**
- Add registry settings to config (quay.io URL, image name)
- Support custom registries for air-gapped environments
- Add `--build-local` flag to skip registry pull

**CI/CD:**
- GitHub Actions workflow to build and push on version tags
- Automated testing of published images before tagging `latest`

**Documentation:**
- Update README to remove local build requirement
- Add troubleshooting for registry pull failures
- Document local build process for development

**Testing:**
- Test pull with no local image
- Test pull failure fallback
- Test version-specific pulls (v2.0.0 vs latest)
- Test air-gapped scenarios with local registry

**Related:**
- Resolves slow first-run experience
- Enables consistent container environments across users
- Prerequisite for production distribution workflows
