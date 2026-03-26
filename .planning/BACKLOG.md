# Backlog

*Last updated: 2026-03-25*

---

## Release Status

| Version | Status |
|---------|--------|
| v2.0.7 | ✅ Shipped & milestone archived (2026-03-21) |
| v2.0.8 | ✅ Shipped & milestone archived (2026-03-25) |

---

## Current Cycle: UAT & Bug Fixes

### Step 5b — Check pending todos ✅ DONE

Ran `/gsd:check-todos` — 0 pending todos.

---

### Step 6 — Run UAT (gsd:verify-work)

```
/gsd:verify-work
```

**Verifying: v2.0.7 features first (oldest unverified), then v2.0.8 fixes**

#### v2.0.7 — OCM Integration & Container Tooling (Phases 33-37)
Features to verify:
- OCM token monitor (daemon, expiry warning, auto re-login)
- Case data store (`sfdc-case.json` + `case.env` in `/case/`)
- Backplane auto-login (cluster_id from sfdc → StateDB → prompt fallback)
- Container config mount (`~/mc/config` read-only in container)
- Claude Code in container (`claude` binary + `~/.claude` mount)

#### v2.0.8 — Update Banner & Test Fixes
Fixes to spot-check:
- `mc` invocation after a failed GitHub API call does NOT spam the API every time (1h throttle)

**Pre-conditions for a useful UAT session:**
- `mc` installed from the v2.0.8 tag (not dev source): `uv tool install --force "git+https://github.com/squirrd/mc@v2.0.8"`
- Valid `~/mc/config/config.toml` with API token
- Podman running
- Valid `ocm.json` at the OCM config path (for OCM monitor testing)
- A real case number with a known cluster ID in Salesforce

**Status:** Active — run `/gsd:verify-work` to begin

---

### Step 7 — Manual UAT test cases

Run these manually to complement the automated suite. Report failures as bug issues.

#### Container lifecycle

| # | Test | Expected |
|---|------|----------|
| 1 | `mc case 12345678` on a new case | Container created, terminal opens, `sfdc-case.json` and `case.env` present in `/case/` |
| 2 | `cat /case/case.env` inside container | All 7 vars present: `MC_CASE_NUMBER`, `MC_CLUSTER_EXTERNAL_ID`, `MC_CUSTOMER_NAME`, `MC_SUMMARY`, `MC_SEVERITY`, `MC_STATUS`, `MC_PRODUCT` |
| 3 | `mc case 12345678` on an already-running case | Focuses the existing terminal window (no duplicate) |
| 4 | `mc case 12345678` after closing the terminal manually | New terminal opens |

#### Backplane auto-login

| # | Test | Expected |
|---|------|----------|
| 5 | Case with known cluster ID in Salesforce | `ocm backplane login <cluster-id>` runs automatically before shell prompt; `oc get nodes` succeeds |
| 6 | Case with no cluster ID in Salesforce | Prompt appears: "Enter cluster ID or press Enter to skip" |
| 7 | Press Enter at cluster ID prompt | Shell opens without backplane login; no hang |
| 8 | Enter cluster ID at prompt, then run `mc case N` again | No re-prompt; stored ID reused; backplane login runs automatically |

#### Container config & Claude

| # | Test | Expected |
|---|------|----------|
| 9 | `mc case-comments <case>` inside container | Output shown; no setup wizard triggered |
| 10 | `touch ~/mc/config/test.txt` inside container | `Permission denied` (read-only mount) |
| 11 | `claude --version` inside container | Returns version string without auth prompt |

#### OCM token monitor

| # | Test | Expected |
|---|------|----------|
| 12 | `mc --help` with a valid non-expiring `ocm.json` | No OCM output (token is fresh) |
| 13 | `mc --help` with `ocm.json` absent | Cyan info message on stderr: "OCM config not found at …" |
| 14 | `mc --help` inside a container (agent mode) | No OCM monitor output (agent mode suppresses it) |

#### mc-update

| # | Test | Expected |
|---|------|----------|
| 15 | `mc-update check` | Table shows installed version (2.0.8), latest, and update status |
| 16 | `mc-update upgrade` | Upgrades to latest; prints new version after |

**Status:** Pending (after Step 6)

---

### Step 8 — Bug fix cycle

For each failure found in Steps 6–7:

1. Document the failure (symptom, steps to reproduce, expected vs actual)
2. Run `/gsd:debug` if root cause is unclear
3. Run `/tdd-issue` to create a red test, fix, green cycle
4. Or for simple fixes: edit directly + add regression test + commit

Track fixes below under "Active Bug Fixes".

**Status:** Pending

---

## Active Bug Fixes

*(None yet — populate as UAT failures are found)*

---

## Do Later

### OCM silent token refresh (investigate)
**Type:** Future feature | **Effort:** Unknown (research required)

Currently, when the OCM refresh token is near expiry, the monitor triggers `ocm login --use-auth-code --url=prd` — a browser-based flow that interrupts the user. Investigate whether the OCM token endpoint supports silent refresh (exchange refresh token for a new refresh token without browser interaction).

**Research questions:**
- Does `https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token` accept `grant_type=refresh_token` with the OCM refresh token?
- If yes: implement as alternative path when token has > N minutes remaining
- If no: document why and close OCM-F01/F02

---

### Extended container tools
**Type:** Future feature | **Effort:** Incremental

Add tools to the container image following the existing downloader stage pattern:

- `rh-aws-saml-login` — AWS auth via Red Hat SSO
- AWS CLI
- ROSA CLI
- `skopeo` (may already be in UBI)
- `tshark` — packet analysis

Each: new downloader stage + SHA256 verification + `COPY --from` in final stage.

---

### Automatic housekeeping
**Type:** Future feature | **Effort:** Medium

Auto-stop/clean containers based on inactivity and case lifecycle:
- Stop after 48h inactivity (configurable)
- Stop when case closed in Salesforce
- Remove stopped containers after 5 days (configurable)
- `mc case compact <caseNumber>` manual command

---

### CASE_NUMBER explicit env passthrough in podman exec
**Type:** Low-severity tech debt | **Effort:** ~15 min
**File:** `src/mc/terminal/attach.py` — `build_exec_command()`

`CASE_NUMBER` reaches `mc agent init-case` and `mc agent backplane-login` via implicit Podman exec env-inheritance (set at container creation time). Adding `--env CASE_NUMBER` explicitly to the exec command would make this dependency visible and robust against any future change in Podman's exec env handling.

---

### Mount policy engine
**Type:** Future feature | **Effort:** Large

Declarative mount config via `~/.mc/mounts.yaml`. Only needed if multi-user container scenarios become a real requirement. Defer until concrete use case exists.
