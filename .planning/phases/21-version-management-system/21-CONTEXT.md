# Phase 21: Version Management System - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Establish versions.yaml as single source of truth for image version, MC CLI version, and tool versions. Independent image versioning (x.y.z) decoupled from MC CLI version enables tool updates without code releases.

This phase creates the configuration file and defines the versioning schema - build automation that consumes it comes in Phase 22.

</domain>

<decisions>
## Implementation Decisions

### YAML Schema Structure
- Nested structure organized by category:
  - `image:` section with `version` field
  - `mc:` section with `version` field
  - `tools:` section with per-tool nested objects
- Tool entries use full metadata format:
  - `version`: semantic version (x.y.z)
  - `url`: template with {version} and {arch} variables
  - `checksum`: SHA256 hash for verification
  - `description`: human-readable tool description
- No schema metadata fields - keep file minimal (just versions)
- Image section contains only image version (MC version tracked separately under `mc:`)

### Version Numbering Policy
- **Independent versioning:** Image version (1.0.0) decoupled from MC CLI version (2.1.0)
- **Image version increments:** Patch bump every time image changes (tool updates, MC updates, Containerfile changes)
- **Tool URL templating:** URLs use {version} and {arch} placeholders (e.g., `https://github.com/org/repo/releases/download/v{version}/ocm-linux-{arch}`)
- **Semantic versioning enforced:** Build script validates x.y.z format, rejects invalid versions

### Version Change Workflow
- **Manual YAML edits:** Developers edit versions.yaml directly (no helper scripts)
- **Build-time validation:** Build script validates YAML syntax and semantics, fails build on invalid schema
- **URL reachability checks:** Build validates tool download URLs are reachable before attempting build (fail fast on 404)
- **Source of truth:** versions.yaml committed to git (note: future phases may generate from external sources)

### Backward Compatibility
- **Fresh start:** No legacy format support (this is first introduction of versions.yaml)
- **Required file:** Build fails with clear error if versions.yaml missing (no fallback defaults)
- **Optional tools:** Missing tool entries are skipped (only build defined tools)
- **Example template:** Include versions.yaml.example showing structure

### Claude's Discretion
- Exact YAML parser library choice
- Error message formatting and verbosity
- Example file content and comments
- Internal validation logic implementation

</decisions>

<specifics>
## Specific Ideas

- Template variables approach allows version updates without touching URLs
- Validation should fail fast - catch problems before expensive build starts
- Future: versions.yaml may be generated from external sources (noted for later phases)

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 21-version-management-system*
*Context gathered: 2026-02-09*
