# Requirements: MC CLI Version Management (Multi-Milestone)

**Defined:** 2026-02-11
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality

**Scope:** Three-milestone incremental delivery
- **v2.0.4 Foundation:** Version checking infrastructure, config system, runtime detection
- **v2.0.5 MC Auto-Update:** MC CLI auto-update, mc-update utility for MC, notifications
- **v2.0.6 Container Management:** Container version checking, auto-pull, unified dual-artifact control

---

## v2.0.4 Requirements (Foundation)

Infrastructure for version checking, configuration management, and runtime detection. Foundation for subsequent milestones.

### Version Checking Infrastructure (MC CLI only)

- [ ] **VCHK-01**: System checks GitHub releases API for latest MC CLI version
- [ ] **VCHK-03**: Version checks use hourly throttling (timestamp-based, no check if <1 hour since last)
- [ ] **VCHK-04**: Version checks are non-blocking (never delay mc command execution)
- [ ] **VCHK-05**: System uses ETag conditional requests to prevent GitHub API rate limiting
- [ ] **VCHK-06**: System caches version data with timestamps for offline resilience
- [ ] **VCHK-07**: System compares versions using PEP 440-compliant comparison (packaging library)
- [ ] **VCHK-08**: System handles network failures gracefully (show warning, continue with current version)

### Configuration Management

- [ ] **UCTL-05**: System persists pinned versions in TOML config (pinned_mc_version field)
- [ ] **UCTL-06**: System persists last version check timestamp in TOML config
- [ ] **UCTL-09**: System uses file locking to prevent concurrent TOML config writes
- [ ] **UCTL-10**: System performs atomic writes to TOML config (write temp, rename)

### Runtime Mode Detection

- [ ] **RTMD-01**: System detects when running in container (agent mode) vs host
- [ ] **RTMD-02**: System disables auto-update when running in container (agent mode)
- [ ] **RTMD-03**: Container mode shows informational message: "Updates managed via container builds"

---

## v2.0.5 Requirements (MC Auto-Update)

MC CLI auto-update functionality, mc-update utility for MC management, and update notifications.

### Update Control & Pinning (MC CLI)

- [ ] **UCTL-01**: User can pin MC CLI to specific version via `mc-update mc <version>`
- [ ] **UCTL-02**: User can unpin MC CLI and update to latest via `mc-update mc` (no version arg)
- [ ] **UCTL-11**: System suppresses pin warnings for 2 days after pinning (grace period)
- [ ] **UCTL-12**: System shows weekly warnings when pinned version is stale (after grace period)

### Update Notifications (MC CLI)

- [ ] **NOTF-01**: System displays update notifications as Rich banners on stderr
- [ ] **NOTF-02**: Notifications are non-blocking (shown post-command, not pre-command)
- [ ] **NOTF-03**: System shows "⚡ Updated to MC v2.0.5" banner after auto-update completes
- [ ] **NOTF-04**: System shows "⚠ MC v2.0.5 available (pinned to v2.0.3)" banner when newer version available but pinned
- [ ] **NOTF-05**: Stale pin notifications include unpin hint: "Run 'mc-update mc' to unpin and update"
- [ ] **NOTF-09**: System suppresses duplicate notifications (once per day per version)
- [ ] **NOTF-10**: User can dismiss notifications for current session

### Auto-Update Mechanics (MC CLI)

- [ ] **AUPD-01**: System auto-updates MC CLI to latest unless version is pinned
- [ ] **AUPD-02**: System uses `uv tool upgrade mc` subprocess for MC CLI updates
- [ ] **AUPD-03**: System validates post-upgrade (`mc --version` check after uv upgrade)
- [ ] **AUPD-04**: System provides recovery instructions if uv upgrade fails
- [ ] **AUPD-08**: System skips auto-update when GitHub API rate limit is hit (retry next hour)

### mc-update Utility (MC commands)

- [ ] **MCUP-01**: mc-update command is bundled with mc package (console_scripts entry point)
- [ ] **MCUP-02**: mc-update survives mc package upgrades (uv tool upgrade preserves both entry points)
- [ ] **MCUP-03**: `mc-update list` shows latest 5 MC CLI versions from GitHub releases with dates
- [ ] **MCUP-05**: `mc-update mc <version>` pins MC CLI to specified version (rollback/upgrade)
- [ ] **MCUP-06**: `mc-update mc` (no args) unpins and updates to latest
- [ ] **MCUP-09**: `mc-update check` manually triggers version check (bypasses hourly throttle)
- [ ] **MCUP-10**: mc-update commands provide clear feedback (success/failure messages)

---

## v2.0.6 Requirements (Container Management)

Container version checking, auto-pull, and unified dual-artifact control via mc-update.

### Version Checking Infrastructure (Container)

- [ ] **VCHK-02**: System checks Quay.io registry API for latest container image version
- [ ] **VCHK-09**: System coordinates dual-artifact checks (MC CLI + container) in single pass

