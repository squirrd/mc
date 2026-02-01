# Roadmap: MC CLI v2.0 Containerization

## Overview

Transform MC from a traditional CLI tool into a container orchestrator providing isolated per-case workspaces. The roadmap progresses from foundation (Podman integration and platform detection) through core orchestration (container lifecycle and state management) to user-facing features (terminal automation and Salesforce integration) to delivery (container image with tooling). Each phase builds on previous work to establish a production-ready container-based workflow for managing Red Hat support cases.

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- 🚧 **v2.0 Containerization** - Phases 9-13 (in progress)

## Phases

<details>
<summary>✅ v1.0 Hardening (Phases 1-8) - SHIPPED 2026-01-22</summary>

### Phase 1: Test Infrastructure Foundation
**Goal**: Establish pytest framework with fixtures for mocking external dependencies
**Plans**: 1 plan
**Status**: Complete

### Phase 2: Critical Path Testing
**Goal**: Comprehensive test coverage for auth, API client, and workspace manager modules
**Plans**: 3 plans
**Status**: Complete

### Phase 3: Configuration System
**Goal**: TOML-based configuration replacing environment variables with cross-platform support
**Plans**: 2 plans
**Status**: Complete

### Phase 4: Security Hardening
**Goal**: Production-ready security with token caching, SSL verification, and input validation
**Plans**: 2 plans
**Status**: Complete

### Phase 5: Performance Optimization
**Goal**: Parallel downloads, intelligent caching, and retry logic for reliability
**Plans**: 2 plans
**Status**: Complete

### Phase 6: Structured Logging
**Goal**: Replace print statements with structured logging including sensitive data redaction
**Plans**: 3 plans
**Status**: Complete

### Phase 7: Code Quality & Error Handling
**Goal**: Robust error handling, improved parsing, and better user feedback
**Plans**: 3 plans
**Status**: Complete

### Phase 8: Type Safety & Modernization
**Goal**: Full type hints, mypy strict mode, and Python 3.11+ syntax
**Plans**: 1 plan
**Status**: Complete

</details>

## 🚧 v2.0 Containerization (In Progress)

**Milestone Goal:** Transform MC into a container orchestrator providing isolated per-case workspaces with persistent containers

### Phase 9: Container Architecture & Podman Integration
**Goal**: Establish Podman platform detection and connection foundation for container orchestration
**Depends on**: Nothing (first phase of v2.0)
**Requirements**: INFRA-01, INFRA-03, INFRA-04
**Success Criteria** (what must be TRUE):
  1. Developer can connect to Podman socket (macOS VM or Linux native)
  2. Platform differences handled transparently (macOS Podman machine auto-starts)
  3. Podman availability validated with helpful error messages
**Plans**: 2 plans
**Status**: Complete
**Completed**: 2026-01-26

Plans:
- [x] 09-01-PLAN.md — Platform detection and Podman availability checking
- [x] 09-02-PLAN.md — Podman client wrapper with lazy connection and retry logic

### Phase 10: Salesforce Integration & Case Resolution
**Goal**: Query Salesforce for case metadata with caching and automatic token refresh
**Depends on**: Nothing (independent of Phase 9, can develop in parallel)
**Requirements**: SF-01, SF-02, SF-03, SF-04, SF-05
**Success Criteria** (what must be TRUE):
  1. Developer can query case metadata from Salesforce API (customer name, cluster ID, severity, owner)
  2. Case metadata cached locally with 30-minute TTL (reduces API calls)
  3. Salesforce access tokens refresh automatically before expiration (no authentication failures)
  4. Rate limiting handled gracefully (exponential backoff on 429 errors)
  5. Workspace paths resolved from case metadata (customer name, case number)
**Plans**: 3 plans
**Status**: Complete
**Completed**: 2026-01-26

Plans:
- [x] 10-01-PLAN.md — Salesforce API client with session management and token refresh
- [x] 10-02-PLAN.md — SQLite cache with background refresh worker
- [x] 10-03-PLAN.md — Case number to workspace path resolution

### Phase 11: Container Lifecycle & State Management
**Goal**: Orchestrate container creation, listing, stopping, deletion with state reconciliation
**Depends on**: Phase 9 (requires Podman integration)
**Requirements**: INFRA-02, INFRA-05, CONT-01, CONT-02, CONT-03, CONT-04, CONT-05, CONT-06, CONT-07, CONT-08
**Success Criteria** (what must be TRUE):
  1. Developer can create container from case number (workspace mounted at /case with correct permissions)
  2. Developer can list all case containers showing status and metadata
  3. Developer can stop running container (graceful shutdown)
  4. Developer can delete container and cleanup workspace
  5. Developer can execute command inside container
  6. Stopped containers auto-restart on access
  7. State reconciles correctly after external Podman operations (no orphaned metadata)
  8. Container volumes use UID/GID mapping (--userns=keep-id) for correct host user permissions
**Plans**: 5 plans
**Status**: Complete
**Completed**: 2026-01-26

