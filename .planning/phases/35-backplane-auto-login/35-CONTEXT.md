# Phase 35: Backplane Auto-Login - Context

**Gathered:** 2026-03-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Automatically run `ocm backplane login <cluster-id>` inside the container when a terminal is attached. Source cluster_id from `sfdc-case.json` if present, fall back to StateDatabase if stored, prompt the user inside the container shell if neither is available. Persist user-entered IDs to StateDatabase. Login failure warns but does not block the shell. OCM token monitoring is a separate phase (36).

</domain>

<decisions>
## Implementation Decisions

### Prompt UX
- Prompt appears **inside the container shell** (not on the host before launch)
- User can skip by pressing Enter — shell opens without backplane login
- Prompt format: simple plain text — `Enter cluster ID (or press Enter to skip): `
- Basic format validation before attempting login (non-empty, reasonable cluster ID format — similar to how `mc case` validates case numbers)

### Login feedback
- Live output passthrough — stream `ocm backplane login` stdout/stderr directly to the terminal
- Login completes (or fails) **before** the shell prompt appears — user waits for login
- On success: no extra success message — let ocm's own output speak for itself
- When cluster_id comes from sfdc-case.json automatically: no announcement — just run login silently (ocm output still visible)
- When cluster_id is reused from StateDatabase: no annotation — transparent reuse

### Failure handling
- On failure: print a clear warning, then shell opens anyway (login failure must not block shell)
- Failure is defined as non-zero exit code from `ocm backplane login`
- On failure: clear the stored cluster_id from StateDatabase (so next session prompts fresh)
- If ocm binary is not found inside container: warn and skip (print notice, open shell normally)
- Token expiry detection: inspect error output for token expiry signals and print a targeted message (e.g., "OCM token expired — run `ocm login` to re-authenticate") rather than a generic failure warning

### Stored ID management
- No manual CLI command to clear/override — management is automatic
- Auto-clear from StateDatabase on login failure (user prompted fresh next attach)
- Skip is not remembered — if user skips the prompt, next `mc case N` prompts again
- **Priority:** `sfdc-case.json` cluster_id wins over StateDatabase stored ID
- User-entered IDs (successful login) persist to StateDatabase only — sfdc-case.json is read-only (written by Phase 34, not modified here)

### Claude's Discretion
- Exact cluster ID format validation pattern
- Specific string matching for token expiry detection in ocm error output
- Warning message wording for failure cases
- How login is invoked inside the container (subprocess, shell script, etc.)

</decisions>

<specifics>
## Specific Ideas

- Cluster ID validation should mirror the pattern used for case number validation in `mc case` — look at that implementation for reference
- sfdc-case.json is the authoritative source (written by Phase 34) — cluster_id from that file always takes precedence

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 35-backplane-auto-login*
*Context gathered: 2026-03-20*
