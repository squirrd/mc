---
phase: 15-window-registry-foundation
plan: 01
subsystem: database
tags: [sqlite, wal-mode, concurrent-access, window-tracking, registry]

# Dependency graph
requires:
  - phase: 12-terminal-automation
    provides: Terminal automation infrastructure (MacOSTerminal class)
provides:
  - WindowRegistry class with SQLite backend for persistent window ID storage
  - WAL mode configuration for concurrent multi-process access
  - Lazy validation with auto-cleanup of stale window entries
  - First-write-wins concurrency control via UNIQUE constraints
affects:
  - 16-macos-window-tracking
  - 17-linux-window-tracking
  - integration-tests

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SQLite WAL mode for concurrent access (follows StateDatabase pattern)
    - Lazy validation with auto-cleanup (self-healing registry)
    - First-write-wins via IntegrityError handling
    - Context manager-based connection lifecycle
    - :memory: database support for testing

key-files:
  created:
    - src/mc/terminal/registry.py
  modified: []

key-decisions:
  - "Use callback-based validator in lookup() for platform-agnostic window validation"
  - "Return bool from register() to signal first-write-wins outcome"
  - "Auto-commit transactions (no BEGIN DEFERRED) to avoid lock upgrade issues"
  - "Update last_validated timestamp only on successful validation"

patterns-established:
  - "WindowRegistry follows StateDatabase pattern: WAL mode, context managers, :memory: support"
  - "Lazy validation: Only validate on lookup, auto-remove stale entries, update timestamp on success"
  - "First-write-wins: Catch sqlite3.IntegrityError, return False (not an error condition)"

# Metrics
duration: 1min
completed: 2026-02-08
---

# Phase 15 Plan 01: Window Registry Foundation Summary

**SQLite-based window registry with WAL mode, lazy validation, and first-write-wins concurrency control**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-08T00:12:49Z
- **Completed:** 2026-02-08T00:13:52Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments
- WindowRegistry class created following proven StateDatabase pattern
- WAL mode configured (journal_mode=WAL, synchronous=NORMAL, busy_timeout=30000, cache_size=-64000)
- register() operation handles concurrent writes with first-write-wins behavior
- lookup() operation validates window existence via callback, auto-removes stale entries
- remove() operation provides explicit entry deletion
- :memory: database support enables unit testing without file I/O

## Task Commits

Each task was committed atomically:

1. **Task 1: Create WindowRegistry class with SQLite backend** - `062a57c` (feat)

**Plan metadata:** Not yet committed (will be committed with STATE.md update)

## Files Created/Modified
- `src/mc/terminal/registry.py` - WindowRegistry class with CRUD operations (register, lookup, remove), WAL mode configuration, schema management, and connection lifecycle handling

## Decisions Made

**1. Callback-based validator in lookup() method**
- **Rationale:** Platform-agnostic design - macOS uses AppleScript window validation, Linux will use wmctrl/X11, validator callback abstracts platform differences
- **Implementation:** `lookup(case_number, validator: Callable[[str], bool])` - caller provides validation logic
- **Benefit:** Registry code stays platform-independent, window validation logic lives in platform-specific modules

**2. Return bool from register() to signal success/duplicate**
- **Rationale:** Caller needs to know if registration succeeded or if another process already registered
- **Implementation:** `return True` on success, `return False` on sqlite3.IntegrityError
- **Benefit:** First-write-wins behavior explicit in API, no exception handling needed by caller

**3. Auto-commit transactions (no explicit BEGIN)**
- **Rationale:** Avoid lock upgrade failures in concurrent scenarios (BEGIN DEFERRED → write = RESERVED lock contention)
- **Implementation:** Context manager commits after each operation
- **Benefit:** Simple transaction model, no deadlocks, matches StateDatabase pattern

**4. Update last_validated only on successful validation**
- **Rationale:** Track when window was last confirmed to exist, not when validation failed
- **Implementation:** UPDATE last_validated only if validator returns True
- **Benefit:** Timestamp indicates "last known good" state, useful for debugging stale entries

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None - StateDatabase pattern provided clear reference implementation. All verifications passed on first attempt.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Ready for Phase 16 (macOS Window Tracking):**
- WindowRegistry operational and tested with :memory: database
- register() and lookup() APIs proven via verification tests
- Auto-cleanup behavior validated (stale entry removal)
- First-write-wins concurrency control tested (duplicate registration handling)

**Platform-specific window validation needed:**
- Phase 16 will implement macOS window ID validation via AppleScript
- Phase 17 will implement Linux window ID validation via wmctrl/X11
- Registry provides validator callback interface for both platforms

**Integration test dependency:**
- `test_duplicate_terminal_prevention_regression` can validate end-to-end behavior once Phase 16 completes
- Current test likely fails because window tracking not yet implemented

**No blockers** - registry foundation complete, ready for platform-specific window tracking.

---
*Phase: 15-window-registry-foundation*
*Completed: 2026-02-08*
