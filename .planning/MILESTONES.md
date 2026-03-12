# Project Milestones: MC CLI Hardening Project

## v2.0.5 Auto-Update & Terminal (Shipped: 2026-03-12)

**Delivered:** MC CLI auto-update functionality (upgrade/pin/unpin/check/banner) and iTerm2 Python API migration for cleaner terminal management

**Phases completed:** 29-32 (4 phases, 8 plans total)

**Key accomplishments:**

- iTerm2 Python API migration — MacOSLauncher now creates windows via iterm2 Python library with MCC-Term profile applied and raw `podman exec` command hidden from terminal scrollback; Terminal.app fallback preserved; iterm2>=2.14 as optional macOS extra
- `mc-update upgrade` standalone entry point — runs `uv tool upgrade mc` with live streaming, post-upgrade `mc --version` verification, and `uv tool install --force mc` recovery instructions on failure; survives partial package upgrades
- Version pinning — `mc-update pin/unpin/check` subcommands with GitHub release validation, config.toml atomic persistence, and pin guard blocking accidental upgrades
- Update notification banner — Rich Panel on stderr at CLI startup, calendar-day suppression, pin-aware messaging, 1.5s threaded timeout replacing VersionChecker background check
- Fixed pre-existing project misconfiguration: `.flake8` aligned with Black's 100-char line length (was missing entirely)

**Stats:**

- 85 files changed (9,824 insertions, 3,085 deletions)
- 9,921 lines of Python code total (up from 7,914 at v2.0.4)
- 4 phases, 8 plans
- Same-day delivery (2026-03-12, ~40 min total)
- Tests: 523 → 579 unit tests (+56 new tests); 67.84% coverage

**Git range:** `3e5cf7b` (docs(29): capture phase context) → `f2b046e` (docs(32): complete update-notifications phase)

**What's next:** Start next milestone via `/gsd:new-milestone`

---

## v2.0.4 Foundation (Shipped: 2026-02-19)

**Delivered:** Version checking infrastructure and configuration foundation for automatic updates (MC CLI only)

**Phases completed:** 26-28 (3 phases, 6 plans total)

**Key accomplishments:**

- Non-blocking version check infrastructure with daemon threads, GitHub API integration with ETag caching, and PEP 440 version comparison
- Configuration foundation extended TOML config with [version] section and atomic write safety for version management fields
- Runtime mode detection with layered container detection preventing auto-updates in containerized environments
- Comprehensive test coverage with 67 tests across 3 phases (100% pass rate) validating infrastructure reliability
- Foundation for auto-updates with clean interfaces and patterns established ready for v2.0.5 MC Auto-Update milestone

**Stats:**

- 32 files created/modified (+6,510 insertions, -55 deletions)
- 7,914 lines of Python code total
- 3 phases, 6 plans
- Same day delivery (2026-02-19, phases 16:40-19:21, ~3 hours)

**Git range:** `9562c88` (docs(26): capture phase context) → `ee5be90` (docs(28): complete version check infrastructure phase)

**What's next:** Start v2.0.5 MC Auto-Update milestone via `/gsd:new-milestone`

---

## v2.0.3 Container Tools (Shipped: 2026-02-10)

**Delivered:** Multi-stage container architecture with efficient layer caching and versioned tool management

**Phases completed:** 20-25 (6 phases, 9 plans total)

**Key accomplishments:**

- Multi-stage Containerfile with three named stages (ocm-downloader, mc-builder, final) achieving 12-layer cache optimization for fast rebuilds
- Independent image versioning (1.0.0) decoupled from MC CLI version (2.0.2) enabling tool updates without code releases
- Build automation pipeline with yq version extraction, semver validation, and podman orchestration supporting dry-run and verbose modes
- Registry integration with skopeo query, exponential backoff retry logic, and digest-based change detection
- Intelligent auto-versioning with patch bumping based on digest comparison and automatic publishing to quay.io
- OCM CLI proof-of-concept with architecture-aware downloads (amd64/arm64), SHA256 verification, and functional validation

**Stats:**

- 45 files created/modified
- 972 lines of Bash/YAML (container infrastructure)
- 6 phases, 9 plans (including 2 gap closure plans)
- 14 hours from phase 20 start to phase 25 complete (2026-02-09, 21:14 → 2026-02-10, 11:30)

**Git range:** `5c6fdeb` (feat(20-01): multi-stage Containerfile) → `1088286` (docs(25): complete Registry Publishing & OCM Verification phase)

**What's next:** Start next milestone via `/gsd:new-milestone`

---

## v2.0.2 Window Tracking (Shipped: 2026-02-08)

**Delivered:** Eliminate duplicate terminal windows by implementing window ID tracking system

**Phases completed:** 15-19 (5 phases, 10 plans total)

**Key accomplishments:**

- SQLite-backed window registry with WAL mode for concurrent multi-process access and lazy validation with auto-cleanup
- macOS duplicate prevention via window ID tracking with AppleScript integration for iTerm2 and Terminal.app, eliminating unreliable title-based search
- Self-healing registry with automatic stale entry cleanup on startup and manual `mc container reconcile` command for troubleshooting
- Linux X11 support with wmctrl/xdotool integration for gnome-terminal and konsole, desktop-native terminal preference, and strict Wayland validation
- Comprehensive test suite with 530 tests passing (74.65% coverage), graceful database corruption recovery, and verified duplicate prevention

**Stats:**

- 57 files created/modified
- 7,349 lines of Python code
- 5 phases, 10 plans
- 6 hours from phase 15 start to phase 19 complete (2026-02-08, 09:48 → 15:36)

**Git range:** `0ef9ea5` (docs(15): capture phase context) → `5dedf59` (docs(19): complete Test Suite & Validation phase)

**What's next:** Start next milestone via `/gsd:new-milestone`

---

## v2.0.1 Cleanup & Hardening (Shipped: 2026-02-02)

**Delivered:** Fixed critical bugs from v2.0 release and completed comprehensive test suite improvements

**Batches completed:** All 5 batches (13 todos total)

**Key accomplishments:**

- Fixed critical terminal attachment bug (Salesforce API method mismatch) - primary workflow now functional
- Comprehensive test suite improvements: 503 tests passing with 77% coverage (up from 18% at v2.0 ship)
- Consolidated configuration under ~/mc/config/ with automatic migration from legacy platformdirs locations
- Structured workspace paths: cases/<customer>/<case>-<description> for better organization
- Container image auto-pull from quay.io registry with local build fallback
- Terminal enhancements: duplicate prevention via window detection and auto-close on shell exit
- Fixed cache database initialization failures and Podman URI byte string errors
- Unified authentication removing direct Salesforce dependencies from container commands

**Stats:**

- 503 tests passing (4 minor failures, 13 skipped)
- 77% test coverage (above 60% requirement)
- 13 todos across 5 batches
- 2 days from v2.0 ship to v2.0.1 release (2026-02-01 → 2026-02-02)

**Git range:** `feat(14.1-05)` → `fix(integration-tests)`

**What's next:** Start next milestone via `/gsd:new-milestone`

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
