# Roadmap: MC CLI Hardening Project

## Milestones

- ✅ **v1.0 Hardening** - Phases 1-8 (shipped 2026-01-22)
- ✅ **v2.0 Containerization** - Phases 9-14.1 (shipped 2026-02-01)
- ✅ **v2.0.1 Cleanup** - Phases 14.2-14.6 (shipped 2026-02-02)
- ✅ **v2.0.2 Window Tracking** - Phases 15-19 (shipped 2026-02-08)
- ✅ **v2.0.3 Container Tools** - Phases 20-25 (shipped 2026-02-10)
- ✅ **v2.0.4 Foundation** - Phases 26-28 (shipped 2026-02-19)
- 🚧 **v2.0.5 Auto-Update & Terminal** - Phases 29-32 (in progress)

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

### 🚧 v2.0.5 Auto-Update & Terminal (In Progress)

**Milestone Goal:** MC CLI auto-update functionality and iTerm2 Python API migration for cleaner terminal management.

#### Phase 29: iTerm2 Python API Migration

**Goal**: Users get cleaner terminal windows when opening case containers on macOS — raw command hidden, custom profile applied, with reliable fallback.
**Depends on**: Phase 28 (terminal infrastructure)
**Requirements**: ITERM-01, ITERM-02, ITERM-03, ITERM-04
**Success Criteria** (what must be TRUE):
  1. Running `mc case 12345678` on macOS opens a new iTerm2 window using the `iterm2` Python library (not AppleScript)
  2. The new window opens with the `MCC-Term` iTerm2 profile applied
  3. The user sees only the container shell prompt — the `podman exec ...` command is not visible in the terminal scrollback
  4. When iTerm2 Python API is unavailable (library missing, API not enabled, or iTerm2 not running), the launcher falls back to Terminal.app without error
**Plans**: TBD

Plans:
- [ ] 29-01: iterm2 library integration and MacOSLauncher refactor
- [ ] 29-02: Profile application, command hiding, and fallback logic

---

#### Phase 30: mc-update Core

**Goal**: Users can explicitly trigger a safe MC CLI upgrade and receive clear feedback on success or failure, including recovery instructions.
**Depends on**: Phase 29 (iTerm2 track independent; update track depends only on v2.0.4 version infrastructure already shipped)
**Requirements**: UPDATE-01, UPDATE-02, UPDATE-03
**Success Criteria** (what must be TRUE):
  1. User can run `mc-update upgrade` and the command executes `uv tool upgrade mc` to upgrade MC CLI
  2. After upgrade, mc-update verifies the new version by running `mc --version` and reports the result
  3. If the upgrade fails, mc-update prints actionable recovery instructions (e.g., `uv tool install --force mc`)
  4. `mc-update` is available as a separate console_scripts entry point that survives package upgrades
**Plans**: 2 plans

Plans:
- [ ] 30-01-PLAN.md — mc-update module (src/mc/update.py), pyproject.toml entry point, and core unit tests
- [ ] 30-02-PLAN.md — Edge case tests: FileNotFoundError paths, post-upgrade mc failure, agent mode subprocess guard, full quality gate

---

#### Phase 31: Version Pinning

**Goal**: Users can lock MC to a specific version and inspect current vs. latest version and pin status at any time.
**Depends on**: Phase 30
**Requirements**: UPDATE-04, UPDATE-05, UPDATE-06
**Success Criteria** (what must be TRUE):
  1. User can run `mc-update pin X.Y.Z` to record a version pin in the TOML config
  2. User can run `mc-update unpin` to remove the version pin from the TOML config
  3. User can run `mc-update check` to see current installed version, latest available version, and whether a pin is active
  4. Pinned version is persisted in `~/mc/config/config.toml` [version] section using existing atomic write infrastructure
**Plans**: TBD

Plans:
- [ ] 31-01: pin, unpin, and check commands with TOML persistence

---

#### Phase 32: Update Notifications

**Goal**: Users are informed of available updates at CLI startup without being spammed — banner appears at most once per day and is silent when pinned.
**Depends on**: Phase 31
**Requirements**: UPDATE-07, UPDATE-08
**Success Criteria** (what must be TRUE):
  1. When a newer MC version is available, a Rich update-available banner appears on stderr at CLI startup
  2. The banner does not appear more than once per calendar day (suppressed after first display)
  3. The banner is fully suppressed when a version pin is active
  4. The banner check never delays CLI command execution (non-blocking, uses existing daemon thread infrastructure)
**Plans**: TBD

Plans:
- [ ] 32-01: Rich update banner and suppression logic

---

## Progress

**Execution Order:**
Phases execute in numeric order: 29 → 30 → 31 → 32

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1-8. Hardening | v1.0 | 21/21 | Complete | 2026-01-22 |
| 9-14.1. Containerization | v2.0 | 22/22 | Complete | 2026-02-01 |
| 14.2-14.6. Cleanup | v2.0.1 | 13/13 | Complete | 2026-02-02 |
| 15-19. Window Tracking | v2.0.2 | 10/10 | Complete | 2026-02-08 |
| 20-25. Container Tools | v2.0.3 | 9/9 | Complete | 2026-02-10 |
| 26-28. Foundation | v2.0.4 | 6/6 | Complete | 2026-02-19 |
| 29. iTerm2 API Migration | v2.0.5 | 0/2 | Not started | - |
| 30. mc-update Core | v2.0.5 | 0/2 | Not started | - |
| 31. Version Pinning | v2.0.5 | 0/1 | Not started | - |
| 32. Update Notifications | v2.0.5 | 0/1 | Not started | - |
