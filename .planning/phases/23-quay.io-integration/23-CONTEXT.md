# Phase 23: Quay.io Integration - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Registry integration for version staleness detection and intelligent version management. Query quay.io to detect if versions already exist, compare image digests to determine if changes require version bumps, and coordinate with the build automation system to prevent conflicts and unnecessary publishes.

Publishing to registry (--push) is Phase 25. This phase focuses on querying and version coordination.

</domain>

<decisions>
## Implementation Decisions

### Registry query behavior
- Query registry on every build (default behavior, not opt-in)
- No caching of query results - always fetch real-time data for accuracy
- Retrieve two pieces of information:
  - Latest versioned tag (highest semantic version, ignoring :latest)
  - Check if specific version from versions.yaml exists on registry
- Support optional authentication:
  - Try authenticated access if credentials available (from podman login)
  - Fall back to anonymous for public image queries
  - If authentication explicitly provided but fails, fail the build (don't silently downgrade)

### Version conflict handling - Change-based bumping
- **Core principle:** Version bumps only when actual image changes detected
- Version bumping workflow:
  1. Build the image first (using current versions.yaml)
  2. Get image digest (SHA256)
  3. Query registry for latest image digest
  4. If digests differ → auto-bump patch version in versions.yaml
  5. If digests match → no bump needed (no publish required)
- Auto-bump updates versions.yaml on disk (persistent change)
- No override flags for auto-bump behavior (always automatic when changes detected)
- Bump validation:
  - If bumping would cross minor version boundary (e.g., 1.0.9 → 1.1.x already exists), fail the build
  - Requires manual version update in versions.yaml for minor/major changes
  - Auto-bump only increments patch version within current minor version

### Failure recovery modes
- Network failures (unreachable, timeout): Fail the build (hard error)
- Rate limiting: Hybrid approach
  - If retry-after header provided by quay.io, respect it and wait
  - Otherwise use exponential backoff with maximum retry limit
  - After retries exhausted, fail the build
- Authentication failures: Fail the build (invalid credentials are errors)
- Unexpected errors (500, invalid JSON, etc.): Fail the build (no retries for server errors)
- Error handling philosophy: Fail-fast for reliability in CI/CD pipelines

### Feedback and visibility
- Display during registry queries:
  - Query status: "Querying quay.io for latest version..." with progress
  - Latest registry version: "Latest on quay.io: 1.0.5" (or "No versions published")
  - Comparison result: "Local version matches" vs "differs from registry"
  - Digest comparison: Show digests and match/differ status
- Verbosity control:
  - Default: Show key information (status, versions, comparison, digest)
  - --verbose flag: Add API details, timing, HTTP responses
  - No --quiet flag (keep build output informative by default)
- Auto-bump notification: Simple message "Version bumped: 1.0.5 → 1.0.6 (image changed)"
- Machine-readable output:
  - --json flag: Output structured JSON with version, digest, changed, bumped fields
  - For CI/CD pipeline consumption and automation

### Claude's Discretion
- Exact registry API endpoint paths and parameters
- HTTP timeout values and retry delay calculations
- JSON schema structure for --json output
- Progress indicator implementation (spinner, dots, etc.)
- Error message formatting and color coding

</decisions>

<specifics>
## Specific Ideas

- Change detection is digest-based, not version-based - even if versions.yaml changes, only bump if the built image actually differs
- Must work efficiently in CI/CD pipelines (GitHub Actions, Quay.io automation) without pulling images
- Bandwidth and time considerations: Don't pull entire images, only query metadata/digests
- Build-first approach: Can't know if image changed without building it first

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 23-quay.io-integration*
*Context gathered: 2026-02-10*
