# Phase 33: Container Setup — Config Mount & Claude Code - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Containerfile and container launch changes to: (1) mount `~/mc/config` read-only so `mc` inside the container finds its config without triggering the setup wizard, and (2) install the `claude` CLI inside the container image and mount host auth credentials so `claude` works inside the container without re-login. No new CLI commands, no new user-facing features — only Containerfile stages and podman run mount arguments.

</domain>

<decisions>
## Implementation Decisions

### Config mount scope
- Mount the entire `~/mc/config` directory (not just `config.toml`) — preserves the structure mc expects including `cache/`
- Mount target inside the container is the same path: `~/mc/config` (container user's home + `/mc/config`)
- Mount is entirely read-only — container cannot write to config or cache
- Mount is added as a runtime flag in the podman run command (`-v ~/mc/config:/home/user/mc/config:ro`), not declared in the Containerfile — this keeps it flexible across Linux and macOS hosts where the source path may differ

### Claude Code installation
- Install via `npm install -g @anthropic-ai/claude-code@VERSION` (npm global install, not binary download)
- Version is pinned — not latest — updated manually like other binary versions in the project
- Install goes in its own Containerfile stage named `claude-downloader` (mirrors the pattern used for `ocm-downloader` and `backplane-downloader`)
- Version tracked via `ARG CLAUDE_VERSION=X.Y.Z` at the top of the Containerfile alongside existing `OCM_VERSION`, `BACKPLANE_VERSION` ARGs

### Claude auth passthrough
- Mount the entire `~/.claude` directory from host into the container
- Mount target: same path `~/.claude` — claude CLI finds it automatically
- Mount is read-write (not read-only) — token refreshes and settings changes inside the container write back to the host
- Both mounts (`~/mc/config` and `~/.claude`) are added together in the same block in mc's container launch code

### Missing mounts behavior (pre-flight checks)
- Pre-flight checks run before podman run is constructed — fail fast
- `~/mc/config` missing on host: **hard failure** — container will not start. mc prints a clear error telling the user that config is missing and that host mc is responsible for setting up `~/mc/` and subdirectories
- `~/.claude` missing on host: **warn and continue** — container opens normally but mc prints a warning that claude will not be authenticated inside the container
- Different severity intentional: config is required for mc to work; Claude auth is optional

</decisions>

<specifics>
## Specific Ideas

- The user confirmed: setup of `~/mc/` and its subdirectories is the host mc's responsibility. The container should not create these — it should fail if they're absent.
- The multi-stage Containerfile pattern (`claude-downloader` stage) should be consistent with existing `ocm-downloader` and `backplane-downloader` stages.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 33-container-setup*
*Context gathered: 2026-03-20*
