# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality
**Current focus:** v2.0.5 Auto-Update & Terminal — Phase 32: Update Notifications

## Current Position

Phase: 32 of 32 (Update Notifications)
Plan: 1 of 2 in current phase
Status: In progress — plan 01 done; plan 02 (banner tests) remaining
Last activity: 2026-03-12 — Completed 32-01-PLAN.md (banner module + ConfigManager extension)

Progress: [████████████████████████░] 98% (Phase 32 plan 01 complete, plan 02 remaining)

## Performance Metrics

**Velocity:**
- Total plans completed: 57+ plans (across phases 1-29)
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
| v2.0.5 Terminal (in progress) | 4 | 2+ | ~4 min so far |

**Recent Trend:**
- v2.0.5 29-01 completed in 4 min — extremely focused implementation plan
- v2.0.5 29-02 completed in 4 min — test suite for new Python API path
- v2.0.5 30-01 completed in 8 min — mc-update module and entry point
- v2.0.5 30-02 completed in 5 min — edge case tests and quality gate
- Trend: Excellent velocity; Phase 30 complete in under 15 min total

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
- v2.0.5 (29-01): iterm2 added as optional [macos] extra, not core dependency — Linux stays clean
- v2.0.5 (29-01): asyncio.timeout(5) applied INSIDE coroutine, not outside run_until_complete()
- v2.0.5 (29-01): _last_api_window_id instance attribute threads window_id from launch() to _capture_window_id()
- v2.0.5 (29-01): _build_iterm_script() retained for backwards-compat; plan 02 adds dedicated tests
- v2.0.5 (29-02): Explicit _try_iterm2_api=None mocking in launcher tests removes dependency on library absence
- v2.0.5 (29-02): monkeypatch.setattr on module-level Path constant for sentinel file isolation in tests
- v2.0.5 (30-01): mc-update module intentionally independent from mc.cli.main — survives partial package upgrades
- v2.0.5 (30-01): Lazy import of is_agent_mode() inside upgrade() function body keeps mc.update importable when CLI is broken
- v2.0.5 (30-01): capture_output=False for uv tool upgrade mc (live streaming); capture_output=True for mc --version (inspect output)
- v2.0.5 (30-02): shell=False assertion via call_args.kwargs.get('shell', False) handles absent kwarg correctly
- v2.0.5 (30-02): Negative stdout assertion ("Upgrade complete" absent) prevents false success message on partial failure paths
- v2.0.5 (31-01): No retry logic in GitHub helpers — interactive commands fail fast, not background polling
- v2.0.5 (31-01): pinned_mc='latest' is sentinel meaning no pin active; check() omits Update line when GitHub unreachable
- v2.0.5 (31-01): _AGENT_MODE_PIN_MSG shared constant unifies pin/unpin/check agent mode stderr message
- v2.0.5 (31-02): Lazy-imported modules patched at source (mc.config.manager.ConfigManager) not at calling module (mc.update.ConfigManager)
- v2.0.5 (32-01): threading.Event + daemon thread for 1.5s banner timeout; result in mutable list [None]
- v2.0.5 (32-01): Network failure from _fetch_latest_version treated same as timeout — no suppression written
- v2.0.5 (32-01): pinned_mc=='latest' sentinel maps to pinned_arg=None in _render_banner for clean None/str check

### Pending Todos

1. **Address orphaned helper functions from v2.0.4** (planning)
   - 3 exported functions not currently used in production
   - All tested and functional — candidates for v2.0.5 mc-update integration
   - File: .planning/todos/pending/2026-02-19-address-orphaned-helper-functions.md

### Blockers/Concerns

- None — iterm2 library blocker resolved in 29-01

## Session Continuity

Last session: 2026-03-12T11:02:12Z
Stopped at: Completed 32-01-PLAN.md — banner module (src/mc/banner.py) + ConfigManager last_banner_shown extension
Resume file: None

---
*State initialized: 2026-03-12 for v2.0.5 Auto-Update & Terminal milestone*
*Last updated: 2026-03-12 (Phase 32 plan 01 complete — banner module created; test_update.py 35 passing)*
