# Roadmap: MC CLI Hardening Project

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- ✅ **v2.0 Containerization** - Phases 9-14.1 (shipped 2026-02-01)
- ✅ **v2.0.1 Cleanup** - Phases 14.2-14.6 (shipped 2026-02-02)
- ✅ **v2.0.2 Window Tracking** - Phases 15-19 (shipped 2026-02-08)
- ✅ **v2.0.3 Container Tools** - Phases 20-25 (shipped 2026-02-10)
- ✅ **v2.0.4 Foundation** - Phases 26-28 (shipped 2026-02-19)
- ✅ **v2.0.5 Auto-Update & Terminal** - Phases 29-32 (shipped 2026-03-12)
- ✅ **v2.0.6 iTerm2 Hotfix** - unplanned fixes (shipped 2026-03-16)
- 🔄 **v2.0.7 OCM Integration & Container Tooling** - Phases 33-36 (in progress)

## Phases

<details>
<summary>✅ v1.0 Hardening (Phases 1-8) - SHIPPED 2026-01-22</summary>

Phases 1-8 delivered: pytest infrastructure, type safety, security hardening, structured logging, parallel downloads, TOML configuration. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0 Containerization (Phases 9-14.1) - SHIPPED 2026-02-01</summary>

Phases 9-14.1 delivered: Container orchestration, terminal automation, Salesforce integration, RHEL 10 image, uv distribution. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0.1 Cleanup (Phases 14.2-14.6) - SHIPPED 2026-02-02</summary>

Phases 14.2-14.6 delivered: Critical bug fixes, test suite improvements, config consolidation, container auto-pull. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0.2 Window Tracking (Phases 15-19) - SHIPPED 2026-02-08</summary>

Phases 15-19 delivered: SQLite window registry, macOS duplicate prevention, Linux X11 support, self-healing registry, 530 tests. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0.3 Container Tools (Phases 20-25) - SHIPPED 2026-02-10</summary>

Phases 20-25 delivered: Multi-stage Containerfile, independent image versioning, build automation, registry integration, OCM CLI. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0.4 Foundation (Phases 26-28) - SHIPPED 2026-02-19</summary>

Phases 26-28 delivered: GitHub API version checking with daemon threads, ETag caching, PEP 440 comparison, TOML [version] section, runtime mode detection. See MILESTONES.md for details.

</details>

<details>
<summary>✅ v2.0.5 Auto-Update & Terminal (Phases 29-32) - SHIPPED 2026-03-12</summary>

Phases 29-32 delivered: iTerm2 Python API migration, mc-update upgrade/pin/unpin/check commands, Rich Panel update notification banner. See milestones/v2.0.5-ROADMAP.md for full details.

</details>

---

## v2.0.7 OCM Integration & Container Tooling (Phases 33-36)

### Phase 33: Container Setup — Config Mount & Claude Code

**Goal:** Fix the missing mc config issue in containers and add Claude Code, both are Containerfile/mount changes that belong together.

**Requirements:** CNT-01, CNT-02, CNT-03, CLD-01, CLD-02, CLD-03

**Success criteria:**
1. `mc case-comments <case>` runs inside container without triggering setup wizard
2. Container cannot write to `~/mc/config` (mount is read-only)
3. `claude` command is available inside container (`claude --version` succeeds)
4. `claude` session inside container uses same auth as host (no re-login needed)
5. All existing container tests still pass

---

### Phase 34: Case Data Store

**Goal:** Extract all available case metadata from the Red Hat API and write it to `case.json` + `case.env` inside the case workspace before/during terminal attachment.

**Requirements:** CDS-01, CDS-02, CDS-03, CDS-04, CDS-05

**Success criteria:**
1. `/case/case.json` exists and is valid JSON after `mc case N` runs
2. `/case/case.env` exists and is `source`-able in bash after `mc case N` runs
3. Both files contain at minimum: case_number, cluster_id (empty string if unknown), customer_name, summary, severity, status, product
4. Files are refreshed (overwritten) on every `mc case N` invocation
5. `cluster_id` key present in both files even when the API doesn't return one (empty string, not absent)
6. Unit tests cover file writing and all field extraction/fallback scenarios

**Plans:** 3 plans
- [ ] 34-01-PLAN.md — Extend RedHatAPIClient with fetch_case_comments() and openshiftClusterID field
- [ ] 34-02-PLAN.md — Create agent/case_data.py module, mc agent init-case CLI command, and unit tests
- [ ] 34-03-PLAN.md — Wire mc agent init-case into build_exec_command() and update terminal attach tests

---

### Phase 35: Backplane Auto-Login

**Goal:** Automatically run `ocm backplane login <cluster-id>` inside the container when a terminal is attached, using the cluster ID from sfdc-case.json, with user-prompt fallback and StateDatabase persistence.

**Requirements:** BPL-01, BPL-02, BPL-03, BPL-04, BPL-05

