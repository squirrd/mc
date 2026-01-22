# Requirements: MC CLI Hardening Project

**Defined:** 2026-01-20
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently

## v1 Requirements

Requirements for production-ready codebase. Each maps to roadmap phases.

### Test Infrastructure

- [x] **TEST-01**: pytest framework configured and working
- [x] **TEST-02**: pytest-mock installed for API/external service mocking
- [x] **TEST-03**: Test fixtures infrastructure set up
- [ ] **TEST-04**: Unit tests for auth module (get_access_token)
- [ ] **TEST-05**: Unit tests for RedHatAPIClient with mocked requests
- [ ] **TEST-06**: Unit tests for WorkspaceManager
- [ ] **TEST-07**: Unit tests for formatters and file_ops utilities
- [ ] **TEST-08**: Mock LDAP responses for integration testing

### Tech Debt

- [x] **DEBT-01**: Fix hardcoded base directory (use TOML config file with default)
- [x] **DEBT-02**: Remove environment variable dependencies and duplicate validation
- [x] **DEBT-03**: Consolidate version management (single source of truth)
- [x] **DEBT-04**: Migrate fully to pyproject.toml (remove setup.py)
- [x] **DEBT-05**: Fix typo "dowloading attachemnts" → "downloading attachments"

### Bug Fixes

- [x] **BUG-01**: Fix LDAP --All flag (change to --all lowercase)
- [x] **BUG-02**: Fix CheckStaus → CheckStatus typo throughout

### Security Hardening

- [ ] **SEC-01**: Add access token expiration validation and caching
- [ ] **SEC-02**: Explicitly set verify=True in all requests calls
- [ ] **SEC-03**: Add case number format validation (8 digits)
- [ ] **SEC-04**: Add file size warning for downloads >3GB (no prompting)

### Performance

- [ ] **PERF-01**: Implement parallel attachment downloads (4+ threads with ThreadPoolExecutor)
- [ ] **PERF-02**: Add file-based caching for case metadata with TTL
- [ ] **PERF-03**: Cache access tokens with expiration tracking

### Code Quality

- [ ] **QUAL-01**: Improve workspace path construction error handling
- [ ] **QUAL-02**: Add robust LDAP parsing with error handling for malformed responses
- [ ] **QUAL-03**: Improve file existence checks (better error messages, pathlib)
- [ ] **QUAL-04**: Add HTTP error handling with meaningful messages (401, 403, 404, 500)
- [ ] **QUAL-05**: Add retry logic for transient API failures

### Infrastructure

- [ ] **INFRA-01**: Implement structured logging framework (replace print statements)
- [ ] **INFRA-02**: Add error recovery and retry for attachment downloads
- [ ] **INFRA-03**: Add download progress indication for large files

### Dependencies

- [ ] **DEP-01**: Update minimum Python version to 3.10+
- [ ] **DEP-02**: Add type hints to all modules
- [ ] **DEP-03**: Configure mypy strict mode and resolve issues

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Configuration

- **CONFIG-01**: YAML-based configuration file support
- **CONFIG-02**: User profiles for different case types
- **CONFIG-03**: Mount configuration management

### Container Features

- **CONTAINER-01**: Per-case container orchestration
- **CONTAINER-02**: Multi-user container support
- **CONTAINER-03**: Container lifecycle management

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| GUI or TUI interface | CLI tool by design; GUI adds massive complexity and defeats automation purpose |
| Real-time notifications | Requires background daemon; polling overhead; not needed for CLI workflow |
| Plugin system | Security risks; version compatibility nightmares; CLI tools should have focused scope |
| Web-based interface | If web UI needed, make it separate project; embedded web server is security risk |
| Database storage | File-based storage is simpler and sufficient; database adds deployment complexity |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | Phase 1 | Complete |
| TEST-02 | Phase 1 | Complete |
| TEST-03 | Phase 1 | Complete |
| TEST-04 | Phase 2 | Complete |
| TEST-05 | Phase 2 | Complete |
| TEST-06 | Phase 2 | Complete |
| TEST-07 | Phase 2 | Complete |
| TEST-08 | Phase 2 | Complete |
| DEBT-01 | Phase 3 | Complete |
| DEBT-02 | Phase 3 | Complete |
| DEBT-03 | Phase 3 | Complete |
| DEBT-04 | Phase 3 | Complete |
| DEBT-05 | Phase 3 | Complete |
| BUG-01 | Phase 3 | Complete |
| BUG-02 | Phase 3 | Complete |
| SEC-01 | Phase 4 | Pending |
| SEC-02 | Phase 4 | Pending |
| SEC-03 | Phase 4 | Pending |
| SEC-04 | Phase 4 | Pending |
| QUAL-01 | Phase 5 | Pending |
| QUAL-02 | Phase 5 | Pending |
| QUAL-03 | Phase 5 | Pending |
| QUAL-04 | Phase 5 | Pending |
| QUAL-05 | Phase 5 | Pending |
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 6 | Pending |
| INFRA-03 | Phase 6 | Pending |
| PERF-01 | Phase 7 | Pending |
| PERF-02 | Phase 7 | Pending |
| PERF-03 | Phase 7 | Pending |
| DEP-01 | Phase 8 | Pending |
| DEP-02 | Phase 8 | Pending |
| DEP-03 | Phase 8 | Pending |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 33
- Unmapped: 0 ✓

---
*Requirements defined: 2026-01-20*
*Last updated: 2026-01-20 after roadmap creation*
