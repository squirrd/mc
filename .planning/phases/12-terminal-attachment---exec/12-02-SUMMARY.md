---
phase: 12-terminal-attachment---exec
plan: 02
subsystem: terminal
tags: [bash, bashrc, terminal-customization, welcome-banner, case-metadata, platformdirs, textwrap]

# Dependency graph
requires:
  - phase: 10-salesforce-integration-&-case-resolution
    provides: "Salesforce case metadata structure (case_number, customer_name, description, summary, next_steps)"
provides:
  - "Custom bashrc generation with PS1 prompt, aliases, helper functions"
  - "Welcome banner formatting with case metadata (description, summary, next steps)"
  - "Environment variable exports (MC_CASE_ID, MC_CUSTOMER, MC_DESCRIPTION)"
  - "Text wrapping to 80 chars for readability"
  - "Graceful handling of missing metadata fields"
affects: [12-03-terminal-launchers, container-attachment, shell-initialization]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Custom bashrc injection via BASH_ENV environment variable"
    - "Welcome banner with metadata sections conditionally displayed"
    - "Text wrapping with prefix alignment using textwrap.fill()"

key-files:
  created:
    - src/mc/terminal/__init__.py
    - src/mc/terminal/shell.py
    - src/mc/terminal/banner.py
    - tests/unit/test_terminal_shell.py
  modified: []

key-decisions:
  - "BASH_ENV over --rcfile: Use BASH_ENV environment variable for bashrc injection (works in both interactive and non-interactive contexts)"
  - "Conditional sections: Summary and next steps sections only displayed if metadata present (cleaner banner for minimal metadata)"
  - "Comments excluded: Comments field stored in metadata but NOT displayed in banner per CONTEXT.md requirements"
  - "Prefix alignment: Text wrapping includes prefix length calculation for multi-line field alignment"

patterns-established:
  - "Banner structure: Delimiter lines, Case/Customer/Description always shown, Summary/Next Steps conditional"
  - "Environment variable naming: MC_ prefix for all container environment variables"
  - "Helper function naming: mc-* prefix for all custom functions (mc-help)"
  - "Alias safety: Use full commands in aliases (ll='ls -lah') to avoid conflicts"

# Metrics
duration: 3min
completed: 2026-01-26
---

# Phase 12 Plan 02: Terminal Attachment & Exec Summary

**Custom bashrc and welcome banner for containerized environments with case metadata display, custom prompt, and helper functions**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-26T11:34:21Z
- **Completed:** 2026-01-26T11:38:41Z
- **Tasks:** 3 (2 implementation, 1 testing)
- **Files modified:** 4

## Accomplishments

- Custom bashrc generator with PS1 prompt showing [MC-{case_number}] prefix
- Welcome banner with case description, summary, and next steps (comments excluded)
- Environment variable exports (MC_CASE_ID, MC_CUSTOMER, MC_DESCRIPTION) for shell scripts
- Helper aliases (ll, case-info) and mc-help function
- Text wrapping to 80 characters with proper prefix alignment
- Graceful handling of missing metadata fields (shows "N/A")
- 100% test coverage (25 tests, shell.py: 23 statements, banner.py: 27 statements)

## Task Commits

Each task was committed atomically:

1. **Tasks 1 & 2: Create custom bashrc generator and welcome banner** - `7539a24` (feat)
   - Custom bashrc generation with prompt, aliases, functions, environment variables
   - Welcome banner formatting with case metadata
   - Text wrapping with prefix alignment
   - Graceful handling of missing fields

2. **Task 3: Create unit tests for shell customization** - `eec01c6` (test)
   - 25 comprehensive test cases
   - 100% code coverage for shell.py and banner.py
   - Tests for prompt, aliases, functions, environment variables
   - Tests for banner wrapping, missing fields, comments exclusion
   - Tests for file permissions, path handling

## Files Created/Modified

- `src/mc/terminal/__init__.py` - Terminal module exports
- `src/mc/terminal/shell.py` - Custom bashrc generation with prompt, aliases, functions (23 statements)
- `src/mc/terminal/banner.py` - Welcome banner formatting with text wrapping (27 statements)
- `tests/unit/test_terminal_shell.py` - 25 unit tests with 100% coverage

## Decisions Made

**1. BASH_ENV environment variable for bashrc injection**
- **Rationale:** BASH_ENV works for both interactive and non-interactive shells, unlike --rcfile which only works for interactive shells
- **Implementation:** write_bashrc() creates file at ~/.mc/bashrc/mc-{case_number}.bashrc, path passed to podman exec via --env BASH_ENV

**2. Conditional banner sections**
- **Rationale:** Not all cases have summary or next steps metadata; showing empty sections clutters banner
- **Implementation:** Check if summary/next_steps are present and non-empty before adding sections to banner

**3. Comments field excluded from banner**
- **Rationale:** CONTEXT.md explicitly states "Comments stored as metadata but NOT displayed in banner"
- **Implementation:** generate_banner() extracts case metadata but never accesses or displays comments field

**4. Text wrapping with prefix alignment**
- **Rationale:** Long descriptions need wrapping to 80 chars, but adding "Description: " prefix makes first line exceed limit
- **Implementation:** format_field() uses textwrap.fill() with initial_indent (prefix) and subsequent_indent (spaces matching prefix length)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

**1. Text wrapping test failure**
- **Problem:** Initial implementation wrapped text to 80 chars, then added "Description: " prefix, causing line to exceed 80 chars
- **Solution:** Modified format_field() to accept prefix parameter and use textwrap.fill() with initial_indent and subsequent_indent
- **Resolution:** All tests pass, lines properly wrapped to 80 chars including prefix

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Plan 12-03 (Terminal Launchers):**
- ✅ Shell customization modules ready for container exec integration
- ✅ write_bashrc() returns absolute path for BASH_ENV environment variable
- ✅ Banner generation handles missing metadata gracefully
- ✅ Helper functions provide basic container environment utilities

**No blockers.**

**Integration notes for next plan:**
- Call write_bashrc(case_number, case_metadata) before podman exec
- Pass returned path via --env BASH_ENV={path}
- Case metadata structure matches Salesforce API from Phase 10
- Custom prompt [MC-{case_number}] clearly indicates containerized environment

---
*Phase: 12-terminal-attachment---exec*
*Completed: 2026-01-26*
