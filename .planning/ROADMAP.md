# Roadmap: MC CLI Hardening Project

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- ✅ **v2.0 Containerization + Distribution** - Phases 9-14.1 (shipped 2026-02-01)
- ✅ **v2.0.1 Cleanup & Hardening** - 5 batches, 13 todos (shipped 2026-02-02)
- ✅ **v2.0.2 Window Tracking** - Phases 15-19 (shipped 2026-02-08)
- ✅ **v2.0.3 Container Tools** - Phases 20-25 (shipped 2026-02-10)
- 🚧 **v2.0.4 Foundation** - Phases 26-28 (current)
- 📋 **v2.0.5 MC Auto-Update** - Phases TBD (planned)
- 📋 **v2.0.6 Container Management** - Phases TBD (planned)

## Phases

<details>
<summary>✅ v1.0 Hardening (Phases 1-8) - SHIPPED 2026-01-22</summary>

### Phase 1: Test Infrastructure
**Goal**: pytest framework and fixtures
**Plans**: 3 plans

Plans:
- [x] 01-01: pytest configuration and fixtures
- [x] 01-02: Mock infrastructure for API/external services
- [x] 01-03: Initial test suite for auth module

### Phase 2: Critical Path Tests
**Goal**: Unit tests for critical modules
**Plans**: 3 plans

Plans:
- [x] 02-01: RedHatAPIClient tests with mocked requests
- [x] 02-02: WorkspaceManager tests
- [x] 02-03: Formatter and file_ops utility tests

### Phase 3: Tech Debt Resolution
**Goal**: Remove hardcoded values and environment dependencies
**Plans**: 3 plans

Plans:
- [x] 03-01: TOML config file with platformdirs
- [x] 03-02: Remove environment variable dependencies
- [x] 03-03: Consolidate version management (single source of truth)

### Phase 4: Security Hardening
**Goal**: Token management and input validation
**Plans**: 2 plans

Plans:
- [x] 04-01: Access token expiration and caching
- [x] 04-02: Input validation and SSL verification

### Phase 5: Performance Optimization
**Goal**: Parallel downloads and caching
**Plans**: 2 plans

Plans:
- [x] 05-01: Parallel attachment downloads (8 threads)
- [x] 05-02: File-based caching for case metadata

### Phase 6: Type Safety
**Goal**: Type hints and mypy validation
**Plans**: 2 plans

Plans:
- [x] 06-01: Add type hints to all modules
- [x] 06-02: Configure mypy strict mode

### Phase 7: Structured Logging
**Goal**: Replace print statements with structured logging
**Plans**: 2 plans

Plans:
- [x] 07-01: Logging framework with sensitive data redaction
- [x] 07-02: Replace print statements throughout codebase

### Phase 8: Bug Fixes
**Goal**: Fix identified bugs
**Plans**: 3 plans

Plans:
- [x] 08-01: Fix LDAP --All flag and typos
- [x] 08-02: Improve error handling and retry logic
- [x] 08-03: Add download progress indication

</details>

<details>
<summary>✅ v2.0 Containerization + Distribution (Phases 9-14.1) - SHIPPED 2026-02-01</summary>

### Phase 9: Container State Management
**Goal**: SQLite state persistence and platform detection
**Plans**: 3 plans

Plans:
- [x] 09-01: SQLite state database schema
- [x] 09-02: Platform detection (macOS/Linux)
- [x] 09-03: Podman connection with retry logic

### Phase 10: Container Lifecycle
**Goal**: Create, list, stop, delete operations
**Plans**: 4 plans

Plans:
- [x] 10-01: Container creation with podman-py
- [x] 10-02: Container listing with state tracking
- [x] 10-03: Container stop and delete operations
- [x] 10-04: Container exec command

### Phase 11: Salesforce Integration
**Goal**: Case metadata querying and workspace resolution
**Plans**: 3 plans

Plans:
- [x] 11-01: Salesforce API client
- [x] 11-02: Case metadata cache (5-minute TTL)
- [x] 11-03: Workspace path resolution

### Phase 12: Terminal Automation
**Goal**: Automatic terminal attachment across platforms
**Plans**: 4 plans

