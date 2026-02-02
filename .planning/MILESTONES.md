# Project Milestones: MC CLI Hardening Project

## v2.0.1 Cleanup & Hardening (In Progress: 2026-02-02)

**Goal:** Fix critical bugs from v2.0 release and complete post-ship cleanup

**Progress:** 12/13 todos complete (92% complete)

**Batches completed:**
- ✅ Batch A: Configuration cleanup (2 todos)
  - Consolidated config under ~/mc/config/ with auto-migration
  - Fixed type annotations in config module
- ✅ Batch B: Container Management (5 todos)
  - Structured workspace paths: cases/<customer>/<case>-<description>
  - Quay.io auto-pull with local fallback
  - Duplicate terminal prevention via window detection
  - Auto-close terminal on shell exit
  - Improved error messaging (connection vs missing image)
- ✅ Batch C: UI Improvements (1 todo)
  - Container list output shows description instead of workspace path
- ✅ Batch D: Authentication & API cleanup (3 todos)
  - Fixed terminal attachment Salesforce API method call
  - Unified authentication removing direct Salesforce dependencies
  - Fixed Podman URI byte string errors
- ⏳ Batch E: Testing (1/5 test suites fixed)
  - ✅ Test dependencies and imports (513 tests collect, 13/13 cache tests pass)
  - ⏳ 4 test suites remaining (47 test failures total)

**Key fixes delivered:**
- ✅ Terminal attachment bug (Salesforce API method mismatch)
- ✅ Cache database initialization failures
- ✅ Podman URI byte string errors
- ✅ Workspace path structure improvements
- ✅ Container image auto-pull from quay.io
- ✅ Config directory consolidation

**What's next:** Complete Batch E testing fixes, then release v2.0.1

---

## v2.0 Containerization + Distribution (Shipped: 2026-02-01)

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

- 124 files created/modified
- 6,056 lines of Python (cumulative)
- 7 phases, 22 plans
- 6 days from start to ship (2026-01-26 → 2026-02-01)

**Git range:** `feat(09-01)` (d3c88a9) → `docs(14.1)` (2495e3f)

**Known issues shipped (v2.0.1 backlog):**
- Terminal attachment broken due to Salesforce API method name mismatch (get_case vs query_case) — **CRITICAL BUG**
- Podman URI byte string errors still occurring despite Phase 14.1-01 fix attempt
- Cache database initialization failures on second `mc create` command run
- Runtime mode detection created but not integrated into decision logic
- Phase 13 missing VERIFICATION.md (deliverables present and verified functional)

**What's next:** v2.0.1 patch release to fix critical terminal attachment bug and UAT issues

---

## v1.0 Hardening (Shipped: 2026-01-22)

**Delivered:** Production-ready MC CLI with comprehensive testing, type safety, security hardening, and performance optimizations

**Phases completed:** 1-8 (21 plans total)

**Key accomplishments:**

- Comprehensive test infrastructure with 100+ tests achieving 80%+ coverage on critical modules (auth, API client, workspace)
- Modern Python 3.11+ codebase with full type safety (98% coverage) and mypy strict validation passing
- Production-ready security features including token caching, SSL verification, input validation, and bandit linting
- Structured logging system replacing 74 print statements with sensitive data redaction and dual-mode formatters
- High-performance downloads with 8 concurrent threads, rich progress bars, and intelligent retry with exponential backoff
- TOML configuration system with cross-platform support and interactive wizard, replacing environment variables

**Stats:**

- 110 files created/modified
- 2,590 lines of Python
- 8 phases, 21 plans, 63 tasks
- 2 days from start to ship (2026-01-20 → 2026-01-22)

**Git range:** `chore(01-01)` → `fix(08-01)`

**Tech debt carried forward:**
- 2 cosmetic type annotation gaps in config module (mypy passes, functionally complete)
- 20 test failures from Path vs string type changes requiring test modernization

**What's next:** Additional features and enhancements (TBD via `/gsd:new-milestone`)

---
