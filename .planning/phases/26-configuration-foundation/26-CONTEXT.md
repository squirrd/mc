# Phase 26: Configuration Foundation - Context

**Gathered:** 2026-02-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Extend the existing TOML config system to persist version management fields (pinned_mc_version, last_version_check) with safe concurrent write patterns and atomic operations. This phase builds the foundation data layer for version checking functionality.

</domain>

<decisions>
## Implementation Decisions

### Config file structure
- Use **[version] section** to group version management fields (cleaner organization, future extensibility)
- Field names: **pinned_mc** and **last_check** (short, concise names)
- Default value: **"latest"** for pinned_mc when not specified
- User requested simplicity throughout

### Concurrent write safety
- **Skip file locking** — assume single-user/single-process usage is typical
- No special documentation of this assumption needed
- Can add locking later if concurrent scenarios emerge

### Atomic write pattern
- Use temp file + rename pattern to prevent partial writes
- All implementation details deferred to Claude's discretion with directive: **keep it as simple as possible**
- Temp file naming, rename failure handling, and cleanup of abandoned temp files all simplified

### Backward compatibility
- Return **"latest"** as default for pinned_mc when [version] section is missing
- Return None for last_check when missing
- Migration strategy and schema_version field handling deferred to Claude with directive: **keep it simple**

### Claude's Discretion
- Temp file naming convention (random suffix vs .tmp)
- Rename failure handling (cleanup vs leave for debugging)
- Abandoned temp file cleanup strategy
- Config migration approach (auto-migrate vs lazy)
- Schema versioning decision (add now vs later)
- Inline comments in TOML for field documentation
- Overall implementation: **prioritize simplicity**

</decisions>

<specifics>
## Specific Ideas

- User emphasized **"keep it simple"** multiple times — avoid over-engineering
- Default for pinned_mc should be **"latest"** (not None)
- No need for file locking complexity given typical single-process usage

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 26-configuration-foundation*
*Context gathered: 2026-02-19*
