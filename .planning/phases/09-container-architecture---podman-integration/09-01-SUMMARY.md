---
phase: 09-container-architecture---podman-integration
plan: 01
subsystem: infra
tags: [podman, podman-py, platform-detection, containers, macos, linux, rootless]

# Dependency graph
requires:
  - phase: 08-type-safety---modernization
    provides: Python 3.11+, mypy strict validation, comprehensive type coverage
provides:
  - Platform detection (macOS/Linux/unsupported) with lazy evaluation
  - Podman availability checking with version compatibility validation
  - macOS Podman machine auto-start prompting
  - Socket path resolution (rootless/rootful fallback, environment override)
  - podman-py 5.7.0+ dependency integration
affects: [09-02, 09-03, 11-container-lifecycle, 12-terminal-automation]

# Tech tracking
tech-stack:
  added: [podman-py>=5.7.0]
  patterns: [lazy platform detection, sliding window version compatibility, subprocess-based CLI integration]

key-files:
  created: [src/mc/integrations/platform_detect.py, tests/unit/test_platform_detect.py]
  modified: [pyproject.toml]

key-decisions:
  - "Use lazy platform detection (no import-time overhead, testable without Podman installed)"
  - "Implement sliding window version compatibility (warn at 3 versions behind, fail at 7+)"
  - "Socket path priority: CONTAINER_HOST env var > XDG_RUNTIME_DIR > UID-based path > rootful fallback"
  - "macOS Podman machine: prompt user to start if stopped (no silent auto-start)"

patterns-established:
  - "Pattern: Platform detection with subprocess-based Podman CLI interaction"
  - "Pattern: Comprehensive unit testing with pytest-mock for subprocess mocking"
  - "Pattern: Google-style docstrings with Args/Returns/Raises sections"

# Metrics
duration: 4min
completed: 2026-01-26
---

# Phase 09 Plan 01: Platform Detection & Podman Foundation Summary

**Platform detection module with macOS/Linux support, Podman availability checking, socket path resolution, and version compatibility validation via sliding window strategy**

## Performance

- **Duration:** 4 min
- **Started:** 2026-01-26T22:13:11Z
- **Completed:** 2026-01-26T22:17:08Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Platform detection supporting macOS (Darwin), Linux, and unsupported platforms with lazy evaluation
- Podman machine status checking for macOS with interactive auto-start prompting
- Socket path resolution with environment override, XDG_RUNTIME_DIR support, and rootless/rootful fallback
- Version compatibility checking using sliding window (warn at 3 versions behind, fail at 7+)
- 33 unit tests achieving 100% coverage on platform_detect module
- Type-safe implementation passing mypy --strict validation

## Task Commits

Each task was committed atomically:

1. **Task 1: Add podman-py dependency** - `a958307` (chore)
2. **Task 2: Create platform detection module** - `d3c88a9` (feat)
3. **Task 3: Create unit tests for platform detection** - `883c498` (test)

## Files Created/Modified

- `pyproject.toml` - Added podman>=5.7.0 to dependencies array
- `src/mc/integrations/platform_detect.py` - Platform detection module with 5 core functions (detect_platform, is_podman_machine_running, ensure_podman_ready, get_socket_path, check_podman_version)
- `tests/unit/test_platform_detect.py` - 33 comprehensive unit tests with full edge case coverage

## Decisions Made

**Platform detection strategy:**
- Lazy detection pattern (no import-time overhead)
- Simple platform.system() check returning 'macos', 'linux', or 'unsupported'
- Unsupported platforms show clear error with documentation link

**macOS Podman machine handling:**
- Check machine status via `podman machine list --format json`
- Interactive prompt if machine stopped: "Podman machine is stopped. Start it? [y/n]"
- No silent auto-start (respects user's resource preferences)
- Raise RuntimeError if user declines to start

**Socket path resolution:**
- Priority order: CONTAINER_HOST env var → XDG_RUNTIME_DIR/podman/podman.sock → /run/user/$UID/podman/podman.sock → /run/podman/podman.sock (rootful fallback)
- Return default rootless path even if socket doesn't exist yet (may be created on first Podman operation)
- macOS returns None for auto-detection by podman-py

**Version compatibility:**
- Sliding window strategy: warn at 3 minor versions behind, fail at 7+
- Expected baseline: Podman 5.0
- Handles version parsing with regex to support "-dev" suffixes
- FileNotFoundError and CalledProcessError treated as "not installed" (action='fail')

**Type safety:**
- Used `dict[str, Optional[int] | str]` for check_podman_version return type
- Passes mypy --strict validation
- Follows v1.0 type safety conventions (98% type coverage)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - all tasks completed without unexpected problems.

## User Setup Required

None - no external service configuration required. Podman installation is a system dependency documented in Phase 9 scope.

## Next Phase Readiness

**Ready for next plans:**
- Platform detection foundation enables Podman client wrapper (Plan 09-02)
- Socket path resolution ready for podman-py connection initialization
- Version checking provides early warning system for compatibility issues

**No blockers identified.**

**Testing coverage:**
- 100% line coverage on platform_detect module
- Comprehensive edge case coverage: macOS machine states, Linux rootless/rootful, error handling, version parsing
- Mock-based testing allows full test suite to run without Podman installed

**Known limitations:**
- Windows/BSD platforms return 'unsupported' with error message (by design - v2.0 targets macOS/Linux)
- Version compatibility assumes Podman 5.0 baseline (configurable via thresholds)
- Socket path fallback assumes standard Linux locations (override via CONTAINER_HOST env var)

---
*Phase: 09-container-architecture---podman-integration*
*Completed: 2026-01-26*
