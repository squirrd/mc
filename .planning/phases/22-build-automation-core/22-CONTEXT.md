# Phase 22: Build Automation Core - Context

**Gathered:** 2026-02-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Automate container builds with version extraction and orchestration. The build script reads versions.yaml, calls podman build with --build-arg flags, tags images with semantic versioning, supports dry-run mode, and is architecture-aware (amd64 foundation). This phase focuses on the build automation itself - not on adding new container features or tools.

</domain>

<decisions>
## Implementation Decisions

### Script Interface Design
- Invocation pattern: `./build-container.sh [OPTIONS]` with optional flags
- versions.yaml location: Hardcoded path at `container/versions.yaml` (no configuration needed)
- Supported flags:
  - `--dry-run` - Preview build without executing (validation and output only)
  - `--verbose` - Show detailed output during execution (useful for debugging)
  - `--help` - Display usage information, available flags, and examples

### Error Handling Strategy
- versions.yaml validation: Fail immediately with clear error if missing or malformed
- Version number validation: Strict semantic versioning only (x.y.z format required)
- podman build failures: Show podman error plus troubleshooting hints (check podman running, permissions, etc.)
- Preflight checks: Validate podman is installed, accessible, AND machine is running before starting
- Philosophy: Fail fast with helpful error messages rather than trying to proceed with defaults

### Dry-Run Behavior
- Display: Show parsed version numbers, exact build command preview, and tags that would be created
- Validation: Full validation in dry-run mode (file exists, podman available, version format) - reliable preview
- Output includes:
  - Image version, MC CLI version, tool versions from versions.yaml
  - Complete podman build command with all --build-arg flags
  - Both versioned tag (e.g., mc-rhel10:1.0.0) and :latest tag

### Build Feedback
- Progress information:
  - Major step announcements (Reading versions.yaml, Starting build, Tagging image)
  - Version info shown at start before podman build runs
  - Podman build output suppressed by default, shown only with --verbose
- Success message includes:
  - Image name and tags created
  - Build time (how long it took)
- Output format: Clean, CI-friendly output (no special characters/colors, predictable format for logs)
- Philosophy: Brief and informative by default, detailed when requested

### Claude's Discretion
- Default verbosity level (without --verbose flag) - determine appropriate balance
- Dry-run visual distinction (how to make it obvious this is preview-only)
- Dry-run exit code behavior (success vs special code)
- Exact troubleshooting hints to show on podman errors
- Specific format/wording of progress messages and success output

</decisions>

<specifics>
## Specific Ideas

- Preflight check must verify both podman installation AND that the podman machine is running
- Error messages should be actionable - tell users what's wrong and what to do about it
- Architecture-aware foundation means amd64 for now, but designed to extend to multi-arch later

</specifics>

<deferred>
## Deferred Ideas

None - discussion stayed within phase scope

</deferred>

---

*Phase: 22-build-automation-core*
*Context gathered: 2026-02-09*
