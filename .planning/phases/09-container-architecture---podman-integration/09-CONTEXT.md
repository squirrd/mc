# Phase 9: Container Architecture & Podman Integration - Context

**Gathered:** 2026-01-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish rootless Podman integration with platform detection and UID/GID mapping so developers can connect to containers with correct file permissions. This phase provides the foundation for container orchestration - creating, managing, and executing commands in containers comes in later phases.

</domain>

<decisions>
## Implementation Decisions

### Platform detection & auto-start
- Lazy detect platform on first Podman operation (not at module import time)
- On macOS: auto-start Podman machine with user prompt if stopped ("Podman machine is stopped. Start it? [y/n]")
- On unsupported platforms (Windows, BSD): show documented fallback error with link to docs explaining requirements and workarounds
- Verify Podman installation during platform detection (check `podman --version` works, fail early with helpful message)

### UID/GID mapping strategy
- Always use `--userns=keep-id` for rootless containers (hard-coded, not configurable)
- On permission denied errors despite :U suffix: offer to fix permissions interactively ("Fix workspace permissions? [y/n]" then run chown)

### Configuration & connection
- Podman API timeout: user-configurable in config file (add `podman.timeout` setting)
- Retry behavior: auto-retry failed API calls up to 3 times with exponential backoff (handles transient socket errors transparently)

### Error messages & validation
- Validation timing: lazy validation (only validate what's needed for current operation, not comprehensive upfront checks)
- Error detail level: include diagnostics in error messages (e.g., "Cannot connect to Podman socket at /run/user/1000/podman/podman.sock")
- Version compatibility: sliding window approach
  - Warn if Podman version is 3+ versions behind the version at container build time
  - Fail/require update if 7+ versions behind
  - This ensures compatibility without forcing bleeding-edge updates
- API error handling: map common Podman API errors to user-friendly messages (e.g., "Image not found" → "Run: podman pull <image>")

### Claude's Discretion
- :U volume suffix strategy (always append, conditional on mount type, or conditional on ownership)
- UID validation after container start (validate or trust --userns=keep-id)
- Podman socket location detection method (standard paths, config-first, or environment variable)
- Rootless vs rootful detection approach (socket path heuristic, API query, or assume rootless)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches based on Podman best practices and existing codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope (Podman integration foundation). Container lifecycle operations (create, list, stop, delete) are Phase 11. Terminal automation is Phase 12. Salesforce integration is Phase 10.

</deferred>

---

*Phase: 09-container-architecture---podman-integration*
*Context gathered: 2026-01-26*
