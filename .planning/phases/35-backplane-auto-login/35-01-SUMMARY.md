---
phase: 35-backplane-auto-login
plan: "01"
subsystem: database
tags: [sqlite, state, cluster-id, backplane, volume-mount, migration]

# Dependency graph
requires:
  - phase: 34-case-data-store
    provides: ContainerMetadata, StateDatabase, ContainerManager with volume mount pattern
provides:
  - ContainerMetadata with cluster_id field (default "")
  - StateDatabase ALTER TABLE migration adding cluster_id column (idempotent via try/except)
  - get_container() and list_all() SELECT and return cluster_id with NULL-to-"" coercion
  - ~/mc/state mounted read-write at /home/mcuser/mc/state in every new container
  - 4 unit tests proving migration idempotency and cluster_id round-trip
affects:
  - 35-02 (agent code writing cluster_id to StateDatabase from inside container)
  - 35-03 (backplane auto-login reading cluster_id from ContainerMetadata on host)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SQLite ALTER TABLE with try/except OperationalError for idempotent column migration"
    - "NULL-to-empty-string coercion at read time (row['cluster_id'] or '') preserves backward compatibility"

key-files:
  created:
    - .planning/phases/35-backplane-auto-login/35-01-SUMMARY.md
  modified:
    - src/mc/container/models.py
    - src/mc/container/state.py
    - src/mc/container/manager.py
    - tests/unit/test_container_state.py

key-decisions:
  - "cluster_id defaults to '' (not None) — callers get consistent str type without None checks"
  - "ALTER TABLE migration placed in _ensure_schema() with try/except OperationalError — no version table needed, SQLite's own error is the idempotency signal"
  - "~/mc/state mounted rw (not ro) — agent writes cluster_id to StateDatabase inside container"
  - "add_container() INSERT not changed — new rows get NULL cluster_id, coerced to '' at read time"

patterns-established:
  - "Phase 35 migration pattern: ALTER TABLE in _ensure_schema(), catch OperationalError for existing columns"

# Metrics
duration: 2min
completed: 2026-03-20
---

# Phase 35 Plan 01: Cluster ID Foundation Summary

**cluster_id column added to StateDatabase via idempotent ALTER TABLE migration, ContainerMetadata extended, and ~/mc/state mounted rw into containers so agent can persist backplane cluster IDs**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-20T11:49:32Z
- **Completed:** 2026-03-20T11:51:17Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Extended ContainerMetadata dataclass with `cluster_id: str = ""` for full backward compatibility
- Added idempotent ALTER TABLE migration in `_ensure_schema()` (try/except OperationalError pattern)
- Updated `get_container()` and `list_all()` to SELECT and return `cluster_id`, coercing NULL to ""
- Added `~/mc/state` volume mount (rw) to `ContainerManager.create()` so agent-side code can read/write StateDatabase
- Added `TestClusterIdMigration` class with 4 tests: migration on old DB, multi-row NULL coercion, round-trip persistence, and clear-to-empty

## Task Commits

Each task was committed atomically:

1. **Task 1: Add cluster_id to ContainerMetadata and extend StateDatabase schema** - `a161ff0` (feat)
2. **Task 2: Mount ~/mc/state and add cluster_id unit tests** - `d113ba9` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `src/mc/container/models.py` - Added `cluster_id: str = ""` field with docstring entry
- `src/mc/container/state.py` - ALTER TABLE migration, updated SELECT in get_container() and list_all()
- `src/mc/container/manager.py` - ~/mc/state volume mount (rw) in create()
- `tests/unit/test_container_state.py` - TestClusterIdMigration class with 4 tests

## Decisions Made

- **cluster_id defaults to "" not None** — callers get consistent `str` type without None guards; empty string is the sentinel for "not yet known"
- **ALTER TABLE in _ensure_schema() with try/except OperationalError** — no version table or migration history needed; SQLite's own "duplicate column name" error is the idempotency signal
- **~/mc/state mounted rw** — agent code running inside the container must be able to write cluster_id back to StateDatabase after the user authenticates via backplane
- **add_container() INSERT unchanged** — new rows get NULL cluster_id naturally; coercion at read time (row["cluster_id"] or "") keeps INSERT simple

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `uv run mypy src/mc/container/manager.py` reports 21 pre-existing errors (unused type: ignore comments, Iterator[bytes] return type mismatch, etc.) — all existed before this plan. `models.py` and `state.py` are clean. No new errors introduced.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- StateDatabase and ContainerMetadata are ready for Phase 35-02: agent-side code that reads cluster ID from the Salesforce case data and writes it to StateDatabase via `update_container(case_number, cluster_id=...)`
- ~/mc/state is now mounted into every newly-created container; existing containers will NOT have this mount (requires recreate)
- No blockers for next plan

---
*Phase: 35-backplane-auto-login*
*Completed: 2026-03-20*
