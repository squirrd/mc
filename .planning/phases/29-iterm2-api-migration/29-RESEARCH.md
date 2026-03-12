# Phase 29: iTerm2 Python API Migration - Research

**Researched:** 2026-03-12
**Domain:** iTerm2 Python API, asyncio integration, macOS terminal automation
**Confidence:** HIGH (core API), MEDIUM (window ID format, focus details), LOW (connection timeout internals)

## Summary

Phase 29 replaces AppleScript-based window creation in `MacOSLauncher` with the `iterm2` Python
library (PyPI package `iterm2`, currently v2.14). The library communicates with iTerm2 over a
local WebSocket connection using protobuf. Script code is async (asyncio), and `iterm2.run_until_complete()`
bridges the sync/async boundary.

The standard pattern is: import iterm2 at runtime (catching `ImportError`), attempt connection with
a 5-second `asyncio.timeout()` context manager (Python 3.11+, already in this project's minimum),
fall back to Terminal.app if import fails or connection times out. Window IDs from the Python API
are UUID/GUID strings — different from the short numeric strings returned by AppleScript — so stale
AppleScript-era IDs in the registry must be treated as misses.

**Primary recommendation:** Use `iterm2.Window.async_create(connection, profile="MCC-Term", command=full_cmd)` inside `asyncio.timeout(5)`, return `window.window_id` for registry storage. Wrap all iterm2 logic in a sync bridge function. Fall back to the existing AppleScript path for Terminal.app and when the iterm2 library is unavailable.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| iterm2 | 2.14 (Feb 2026) | iTerm2 Python API | Official library from iTerm2 author |
| asyncio | stdlib (3.11+) | Async event loop | Required by iterm2 library |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| asyncio.timeout() | Python 3.11+ | Connection/operation timeout | Wrapping iterm2 calls with 5s limit |
| pathlib / datetime | stdlib | Once-per-day notice suppression | Lightweight file-based sentinel |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.timeout()` | `asyncio.wait_for()` | Both work on 3.11+; `timeout()` is cleaner as context manager, preferred |
| file-based notice sentinel | config entry | File sentinel (`~/.cache/mc/iterm2_fallback_date`) is simpler, no config schema change |

### Installation
```bash
uv add "iterm2>=2.14; sys_platform == 'darwin'"
```

Add to `pyproject.toml` optional-dependencies, NOT core dependencies:
```toml
[project.optional-dependencies]
macos = [
    "iterm2>=2.14; sys_platform == 'darwin'",
]
```

The library is macOS-only (iTerm2 is a macOS terminal). Using an optional extra prevents
installation errors on Linux. Graceful `ImportError` handling is the runtime gate, not the
packaging marker — the marker is a best-effort hint.

Add mypy override (library has no stubs):
```toml
[[tool.mypy.overrides]]
module = "iterm2.*"
ignore_missing_imports = true
```

## Architecture Patterns

### Recommended Project Structure
```
src/mc/terminal/
├── macos.py          # MacOSLauncher — PRIMARY file to modify
│                     #   Add _launch_via_iterm2_api() (sync bridge)
│                     #   Modify launch() to try API first, AppleScript fallback
│                     #   Modify _window_exists_by_id() to handle both ID formats
│                     #   Modify focus_window_by_id() similarly
├── launcher.py       # LaunchOptions, get_launcher() — unchanged
├── registry.py       # WindowRegistry — unchanged
└── attach.py         # attach_terminal() — unchanged (uses launcher.launch())
```

### Pattern 1: Sync Bridge for Async iterm2 API

The existing `MacOSLauncher.launch()` is synchronous. The iterm2 library requires asyncio.
The bridge pattern runs a new event loop inside the sync method:

```python
# Source: https://iterm2.com/python-api/tutorial/running.html
# run_until_complete() creates a new event loop, runs the coro, returns when done.
# Use this pattern rather than asyncio.run() to stay compatible with iterm2's own
# event loop management.

import iterm2

def _launch_via_iterm2_api(self, options: LaunchOptions) -> str | None:
    """Returns window_id on success, None on failure/timeout."""
    result: list[str | None] = [None]  # mutable container for async result

    async def main(connection: iterm2.Connection) -> None:
        try:
            async with asyncio.timeout(5):
                window = await iterm2.Window.async_create(
                    connection,
                    profile="MCC-Term",
                    command=options.command,
                )
                if window is not None:
                    result[0] = window.window_id
        except asyncio.TimeoutError:
            pass  # result stays None → caller falls back

    iterm2.run_until_complete(main)
    return result[0]
```

**Note:** `iterm2.run_until_complete(main)` calls `main(connection)` with a live connection.
It does NOT take a timeout parameter. The 5-second timeout must be applied INSIDE `main` using
`asyncio.timeout()`.

### Pattern 2: API Availability Detection

Two failure modes require different detection:

```python
# 1. Library missing — detect at import time
try:
    import iterm2  # noqa: F401
    _ITERM2_AVAILABLE = True
except ImportError:
    _ITERM2_AVAILABLE = False

# 2. API disabled or iTerm2 not running — detected at connection time.
# iterm2.connection.py catches (ConnectionRefusedError, OSError) when
# connecting. Without retry=True, it prints an error and raises.
# With retry=False (default), a failed connection raises immediately.
#
# Practical approach: wrap run_until_complete() in try/except Exception.
# If it raises (connection refused, API disabled), treat as API unavailable.

def _try_iterm2_api(self, options: LaunchOptions) -> str | None:
    if not _ITERM2_AVAILABLE:
        return None
    try:
        return self._launch_via_iterm2_api(options)
    except Exception:
        return None  # Connection failed → caller falls back
```

**Key insight:** `run_until_complete(main, retry=False)` (the default) will raise or print-and-exit
when connection fails. The exact exception type is `OSError`/`ConnectionRefusedError` from the
websockets layer. Catching `Exception` broadly is the safe approach here.

### Pattern 3: Window Existence and Focus via Python API

```python
# Source: https://iterm2.com/python-api/app.html
# App.get_window_by_id(window_id) returns Window | None

async def _check_window_exists_api(connection: iterm2.Connection, window_id: str) -> bool:
    app = await iterm2.async_get_app(connection)
    window = app.get_window_by_id(window_id)
    return window is not None

async def _focus_window_api(connection: iterm2.Connection, window_id: str) -> bool:
    app = await iterm2.async_get_app(connection)
    window = app.get_window_by_id(window_id)
    if window is None:
        return False
    # Must activate BOTH app and window for reliable focus
    await app.async_activate()
    await window.async_activate()
    return True
```

### Pattern 4: Window ID Format Difference

- **AppleScript-era IDs:** Short numeric strings (e.g., `"12345"`) or short labels
- **Python API window_id:** UUID-format strings (e.g., `"w1234567-abcd-..."`) or similar GUID

Registry entries have a `terminal_type` column (e.g., `"iTerm2"`). Use it to detect stale IDs:
if `terminal_type == "iTerm2"` but ID doesn't look like a UUID (no hyphens or too short),
treat as AppleScript-era miss and open a new window. Or simply: always treat Python API IDs
as the authoritative format going forward; stale entries will fail `get_window_by_id()` (returns
None) and be cleaned up naturally by the registry's lazy validation.

### Pattern 5: Once-Per-Day Fallback Notice

```python
import datetime
from pathlib import Path

_NOTICE_SENTINEL = Path.home() / ".cache" / "mc" / "iterm2_fallback_notice_date"

def _should_show_fallback_notice() -> bool:
    today = datetime.date.today().isoformat()
    try:
        return _NOTICE_SENTINEL.read_text().strip() != today
    except (OSError, FileNotFoundError):
        return True

def _record_fallback_notice_shown() -> None:
    today = datetime.date.today().isoformat()
    _NOTICE_SENTINEL.parent.mkdir(parents=True, exist_ok=True)
    _NOTICE_SENTINEL.write_text(today)
```

### Anti-Patterns to Avoid
- **Using `retry=True` in `run_until_complete`:** This makes the call block indefinitely until
  iTerm2 responds. Never use it in this context — we need the 5-second timeout behavior.
- **Calling `asyncio.run()` directly:** The iterm2 library manages its own event loop via
  `run_until_complete()`. Calling `asyncio.run()` can conflict with it.
- **Importing iterm2 at module level:** Must be inside a try/except or inside the function so
  Linux installs (where iterm2 is not installed) don't fail on import.
- **Storing `Window` objects across connections:** Each `run_until_complete()` call creates a
  fresh connection. Window objects are per-connection and cannot be reused.
- **Assuming window_id format is stable across AppleScript and Python API:** It is not.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Async-to-sync bridge | Custom event loop with asyncio.run() | `iterm2.run_until_complete(main)` | iterm2 manages its own loop setup; custom loops conflict |
| Connection timeout | asyncio.wait_for() on run_until_complete() | `asyncio.timeout(5)` inside the async main | run_until_complete() is sync; timeout must be inside the coro |
| Window lookup by ID | Iterating App.windows manually | `app.get_window_by_id(window_id)` | Built-in method; returns None cleanly if not found |

**Key insight:** The iterm2 library handles protobuf encoding, WebSocket management, and event loop
setup. Only the application-level logic (window ID storage, fallback routing, notice) needs custom
implementation.

## Common Pitfalls

### Pitfall 1: `run_until_complete` Has No Timeout Parameter
**What goes wrong:** Developer assumes `run_until_complete(main, timeout=5)` works, or tries to
wrap the entire `run_until_complete()` call in `asyncio.timeout()` (which is a sync call, not async).
**Why it happens:** The API name suggests it "runs until complete" — users expect a timeout arg.
**How to avoid:** Apply `asyncio.timeout(5)` INSIDE the `async def main(connection)` coroutine,
not outside `run_until_complete()`.
**Warning signs:** `TypeError: run_until_complete() got unexpected keyword argument 'timeout'`

### Pitfall 2: Connection Failure Exception Is Broad
**What goes wrong:** Code catches only `ConnectionRefusedError` but misses `OSError` (the actual
wrapper from websockets), or vice versa. iTerm2's `connection.py` catches both.
**Why it happens:** The websockets library wraps `ConnectionRefusedError` in `OSError` per
[websockets issue #593](https://github.com/aaugustin/websockets/issues/593).
**How to avoid:** Catch `Exception` broadly in the sync wrapper function, log the specific error
at debug level, then proceed to fallback.
**Warning signs:** Fallback not triggering when iTerm2 is not running.

### Pitfall 3: `command=` and `profile_customizations=` Are Mutually Exclusive
**What goes wrong:** Developer passes both `command=` and `profile_customizations=` to
`Window.async_create()`, causing a runtime error.
**Why it happens:** The API silently prioritizes one or the other in some versions; other versions
raise `CreateWindowException`.
**How to avoid:** Use only `profile="MCC-Term"` and `command=full_cmd`. Never combine with
`profile_customizations`.
**Warning signs:** `CreateWindowException` or unexpected behavior in window creation.

### Pitfall 4: Focusing Requires Both App and Window Activation
**What goes wrong:** `await window.async_activate()` alone doesn't bring iTerm2 to the foreground
if the app itself is not active.
**Why it happens:** macOS requires application-level activation separately from window-level focus.
**How to avoid:** Always call `await app.async_activate()` BEFORE `await window.async_activate()`.
**Warning signs:** Window appears to move but iTerm2 stays behind other apps.

### Pitfall 5: Stale AppleScript Window IDs in Registry
**What goes wrong:** Registry contains numeric window IDs from before Phase 29. Python API's
`get_window_by_id()` returns None for these (format mismatch), triggering unnecessary new window
creation.
**Why it happens:** AppleScript returns a short numeric ID; Python API uses UUID strings.
**How to avoid:** Accept this as correct behavior — stale entries will fail validation and be
removed by the registry's lazy cleanup. No special migration needed.
**Warning signs:** First run after migration always opens a new window even when one exists.
This is expected and self-corrects after one cycle.

### Pitfall 6: `iterm2` Package Is GPLv2 — Check License Compatibility
**What goes wrong:** Licensing conflict if mc-cli ever becomes proprietary.
**Why it happens:** The iterm2 PyPI package is licensed GPLv2+, not MIT like mc-cli.
**How to avoid:** Note this in planning. As an optional dependency invoked at runtime (not
distributed bundled), this is typically acceptable. Confirm with project owner.
**Warning signs:** Legal review flags GPLv2 optional dependency.

## Code Examples

Verified patterns from official sources:

### Create Window with Profile and Command
```python
# Source: https://iterm2.com/python-api/window.html
# Source: https://iterm2.com/python-api/examples/launch_and_run.html
import iterm2

async def main(connection: iterm2.Connection) -> None:
    async with asyncio.timeout(5):
        window = await iterm2.Window.async_create(
            connection,
            profile="MCC-Term",
            command="/bin/zsh -c 'podman exec -it mc-12345678 /bin/bash; exit'",
        )
        if window is not None:
            print(window.window_id)  # UUID string like "w0" or GUID

iterm2.run_until_complete(main)
```

### Focus Existing Window by ID
```python
# Source: https://iterm2.com/python-api/app.html (get_window_by_id, async_activate)
# Source: https://iterm2.com/python-api/window.html (Window.async_activate)
async def main(connection: iterm2.Connection) -> None:
    app = await iterm2.async_get_app(connection)
    window = app.get_window_by_id(stored_window_id)
    if window is not None:
        await app.async_activate()        # Bring iTerm2 app to foreground
        await window.async_activate()     # Bring specific window to front
```

### Check Window Exists by ID
```python
# Source: https://iterm2.com/python-api/app.html
async def main(connection: iterm2.Connection) -> None:
    app = await iterm2.async_get_app(connection)
    window = app.get_window_by_id(stored_window_id)
    exists = window is not None
```

### Import Guard Pattern
```python
# At module top — import lazily to support Linux installs
try:
    import iterm2 as _iterm2_module
    _ITERM2_LIB_AVAILABLE = True
except ImportError:
    _ITERM2_LIB_AVAILABLE = False
```

### Bridging sync/async in MacOSLauncher.launch()
```python
# Source: iterm2 connection.py — run_until_complete is the correct bridge
def _run_iterm2_coro(self, coro_factory: ...) -> ...:
    """Run an iterm2 async operation synchronously."""
    import iterm2
    result_holder: list[...] = [None]

    async def main(connection: iterm2.Connection) -> None:
        async with asyncio.timeout(5):
            result_holder[0] = await coro_factory(connection)

    try:
        iterm2.run_until_complete(main)  # retry=False (default) — fail fast
    except Exception:
        pass  # Connection failed; result_holder stays None

    return result_holder[0]
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `write text` AppleScript | `command=` in `Window.async_create` | Phase 29 | Command no longer echoed to terminal |
| AppleScript `create window with default profile` | `Window.async_create(profile="MCC-Term")` | Phase 29 | Custom profile applied |
| `subprocess.Popen` + daemon thread (fire-and-forget) | `iterm2.run_until_complete()` (blocking) | Phase 29 | Window ID available synchronously after launch |
| AppleScript `id of current window` (numeric) | `window.window_id` (UUID string) | Phase 29 | Registry ID format changes; stale entries invalidated |

**Deprecated/outdated after Phase 29:**
- `_build_iterm_script()`: Replaced by Python API for window creation
- AppleScript `_capture_window_id()` for iTerm2: Replaced by `window.window_id` from API
- `_window_exists_by_id()` (AppleScript) for iTerm2: Replaced by `app.get_window_by_id()`
- `focus_window_by_id()` (AppleScript) for iTerm2: Replaced by `app/window.async_activate()`

All AppleScript paths KEPT for Terminal.app fallback.

## Open Questions

1. **Exact exception type from `run_until_complete` on connection failure**
   - What we know: `connection.py` catches `(ConnectionRefusedError, OSError)` and without
     `retry=True` it prints a message. The outer behavior (raise vs sys.exit) is unverified.
   - What's unclear: Does it raise the OSError to the caller, or does it call `sys.exit()`?
   - Recommendation: During implementation, test by calling `run_until_complete` with iTerm2
     closed. If it calls `sys.exit()`, we need to intercept differently (e.g., mock or
     subprocess isolation). LOW confidence.

2. **`window_id` format in practice**
   - What we know: It's a `str` returned by `window.window_id`. Documentation shows it's a
     UUID-like GUID. Some sources mention short strings like `"w0"`.
   - What's unclear: The actual format on the production version (2.14).
   - Recommendation: Log the actual `window_id` value in the first implementation run to
     verify format before writing ID-format detection logic.

3. **`asyncio.timeout()` inside `run_until_complete` — does it work?**
   - What we know: `run_until_complete` creates and runs an event loop. `asyncio.timeout()`
     is a stdlib async context manager (Python 3.11+) that works within any running event loop.
   - What's unclear: Whether iterm2's event loop setup interferes with `asyncio.timeout`.
   - Recommendation: HIGH confidence this works (asyncio.timeout is loop-agnostic). Verify
     in integration test. If it doesn't work, fall back to `asyncio.wait_for()`.

## Sources

### Primary (HIGH confidence)
- [iterm2.com/python-api/window.html](https://iterm2.com/python-api/window.html) — `async_create`, `window_id`, `async_activate`
- [iterm2.com/python-api/app.html](https://iterm2.com/python-api/app.html) — `async_get_app`, `get_window_by_id`, `async_activate`
- [iterm2.com/python-api/examples/launch_and_run.html](https://iterm2.com/python-api/examples/launch_and_run.html) — canonical create-window example
- [pypi.org/project/iterm2/](https://pypi.org/project/iterm2/) — current version (2.14), license (GPLv2+)

### Secondary (MEDIUM confidence)
- WebSearch confirmed: `run_until_complete(main, retry=False)` behavior — catches `(ConnectionRefusedError, OSError)`
- WebSearch confirmed: `asyncio.timeout()` (Python 3.11+) works inside async coroutines
- WebSearch confirmed: `get_window_by_id()` on `App` takes string ID, returns `Window | None`
- [iterm2.com/python-api/tutorial/running.html](https://iterm2.com/python-api/tutorial/running.html) — `run_until_complete` / `retry` param

### Tertiary (LOW confidence)
- window_id format (UUID vs short string) — derived from source code snippets in WebSearch, not directly verified from running code
- Whether `run_until_complete` raises or calls `sys.exit()` on connection failure — inferred from `connection.py` source snippets

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyPI page confirmed current version; official docs verified API signatures
- Architecture: HIGH (patterns), MEDIUM (window ID format details)
- Pitfalls: HIGH (connection error types from official source); MEDIUM (focus behavior, from docs + deduction)

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable API; iterm2 library releases frequently but API surface is stable)