**Success criteria:**
1. When `mc case N` opens a terminal and cluster_id is present in sfdc-case.json, `ocm backplane login` runs automatically inside the container
2. `oc get nodes` succeeds in the container immediately after shell opens (cluster is logged in)
3. When cluster_id is absent, user is prompted — entered ID is stored in StateDatabase
4. Subsequent `mc case N` on same case reuses stored cluster ID without re-prompting
5. Backplane login failure prints warning but does not prevent shell from opening
6. StateDatabase `containers` table has `cluster_id` column (migration-safe)
7. Unit tests for StateDatabase migration and cluster ID read/write

**Plans:** 3 plans
- [x] 35-01-PLAN.md — StateDatabase cluster_id column migration, ContainerMetadata extension, ~/mc/state volume mount
- [x] 35-02-PLAN.md — Agent backplane-login core module (backplane_login.py) and full unit tests
- [x] 35-03-PLAN.md — Wire backplane-login CLI command into agent.py, main.py, and build_exec_command()

---

### Phase 36: OCM Token Background Monitor

**Goal:** Add a host-side daemon thread that monitors OCM refresh token expiry every 30 minutes and notifies the user + triggers re-login when expiry is within 60 minutes.

**Requirements:** OCM-01, OCM-02, OCM-03, OCM-04, OCM-05

**Success criteria:**
1. OCM monitor starts as daemon thread when any `mc` command runs on host
2. When refresh token `exp` is within 60 minutes: warning message is printed to terminal
3. `ocm login --use-auth-code --url=prd` runs in background subprocess after warning
4. When `ocm.json` is not found: prints informational message (not silent)
5. No mc command is delayed or blocked by the OCM monitor
6. Unit tests cover JWT decode, expiry logic (near-expiry, expired, fresh), and file-absent case

**Plans:** 2 plans
- [ ] 36-01-PLAN.md — OCM monitor core module (ocm_monitor.py + unit tests)
- [ ] 36-02-PLAN.md — Wire start_background_monitor() into main.py

---

---

## v2.0.7 Milestone Closeout (Phase 37)

### Phase 37: Pre-Release Fixes & Tech Debt

**Goal:** Close three known defects before archiving the v2.0.7 milestone: fix the StateDatabase path bug that silently breaks BPL-04, add missing test coverage for the banner agent-mode guard, and resolve orphaned helper functions by wiring `should_check_for_updates()` into `main.py`.

**Success criteria:**
1. `_get_state_db()` in `agent/backplane_login.py` uses explicit path `~/mc/state/containers.db`
2. Unit tests confirm `show_update_banner` is called in host mode and suppressed in agent mode
3. `should_check_for_updates()` replaces the raw `get_runtime_mode() != 'agent'` guard in `main.py`
4. `check_for_updates()` and `update_version_config()` either wired in or deleted (no dead public API)
5. All existing tests still pass after changes

**Plans:** 3 plans
- [x] 37-01-PLAN.md — Fix _get_state_db() StateDatabase path bug (BPL-04) and add path assertion test
- [x] 37-02-PLAN.md — Add banner agent-mode guard tests to test_main.py
- [x] 37-03-PLAN.md — Wire should_check_for_updates() into main.py; delete orphaned check_for_updates()

---

## Progress

**Execution Order:**
Phases execute in numeric order: 33 → 34 → 35 → 36

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-8. Hardening | v1.0 | 21/21 | Complete | 2026-01-22 |
| 9-14.1. Containerization | v2.0 | 22/22 | Complete | 2026-02-01 |
| 14.2-14.6. Cleanup | v2.0.1 | 13/13 | Complete | 2026-02-02 |
| 15-19. Window Tracking | v2.0.2 | 10/10 | Complete | 2026-02-08 |
| 20-25. Container Tools | v2.0.3 | 9/9 | Complete | 2026-02-10 |
| 26-28. Foundation | v2.0.4 | 6/6 | Complete | 2026-02-19 |
| 29. iTerm2 API Migration | v2.0.5 | 2/2 | Complete | 2026-03-12 |
| 30. mc-update Core | v2.0.5 | 2/2 | Complete | 2026-03-12 |
| 31. Version Pinning | v2.0.5 | 2/2 | Complete | 2026-03-12 |
| 32. Update Notifications | v2.0.5 | 2/2 | Complete | 2026-03-12 |
| 33. Container Setup | v2.0.7 | 2/2 | Complete | 2026-03-20 |
| 34. Case Data Store | v2.0.7 | 3/3 | Complete | 2026-03-20 |
| 35. Backplane Auto-Login | v2.0.7 | 3/3 | Complete | 2026-03-20 |
| 36. OCM Token Monitor | v2.0.7 | 2/2 | Complete | 2026-03-20 |
| 37. Pre-Release Fixes | v2.0.7 | 3/3 | Complete | 2026-03-21 |
