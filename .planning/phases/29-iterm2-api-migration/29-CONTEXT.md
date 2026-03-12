# Phase 29: iTerm2 API Migration - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace AppleScript-based window creation in `MacOSLauncher` with the `iterm2` Python library.
Covers: new window creation via Python API with `MCC-Term` profile, clean terminal startup
(podman exec command hidden), and Terminal.app fallback when iTerm2 Python API is unavailable.
Window focus/existence check also migrated to Python API where feasible; AppleScript used as
fallback where Python API is too difficult or impossible.

</domain>

<decisions>
## Implementation Decisions

### Fallback UX
- Brief stderr notice when falling back: "iTerm2 API unavailable, using Terminal.app"
- Notice includes setup hint: "Enable via iTerm2 > Settings > General > Magic > Enable Python API"
- Notice shown once per day (like update banners) — suppressed on subsequent invocations within same calendar day
- Three conditions trigger fallback: library not installed (`import iterm2` fails), API not enabled
  (library installed but iTerm2 rejects connection), connection timeout (5s)
- "iTerm2 not running" implicitly covered by connection timeout

### Duplicate Prevention
- Window focus behavior must be preserved — `mc case XXXXX` twice should focus the existing window
- Python API used for everything including focus/existence check where the API supports it
- AppleScript used as fallback only where Python API is too difficult or impossible
- If stored window ID format doesn't match (stale AppleScript-era ID in registry): treat as not found,
  open a new window, update registry with new Python API window ID

### Launch Timing
- Wait for confirmation: block until iTerm2 confirms window opened (enables reliable window ID capture)
- Timeout: 5 seconds — if iTerm2 doesn't respond within 5s, treat as failure
- This replaces the current fire-and-forget (Popen + daemon thread) pattern for iTerm2 path

### API Failure Handling
- Two distinct failure modes with different behavior:
  1. **API unavailable at startup** (library missing, API disabled, timeout) → fall back to Terminal.app
     with stderr notice + setup hint (once per day)
  2. **API call fails mid-operation** (async_create raises exception) → fail with error message,
     no fallback
- Error message format for mid-operation failure:
  "iTerm2 API error: [exception message]. Try: check iTerm2 is running and API is enabled in Settings > General > Magic"

### Claude's Discretion
- How to bridge `iterm2.run_until_complete()` (blocking async) with existing sync MacOSLauncher
- Whether to store the Python API window ID as-is or normalize to a common format
- Which specific window focus/existence operations are feasible via Python API vs require AppleScript
- The `iterm2` library dependency: optional macOS extra in pyproject.toml vs graceful import-time miss
- Once-per-day fallback notice suppression mechanism (config vs lightweight cache file)

</decisions>

<specifics>
## Specific Ideas

- User provided example API usage:
  ```python
  async def main(connection):
      full_command = f"/bin/zsh -c 'podman exec -it {container_id} {internal_cmd}'"
      await iterm2.Window.async_create(connection, profile="Default", command=full_command)
  iterm2.run_until_complete(main)
  ```
  Profile should be `"MCC-Term"` (already exists in user's iTerm2).

- Command hiding works naturally via `command=` parameter in `async_create` — the command runs
  directly without being echoed as a shell input, unlike the current `write text` AppleScript approach.

- User's actual terminal currently shows the raw podman command twice (once as command, once as prompt)
  because the current approach types it into the shell. Python API eliminates this.

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope.

</deferred>

---

*Phase: 29-iterm2-api-migration*
*Context gathered: 2026-03-12*