Plans:
- [x] 11-01-PLAN.md — SQLite state management with WAL mode and reconciliation
- [x] 11-02-PLAN.md — Container creation with volume mounting and UID/GID mapping
- [x] 11-03-PLAN.md — Container listing with formatted table output
- [x] 11-04-PLAN.md — Container lifecycle operations (stop, delete, status, logs)
- [x] 11-05-PLAN.md — Command execution with auto-restart and CLI integration

### Phase 12: Terminal Attachment & Exec
**Goal**: Auto-open terminal windows to containerized workspaces on case access
**Depends on**: Phase 11 (requires working container lifecycle)
**Requirements**: TERM-01, TERM-02, TERM-03, TERM-04, TERM-05
**Success Criteria** (what must be TRUE):
  1. Developer runs `mc case 12345678` and new terminal window opens attached to container
  2. Terminal detection works across platforms (iTerm2/Terminal.app on macOS, gnome-terminal/konsole/xterm on Linux)
  3. Host terminal returns to prompt after launching container terminal
  4. Graceful degradation when terminal emulator unsupported (helpful error message)
  5. TTY detection prevents breaking piped/programmatic output
**Plans**: 3 plans
**Status**: Complete
**Completed**: 2026-01-27

Plans:
- [x] 12-01-PLAN.md — Terminal launcher abstraction with macOS and Linux support
- [x] 12-02-PLAN.md — Shell customization and welcome banner with case metadata
- [x] 12-03-PLAN.md — CLI integration with auto-create/attach workflow

### Phase 13: Container Image & Backwards Compatibility
**Goal**: Build RHEL 10 container image with mc CLI and validate v1.0 commands work unchanged
**Depends on**: Phase 11 (requires container lifecycle for testing)
**Requirements**: IMG-01, IMG-02, IMG-04, IMG-05, IMG-06, IMG-07, COMPAT-01, COMPAT-02, COMPAT-03
**Success Criteria** (what must be TRUE):
  1. RHEL 10 base image builds successfully with essential bash tools (openssl, curl, jq, vim)
  2. MC CLI installed in container with runtime mode detection (agent mode)
  3. Case workspace mounted at /case
  4. MC CLI configuration accessible in container
  5. Container entrypoint initializes environment and drops to shell
  6. All v1.0 commands work unchanged on host (no breaking changes)
  7. Existing workspace structure compatible with containers
**Plans**: 2 plans
**Status**: Complete
**Completed**: 2026-01-27

Plans:
- [x] 13-01-PLAN.md — RHEL 10 UBI image with mc CLI and runtime mode detection
- [x] 13-02-PLAN.md — Container integration with ContainerManager and lifecycle testing

### Phase 14: Installation & Distribution - Support dev/UAT/prod workflows with uv tool

**Goal:** Establish portable installation workflows for development, UAT, and production using uv tool
**Depends on:** Phase 13
**Plans:** 2 plans
**Status:** Complete
**Completed:** 2026-02-01

Plans:
- [x] 14-01-PLAN.md — uv project setup with lockfile and installation documentation
- [x] 14-02-PLAN.md — Entry point testing and UAT workflow validation

**Details:**
Three distinct workflows enabled by uv tool:
- Development: `uv run` for automatic environment management and editable installs
- UAT: `uv tool install -e .` for temporary testing from local directory
- Production: `uv tool install git+...` for global installation from git or PyPI

## Progress

**Execution Order:**
Phases execute in numeric order: 9 → 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Test Infrastructure Foundation | v1.0 | 1/1 | Complete | 2026-01-20 |
| 2. Critical Path Testing | v1.0 | 3/3 | Complete | 2026-01-20 |
| 3. Configuration System | v1.0 | 2/2 | Complete | 2026-01-21 |
| 4. Security Hardening | v1.0 | 2/2 | Complete | 2026-01-21 |
| 5. Performance Optimization | v1.0 | 2/2 | Complete | 2026-01-21 |
| 6. Structured Logging | v1.0 | 3/3 | Complete | 2026-01-21 |
| 7. Code Quality & Error Handling | v1.0 | 3/3 | Complete | 2026-01-22 |
| 8. Type Safety & Modernization | v1.0 | 1/1 | Complete | 2026-01-22 |
| 9. Container Architecture & Podman Integration | v2.0 | 2/2 | Complete | 2026-01-26 |
| 10. Salesforce Integration & Case Resolution | v2.0 | 3/3 | Complete | 2026-01-26 |
| 11. Container Lifecycle & State Management | v2.0 | 5/5 | Complete | 2026-01-26 |
| 12. Terminal Attachment & Exec | v2.0 | 3/3 | Complete | 2026-01-27 |
| 13. Container Image & Backwards Compatibility | v2.0 | 2/2 | Complete | 2026-01-27 |
| 14. Installation & Distribution | v2.0 | 2/2 | Complete | 2026-02-01 |

**Note:** OpenShift tools (oc, ocm, backplane) deferred to v2.1+ milestones. Each tool will be its own milestone to handle tool-specific configuration mounting requirements.

---
*Roadmap created: 2026-01-26*
*Last updated: 2026-02-01 (Phase 14 complete: v2.0 milestone finished)*