Plans:
- [x] 12-01: iTerm2 integration
- [x] 12-02: Terminal.app integration
- [x] 12-03: Linux terminal support (gnome-terminal, konsole)
- [x] 12-04: Custom bashrc and welcome banners

### Phase 13: Container Image
**Goal**: RHEL 10 UBI container with MC CLI
**Plans**: 3 plans

Plans:
- [x] 13-01: Containerfile with MC CLI installation
- [x] 13-02: Essential bash tools and environment
- [x] 13-03: Runtime mode detection

### Phase 14: Distribution
**Goal**: Modern distribution via uv tool
**Plans**: 2 plans

Plans:
- [x] 14-01: pyproject.toml for uv tool
- [x] 14-02: UAT testing (uv tool install -e .)

### Phase 14.1: UAT Fixes (INSERTED)
**Goal**: Fix critical bugs found during UAT
**Plans**: 5 plans

Plans:
- [x] 14.1-01: Fix Podman URI byte string errors
- [x] 14.1-02: Fix cache database initialization failures
- [x] 14.1-03: Fix terminal attachment (Salesforce API method mismatch)
- [x] 14.1-04: Add container auto-pull from quay.io
- [x] 14.1-05: Consolidate config under ~/mc/config/

</details>

<details>
<summary>✅ v2.0.1 Cleanup & Hardening (5 batches) - SHIPPED 2026-02-02</summary>

**Batches completed:** 5 batches, 13 todos total

Key accomplishments:
- Fixed critical terminal attachment bug (Salesforce API method mismatch)
- Comprehensive test suite improvements: 503 tests passing with 77% coverage
- Consolidated configuration under ~/mc/config/ with automatic migration
- Structured workspace paths: cases/<customer>/<case>-<description>
- Container image auto-pull from quay.io registry with local build fallback
- Terminal enhancements: duplicate prevention via window detection and auto-close on shell exit
- Fixed cache database initialization failures and Podman URI byte string errors
- Unified authentication removing direct Salesforce dependencies from container commands

</details>

<details>
<summary>✅ v2.0.2 Window Tracking (Phases 15-19) - SHIPPED 2026-02-08</summary>

### Phase 15: Window Registry Foundation
**Goal**: SQLite-backed window registry with WAL mode
**Plans**: 2 plans

Plans:
- [x] 15-01: Window registry database schema
- [x] 15-02: Store/lookup/cleanup operations

### Phase 16: macOS Duplicate Prevention
**Goal**: Window ID tracking for iTerm2 and Terminal.app
**Plans**: 2 plans

Plans:
- [x] 16-01: AppleScript window ID tracking
- [x] 16-02: Focus existing window instead of creating duplicate

### Phase 17: Self-Healing Registry
**Goal**: Automatic stale entry cleanup
**Plans**: 2 plans

Plans:
- [x] 17-01: Startup reconciliation
- [x] 17-02: Manual reconcile command

### Phase 18: Linux X11 Support
**Goal**: wmctrl/xdotool integration for Linux
**Plans**: 2 plans

Plans:
- [x] 18-01: Linux window ID tracking
- [x] 18-02: Desktop-native terminal preference

### Phase 19: Test Suite & Validation
**Goal**: Comprehensive testing for window tracking
**Plans**: 2 plans

Plans:
- [x] 19-01: Integration test for duplicate prevention
- [x] 19-02: Platform-specific tests and coverage validation

</details>

<details>
<summary>✅ v2.0.3 Container Tools (Phases 20-25) - SHIPPED 2026-02-10</summary>

### Phase 20: Multi-Stage Containerfile
**Goal**: Three-stage build with efficient layer caching
**Plans**: 2 plans

Plans:
- [x] 20-01: Multi-stage Containerfile architecture
- [x] 20-02: ARG parameter injection system

### Phase 21: Version Management
**Goal**: Independent image versioning with versions.yaml
**Plans**: 2 plans

Plans:
- [x] 21-01: versions.yaml config file
- [x] 21-02: Version extraction and validation

### Phase 22: Build Automation
**Goal**: build-container.sh with podman orchestration
**Plans**: 2 plans

Plans:
- [x] 22-01: Build script with yq version extraction
- [x] 22-02: Dry-run and verbose modes

