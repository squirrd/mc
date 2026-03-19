# Research Summary: v2.0.7 OCM Integration & Container Tooling

**Project:** MC CLI v2.0.7
**Domain:** OCM token lifecycle, container configuration sharing, Claude Code in Podman
**Researched:** 2026-03-19
**Confidence:** HIGH (codebase-verified + live data)

## Executive Summary

All four v2.0.7 features have clear, low-risk implementation paths confirmed directly against the existing codebase. No new external dependencies are required. The OCM token monitor follows established daemon-thread patterns from `version_check.py`. The config mount is a one-line change to `ContainerManager.create()`. The backplane auto-login is best-effort (cluster ID from Red Hat API if available, user-prompt fallback). Claude Code installation is straightforward npm + ~/.claude mount.

The highest-risk item is the cluster ID extraction: the Red Hat API `/v1/cases/{case_number}` endpoint may include a `clusterId` field for OCP/ROSA cases but NOT for non-cluster cases — confirmed by inspecting cached case data. The implementation must handle absent cluster IDs gracefully.

## Feature Research

### Feature 1: OCM Token Background Monitor

**OCM config file structure** (`~/Library/Application Support/ocm/ocm.json` on macOS, `~/.config/ocm/ocm.json` on Linux):
```json
{
  "access_token": "<JWT>",    // expires in ~15 minutes
  "client_id": "ocm-cli",
  "refresh_token": "<JWT>",   // expires in ~10 hours (confirmed from live file)
  "scopes": ["openid"],
  "token_url": "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token",
  "url": "https://api.openshift.com"
}
```

**JWT decoding:** Python stdlib only — `base64.b64decode(payload_part + "==")` then `json.loads()`. The `exp` claim is a Unix timestamp. No new dependencies required.

**What to monitor:** Check the **refresh_token** `exp` claim. When within 1 hour of expiry, the user needs to re-authenticate via `ocm login --use-auth-code --url=prd`.

**The access_token** (15 min) is auto-refreshed by OCM internally — monitoring it would trigger too frequently.

**Trigger:** `ocm login --use-auth-code --url=prd` launches a browser for auth-code flow. This is user-interactive. Best-effort: run in background subprocess, print warning ahead of time so user can be ready.

**Notification message:** "OCM refresh token expiring in <N> min. Please complete SSO login in the browser that will open shortly."

**Implementation pattern:** Follow `version_check.py` — daemon thread, 30-min poll interval, fail silently if `ocm.json` absent (user not logged in), store last-check in state file.

**Edge cases:**
- OCM not installed: silently skip (check `ocm_config_path.exists()`)
- Already expired: still attempt login (it can re-auth from scratch)
- Token just refreshed by `ocm` itself: the `exp` will have moved forward, no re-login needed

---

### Feature 2: Mount ~/mc/config Read-Only in Container

**Current mounts in `ContainerManager.create()`:**
- `{workspace_path}` → `/case` (rw) — case workspace
- `~/Library/Application Support/ocm/ocm.json` → `/home/mcuser/.config/ocm/ocm.json` (ro) — OCM credentials

**What's missing:** The container's `/home/mcuser/mc/` starts empty (`~/mc/config/` has an empty `config/` dir). Running `mc case-comments` inside the container triggers the setup wizard because there's no `config.toml`.

**Fix:** Add a third mount:
- `~/mc/config` → `/home/mcuser/mc/config` (ro) — shares host mc config

**Read-only** is safe because:
- The container runs as `mcuser` with `MC_RUNTIME_MODE=agent`
- Container commands that read config will work correctly
- Container cannot corrupt host config

**Implementation:** One mount added to the `volumes` dict in `ContainerManager.create()`. Uses the same `get_ocm_config_path()` pattern already present.

**IMPORTANT:** This also shares the `cache/case_metadata.db` (SQLite). With WAL mode (already used by the cache), concurrent reads from both host and container are safe. The cache is read-only from the container's perspective (mode="ro" prevents writes).

---

### Feature 3: Backplane Auto-Login After Terminal Attach

**Trigger:** During `attach_terminal()` in `terminal/attach.py`, after the container is started but BEFORE the user's shell opens. This gives the user a logged-in cluster when they first see the prompt.

**Cluster ID source — investigation results:**
1. **Red Hat API `/v1/cases/{case_number}`:** The response does NOT include a cluster ID for all cases. Confirmed: the cached case data (from a non-OCP case `04347612`) has no cluster field. OCP/ROSA cases likely DO have a `clusterId` or similar field — needs runtime check.
2. **Salesforce SOQL:** `Cluster_ID__c` is queried in `salesforce_api.py` but requires direct Salesforce credentials (username/password/security_token) which the user does NOT have configured this way. Salesforce access is via the Red Hat internal API (same `rh_api_offline_token`).
3. **User input fallback:** If cluster ID not available from API, prompt: "Enter cluster ID for backplane login (Enter to skip):"

