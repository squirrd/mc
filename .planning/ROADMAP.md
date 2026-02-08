# Roadmap: MC CLI Window Tracking System

## Overview

Add window ID tracking to MC CLI's terminal automation to eliminate duplicate terminal windows. The system extends existing SQLite infrastructure with a window registry, captures platform-specific window IDs at creation time, and focuses existing windows instead of creating duplicates. Five phases deliver incrementally: foundation registry, macOS implementation, cleanup mechanisms, Linux support, and comprehensive testing.

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- ✅ **v2.0 Containerization** - Phases 9-14 (shipped 2026-02-01)
- ✅ **v2.0.1 Cleanup** - Phase 14.1 (shipped 2026-02-02)
- 🚧 **v2.0.2 Window Tracking** - Phases 15-19 (in progress)

## Phases

<details>
<summary>✅ v1.0 Hardening (Phases 1-8) - SHIPPED 2026-01-22</summary>

### Phase 1: Test Infrastructure
**Goal**: pytest framework configured with fixtures and mocking
**Plans**: 3 plans

Plans:
- [x] 01-01: Setup pytest framework
- [x] 01-02: Install pytest-mock and create fixtures
- [x] 01-03: Configure test structure

### Phase 2: Critical Path Testing
**Goal**: Core modules have 80%+ test coverage
**Plans**: 3 plans

Plans:
- [x] 02-01: Unit tests for auth module
- [x] 02-02: Unit tests for RedHatAPIClient
- [x] 02-03: Unit tests for WorkspaceManager

### Phase 3: Tech Debt Resolution
**Goal**: Remove hardcoded values and environment dependencies
**Plans**: 2 plans

Plans:
- [x] 03-01: Implement TOML config system
- [x] 03-02: Remove environment variables and consolidate version

### Phase 4: Bug Fixes
**Goal**: Known bugs resolved
**Plans**: 1 plan

Plans:
- [x] 04-01: Fix LDAP --All flag and typos

### Phase 5: Security Hardening
**Goal**: Production-ready security features implemented
**Plans**: 2 plans

Plans:
- [x] 05-01: Add token caching and validation
- [x] 05-02: Input validation and file size warnings

### Phase 6: Performance Optimization
**Goal**: Fast parallel downloads with caching
**Plans**: 2 plans

Plans:
- [x] 06-01: Implement parallel attachment downloads
- [x] 06-02: Add file-based caching for case metadata

### Phase 7: Code Quality Improvements
**Goal**: Robust error handling and modern Python patterns
**Plans**: 2 plans

Plans:
- [x] 07-01: Improve error handling throughout
- [x] 07-02: Add retry logic for API failures

### Phase 8: Type Safety and Logging
**Goal**: Full type hints with mypy strict mode and structured logging
**Plans**: 3 plans

Plans:
- [x] 08-01: Add type hints and configure mypy
- [x] 08-02: Implement structured logging framework
- [x] 08-03: Add download progress indication

</details>

<details>
<summary>✅ v2.0 Containerization (Phases 9-14) - SHIPPED 2026-02-01</summary>

### Phase 9: Container Foundations
**Goal**: podman-py integration with lifecycle management
**Plans**: 3 plans

Plans:
- [x] 09-01: Install podman-py and implement ContainerManager
- [x] 09-02: Add SQLite state persistence
- [x] 09-03: Implement create/list/stop/delete commands

### Phase 10: Platform Detection & Podman
**Goal**: Cross-platform Podman setup with lazy connection
**Plans**: 2 plans

Plans:
- [x] 10-01: Detect macOS/Linux and handle Podman machine
- [x] 10-02: Implement lazy connection with retry logic

### Phase 11: Salesforce Integration
**Goal**: Automatic case metadata resolution from Salesforce
**Plans**: 2 plans

Plans:
- [x] 11-01: Implement SalesforceClient with query_case
- [x] 11-02: Add 5-minute cache TTL and workspace path resolution

### Phase 12: Terminal Automation
**Goal**: Automatic terminal attachment for case containers
**Plans**: 3 plans

Plans:
- [x] 12-01: Implement terminal detection (iTerm2, Terminal.app, gnome-terminal, konsole)
- [x] 12-02: Create custom bashrc with welcome banner
- [x] 12-03: Add terminal window launching

### Phase 13: Container Image
**Goal**: RHEL 10 UBI image with MC CLI and essential tools
**Plans**: 3 plans

Plans:
- [x] 13-01: Create Containerfile with RHEL 10 UBI base
- [x] 13-02: Install MC CLI and bash tools
- [x] 13-03: Add runtime mode detection

### Phase 14: Modern Distribution
**Goal**: uv tool distribution for dev, UAT, and production
**Plans**: 2 plans

Plans:
- [x] 14-01: Configure pyproject.toml for uv tool install
- [x] 14-02: Document installation workflows

### Phase 14.1: Critical Fixes (INSERTED)
**Goal**: Fix terminal attachment and Podman URI bugs from v2.0
**Plans**: 5 plans

Plans:
- [x] 14.1-01: Fix terminal attachment bug (Salesforce API method)
- [x] 14.1-02: Fix Podman URI byte string errors
- [x] 14.1-03: Fix cache database initialization
- [x] 14.1-04: Consolidate configuration paths
- [x] 14.1-05: Improve test suite (503 tests, 77% coverage)

</details>

### 🚧 v2.0.2 Window Tracking (In Progress)

