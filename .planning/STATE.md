# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality
**Current focus:** v2.0.7 — OCM Integration & Container Tooling

## Current Position

Phase: 35 of ongoing (35-backplane-auto-login)
Plan: 03 of 03
Status: Phase complete — Plan 35-03 complete
Last activity: 2026-03-20 — Completed 35-03-PLAN.md (backplane-login CLI wiring + exec chain update)

Progress: [██████████████░░░░░░░░░░░] 56% (v2.0.7: Phases 33-35 complete)

## Performance Metrics

**Velocity:**
- Total plans completed: 67+ plans (across phases 1-32)
- Average duration: ~45 min per plan (estimated from v2.0.2 and v2.0.3 data)
- Total execution time: ~42 hours across v1.0, v2.0, v2.0.2, v2.0.3, v2.0.4, v2.0.5

**By Milestone:**

| Milestone | Phases | Plans | Duration |
|-----------|--------|-------|----------|
| v1.0 Hardening | 8 | 21 | 2 days |
| v2.0 Containerization | 7 | 22 | 6 days |
| v2.0.1 Cleanup | 5 batches | 13 todos | 2 days |
| v2.0.2 Window Tracking | 5 | 10 | 6 hours |
| v2.0.3 Container Tools | 6 | 9 | 14 hours |
| v2.0.4 Foundation | 3 | 6 | 3 hours |
| v2.0.5 Auto-Update & Terminal | 4 | 8 | ~40 min total |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
All v2.0.6 decisions recorded in PROJECT.md.

**33-02 decisions:**
- ~/mc/config is required for container creation (hard fail without it)
- ~/.claude is optional (warn-and-continue if absent)
- mc/config mounted read-only; claude dir mounted read-write
- Pre-flight checks placed before os.makedirs to fail fast before side effects

**34-01 decisions:**
- fetch_case_comments() return type is list[dict[str, Any]] — no filtering or transformation of API response
- openshiftClusterID added as NotRequired[str] to CaseDetails — may not be present on all cases
- customerName added as NotRequired[str] to CaseDetails — matches what the API returns

**34-02 decisions:**
- ConfigManager, get_access_token, RedHatAPIClient imported inside init_case_data() body — avoids circular imports and keeps agent startup fast
- case_number for mc agent init-case comes from CASE_NUMBER env var (set by ContainerManager), not a CLI arg
- Unit test mocking patches at original module paths (mc.config.manager.ConfigManager) not mc.agent.case_data.X — required because lazy imports bypass module-level attribute lookup

**34-03 decisions:**
- exec bash used instead of plain bash — exec replaces the bash -c subshell PID with the interactive shell, providing proper job control
- || true pattern keeps the interactive shell guarantee even if mc agent init-case fails (no network, CASE_NUMBER missing, etc.)

**35-01 decisions:**
- cluster_id defaults to "" (not None) — callers get consistent str type without None checks; empty string is the sentinel for "not yet known"
- ALTER TABLE migration in _ensure_schema() with try/except OperationalError — no version table needed; SQLite's own "duplicate column name" error is the idempotency signal
- ~/mc/state mounted rw (not ro) — agent must write cluster_id back to StateDatabase after backplane auth
- add_container() INSERT unchanged — new rows get NULL cluster_id, coerced to "" at read time

**35-02 decisions:**
- run_backplane_login() only persists user-entered cluster_id — sfdc and state_db sources are authoritative externally; not overwritten on success
- Failed login clears StateDatabase cluster_id — ensures stale ID does not silently repeat a failing cluster on next session
- Token expiry detected in stderr triggers targeted message ('run ocm login') separate from generic warning
- state_db=None injection point with _get_state_db() wrapper enables unit testing without filesystem

**35-03 decisions:**
- backplane_login(args) lazy import inside function body — matches init_case() pattern, avoids import-time side effects
- Per-command import in routing elif blocks — each agent subcommand gets its own import (consistent, extensible pattern)
- || true applied to backplane-login in exec chain — interactive shell must always open regardless of login outcome

### Pending Todos

1. **Address orphaned helper functions from v2.0.4** (planning)
   - 3 exported functions not currently used in production
   - All tested and functional — candidates for v2.0.5 mc-update integration
   - File: .planning/todos/pending/2026-02-19-address-orphaned-helper-functions.md

2. **Banner agent-mode guard test coverage** (tech debt from v2.0.5 audit)
   - main.py:151 `if get_runtime_mode() != 'agent': show_update_banner()` has no test coverage
   - Suggested fix: 2 unit tests in test_main.py

### Blockers/Concerns

- Backplane auto-login depends on extracting cluster ID from Salesforce case data — MC does not yet have this capability. Scoped in as best-effort; fall back to prompting user if extraction is not straightforward.

## Session Continuity

Last session: 2026-03-20
Stopped at: Completed 35-03-PLAN.md — backplane-login CLI wiring + exec chain (Phase 35 complete)
Resume file: None

---
*State initialized: 2026-03-19 for v2.0.7 OCM Integration & Container Tooling milestone*
*Last updated: 2026-03-20 (Phase 34 verified passed — 6/6 must-haves)*