**Implementation approach:**
1. In `attach_terminal()`, after container is ensured running, attempt to get cluster ID from `case_details` (full Red Hat API response — may include `clusterId` for OCP cases)
2. If found: `podman exec mc-{case_number} ocm backplane login {cluster_id}` (blocking exec before shell launch)
3. If not found: prompt user, store result in StateDatabase `containers` table (new `cluster_id` column)
4. If empty/skipped: proceed without backplane login

**StateDatabase change:** Add `cluster_id TEXT` column to `containers` table. Store the cluster ID so subsequent `mc case N` invocations don't re-prompt (retrieve and reuse).

**The `ocm` binary** is already installed in the container image (from `build-container.sh`). The OCM credentials are already mounted read-only (`ocm.json`). So `ocm backplane login` will work inside the container.

**User experience:**
```
Attaching to case 04387781...
Logging into cluster a7fdee93-8d3c-4a05-9412-752d6b973a25 via backplane...
✓ Cluster login successful
[MC-04387781] /case/sfdc$
```

---

### Feature 4: Claude Code in Container

**Installation in Containerfile:**
1. Install Node.js (RHEL 10 UBI requires `nodejs` from AppStream — `microdnf install nodejs`)
2. Install Claude Code: `npm install -g @anthropic-ai/claude-code`

**Auth sharing:** The `~/.claude` directory contains session tokens and configuration. The critical file is `~/.claude/credentials.json` (or similar). Mounting the full `~/.claude` is the simplest approach and ensures all session data is available.

**Mount:** `~/.claude` → `/home/mcuser/.claude` (rw — session state needs to be writable for session continuity)

**Key flags for container usage:**
- `claude --dangerously-skip-permissions` — skips safety confirmation prompts for autonomous use
- `--network=host` is not needed (container can reach external APIs on its network)

**No ANTHROPIC_API_KEY env var needed** — confirmed by user: the key is empty on the host. Session tokens in `~/.claude` handle auth.

**Containerfile placement:** Add after existing OCM/backplane tool installation in the `final` stage.

**Version pinning:** Use `npm install -g @anthropic-ai/claude-code@latest` — or pin to a specific version. Given the rapid iteration of Claude Code, `@latest` is acceptable for the Containerfile (follows same pattern as other tools that use `latest`).

---

## Critical Pitfalls

1. **OCM token monitor triggers too early:** Monitor the refresh_token exp, not access_token. Access token is 15min and will always look "about to expire." Refresh token is the long-lived session credential.

2. **Config mount breaks container-side config writes:** With `~/mc/config` mounted read-only, any mc command that tries to WRITE config inside the container will fail. Given `MC_RUNTIME_MODE=agent`, the setup wizard is already blocked. Confirm other container-side commands don't write config.

3. **Cluster ID prompt UX in non-interactive contexts:** The `attach_terminal()` prompt for cluster ID should only show in TTY mode (already guarded by `should_launch_terminal()`). For `mc container create`, skip cluster ID entirely — it's handled at terminal attach time.

4. **Node.js in RHEL 10 UBI:** The UBI minimal image may not have the nodejs AppStream by default. May need `microdnf install nodejs npm` or use a Node.js module stream. Test during planning.

5. **~/.claude mount with --userns=keep-id:** The container uses `--userns=keep-id` for volume permissions. The `~/.claude` mount will work correctly as host UID = container UID with this option.

6. **StateDatabase schema migration:** Adding `cluster_id` column to the existing `containers` table requires a migration for existing databases. Use `ALTER TABLE ... ADD COLUMN cluster_id TEXT` with `IF NOT EXISTS` guard or check-then-add pattern.

---

## Implementation Order

Phase ordering rationale (dependent on each other):

1. **Container Config Mount** (Phase 33) — Simple, foundational. Fix the no-config issue first. Required for Claude Code and mc commands to work inside the container.

2. **Claude Code in Container** (Phase 34) — Containerfile change. Independent of other features. Grouped with config mount since both touch container setup.

3. **Backplane Auto-Login** (Phase 35) — Needs StateDatabase schema change. Touches terminal/attach.py. Should be isolated to its own phase to avoid complexity.

4. **OCM Token Monitor** (Phase 36) — Pure host-side daemon. Independent of container changes. Last because it's purely additive and doesn't block other features.

---

## Stack Impact

**No new Python dependencies required.** All implementation uses:
- `base64`, `json`, `threading`, `subprocess` (stdlib) — OCM JWT decode + monitor
- `podman-py` (already present) — container exec for backplane login
- `npm` (Node.js) — Claude Code install in Containerfile

**Containerfile additions:**
- `microdnf install nodejs`
- `npm install -g @anthropic-ai/claude-code`

---
*Research completed: 2026-03-19*
*Ready for roadmap: yes*
