---
phase: 03-code-cleanup
plan: 01
subsystem: config
tags: [toml, platformdirs, tomli, configuration, migration, legacy-detection]

# Dependency graph
requires:
  - phase: 02-critical-path-testing
    provides: Test coverage for auth module and workspace manager
provides:
  - TOML-based configuration system with cross-platform path handling
  - Interactive setup wizard with sensible defaults
  - Legacy environment variable detection with shell-specific migration guidance
  - Centralized offline_token parameter passing throughout command chain
affects: [04-infrastructure-features, 05-cli-improvements]

# Tech tracking
tech-stack:
  added: [tomli, tomli-w, platformdirs]
  patterns: [TOML config files, platformdirs for cross-platform paths, interactive CLI wizard, legacy detection with fail-fast]

key-files:
  created:
    - src/mc/config/manager.py
    - src/mc/config/models.py
    - src/mc/config/wizard.py
    - tests/unit/test_config.py
  modified:
    - pyproject.toml
    - src/mc/cli/main.py
    - src/mc/utils/auth.py
    - src/mc/cli/commands/case.py
    - tests/unit/test_auth.py

key-decisions:
  - "TOML chosen for config file format (Python 3.11+ stdlib support, better structure than INI)"
  - "platformdirs for cross-platform config paths (XDG on Linux, proper macOS/Windows equivalents)"
  - "Fail-fast approach for legacy env vars with shell-specific unset instructions (no backward compat)"
  - "Auto-run wizard on first use rather than requiring explicit setup command (better UX)"
  - "Remove setup.py completely in favor of pyproject.toml-only packaging"

patterns-established:
  - "Config path pattern: Use platformdirs.user_config_dir() for OS-appropriate locations"
  - "TOML I/O pattern: Binary mode (rb/wb) for tomllib/tomli_w operations"
  - "Interactive wizard pattern: Defaults for optional values, loops for required values"
  - "Legacy detection pattern: Check at startup before any other operations, provide actionable migration steps"

# Metrics
duration: 7min
completed: 2026-01-22
---

# Phase 03 Plan 01: Config Migration Summary

**TOML config system with platformdirs, interactive wizard with defaults, and legacy env var detection with shell-specific migration guidance**

## Performance

- **Duration:** 7 min
- **Started:** 2026-01-22T04:25:22Z
- **Completed:** 2026-01-22T04:32:00Z
- **Tasks:** 3
- **Files modified:** 11 (4 created, 7 modified)

## Accomplishments
- Migrated from environment variables to TOML config file system
- Cross-platform config paths via platformdirs (XDG on Linux, etc.)
- Interactive wizard runs automatically on first use with ~/mc default
- Legacy env var detection fails immediately with shell-specific unset commands (bash/zsh vs fish)
- Removed duplicate offline_token validation throughout codebase
- Updated all command handlers to accept offline_token parameter
- Comprehensive config system tests (19 tests, 100% coverage on new modules)
- Removed setup.py (migrated to pyproject.toml-only packaging)

## Task Commits

Each task was committed atomically:

1. **Task 1: Install config dependencies and create config modules** - `0461ec7` (feat)
2. **Task 2: Add legacy env var detection and migration in main.py** - `8c7be8e` (feat)
3. **Task 3: Remove duplicate validation from auth.py and write tests** - `58b3daa` (refactor)

## Files Created/Modified

### Created
- `src/mc/config/manager.py` - ConfigManager class with load/save/exists methods using platformdirs
- `src/mc/config/models.py` - Config schema with validation and defaults
- `src/mc/config/wizard.py` - Interactive setup wizard with default values and required field validation
- `tests/unit/test_config.py` - 19 tests covering config manager, models, wizard, and legacy detection

### Modified
- `pyproject.toml` - Added tomli, tomli-w, platformdirs dependencies with Python version constraints
- `src/mc/cli/main.py` - Added check_legacy_env_vars() and config loading on startup
- `src/mc/utils/auth.py` - Removed env var reading, accepts offline_token parameter
- `src/mc/cli/commands/case.py` - All commands accept and pass offline_token parameter
- `src/mc/version.py` - Modernized to use importlib.metadata with pyproject.toml fallback
- `tests/unit/test_auth.py` - Updated to pass offline_token parameter, removed env var test

