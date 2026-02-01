---
created: 2026-02-01T18:43
title: Fix Podman URI scheme error - byte string passed instead of decoded string
area: api
files:
  - src/mc/integrations/podman.py:130
  - src/mc/integrations/platform_detect.py:96-141
---

## Problem

Running `mc container list` on macOS fails with a ValueError from podman-py library:

```
ValueError: The scheme 'b''' must be one of ('unix', 'http+unix', 'ssh', 'http+ssh', 'tcp', 'http')
```

**Full traceback:**
```
File "/Users/dsquirre/Repos/mc/src/mc/cli/commands/container.py", line 63, in list_containers
    containers = manager.list()
File "/Users/dsquirre/Repos/mc/src/mc/container/manager.py", line 213, in list
    containers = self.podman.client.containers.list(
File "/Users/dsquirre/Repos/mc/src/mc/integrations/podman.py", line 133, in client
    self._client = retry_podman_operation(_connect)
File "/Users/dsquirre/Repos/mc/src/mc/integrations/podman.py", line 130, in _connect
    return podman.PodmanClient(base_url=uri, timeout=self._timeout)
File ".../podman/api/client.py", line 189, in _normalize_url
    raise ValueError(...)
```

**Discovered during:** Test 2.2 (List Containers) in manual UAT testing

**Root cause analysis:**

The error message "The scheme 'b'''" (note the 'b' prefix) indicates that podman-py is receiving a byte string instead of a regular string for the base_url parameter.

On macOS:
1. `get_socket_path('macos')` returns `None` (line 138 in platform_detect.py) to trigger podman-py auto-detection
2. `PodmanClient(base_url=None, ...)` is called (line 130 in podman.py)
3. podman-py attempts to auto-detect socket from podman machine config
4. Something in the auto-detection chain returns bytes instead of a decoded string

**Possible causes:**
- podman-py library bug in auto-detection (reads config file as bytes)
- Environment variable or config file being read without proper decoding
- podman machine command output not being decoded (subprocess without text=True)

**User impact:**
All container lifecycle commands fail on macOS (list, stop, delete, exec). The container creation and terminal attachment might work if they bypass the list operation.

## Solution

**Investigation needed:**
1. Check what podman-py does when base_url=None on macOS
2. Verify if this is a podman-py version issue (5.7.0 currently in use)
3. Test if explicitly providing the socket path avoids the issue

**Potential fixes:**

**Option 1: Explicit socket path on macOS**
Instead of returning `None` for macOS, query podman machine to get the actual socket path:
```python
elif platform_type == 'macos':
    # Query podman machine for socket path instead of relying on auto-detection
    result = subprocess.run(
        ['podman', 'machine', 'inspect', '--format', '{{.ConnectionInfo.PodmanSocket.Path}}'],
        capture_output=True,
        text=True,  # CRITICAL: Ensure string, not bytes
        check=True
    )
    return result.stdout.strip()
```

**Option 2: Decode in uri construction**
Add defensive decoding in podman.py before constructing URI:
```python
if socket_path:
    # Ensure socket_path is str, not bytes
    if isinstance(socket_path, bytes):
        socket_path = socket_path.decode('utf-8')
    uri = f"unix://{socket_path}"
```

**Option 3: Update podman-py**
Check if newer podman-py version (>5.7.0) fixes this issue.

**Testing:**
After fix, verify all container commands work on macOS:
- `mc container list`
- `mc container create <case>`
- `mc container stop <case>`
- `mc container delete <case>`
- `mc container exec <case> ls`
