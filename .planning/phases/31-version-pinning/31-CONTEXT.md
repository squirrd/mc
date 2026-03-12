# Phase 31: Version Pinning - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Three `mc-update` subcommands: `pin X.Y.Z`, `unpin`, and `check`. Users lock MC to a specific version, remove that lock, and inspect current/latest/pin status. Pin is persisted in `~/mc/config/config.toml` [version] section via existing atomic write infrastructure. Restore/downgrade execution is part of this phase (upgrade enforces pin). Version notifications (banner) are Phase 32.

</domain>

<decisions>
## Implementation Decisions

### check output format
- Aligned key-value block printed to stdout:
  ```
  Version status:
    Installed : 2.0.4
    Latest    : 2.0.5
    Pin       : none
    Update    : available
  ```
- When a pin is active, Pin field shows just the version: `Pin : 2.0.3` (no extra annotation)
- Always fetches latest version live from GitHub (uses existing version check infrastructure — no cache)
- If GitHub is unreachable: show partial info with a note rather than failing:
  ```
  Version status:
    Installed : 2.0.4
    Latest    : unavailable (network error)
    Pin       : none
  ```

### Pin enforcement behavior
- Pin means **exact lock** — "stay on this version", not a ceiling
- `mc-update upgrade` while pinned: blocked with clear message and non-zero exit
  - Message: `"Version pinned to 2.0.3. Run mc-update unpin first."`
- `mc-update upgrade` while pinned (if pinned version != installed): installs the pinned version (enforces exact version, may downgrade)
- Phase 32 update banner: shown even when pinned — do not suppress (user should be informed, can choose to unpin)

### Pin validation
- Version is validated against GitHub releases before saving to config (network required)
- Accept both bare semver (`2.0.3`) and v-prefix (`v2.0.3`); strip leading `v` before storing
- If pinned version does not exist on GitHub: fail with clear error, do not save
- If GitHub is unreachable during `pin`: fail — require network, do not save without validation
  - Message: `"Cannot validate version: network unreachable. Try again when online."`
- If pinned version is already installed: accept silently and confirm (no special-casing)
- Success output: `"Pinned to 2.0.3. Run mc-update unpin to remove."`

### Error handling
- `mc-update unpin` with no active pin: no-op, exits 0
  - Message: `"No pin active."`
- Agent mode: **all subcommands blocked** (pin, unpin, check) — consistent with mc-update upgrade guard
  - Error message should note that pinning is a host-side operation; to control the mc version inside a case container, pin the container image instead

### Claude's Discretion
- Exact column alignment/padding in check output
- Exit code conventions for non-error informational cases (e.g., check when already up to date)
- Internal key name for pin in TOML [version] section

</decisions>

<specifics>
## Specific Ideas

- Agent mode error message should reference "pin the container" as the alternative — user explicitly wants this guidance for users who run mc-update inside a case container

</specifics>

<deferred>
## Deferred Ideas

- None — discussion stayed within phase scope

</deferred>

---

*Phase: 31-version-pinning*
*Context gathered: 2026-03-12*