**Milestone Goal:** Eliminate duplicate terminal windows by implementing window ID tracking system

#### Phase 15: Window Registry Foundation
**Goal**: Persistent window ID storage with concurrent access support
**Depends on**: Nothing (foundation phase)
**Requirements**: WR-01, WR-02, WR-03, WR-04
**Success Criteria** (what must be TRUE):
  1. System stores window ID when terminal created (case_number → window_id mapping)
  2. System retrieves window ID by case number from registry
  3. Registry persists across mc process restarts (SQLite-backed)
  4. Multiple concurrent mc processes access registry without corruption (WAL mode)
**Plans**: 2 plans

Plans:
- [x] 15-01: WindowRegistry class with SQLite backend (Wave 1)
- [x] 15-02: macOS window ID methods and unit tests (Wave 2)

#### Phase 16: macOS Window Tracking
**Goal**: Duplicate terminal prevention working on macOS
**Depends on**: Phase 15
**Requirements**: WM-01, WM-02, WM-03, WM-04, WM-06
**Success Criteria** (what must be TRUE):
  1. Running `mc case XXXXX` twice focuses existing window instead of creating duplicate
  2. System validates window still exists before attempting focus
  3. System creates new window if previous window was closed manually
  4. Window focusing works reliably on iTerm2 and Terminal.app
  5. User sees feedback message when focusing vs creating ("Focused existing window" vs "Created new terminal")
**Plans**: 2 plans

Plans:
- [ ] 16-01-PLAN.md — Window focus implementation (focus_window_by_id method)
- [ ] 16-02-PLAN.md — Registry integration (attach_terminal workflow updates)

#### Phase 17: Registry Cleanup & Maintenance
**Goal**: Self-healing registry that stays accurate over time
**Depends on**: Phase 16
**Requirements**: WR-05, WR-06, WR-07
**Success Criteria** (what must be TRUE):
  1. System detects and removes stale entries for manually closed windows
  2. Automatic cleanup on startup reconciles registry with actual windows
  3. Manual `mc container reconcile` command cleans orphaned entries
  4. Registry stays accurate after 1 week of daily use (no accumulation of stale entries)
**Plans**: TBD

Plans:
- [ ] 17-01: [Plan TBD - run /gsd:plan-phase 17]

#### Phase 18: Linux Support
**Goal**: Cross-platform window tracking with graceful fallback
**Depends on**: Phase 16
**Requirements**: WM-05
**Success Criteria** (what must be TRUE):
  1. Window focusing works on Linux X11 systems (gnome-terminal, konsole)
  2. System detects X11 vs Wayland and uses appropriate APIs
  3. System falls back gracefully when wmctrl/xdotool unavailable
  4. Documentation clearly states X11-only support
**Plans**: TBD

Plans:
- [ ] 18-01: [Plan TBD - run /gsd:plan-phase 18]

#### Phase 19: Test Suite & Validation
**Goal**: Comprehensive testing proves no duplicate terminals created
**Depends on**: Phases 16, 17, 18
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. Integration test `test_duplicate_terminal_prevention_regression` passes consistently
  2. Unit tests validate WindowRegistry store/lookup/cleanup operations
  3. Manual testing on macOS confirms no duplicates on repeated `mc case XXXXX`
  4. Platform-specific tests pass on both macOS and Linux
**Plans**: TBD

Plans:
- [ ] 19-01: [Plan TBD - run /gsd:plan-phase 19]

## Progress

**Execution Order:**
Phases execute in numeric order: 15 → 16 → 17 → 18 → 19

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Test Infrastructure | v1.0 | 3/3 | Complete | 2026-01-22 |
| 2. Critical Path Testing | v1.0 | 3/3 | Complete | 2026-01-22 |
| 3. Tech Debt Resolution | v1.0 | 2/2 | Complete | 2026-01-22 |
| 4. Bug Fixes | v1.0 | 1/1 | Complete | 2026-01-22 |
| 5. Security Hardening | v1.0 | 2/2 | Complete | 2026-01-22 |
| 6. Performance Optimization | v1.0 | 2/2 | Complete | 2026-01-22 |
| 7. Code Quality | v1.0 | 2/2 | Complete | 2026-01-22 |
| 8. Type Safety & Logging | v1.0 | 3/3 | Complete | 2026-01-22 |
| 9. Container Foundations | v2.0 | 3/3 | Complete | 2026-02-01 |
| 10. Platform Detection | v2.0 | 2/2 | Complete | 2026-02-01 |
| 11. Salesforce Integration | v2.0 | 2/2 | Complete | 2026-02-01 |
| 12. Terminal Automation | v2.0 | 3/3 | Complete | 2026-02-01 |
| 13. Container Image | v2.0 | 3/3 | Complete | 2026-02-01 |
| 14. Modern Distribution | v2.0 | 2/2 | Complete | 2026-02-01 |
| 14.1. Critical Fixes | v2.0.1 | 5/5 | Complete | 2026-02-02 |
| 15. Window Registry Foundation | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 16. macOS Window Tracking | v2.0.2 | 2/2 | Complete | 2026-02-08 |
| 17. Registry Cleanup | v2.0.2 | 0/TBD | Not started | - |
| 18. Linux Support | v2.0.2 | 0/TBD | Not started | - |
| 19. Test Suite & Validation | v2.0.2 | 0/TBD | Not started | - |
