# Backlog

*Last updated: 2026-03-21*

---

## Release Plan: v2.0.7 Ship & v2.0.8 Prep

### Step 1 — Push to GitHub

```bash
git push origin main
```

GitHub repo: https://github.com/squirrd/mc

---

### Step 2 — Tag and release v2.0.7

```bash
# Create version tag
git tag v2.0.7

# Move the floating `latest` tag
git tag -f latest

# Push both (force needed for latest since it moves)
git push origin v2.0.7
git push origin latest --force
```

Create GitHub release:

```bash
gh release create v2.0.7 \
  --title "v2.0.7 — OCM Integration & Container Tooling" \
  --notes "$(cat <<'EOF'
## What's New

- **OCM token monitor** — host-side daemon thread warns when OCM refresh token expires within 60 min and triggers `ocm login --use-auth-code --url=prd` automatically
- **Case data store** — `mc case N` writes `sfdc-case.json` + `case.env` into the container workspace before the shell opens; includes case_number, cluster_id, customer, summary, severity, status, product
- **Backplane auto-login** — reads cluster_id from case data and runs `ocm backplane login` automatically; falls back to StateDatabase, then user prompt
- **Container config mount** — `~/mc/config` mounted read-only into containers so `mc` commands work inside without re-running setup wizard
- **Claude Code in container** — `claude` binary included in container image; `~/.claude` mounted from host so no re-auth needed
- **StateDatabase path fix** — `_get_state_db()` now uses the explicit mounted path `~/mc/state/containers.db` (fixes silent BPL-04 regression)

## Install / Upgrade

```bash
# Fresh install
uv tool install git+https://github.com/squirrd/mc@v2.0.7

# Upgrade existing install
mc-update upgrade
```
EOF
)"
```

Verify install works from the tag:

```bash
uv tool install --force "git+https://github.com/squirrd/mc@v2.0.7"
mc --version   # should print: mc 2.0.7
```

---

### Step 3a — Rebase v2.0.8 onto main

The v2.0.8 branch diverged before the v2.0.7 version bump, so it still has
`version = "2.0.6"` in pyproject.toml. Rebasing first replays the 3 v2.0.8
fixes on top of the current main tip, giving a clean linear history and
avoiding a pyproject.toml conflict on merge.

```bash
git checkout v2.0.8
git rebase main
```

If there are conflicts (unlikely — the 3 fixes touch different files):

```bash
# Resolve conflict, then:
git add <file>
git rebase --continue
```

After rebase, confirm the branch has v2.0.7 commits underneath the 3 fixes:

```bash
git log --oneline -8
```

### Step 3b — Bump version to 2.0.8

Now that v2.0.8 sits on top of main (which has `version = "2.0.7"`), bump it:

```bash
# Edit pyproject.toml: version = "2.0.7" → "2.0.8"
uv run mc --version   # confirm: mc 2.0.8
git add pyproject.toml
git commit -m "chore: bump version to 2.0.8"
```

### Step 3c — Merge v2.0.8 into main

With the rebase done, this will be a clean fast-forward — no merge commit, no conflicts:

```bash
git checkout main
git merge v2.0.8   # fast-forward
```

Verify tests still pass:

```bash
uv run pytest tests/unit/ -q
```

---

### Step 4 — Tag and release v2.0.8

Same pattern as Step 2:

```bash
git tag v2.0.8
git tag -f latest
git push origin main
git push origin v2.0.8
git push origin latest --force

gh release create v2.0.8 \
  --title "v2.0.8 — Update Banner & Integration Test Fixes" \
  --notes "$(cat <<'EOF'
## What's New

### Bug Fixes

- **Update banner failure throttle** (`src/mc/banner.py`) — when the GitHub releases API call fails (404, network error), the failure timestamp is now stored and the check is skipped for 1 hour. Previously a failed fetch stored no timestamp, causing a fresh GitHub API call on every `mc` invocation indefinitely. Adds `last_failed_fetch` field to config.
- **Stale integration test APIs fixed** — `test_container_delete_clears_window_registry_regression` removed stale `image=` argument; `ContainerManager.create()` no longer accepts it.
- **macOS proxy mock in integration tests** — `test_container_ocm_env_setup_https_proxy_absent_when_unset_regression` now mocks `detect_macos_proxy()` so the test correctly isolates the no-proxy path on machines with a corporate proxy configured.

## Install / Upgrade

```bash
# Fresh install
uv tool install git+https://github.com/squirrd/mc@v2.0.8

# Upgrade existing install
mc-update upgrade
```
EOF
)"
```

Verify install from tag:

```bash
uv tool install --force "git+https://github.com/squirrd/mc@v2.0.8"
mc --version   # should print: mc 2.0.8
```

---

### Step 5 — Set up for bug fixes

After v2.0.8 ships, prepare the bug-fix cycle:

1. Run `/gsd:complete-milestone` to archive v2.0.7 planning artifacts
2. Run `/gsd:new-milestone` to initialise v2.0.8 (or v2.0.9) milestone tracking
3. Check pending todos: `/gsd:check-todos`

---

### Step 6 — Run UAT (gsd:verify-work)

```
/gsd:verify-work
```

This runs the verifier agent conversationally against the v2.0.7 feature set. Have a container running and a real case number ready.

**Pre-conditions for a useful UAT session:**
- `mc` installed from the v2.0.7 tag (not dev source)
- Valid `~/mc/config/config.toml` with API token
- Podman running
- Valid `ocm.json` at the OCM config path (for OCM monitor testing)
- A real case number with a known cluster ID in Salesforce

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
| 15 | `mc-update check` | Table shows installed version (2.0.7 or 2.0.8), latest, and update status |
| 16 | `mc-update upgrade` | Upgrades to latest; prints new version after |

---

### Step 8 — Bug fix cycle

For each failure found in Steps 6–7:

1. Document the failure (symptom, steps to reproduce, expected vs actual)
2. Run `/gsd:debug` if root cause is unclear
3. Run `/tdd-issue` to create a red test, fix, green cycle
4. Or for simple fixes: edit directly + add regression test + commit

Track fixes in `.planning/BACKLOG.md` under a new "Active Bug Fixes" section.

---

## Do Later

### OCM silent token refresh (investigate)
**Type:** Future feature | **Effort:** Unknown (research required)
**Requirement:** OCM-F01/F02 from REQUIREMENTS.md

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