### Phase 23: Registry Integration
**Goal**: skopeo query and exponential backoff retry
**Plans**: 1 plan

Plans:
- [x] 23-01: Registry query with retry logic

### Phase 24: Intelligent Auto-Versioning
**Goal**: Digest-based change detection and patch bumping
**Plans**: 1 plan

Plans:
- [x] 24-01: Digest comparison and auto-versioning logic

### Phase 25: Registry Publishing & OCM Verification
**Goal**: Automatic publishing to quay.io and OCM proof-of-concept
**Plans**: 2 plans

Plans:
- [x] 25-01: Automatic push to quay.io when image content changes
- [x] 25-02: OCM CLI integration with architecture-aware downloads and SHA256 verification

</details>

### 🚧 v2.0.4 Foundation (In Progress)

**Milestone Goal:** Build version checking infrastructure and configuration foundation for automatic updates (MC CLI only in this milestone)

#### Phase 26: Configuration Foundation
**Goal**: Extend TOML config system with version management fields and safe concurrent write patterns
**Depends on**: Phase 25 (v2.0.3 shipped)
**Requirements**: UCTL-05, UCTL-06, UCTL-09, UCTL-10
**Success Criteria** (what must be TRUE):
  1. TOML config persists pinned_mc_version field and last_version_check timestamp
  2. Concurrent mc processes can safely write to config without corruption (file locking)
  3. Config writes are atomic (temp file + rename pattern prevents partial writes)
  4. Config read operations return defaults when version management fields are missing (backward compatibility)
**Plans**: 2 plans

Plans:
- [ ] 26-01-PLAN.md — Extend config models with [version] section and atomic write implementation
- [ ] 26-02-PLAN.md — Test suite for version config functionality and backward compatibility

#### Phase 27: Runtime Mode Detection
**Goal**: Detect container vs host execution context to prevent auto-update in containerized environments
**Depends on**: Phase 26 (config foundation exists)
**Requirements**: RTMD-01, RTMD-02, RTMD-03
**Success Criteria** (what must be TRUE):
  1. System correctly identifies when running in container (agent mode) vs host
  2. Auto-update functionality is disabled when running in container mode
  3. Container mode shows informational message: "Updates managed via container builds"
  4. Runtime mode detection works across different container runtimes (podman, docker)
**Plans**: TBD

Plans:
- [ ] 27-01: TBD during planning

#### Phase 28: Version Check Infrastructure
**Goal**: Non-blocking GitHub API integration with throttling and caching for MC CLI version checking
**Depends on**: Phase 27 (runtime mode detection prevents container updates)
**Requirements**: VCHK-01, VCHK-03, VCHK-04, VCHK-05, VCHK-06, VCHK-07, VCHK-08
**Success Criteria** (what must be TRUE):
  1. System checks GitHub releases API for latest MC CLI version without blocking commands
  2. Version checks respect hourly throttle (no check if less than 1 hour since last check)
  3. System uses ETag conditional requests and caches version data with timestamps
  4. Version comparison uses PEP 440-compliant logic (packaging library)
  5. Network failures are handled gracefully (show warning, continue with current version)
**Plans**: TBD

Plans:
- [ ] 28-01: TBD during planning
- [ ] 28-02: TBD during planning

### 📋 v2.0.5 MC Auto-Update (Planned)

**Milestone Goal:** MC CLI auto-update functionality, mc-update utility for MC management, and update notifications

Phases TBD when v2.0.4 completes.

### 📋 v2.0.6 Container Management (Planned)

**Milestone Goal:** Container version checking, auto-pull, and unified dual-artifact control via mc-update

Phases TBD when v2.0.5 completes.

## Progress

**Execution Order:**
Phases execute in numeric order: 26 → 27 → 28

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 26. Configuration Foundation | v2.0.4 | 0/2 | Not started | - |
| 27. Runtime Mode Detection | v2.0.4 | 0/TBD | Not started | - |
| 28. Version Check Infrastructure | v2.0.4 | 0/TBD | Not started | - |

---
*Roadmap created: 2026-02-11 for v2.0.4 Foundation milestone*
*Last updated: 2026-02-19*
