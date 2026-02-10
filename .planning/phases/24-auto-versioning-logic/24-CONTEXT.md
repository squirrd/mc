# Phase 24: Auto-Versioning Logic - Context

**Gathered:** 2026-02-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Intelligent patch version bumping for container images based on digest comparison. Build script queries quay.io registry, builds image locally, compares digests, and auto-bumps/publishes only when content changes. Manual minor version management in versions.yaml.

</domain>

<decisions>
## Implementation Decisions

### Versioning Model
- versions.yaml contains `image.version: "x.y"` (e.g., "1.2") — manually managed minor version
- Patch version (z in x.y.z) is auto-calculated at build time — never stored in versions.yaml
- Adding new tools triggers manual minor bump (1.2 → 1.3) — no enforcement, trust developer
- Patch version continues indefinitely (1.2.0 → 1.2.100+) until minor bump resets it

### Bump Trigger Detection
- **Trigger:** Building a new image (not tool version changes)
- **Detection:** Compare image digest (not versions.yaml content)
- Build flow:
  1. Read versions.yaml → image.version = "1.2"
  2. Query quay.io → latest 1.2.* = "1.2.17"
  3. Build image locally (always build to get digest)
  4. Compare new image digest vs quay.io 1.2.17 digest
  5. If same digest → No-op (no bump, no push)
  6. If different digest → Auto-bump to 1.2.18, tag, auto-push

### Registry as Source of Truth
- quay.io registry determines current patch version, not local files
- Query quay.io for latest tag matching "x.y.*" pattern (e.g., "1.2.*")
- If no matching tags exist (new minor version or first build), start at x.y.0
- Example: versions.yaml has "1.3", quay.io has 1.3.11 → next version is 1.3.12

### Failure Handling
- **Registry query failure:** Fail hard — error and stop build
- **Reason:** Build requires registry connectivity to determine version and compare digests
- **No fallback:** Forces user to fix network/auth issues before building

### Digest Comparison
- Use quay.io API manifest query (skopeo inspect or direct API) to get published image digest
- Compare manifest digest without pulling full image (network-only, fast)
- No --force-bump override — digest comparison is always authoritative
- To re-release same content: manually bump minor version in versions.yaml

### Auto-Push Behavior
- When digest differs: automatically push to quay.io after tagging
- No --push flag required — content change = automatic publish
- Tag both versioned (1.2.18) and :latest tags before push

### Claude's Discretion
- YAML structure for image.version (string "1.2" vs separate major/minor fields)
- Exact quay.io API implementation (skopeo vs direct API calls)
- Error message formatting and verbosity
- Logging format for version determination steps

</decisions>

<specifics>
## Specific Ideas

- Always build first, then compare — this ensures we have an actual digest to compare, not guessing from file changes
- Patch version can grow indefinitely (1.2.157 is fine) until developer manually bumps minor version
- No hybrid states — either identical (no action) or different (bump + push)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 24-auto-versioning-logic*
*Context gathered: 2026-02-10*
