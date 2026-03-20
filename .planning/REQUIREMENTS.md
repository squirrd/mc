# Requirements: MC CLI v2.0.7

**Defined:** 2026-03-19
**Core Value:** Make the codebase testable and maintainable so new features can be added confidently without breaking existing functionality

## v1 Requirements

Requirements for v2.0.7 release. Each maps to roadmap phases.

### OCM Token Monitor (host-side)

- [ ] **OCM-01**: Background daemon checks OCM refresh token expiry every 30 minutes when any mc command runs on host
- [ ] **OCM-02**: If refresh token expires within 60 minutes, prints warning: "OCM refresh token expiring in N min. Please complete SSO login in the browser that will open shortly"
- [ ] **OCM-03**: Runs `ocm login --use-auth-code --url=prd` in background subprocess after warning is shown
- [ ] **OCM-04**: Prints informational message when `ocm.json` is not found (user not using OCM) — does not silently skip
- [ ] **OCM-05**: Daemon thread never blocks or delays CLI commands (follows version_check.py pattern)

### Container Config Mount

- [x] **CNT-01**: `~/mc/config` mounted read-only into container at `/home/mcuser/mc/config`
- [x] **CNT-02**: `mc case-comments <case>` and other mc commands work inside case container without triggering setup wizard
- [x] **CNT-03**: Container cannot write to host config (read-only mount enforced by podman)

### Case Data Store

- [ ] **CDS-01**: Before container is attached (at terminal attach time), all available case metadata is extracted from the Red Hat API and written to `/case/case.json` (structured JSON)
- [ ] **CDS-02**: Same data written to `/case/case.env` (KEY=VALUE format) for bash `source`-ability
- [ ] **CDS-03**: `case.json` and `case.env` include at minimum: case_number, cluster_id (if available), customer_name, summary, severity, status, product
- [ ] **CDS-04**: Both files are overwritten on every `mc case N` invocation (always fresh)
- [ ] **CDS-05**: cluster_id field is present in both files even when empty (empty string, not absent key) so consuming code doesn't need existence checks

### Container Backplane Auto-Login

- [x] **BPL-01**: After case data is written and container is started, reads cluster_id from `case.json`
- [x] **BPL-02**: If cluster_id is non-empty, runs `ocm backplane login <cluster-id>` inside container before user sees shell prompt
- [x] **BPL-03**: If cluster_id is empty, prompts user to enter cluster ID or press Enter to skip
- [x] **BPL-04**: User-entered cluster ID stored in StateDatabase `containers` table — reused on subsequent `mc case N` (no re-prompt)
- [x] **BPL-05**: Backplane login failure is non-fatal — logs warning, prints message, opens shell anyway

### Claude Code in Container

- [x] **CLD-01**: `claude` binary available in container (installed via `npm install -g @anthropic-ai/claude-code` in Containerfile)
- [x] **CLD-02**: `~/.claude` directory mounted read-write from host into container at `/home/mcuser/.claude`
- [x] **CLD-03**: No additional auth steps needed inside container — session tokens carry from host mount

## Future Requirements

### OCM Token Refresh (without full re-auth)

- **OCM-F01**: Investigate whether OCM refresh token can be silently refreshed via the token endpoint before it expires — avoiding the browser-based auth-code flow
- **OCM-F02**: If silent refresh is possible, implement as alternative to `ocm login --use-auth-code` when enough refresh token lifetime remains

### Case Data Store Extensions

- **CDS-F01**: Additional fields from case data (comments summary, attachments list, contacts) added to case.json as they become available
- **CDS-F02**: Case data refresh command (`mc case refresh N`) to force re-fetch outside of `mc case N` flow

### Claude Code Configuration

- **CLD-F01**: Investigate whether specific subdirectories of `~/.claude` can be mounted instead of the full directory (reduce mount surface)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Automatic OCM token refresh without user interaction | Requires token endpoint investigation — deferred to future milestone |
| Container auto-pull of new image version at backplane login | Separate feature from cluster login, different scope |
| Direct Salesforce SOQL for cluster ID | Requires SF username/password/security_token credentials not configured |
| Claude Code `--dangerously-skip-permissions` default | User can set this manually; tool should not prescribe AI safety settings |
| OCM monitor on Linux (first iteration) | macOS path confirmed; Linux path is `~/.config/ocm/ocm.json` — same code handles it via `get_ocm_config_path()` |

## Traceability

Which phases cover which requirements. Updated after roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| CNT-01 | Phase 33 | Complete |
| CNT-02 | Phase 33 | Complete |
| CNT-03 | Phase 33 | Complete |
| CLD-01 | Phase 33 | Complete |
| CLD-02 | Phase 33 | Complete |
| CLD-03 | Phase 33 | Complete |
| CDS-01 | Phase 34 | Complete |
| CDS-02 | Phase 34 | Complete |
| CDS-03 | Phase 34 | Complete |
| CDS-04 | Phase 34 | Complete |
| CDS-05 | Phase 34 | Complete |
| BPL-01 | Phase 35 | Complete |
| BPL-02 | Phase 35 | Complete |
| BPL-03 | Phase 35 | Complete |
| BPL-04 | Phase 35 | Complete |
| BPL-05 | Phase 35 | Complete |
| OCM-01 | Phase 36 | Complete |
| OCM-02 | Phase 36 | Complete |
| OCM-03 | Phase 36 | Complete |
| OCM-04 | Phase 36 | Complete |
| OCM-05 | Phase 36 | Complete |

**Coverage:**
- v1 requirements: 21 total
- Mapped to phases: 21
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-19*
*Last updated: 2026-03-19 after initial definition*
