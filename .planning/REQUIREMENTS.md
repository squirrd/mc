# Requirements: MC CLI v2.0 Containerization

**Defined:** 2026-01-26
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently

## v2.0 Requirements

Requirements for containerization milestone. Each maps to roadmap phases.

### Infrastructure

- [ ] **INFRA-01**: Podman integration via podman-py library
- [ ] **INFRA-02**: SQLite state database for container metadata
- [ ] **INFRA-03**: Platform detection (macOS vs Linux)
- [ ] **INFRA-04**: Podman machine auto-start on macOS
- [ ] **INFRA-05**: Rootless container UID/GID mapping configured

### Container Lifecycle

- [ ] **CONT-01**: User can create container from case number
- [ ] **CONT-02**: User can list all case containers (running and stopped)
- [ ] **CONT-03**: User can stop running container
- [ ] **CONT-04**: User can delete container and cleanup workspace
- [ ] **CONT-05**: User can execute command inside container
- [ ] **CONT-06**: User can check container status (running, stopped, missing)
- [ ] **CONT-07**: User can view container logs
- [ ] **CONT-08**: Stopped containers auto-restart on access

### Salesforce Integration

- [ ] **SF-01**: Query Salesforce for case metadata (customer name, cluster ID)
- [ ] **SF-02**: Cache case metadata locally with 5-minute TTL
- [ ] **SF-03**: Auto-refresh Salesforce access tokens before expiration
- [ ] **SF-04**: Handle Salesforce rate limits with exponential backoff
- [ ] **SF-05**: Resolve workspace paths from case metadata

### Terminal Integration

- [ ] **TERM-01**: Auto-open new terminal window on `mc case <number>`
- [ ] **TERM-02**: Detect terminal emulator (iTerm2, gnome-terminal, etc.)
- [ ] **TERM-03**: Attach container shell in new terminal window
- [ ] **TERM-04**: Graceful degradation if terminal emulator unsupported
- [ ] **TERM-05**: Return host terminal to prompt after launching container

### Container Image

- [ ] **IMG-01**: Build RHEL 10 base container image
- [ ] **IMG-02**: Install essential bash tools in image (openssl, curl, jq, vim, etc.)
- [ ] **IMG-04**: Install mc CLI in container (agent mode)
- [ ] **IMG-05**: Mount case workspace at /case in container
- [ ] **IMG-06**: Container has access to mc CLI configuration
- [ ] **IMG-07**: Container entrypoint initializes environment and drops to shell

### Backwards Compatibility

- [ ] **COMPAT-01**: All v1.0 commands work unchanged on host
- [ ] **COMPAT-02**: Existing workspace structure compatible with containers
- [ ] **COMPAT-03**: Configuration files readable by both host and container mc

## v2.1+ Requirements

Deferred to future milestones.

### Auto-Update System

- **UPDATE-01**: Host mc CLI auto-updates from PyPI
- **UPDATE-02**: Container image auto-pulls from quay.io
- **UPDATE-03**: Image versioning and upgrade detection
- **UPDATE-04**: mc update command with version pinning

### Advanced Lifecycle

- **CONT-09**: Bulk operations (stop all, cleanup old containers)
- **CONT-10**: Resource limits (memory, CPU) per container
- **CONT-11**: Health monitoring and alerts

### Advanced Terminal

- **TERM-06**: Multiple terminal windows to same container
- **TERM-07**: Custom shell preferences (bash, zsh, fish)

### Mount Policy Engine

- **MOUNT-01**: Declarative mount configuration (mounts.yaml)
- **MOUNT-02**: Multi-user permissions (admin/user roles)
- **MOUNT-03**: Dynamic variable substitution in mount paths

### Automatic Housekeeping

- **MAINT-01**: Auto-stop containers after inactivity
- **MAINT-02**: Auto-cleanup stopped containers after N days
- **MAINT-03**: Compact case data (remove duplicates)

### Container Tools

Each tool becomes its own milestone (v2.1, v2.2, etc.) to handle tool-specific configuration mounting:

- **IMG-03**: Install OpenShift tools (oc, ocm, backplane) with tool-specific config mounting
- **TOOLS-01**: AWS CLI and rh-aws-saml-login
- **TOOLS-02**: ROSA CLI
- **TOOLS-03**: claude code and AI tools
- **TOOLS-04**: wireshark and analysis tools

## Out of Scope

Explicitly excluded from v2.x.

| Feature | Reason |
|---------|--------|
| Docker support | Podman only - rootless security model, Red Hat ecosystem alignment |
| Windows native support | WSL2 + Podman sufficient, native Windows complexity not justified |
| GUI/web interface | CLI-focused tool by design |
| SSH into containers | Anti-pattern - use exec, not SSH servers in containers |
| Running containers as root | Security risk - rootless only |
| Nested virtualization | Use Podman-in-Podman for container testing if needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| INFRA-01 | Phase 9 | Pending |
| INFRA-02 | Phase 11 | Pending |
| INFRA-03 | Phase 9 | Pending |
| INFRA-04 | Phase 9 | Pending |
| INFRA-05 | Phase 11 | Pending |
| CONT-01 | Phase 11 | Pending |
| CONT-02 | Phase 11 | Pending |
| CONT-03 | Phase 11 | Pending |
| CONT-04 | Phase 11 | Pending |
| CONT-05 | Phase 11 | Pending |
| CONT-06 | Phase 11 | Pending |
| CONT-07 | Phase 11 | Pending |
| CONT-08 | Phase 11 | Pending |
| SF-01 | Phase 10 | Pending |
| SF-02 | Phase 10 | Pending |
| SF-03 | Phase 10 | Pending |
| SF-04 | Phase 10 | Pending |
| SF-05 | Phase 10 | Pending |
| TERM-01 | Phase 12 | Pending |
| TERM-02 | Phase 12 | Pending |
| TERM-03 | Phase 12 | Pending |
| TERM-04 | Phase 12 | Pending |
| TERM-05 | Phase 12 | Pending |
| IMG-01 | Phase 13 | Pending |
| IMG-02 | Phase 13 | Pending |
| IMG-04 | Phase 13 | Pending |
| IMG-05 | Phase 13 | Pending |
| IMG-06 | Phase 13 | Pending |
| IMG-07 | Phase 13 | Pending |
| COMPAT-01 | Phase 13 | Pending |
| COMPAT-02 | Phase 13 | Pending |
| COMPAT-03 | Phase 13 | Pending |

**Coverage:**
- v2.0 requirements: 32 total (IMG-03 deferred to v2.1+)
- Mapped to phases: 32 (100% coverage)
- Unmapped: 0

**Phase breakdown:**
- Phase 9: 3 requirements (INFRA-01, INFRA-03, INFRA-04)
- Phase 10: 5 requirements (SF-01, SF-02, SF-03, SF-04, SF-05)
- Phase 11: 10 requirements (INFRA-02, INFRA-05, CONT-01 through CONT-08)
- Phase 12: 5 requirements (TERM-01 through TERM-05)
- Phase 13: 9 requirements (IMG-01, IMG-02, IMG-04 through IMG-07, COMPAT-01 through COMPAT-03)

---
*Requirements defined: 2026-01-26*
*Last updated: 2026-01-26 (SF-02 clarified: 5-minute TTL)*
