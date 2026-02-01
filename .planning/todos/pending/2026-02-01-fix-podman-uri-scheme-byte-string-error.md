---
created: 2026-02-01T21:15
title: Fix Podman URI scheme byte string error in container commands
area: api
files:
  - src/mc/integrations/podman.py:133
  - src/mc/integrations/platform_detect.py:107-116
  - src/mc/cli/commands/container.py:70
---

## Problem

Container commands fail with URI scheme error despite Phase 14.1-01 fix:

```
ValueError: The scheme 'b''' must be one of ('unix', 'http+unix', 'ssh', 'http+ssh', 'tcp', 'http')
```

**Affected commands:**
- `mc container list`
- `mc container create <case>`

**Stack trace:**
```python
File "/Users/dsquirre/Repos/mc/src/mc/integrations/podman.py", line 133, in client
    self._client = retry_podman_operation(_connect)
File "/Users/dsquirre/Repos/mc/src/mc/integrations/podman.py", line 130, in _connect
    return podman.PodmanClient(base_url=uri, timeout=self._timeout)
File ".../podman/api/client.py", line 189, in _normalize_url
    raise ValueError(
ValueError: The scheme 'b''' must be one of (...)
```

**Symptom analysis:** The error "The scheme 'b'''" indicates an **empty byte string** `b''` is being passed as the URI. The podman library is interpreting the literal characters `b''` as a scheme name.

**Context:** Phase 14.1-01 added byte string detection in `get_socket_path()` but this error still occurs, suggesting:
1. The fix isn't being triggered in all code paths
2. Byte string is being created elsewhere
3. The CONTAINER_HOST environment variable is set to empty byte string
4. There's a code path that bypasses the fixed function

## Solution

**Debug steps:**
1. Check where `uri` comes from in `podman.py` line 130
2. Verify `get_socket_path()` is being called
3. Check if config's `socket_path` field is byte string instead of string
4. Trace all paths that set the Podman URI

**Likely fix locations:**

**1. Config socket_path serialization (mentioned in 14.1-04 as auto-fixed):**
```python
# In src/mc/config/models.py or manager.py
# Ensure socket_path is always str, never bytes
if isinstance(socket_path, bytes):
    socket_path = socket_path.decode('utf-8')
```

**2. Additional byte string check in PodmanClient:**
```python
# In src/mc/integrations/podman.py client property
def client(self) -> "podman.PodmanClient":
    if self._client is None:
        uri = get_socket_path()

        # Defensive: ensure uri is string, not bytes
        if isinstance(uri, bytes):
            uri = uri.decode('utf-8')

        def _connect():
            return podman.PodmanClient(base_url=uri, timeout=self._timeout)

        self._client = retry_podman_operation(_connect)
    return self._client
```

**3. Check config.toml for byte string literals:**
```bash
# User's config might have:
[podman]
socket_path = b''  # Invalid TOML, but check
```

**Investigation needed:**
- Print `type(uri)` and `repr(uri)` before passing to PodmanClient
- Check user's actual config.toml `socket_path` value
- Verify CONTAINER_HOST environment variable value and type

**Testing:**
- Test with empty socket_path in config
- Test with CONTAINER_HOST unset
- Test with CONTAINER_HOST set to valid path
- Test after config regeneration
