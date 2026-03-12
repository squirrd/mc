# Requirements: MC CLI v2.0.5 Auto-Update & Terminal

**Defined:** 2026-03-12
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality

## v1 Requirements (this milestone)

### Auto-Update

- [ ] **UPDATE-01**: User can run `mc-update upgrade` to upgrade MC CLI via `uv tool upgrade mc`
- [ ] **UPDATE-02**: mc-update validates the upgrade completed successfully by checking `mc --version`
- [ ] **UPDATE-03**: mc-update shows clear recovery instructions when upgrade fails (e.g., `uv tool install --force mc`)
- [ ] **UPDATE-04**: User can pin MC to a specific version with `mc-update pin X.Y.Z`
- [ ] **UPDATE-05**: User can remove a version pin with `mc-update unpin`
- [ ] **UPDATE-06**: User can inspect current vs latest version and pin status with `mc-update check`
- [ ] **UPDATE-07**: MC CLI displays a Rich update-available banner at startup when a newer version exists
- [ ] **UPDATE-08**: Update banner is suppressed when already shown today or when version is pinned

### iTerm2 Terminal

- [ ] **ITERM-01**: MacOSLauncher creates new case terminal windows using the iTerm2 Python API (`iterm2` library)
- [ ] **ITERM-02**: New terminal windows are created with the `MCC-Term` iTerm2 profile
- [ ] **ITERM-03**: Terminal opens with the raw `podman exec ...` command hidden — user sees only the container shell prompt
- [ ] **ITERM-04**: MacOSLauncher falls back to Terminal.app if the iTerm2 Python API is unavailable (library missing, API not enabled, or not running iTerm2)

## Future Requirements

### Auto-Update (v2.1+)

- Stale pin warnings after 30 days (weekly reminders after 60 days)
- Container image version management (`mc-update container pull`)
- Version listing with release dates (`mc-update list`)
- Changelog integration — link to GitHub releases

### iTerm2 Terminal (v2.1+)

- Window focus/raise via iTerm2 Python API (replacing AppleScript focus logic)
- Window existence check via iTerm2 Python API

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto-update without user trigger | Security risk — users must explicitly invoke upgrade |
| pip-based upgrade path | mc requires uv; document uv as prerequisite |
| iTerm2 AppleScript as intermediate fallback | Simplify fallback chain: iTerm2 API -> Terminal.app only |
| Custom MCC-Term profile creation | Profile already exists in user's iTerm2 |
| Wayland/Linux terminal changes | iTerm2 is macOS only; Linux path unchanged |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ITERM-01    | Phase 29 | Complete |
| ITERM-02    | Phase 29 | Complete |
| ITERM-03    | Phase 29 | Complete |
| ITERM-04    | Phase 29 | Complete |
| UPDATE-01   | Phase 30 | Complete |
| UPDATE-02   | Phase 30 | Complete |
| UPDATE-03   | Phase 30 | Complete |
| UPDATE-04   | Phase 31 | Pending |
| UPDATE-05   | Phase 31 | Pending |
| UPDATE-06   | Phase 31 | Pending |
| UPDATE-07   | Phase 32 | Pending |
| UPDATE-08   | Phase 32 | Pending |

**Coverage:**
- v1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 — traceability confirmed after roadmap creation*
