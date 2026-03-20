# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-19)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality
**Current focus:** v2.0.7 — OCM Integration & Container Tooling

## Current Position

Phase: 37-pre-release-fixes (in progress)
Plan: 03 of 3 complete
Status: In progress — 37-03 complete
Last activity: 2026-03-20 — Completed 37-03-PLAN.md (orphaned helper cleanup)

Progress: [████████████████████████████] (37-01, 37-02, 37-03 done)

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

**36-01 decisions:**
- _read_refresh_token casts dict value via str(value) to satisfy mypy no-any-return — avoids Any from json.loads
- PID lock uses ~/mc/state/ocm-monitor.pid — colocated with containers.db and cluster_id state
- subprocess.run for ocm login inherits terminal (no stdout=/stderr= redirection) so interactive auth code flow streams to user
- PermissionError in os.kill treated as alive — conservative to prevent duplicate monitors from false-cleaning live PIDs

**36-02 decisions:**
- Two separate if get_runtime_mode() != 'agent' blocks kept adjacent — each startup concern independently guarded, not combined
- Lazy import from mc.utils.ocm_monitor inside try/except — failures silently logged at debug level, no mc command ever blocked

**37-01 decisions:**
- db_path hardcoded to Path.home() / "mc" / "state" / "containers.db" — matches host-mounted path ContainerManager uses at container creation
- StateDatabase() with no args is wrong for agent code: platformdirs defaults to ~/.local/share/mc/containers.db (not the mounted path)

**37-02 decisions:**
- Patch mc.cli.main.should_check_for_updates (return_value=True/False) for banner guard tests — the guard calls should_check_for_updates() which routes through mc.runtime, so patching get_runtime_mode at mc.cli.main does not affect banner
- Keep get_runtime_mode patch alongside should_check_for_updates for OCM monitor guard at line 167 which calls get_runtime_mode directly
- Use ['mc', 'ls', 'someuid'] command vector to reach line 160 past --help SystemExit

**37-03 decisions:**
- Mock should_check_for_updates in test_main.py (not get_runtime_mode) for banner guard tests — mock must match actual call site
- etag or '' in 304 return branch — coerces Optional[str] to str to satisfy declared return type
- Path.home() / "mc" / "state" computed directly in test assertions — mirrors production code, no need to mock Path

### Pending Todos

1. **Address orphaned helper functions from v2.0.4** — RESOLVED in 37-03 (check_for_updates deleted; should_check_for_updates wired)

### Blockers/Concerns

- (Resolved) Backplane auto-login cluster ID sourced from sfdc-case.json (openshiftClusterID field) with StateDatabase fallback and user-prompt as last resort.

## Session Continuity

Last session: 2026-03-20T23:30:36Z
Stopped at: 37-02-PLAN.md complete — banner agent-mode guard tests
Resume file: None

---
*State initialized: 2026-03-19 for v2.0.7 OCM Integration & Container Tooling milestone*
*Last updated: 2026-03-20 (37-02 complete — banner agent-mode guard tests added to test_main.py)*
*Last updated: 2026-03-20 (37-03 complete — should_check_for_updates wired, check_for_updates deleted)*
*Last updated: 2026-03-20 (37-01 complete — BPL-04 fixed: StateDatabase explicit path in _get_state_db)*
*Last updated: 2026-03-20 (Phase 36 complete — OCM token monitor end-to-end)*