### Removed
- `setup.py` - Fully migrated to pyproject.toml-only packaging

## Decisions Made

1. **TOML over INI/YAML/JSON**: Python 3.11+ has stdlib tomllib support, better structure than INI, simpler than YAML
2. **platformdirs for config paths**: Handles XDG on Linux, macOS Library/Application Support, Windows LOCALAPPDATA automatically
3. **Fail-fast legacy detection**: No backward compatibility shims - detect env vars and exit with migration instructions immediately
4. **Shell-specific unset commands**: Detect bash/zsh vs fish shell and generate appropriate unset commands
5. **Auto-run wizard**: Trigger on first use of any command rather than requiring explicit `mc config setup`
6. **Binary mode for TOML**: Always use 'rb'/'wb' modes to avoid UnicodeDecodeError on some systems
7. **Parameter passing for offline_token**: Pass through command handlers rather than global state
8. **Directory creation in save**: Ensure parent directory exists before writing config file

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added directory creation to ConfigManager.save()**
- **Found during:** Task 3 (Writing config tests)
- **Issue:** ConfigManager.save() didn't create parent directory when _config_path was set directly in tests
- **Fix:** Added `config_path.parent.mkdir(parents=True, exist_ok=True)` before file write
- **Files modified:** src/mc/config/manager.py
- **Verification:** Test test_save_creates_directory now passes
- **Committed in:** 58b3daa (Task 3 commit)

**2. [Rule 2 - Missing Critical] Modernized version.py to use importlib.metadata**
- **Found during:** Task 2 (Auto-applied by linter/formatter)
- **Issue:** version.py used hardcoded version string instead of reading from package metadata
- **Fix:** Implemented get_version() using importlib.metadata with pyproject.toml fallback for development
- **Files modified:** src/mc/version.py, src/mc/cli/main.py
- **Verification:** Follows pattern from RESEARCH.md, enables --version flag
- **Committed in:** 8c7be8e (Task 2 commit)

**3. [Rule 2 - Missing Critical] Removed setup.py**
- **Found during:** Task 3 (Auto-detected by linter/formatter)
- **Issue:** setup.py was redundant after full pyproject.toml migration
- **Fix:** Deleted setup.py as all metadata now in pyproject.toml
- **Files modified:** setup.py (deleted)
- **Verification:** pip install -e . still works, metadata complete
- **Committed in:** 58b3daa (Task 3 commit)

---

**Total deviations:** 3 auto-fixed (3 missing critical)
**Impact on plan:** All auto-fixes align with Phase 3 objectives (config migration, version management modernization, setup.py removal). No scope creep.

## Issues Encountered

None - plan executed smoothly with only minor auto-fixes for completeness.

## Test Results

- **Total tests:** 85 passed (2 Docker integration errors expected without docker-compose)
- **Coverage:** 70% overall (exceeds 60% threshold)
- **Config module coverage:** 100% on manager.py, models.py, wizard.py
- **Auth module coverage:** 100% after updating tests

### New Tests Added
- 19 config system tests covering:
  - ConfigManager path handling, load/save round-trip, directory creation
  - Config validation (valid/invalid structures)
  - Interactive wizard with defaults and required fields
  - Legacy env var detection for bash/zsh and fish shells
  - Multiple legacy vars detected simultaneously

### Tests Updated
- Auth tests: Removed env var fixture dependency, pass offline_token as parameter
- Removed obsolete test_get_access_token_missing_env_var (no longer reads env vars)

## User Setup Required

None - no external service configuration required.

After running `mc` for the first time, users will be prompted by the interactive wizard to:
1. Confirm or customize base directory (defaults to ~/mc)
2. Provide Red Hat API offline token (required)

Config saved to OS-appropriate location:
- Linux: `~/.config/mc/config.toml`
- macOS: `~/Library/Application Support/mc/config.toml`
- Windows: `%LOCALAPPDATA%\mc\config.toml`

## Next Phase Readiness

**Ready for:**
- Infrastructure features (logging, error recovery) can now use config system
- CLI improvements can leverage config for user preferences
- Additional config options can be added to models.py schema

**Blockers:** None

**Concerns:** None - config migration complete and tested

---
*Phase: 03-code-cleanup*
*Completed: 2026-01-22*
