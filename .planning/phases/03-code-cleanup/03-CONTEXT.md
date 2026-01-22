# Phase 3: Code Cleanup - Context

**Gathered:** 2026-01-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Clean up technical debt and fix bugs under the safety of test coverage from Phase 2. This includes consolidating configuration (migrate from environment variables to config file), fixing typos in CLI flags and status classes, removing duplicate code, and establishing single sources of truth for version management. Creating new capabilities belongs in other phases.

</domain>

<decisions>
## Implementation Decisions

### Configuration Approach
- **Config file required, no environment variables**: Remove all environment variable support (MC_BASE_DIR, etc.). Configuration comes exclusively from a config file.
- **Interactive setup wizard with defaults**: When config file doesn't exist on first run, launch interactive wizard that recommends sensible defaults (~/mc for base directory) but lets user customize.
- **Fail if env vars detected**: If MC_BASE_DIR (or other legacy env vars) is detected in the environment, fail immediately with clear error message before running any commands.
- **Shell-specific unset instructions**: Error message when env vars detected should provide copy-paste commands for unsetting in bash/zsh (`unset MC_BASE_DIR`) and fish (`set -e MC_BASE_DIR`).

### Breaking Changes Policy
- **Fix all typos now**: This is the right time for breaking changes. Fix typos in CLI flags and status classes even if it breaks existing usage. Clean slate approach.
- **Clean break, no shims**: No backward compatibility shims or legacy support. Remove old behavior completely (env vars, typo'd flags, duplicate code).
- **Fail with migration help**: When old usage patterns are detected (env vars, old flags), provide specific migration guidance in error message, not just generic failure.

### Claude's Discretion
- Config file location and format (INI, TOML, YAML, JSON) — choose based on Python ecosystem conventions and cross-platform compatibility
- Commit organization strategy — sequence commits for safety and clarity based on dependency analysis
- Task sequencing — order cleanup tasks based on what needs to happen before what
- Verification approach after each change — run full suite, affected tests only, or smart selection based on change impact
- Scope creep handling — use judgment to fix trivial inline issues but defer significant discoveries
- Migration documentation level — determine appropriate depth for migration guide/changelog
- Breaking changes communication — choose strategy appropriate for tool maturity (version bumping, changelog format)
- Error message design — craft helpful messages that guide users through migration
- Version access mechanism — choose approach that works in both development and installed environments (importlib.metadata, parse pyproject.toml, or generated version.py)
- Version display format — balance simplicity with diagnostic utility (version only, +Python info, +build info)
- Development version handling — distinguish dev/unreleased versions if helpful for troubleshooting
- Version placement — show version where most useful (--version only, debug output, help header)
- Setup.py migration verification — ensure complete metadata migration with appropriate testing
- pyproject.toml documentation — add inline comments where they genuinely help maintainability
- Version bump process — document or automate if needed for maintainability

</decisions>

<specifics>
## Specific Ideas

- "Fail if MC_BASE_DIR env variable exists and warn that these are no longer supported and to remove them from the environment to proceed"
- Error messages should provide shell-specific commands (bash/zsh vs fish) for removing environment variables

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-code-cleanup*
*Context gathered: 2026-01-22*
