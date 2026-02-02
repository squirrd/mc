---
created: 2026-02-01T21:15
title: Fix container create image detection failing despite image existing
area: api
files:
  - src/mc/container/manager.py
  - src/mc/integrations/podman.py
---

## Problem

`mc container create <case>` reports image not found despite image existing in Podman:

```bash
mc container create 04363690
Warning: Failed to reconcile container state: The scheme 'b''' must be one of (...)
Error: Image mc-rhel10:latest not found. Run 'podman build...' first.
Error: The scheme 'b''' must be one of ('unix', 'http+unix', 'ssh', 'http+ssh', 'tcp', 'http')

# But image exists:
podman images | grep mc-rhel10
localhost/mc-rhel10   latest   9d73eabd94c1   6 hours ago   549 MB
```

**Root cause analysis:**

This appears to be a **consequence of the Podman URI error** (see related todo: `2026-02-01-fix-podman-uri-scheme-byte-string-error.md`).

The error chain:
1. ContainerManager tries to verify image exists
2. Calls `podman.client.images.list()` or similar
3. PodmanClient fails to connect due to URI byte string error
4. Image verification fails
5. User sees "image not found" error (misleading)

**Evidence:**
- Same URI scheme error appears in both error messages
- "Failed to reconcile container state" warning appears first (same Podman connection issue)
- Image verification requires working Podman connection
- Image clearly exists when checked with `podman images`

## Solution

**Primary fix:** Resolve the Podman URI byte string error (see related todo).

**Secondary improvement:** Better error messaging

Current behavior:
```
Error: Image mc-rhel10:latest not found. Run 'podman build...' first.
```

Improved behavior:
```
Error: Failed to connect to Podman: <actual error>
Unable to verify image mc-rhel10:latest exists. Check Podman connection first.
```

**Implementation:**

```python
# In src/mc/container/manager.py create() method
try:
    # Verify image exists
    images = self.podman.client.images.list(filters={"reference": image_name})
    if not images:
        raise ContainerError(
            f"Image {image_name} not found.",
            f"Run 'podman build -t {image_name} -f container/Containerfile .' first."
        )
except PodmanConnectionError as e:
    # Don't mislead user about missing image if Podman connection failed
    raise ContainerError(
        f"Failed to connect to Podman: {e}",
        "Fix Podman connection before creating containers. Run 'mc --check-podman' for diagnostics."
    )
```

**Testing:**
- Test with image missing (should show "image not found")
- Test with Podman connection broken (should show "connection failed", not "image not found")
- Test with image present and Podman working (should succeed)

**Related:**
- `2026-02-01-fix-podman-uri-scheme-byte-string-error.md` - Primary root cause
- Once URI error is fixed, this symptom should disappear