### Update Control & Pinning (Container)

- [ ] **UCTL-03**: User can pin container image to specific version via `mc-update container <version>`
- [ ] **UCTL-04**: User can unpin container image and use latest via `mc-update container` (no version arg)
- [ ] **UCTL-05b**: System persists pinned_container_version in TOML config (extends v2.0.4 UCTL-05)

### Update Notifications (Container)

- [ ] **NOTF-06**: System shows "⚡ Container updated to 1.0.6" banner after container image auto-pull
- [ ] **NOTF-07**: System shows "⚠ Container 1.0.6 available (pinned to 1.0.5)" banner when newer image available but pinned
- [ ] **NOTF-08**: Container pin notifications include unpin hint: "Run 'mc-update container' to unpin"

### Auto-Update Mechanics (Container)

- [ ] **AUPD-05**: System auto-pulls latest container image for new containers unless version is pinned
- [ ] **AUPD-06**: System uses existing Podman integration for container image pulls
- [ ] **AUPD-07**: Running containers are unaffected by image updates (only new containers use updated image)
- [ ] **AUPD-09**: System skips auto-update when Quay.io API is unavailable (retry next hour)

### mc-update Utility (Container commands)

- [ ] **MCUP-04**: `mc-update list` shows latest 5 container versions from Quay.io registry with dates
- [ ] **MCUP-07**: `mc-update container <version>` pins container image to specified version
- [ ] **MCUP-08**: `mc-update container` (no args) unpins and uses latest image

---

## Future Requirements (v2.1+)

Deferred to future releases. Tracked but not in current roadmap.

### Advanced Pinning

- **APIN-01**: Support granular pin patterns (2.0.x for patches, 2.x for minor+patches)
- **APIN-02**: Support pinning with reason annotation (`mc-update mc pin 2.0.3 --reason "auth bug in 2.0.4"`)
- **APIN-03**: Display pin reason in stale warnings

### Release Verification

- **VRFY-01**: Verify GitHub release signatures before auto-update
- **VRFY-02**: Verify container image signatures from Quay.io

### Advanced Notifications

- **ADVN-01**: Support notification suppression config (disable for CI environments)
- **ADVN-02**: Support notification verbosity levels (minimal/normal/verbose)

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Automatic silent updates | Breaks user trust; surprise changes; research shows explicit control is table stakes |
| Real-time update notifications | Workflow interruption; API spam; hourly check is sufficient |
| Forced updates | Breaks mid-task workflows; user should control timing |
| Pre-release channels (alpha/beta) | Support burden; CLI tools should ship stable releases |
| Multiple versions installed side-by-side | Path management nightmare; uv tool supports single version only |
| Automatic rollback on failure | Hidden state changes; confusing UX; user should explicitly pin previous version |
| Update scheduling/cron | Daemon complexity; timestamp-based throttling is simpler |
| Interactive update prompts | Blocks automation; non-interactive banners are better UX |

## Milestone Summary

| Milestone | Requirements | Focus |
|-----------|--------------|-------|
| v2.0.4 Foundation | 14 | Version checking infrastructure (MC only), config management, runtime detection |
| v2.0.5 MC Auto-Update | 19 | MC auto-update, mc-update utility, notifications, pinning |
| v2.0.6 Container Management | 11 | Container version checking, dual-artifact coordination, unified control |

**Total: 44 requirements across 3 milestones**

## Traceability

Which phases cover which requirements. Updated during roadmap creation for each milestone.

### v2.0.4 Foundation

| Requirement | Phase | Status |
|-------------|-------|--------|
| UCTL-05 | Phase 26 | Pending |
| UCTL-06 | Phase 26 | Pending |
| UCTL-09 | Phase 26 | Pending |
| UCTL-10 | Phase 26 | Pending |
| RTMD-01 | Phase 27 | Pending |
| RTMD-02 | Phase 27 | Pending |
| RTMD-03 | Phase 27 | Pending |
| VCHK-01 | Phase 28 | Pending |
| VCHK-03 | Phase 28 | Pending |
| VCHK-04 | Phase 28 | Pending |
| VCHK-05 | Phase 28 | Pending |
| VCHK-06 | Phase 28 | Pending |
| VCHK-07 | Phase 28 | Pending |
| VCHK-08 | Phase 28 | Pending |

**Coverage:**
- v2.0.4 requirements: 14 total
- Mapped to phases: 14/14 (100%)
- Unmapped: 0

### v2.0.5 MC Auto-Update

| Requirement | Phase | Status |
|-------------|-------|--------|
| (To be filled by roadmapper when v2.0.5 starts) | | |

### v2.0.6 Container Management

| Requirement | Phase | Status |
|-------------|-------|--------|
| (To be filled by roadmapper when v2.0.6 starts) | | |

---
*Requirements defined: 2026-02-11*
*Last updated: 2026-02-11 with v2.0.4 traceability*
