# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-01)

**Core value:** Make the codebase testable and maintainable so new features can be added confidently

## Current Position

**Milestone:** Ready for next milestone definition
**Status:** v2.0 shipped (2026-02-01)
**Last activity:** 2026-02-01 - Completed and archived v2.0 milestone

## Accumulated Context

### v2.0 Containerization + Distribution (SHIPPED 2026-02-01)

**Delivered:** Transform MC into a container orchestrator providing isolated per-case workspaces with persistent containers

**Phases completed:** 9-14.1 (7 phases, 22 plans total)

**Key accomplishments:**
- Container orchestration with full lifecycle management (create, list, stop, delete, exec) using podman-py and SQLite state persistence
- Platform detection for macOS/Linux with automatic Podman machine handling, lazy connection, and retry logic with exponential backoff
- Salesforce integration for case metadata querying with 5-minute cache TTL, automatic token refresh, and workspace path resolution
- Terminal automation across iTerm2, Terminal.app, gnome-terminal, and konsole with custom bashrc and welcome banners
- RHEL 10 UBI container image (549 MB) with MC CLI, essential bash tools, and runtime mode detection preserving v1.0 backwards compatibility
- Modern distribution via uv tool supporting development (uv run), UAT (uv tool install -e .), and production (uv tool install git+) workflows

**Stats:**
- 6,056 lines of Python (cumulative)
- 7 phases, 22 plans
- 6 days from start to ship (2026-01-26 → 2026-02-01)

**Known issues shipped (v2.0.1 backlog):**
- ✅ FIXED: Terminal attachment broken due to Salesforce API method name mismatch
- ✅ FIXED: Cache database initialization failures on second `mc create` command run
- ✅ FIXED: Podman URI byte string errors (byte string handling added)
- Runtime mode detection created but not integrated into decision logic
- Phase 13 missing VERIFICATION.md (deliverables present and verified functional)
- Podman URI scheme error on macOS (still investigating - see pending todos)

See `.planning/milestones/v2.0-ROADMAP.md` for full phase details.

### v1.0 Hardening (SHIPPED 2026-01-22)

**Major Accomplishments:**
- 100+ tests with 80%+ coverage on critical modules
- Python 3.11+ with 98% type coverage and mypy strict validation
- Production-ready security (token caching, SSL verification, input validation)
- Structured logging (74 print statements migrated, sensitive data redaction)
- 8x faster downloads (parallel with rich progress bars, intelligent retry)
- TOML configuration system replacing environment variables

**Tech Stack:**
- Python 3.11+, pytest, requests, rich, tqdm, tenacity, backoff, platformdirs
- 2,590 lines of production code
- 110 files modified

See `.planning/milestones/v1.0-ROADMAP.md` for full phase details (if exists).

### Pending Todos (16 remaining)

**Completed (moved to done/):**
- [2026-01-27] ✅ Migrate mc-cli distribution to use pipx/uv tool
- [2026-02-01] ✅ Rename offline_token config to rh_api_offline_token
- [2026-02-01] ✅ Fix UAT test plan - mc container ls → mc container list
- [2026-02-01] ✅ Fix terminal attachment Salesforce API method call
- [2026-02-01] ✅ Fix cache database initialization in mc create command
- [2026-02-01] ✅ Fix Podman URI scheme byte string error in container commands
- [2026-02-01] ✅ Unify authentication - remove direct Salesforce dependency from container commands
- [2026-02-01] ✅ Fix Podman URI scheme error - byte string passed instead of decoded string

**Still pending:**
- [2026-01-22] Fix Phase 8 type annotation cosmetic gaps (area: config)
- [2026-01-26] v2.x deferred containerization features (area: planning)
- [2026-02-01] Validate case number format before credential/API checks (area: general)
- [2026-02-01] Consolidate config directory under ~/mc workspace (area: config)
- [2026-02-01] Fix container create image detection failure (area: containers)
- [2026-02-01] Use pre-built container images from quay.io instead of local builds (area: containers)
- [2026-02-01] Fix workspace path structure to use cases/<customer>/<case>-<description> (area: containers)
- [2026-02-01] Improve container list output - replace workspace path with description (area: ui)
- [2026-02-01] Prevent duplicate terminal launches and focus existing terminals (area: containers)
- [2026-02-01] Auto-close terminal when shell exits (area: containers)
- [2026-02-01] Fix test dependencies and imports (area: testing) - 2 import errors
- [2026-02-01] Fix HTTP error handling tests (area: testing) - 14 test failures
- [2026-02-01] Fix container management tests (area: testing) - 6 test failures
- [2026-02-01] Fix terminal attachment tests (area: testing) - 17 test failures
- [2026-02-01] Fix validation and integration tests (area: testing) - 5 test failures/errors
- [2026-02-01] Fix workspace and metadata tests (area: testing) - 5 test failures

## Session Continuity

Last session: 2026-02-01
Stopped at: v2.0 milestone archived and tagged
Resume: Ready for `/gsd:new-milestone` to define next milestone

---
*State initialized: 2026-01-20*
*Last updated: 2026-02-01 (v2.0 milestone complete and archived)*
