# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality
**Current focus:** v2.0.5 Auto-Update & Terminal — Phase 29: iTerm2 Python API Migration

## Current Position

Phase: 29 of 32 (iTerm2 Python API Migration)
Plan: 0 of 2 in current phase
Status: Roadmap created — ready to plan
Last activity: 2026-03-12 — Roadmap created for v2.0.5 (phases 29-32, 12 requirements mapped)

Progress: [████████████████████] 81% (6 of 4 v2.0.5 phases remain — 28 phases complete across all milestones)

## Performance Metrics

**Velocity:**
- Total plans completed: 56+ plans (across phases 1-28)
- Average duration: ~45 min per plan (estimated from v2.0.2 and v2.0.3 data)
- Total execution time: ~42 hours across v1.0, v2.0, v2.0.2, v2.0.3, v2.0.4

**By Milestone:**

| Milestone | Phases | Plans | Duration |
|-----------|--------|-------|----------|
| v1.0 Hardening | 8 | 21 | 2 days |
| v2.0 Containerization | 7 | 22 | 6 days |
| v2.0.1 Cleanup | 5 batches | 13 todos | 2 days |
| v2.0.2 Window Tracking | 5 | 10 | 6 hours |
| v2.0.3 Container Tools | 6 | 9 | 14 hours |
| v2.0.4 Foundation | 3 | 6 | 3 hours |

**Recent Trend:**
- v2.0.4 showed efficient same-day delivery (3 hours total)
- Trend: Excellent velocity with focused infrastructure implementation

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- v2.0.4 (28-02): Silent failure for auto-check (DEBUG logging), visible errors for manual command (stderr + exit 1)
- v2.0.4 (28-02): Separate hourly check throttle (3600s) from daily notification throttle (86400s)
- v2.0.4 (28-02): Runtime mode check guards containerized operations (get_runtime_mode() != 'agent')
- v2.0.4 (28-01): ETag conditional requests to preserve GitHub API quota
- v2.0.5 roadmap: iTerm2 AppleScript dropped entirely — fallback chain is iTerm2 API only → Terminal.app
- v2.0.5 roadmap: mc-update needs separate console_scripts entry point (survives package upgrades)

### Pending Todos

1. **Address orphaned helper functions from v2.0.4** (planning)
   - 3 exported functions not currently used in production
   - All tested and functional — candidates for v2.0.5 mc-update integration
   - File: .planning/todos/pending/2026-02-19-address-orphaned-helper-functions.md

### Blockers/Concerns

- `iterm2` Python library must be added as optional macOS dependency — check pyproject.toml extras or optional-dependencies pattern

## Session Continuity

Last session: 2026-03-12
Stopped at: Roadmap created for v2.0.5 — ready to plan Phase 29
Resume file: None

---
*State initialized: 2026-03-12 for v2.0.5 Auto-Update & Terminal milestone*
*Last updated: 2026-03-12 (roadmap created)*
