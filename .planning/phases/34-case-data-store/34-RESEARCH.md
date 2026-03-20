# Phase 34: Case Data Store - Research

**Researched:** 2026-03-20
**Domain:** Python file I/O, Red Hat API integration, agent-mode execution, OCM CLI subprocess
**Confidence:** HIGH (code verified by direct inspection; API field names verified by existing integration code and tests)

## Summary

Phase 34 writes four files (`sfdc-case.json`, `sfdc-comments.json`, `ocm-cluster.json`, `case.env`) to the case workspace before the interactive shell opens. According to CONTEXT.md, execution happens **inside the container** in agent mode, triggered as part of the attach sequence. The existing codebase already has all necessary API clients: `RedHatAPIClient` (host-side, OAuth token) for SFDC case data and comments, and `SalesforceAPIClient` (Salesforce SOQL) for the `Cluster_ID__c` field that maps to `MC_CLUSTER_EXTERNAL_ID`. The `ocm get cluster` call runs as a subprocess inside the container using the OCM binary already present at `/usr/local/bin/ocm`. The insertion point is **inside the container entrypoint or a new agent-mode hook** invoked before `exec bash` — not in the host-side `attach_terminal` flow.

**Primary recommendation:** Create a new `src/mc/agent/case_data.py` module that handles the fetch-and-write sequence, invoked from the container entrypoint or a new agent CLI command that runs before the interactive shell opens.

## Existing Flow

### Host side: `mc case N`

```
cli/main.py: args.command == 'case' or quick_access
  → cli/commands/container.py: case_terminal(args)
    1. Loads config (offline token)
    2. Authenticates → RedHatAPIClient(access_token)
    3. attach_terminal(case_number, config_manager, api_client, container_manager)
```

### attach_terminal (terminal/attach.py)

```
1. TTY check
2. Validate case number
3. get_case_metadata(case_number, api_client)  ← Red Hat API (host-side)
4. Auto-create container if missing (ContainerManager.create)
5. Auto-start container if stopped
6. Get workspace_path
7. Build case_metadata dict (case_number, customer_name, description, summary, status, severity)
8. write_bashrc(case_number, case_metadata) → /tmp/mc-bashrc-{case_number}
9. Build podman exec command: "podman exec -it --env 'BASH_ENV=...' mc-{case_number} /bin/bash; exit"
10. Launch terminal window
11. Return (non-blocking)
```

The terminal window then runs `podman exec -it mc-{case_number} /bin/bash` which triggers the container's `/usr/local/bin/entrypoint.sh`, then drops into bash.

### Container startup: entrypoint.sh

```bash
export CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH
export PS1="[case-${CASE_NUMBER}]$ "
cd /case
exec "$@"   # "$@" = /bin/bash (from CMD directive)
```

### What currently happens inside the container at attach time

Nothing fetches data inside the container. The entrypoint only sets environment variables from what ContainerManager passed at `docker create` time (`CASE_NUMBER`, `CUSTOMER_NAME`, `WORKSPACE_PATH`, `MC_RUNTIME_MODE=agent`). No API calls, no file writes.

## Red Hat API

### Case details endpoint (existing `RedHatAPIClient.fetch_case_details`)

**URL:** `GET https://api.access.redhat.com/support/v1/cases/{caseNumber}`

**Known response fields** (from `CaseDetails` TypedDict in `redhat_api.py`):
- `summary` (str, required)
- `accountNumberRef` (str, required)
- `status` (str, required)
- `severity` (NotRequired[str])
- `product` (NotRequired[str])

The TypedDict is conservative — the API returns more fields than typed. The `openshiftClusterID` field is **not** in the current TypedDict, but based on the CONTEXT.md decision, the SFDC API field `openshiftClusterID` maps to `MC_CLUSTER_EXTERNAL_ID`. This is likely a field the API returns but the current code doesn't use (the TypedDict only declares what the existing code accesses).

**Confidence on `openshiftClusterID`:** MEDIUM. The CONTEXT.md author asserts this field exists in the SFDC API response; the existing `SalesforceAPIClient.query_case` uses `Cluster_ID__c` from SOQL which produces the same data under `cluster_id` key. The Red Hat customer portal API docs are currently 404ing.

### Comments endpoint (not yet implemented)

**URL:** `GET https://api.access.redhat.com/support/v1/cases/{caseNumber}/comments`

**Confirmed:** The Red Hat Customer Portal Integration Guide confirms this endpoint exists (search result). A new `fetch_case_comments(case_number)` method needs to be added to `RedHatAPIClient`.

**Authentication:** Same Bearer token as `fetch_case_details`.

### What to add to RedHatAPIClient

New method: `fetch_case_comments(case_number: str) -> list[dict[str, Any]]`
- URL: `{BASE_URL}/cases/{case_number}/comments`
- Same error handling pattern as `fetch_case_details`
- Returns raw JSON list (full response, no filtering)

## Workspace Layout

### Host to container path mapping

The workspace path on the host (e.g., `~/mc/cases/AcmeCorp/12345678-Server_Down`) is mounted at `/case` inside the container:

```python
# container/manager.py, create()
volumes: dict[str, dict[str, str]] = {
    workspace_path: {"bind": "/case", "mode": "rw"},
    ...
}
```

### Directory structure (from WorkspaceManager._generate_file_dir_list)

```
/case/                  # = workspace_path on host
├── dt/
│   ├── logs/
│   └── metrics/
├── jira/
│   └── atts/
├── notes/
│   ├── ai/
│   ├── notes-01.md
│   ├── notes-02.md
│   ├── notes-03.md
│   └── tmp.md
├── oc/
└── sfdc/
    └── atts/
```

The new files per CONTEXT.md will be written to `/case/` (top level):
- `/case/sfdc-case.json`
- `/case/sfdc-comments.json`
- `/case/ocm-cluster.json` (conditional)
- `/case/case.env`

These are all **inside the container** at write time, but they land on the host's workspace_path via the volume mount. The `mcuser` container user needs write access, which is guaranteed by `userns_mode="keep-id"` (rootless Podman maps the container user to the host user).

## cluster_id Extraction

### Source: SalesforceAPIClient (Salesforce SOQL)

The `SalesforceAPIClient.query_case` already queries `Cluster_ID__c` from Salesforce and returns it as `cluster_id` in the response dict. This is the source for `MC_CLUSTER_EXTERNAL_ID`.

```python
# salesforce_api.py
'cluster_id': record.get('Cluster_ID__c', ''),
```

**Problem:** The current phase design says execution happens **inside the container** where the `SalesforceAPIClient` is not configured (it needs `SF_USERNAME`, `SF_PASSWORD`, `SF_SECURITY_TOKEN` which are not mounted into the container). The `RedHatAPIClient` uses the offline token from `~/mc/config/config.toml` which **is** mounted read-only.

### Source: RedHatAPIClient (Red Hat API)

The Red Hat API case response likely contains `openshiftClusterID`. Per CONTEXT.md, this is the field to use inside the container. The existing `CaseDetails` TypedDict does not currently include it, so it would need to be added or accessed via raw dict access.

### Fallback strategy

Per CONTEXT.md decisions:
- If `openshiftClusterID` is present and non-empty: use it as `MC_CLUSTER_EXTERNAL_ID`, also run `ocm get cluster <external_id>` → `ocm-cluster.json`
- If absent or empty: `MC_CLUSTER_EXTERNAL_ID=""` in `case.env`, no `ocm-cluster.json` written

### OCM CLI subprocess

The `ocm` binary is at `/usr/local/bin/ocm` inside the container (copied from `ocm-downloader` stage). The OCM config is mounted at `/home/mcuser/.config/ocm/ocm.json` (from `container/manager.py`).

```python
import subprocess
result = subprocess.run(
    ["ocm", "get", "cluster", external_id],
    capture_output=True,
    text=True,
    timeout=30,
)
if result.returncode == 0:
    # write ocm-cluster.json
else:
    # print warning, continue
```

## Insertion Point

### Decision from CONTEXT.md

Data is fetched and files are written **inside the container**, triggered by `mc` running in agent mode as part of the attach sequence — before the interactive shell opens.

### Two viable approaches

**Option A: Modify entrypoint.sh**

Add a `mc agent init-case` (or similar) call before `exec "$@"` in `entrypoint.sh`. This runs once when the terminal attaches.

```bash
# entrypoint.sh (modified)
mc agent init-case || echo "Warning: Failed to initialize case data, continuing..."
exec "$@"
```

**Option B: Agent-mode CLI command invoked via podman exec**

Modify `build_exec_command()` in `terminal/attach.py` to first run `mc agent init-case && podman exec... /bin/bash`.

**Preferred approach: Option A (entrypoint.sh + new agent CLI command)**

Reasons:
- The entrypoint already runs inside the container before bash starts
- Adding `mc agent init-case` there keeps the host-side `attach_terminal` clean
- The `MC_RUNTIME_MODE=agent` env var is already set, so `is_agent_mode()` works
- Agent CLI command is testable in isolation

### Implementation sketch

1. Add `mc agent init-case` CLI subcommand (new `src/mc/agent/case_data.py`)
2. Modify `container/entrypoint.sh` to call it before `exec "$@"`
3. The command reads config from `/home/mcuser/mc/config/config.toml` (mounted read-only)
4. Fetches from Red Hat API using access token obtained from offline token in config
5. Writes files to `/case/` (current working directory)

### Alternative: Host-side pre-write

Write the files from the host before attaching, using the host's existing authenticated clients. This is simpler (no new agent CLI) but contradicts CONTEXT.md's decision that writing happens inside the container.

**Recommendation: Follow CONTEXT.md — write inside container. Use entrypoint.sh hook.**

## Test Patterns

### Existing patterns to follow

1. **Unit tests for API clients:** Use `@responses.activate` decorator + `responses.add(...)` to mock HTTP (see `test_redhat_api.py`). Use `MagicMock` for Salesforce session (see `test_salesforce_api.py`).

2. **Unit tests for file writing:** Use `tmp_path` pytest fixture (built-in) to get real temp directories without cleanup burden. Use `mocker.patch` for external calls.

3. **Fixtures:** Add reusable fixtures to `tests/unit/conftest.py` for mock SFDC case response, mock comments response.

### Test file to create

`tests/unit/test_agent_case_data.py`

### Test scenarios to cover (per requirement CDS-05/CDS-06)

```python
# Field extraction
def test_extract_fields_all_present()
def test_extract_fields_missing_cluster_id_produces_empty_string()
def test_extract_fields_missing_product_produces_empty_string()
def test_extract_fields_missing_severity_produces_empty_string()

# case.env writing
def test_case_env_has_mc_prefix_on_all_vars()
def test_case_env_all_values_quoted()
def test_case_env_has_header_comment()
def test_case_env_mc_cluster_external_id_present_when_empty()
def test_case_env_is_valid_bash_source(tmp_path)

# File writing
def test_sfdc_case_json_written(tmp_path)
def test_sfdc_case_json_is_valid_json(tmp_path)
def test_sfdc_comments_json_written(tmp_path)
def test_case_env_written(tmp_path)
def test_ocm_cluster_json_written_when_cluster_id_present(tmp_path, mocker)
def test_ocm_cluster_json_not_written_when_cluster_id_absent(tmp_path, mocker)
def test_ocm_cluster_json_not_written_when_ocm_fails(tmp_path, mocker)

# Failure handling
def test_sfdc_api_failure_prints_warning_does_not_raise(mocker)
def test_comments_api_failure_prints_warning_does_not_raise(mocker)
def test_files_overwritten_on_each_call(tmp_path)
```

### Key testing consideration

The `case.env` sourcing test requires spawning a bash subprocess. Use `subprocess.run(["bash", "-c", f"source {env_path} && echo $MC_CASE_NUMBER"], ...)` to verify file is source-able.

## Key Files

### Files to modify

| File | Change |
|------|--------|
| `src/mc/integrations/redhat_api.py` | Add `fetch_case_comments()` method; extend `CaseDetails` TypedDict with `openshiftClusterID`, `product`, `severity` |
| `container/entrypoint.sh` | Add `mc agent init-case || true` before `exec "$@"` |

### Files to create

| File | Purpose |
|------|---------|
| `src/mc/agent/case_data.py` | Core logic: fetch SFDC case, comments, run OCM, write files |
| `src/mc/cli/commands/agent.py` | CLI command handler for `mc agent init-case` (or similar) |
| `tests/unit/test_agent_case_data.py` | Unit tests for the new module |

### Files to review (but likely not modify)

| File | Why |
|------|-----|
| `src/mc/cli/main.py` | May need new `agent` subcommand registered |
| `src/mc/runtime.py` | Agent mode detection already correct (`is_agent_mode()`) |
| `src/mc/utils/auth.py` | Token exchange already works; verify it works inside container |

## Risks & Open Questions

### Risk 1: `openshiftClusterID` field name in Red Hat API response

**What we know:** CONTEXT.md author asserts this field exists. The Salesforce SOQL uses `Cluster_ID__c` which is the same data.

**What's unclear:** The exact JSON key name in the `GET /support/v1/cases/{caseNumber}` response. The Red Hat API docs are 404ing. The existing `CaseDetails` TypedDict does not include it.

**Recommendation:** When implementing, test with a real case number using `curl` to inspect the full response and confirm field name before coding. Treat as `response.get("openshiftClusterID", "")` with fallback to empty string.

### Risk 2: Auth inside the container

**What we know:** The MC config (`~/mc/config/config.toml`) is mounted read-only at `/home/mcuser/mc/config`. It contains `rh_api_offline_token`.

**What's unclear:** Whether the offline token → access token exchange (`get_access_token()`) works correctly inside the container (no VPN issues, CA bundle, etc.).

**Recommendation:** The container already has the CA bundle from RHEL 10 UBI. The network path for token exchange (`sso.redhat.com`) should be accessible if VPN is active. This is MEDIUM risk — test manually.

### Risk 3: OCM login state inside container

**What we know:** OCM config is mounted at `/home/mcuser/.config/ocm/ocm.json`. This is the OCM session token file.

**What's unclear:** Whether the mounted OCM config is current and valid. If `ocm get cluster` fails due to expired OCM token, the phase should print a warning and continue without `ocm-cluster.json`.

**Recommendation:** Per CONTEXT.md, failure is acceptable — print warning, skip `ocm-cluster.json`. This is already in the design.

### Risk 4: entrypoint.sh runs on every container start, not just terminal attach

**What we know:** The container is started with `tail -f /dev/null` as its process (CMD). The entrypoint.sh runs when the container starts, not when `podman exec` attaches a terminal.

**What's unclear:** If writing happens in entrypoint.sh, files are written at container start time, not at each terminal attach. Per CONTEXT.md, files should be refreshed on every `mc case N` invocation.

**Recommendation:** The file write should happen in the `podman exec` command (not entrypoint), OR at the start of the bash session via `BASH_ENV`/bashrc. **Most correct approach:** Add the init call to `build_exec_command()` in `terminal/attach.py` — prepend `mc agent init-case; ` before `/bin/bash`. This runs on every terminal attach.

Revised insertion point:
```python
# terminal/attach.py: build_exec_command()
return (
    f"podman exec -it "
    f"--env 'BASH_ENV={bashrc_path}' "
    f"--env 'PS1=[MC-{case_number}] \\w\\$ ' "
    f"{proxy_env}"
    f"{container_id} /bin/bash -c 'mc agent init-case; exec bash'; exit"
)
```

This ensures files are written on every `mc case N` invocation (per CDS-04), not only on container creation.

### Open Question: Where exactly does `mc agent init-case` get its token?

The command runs inside the container as `mcuser`. It needs to:
1. Read offline token from `/home/mcuser/mc/config/config.toml`
2. Exchange for access token via SSO
3. Call Red Hat API

This is the same flow as host-side auth, just running in a different environment. The config mount is read-only, which is correct (token reading only).

## Sources

### Primary (HIGH confidence)
- Direct code inspection: `src/mc/integrations/redhat_api.py` — existing API client, `fetch_case_details` method, `CaseDetails` TypedDict
- Direct code inspection: `src/mc/integrations/salesforce_api.py` — `Cluster_ID__c` field, `query_case` method
- Direct code inspection: `src/mc/terminal/attach.py` — full attach workflow, `attach_terminal` function
- Direct code inspection: `src/mc/container/manager.py` — volume mounts, container creation, `workspace_path: /case`
- Direct code inspection: `container/Containerfile` — OCM binary at `/usr/local/bin/ocm`, `MC_RUNTIME_MODE=agent`
- Direct code inspection: `container/entrypoint.sh` — current entrypoint, `exec "$@"` pattern
- Direct code inspection: `.planning/phases/34-case-data-store/34-CONTEXT.md` — locked implementation decisions

### Secondary (MEDIUM confidence)
- Red Hat Customer Portal Integration Guide (WebSearch) — confirms `/cases/{caseNumber}/comments` endpoint exists
- Existing test patterns: `tests/unit/test_redhat_api.py`, `tests/unit/test_salesforce_api.py`, `tests/unit/test_terminal_attach.py`

### Tertiary (LOW confidence)
- `openshiftClusterID` field name in the Red Hat API case response — asserted by CONTEXT.md author, not independently verified (API docs 404)

## Metadata

**Confidence breakdown:**
- Existing flow trace: HIGH — verified by reading actual code
- Workspace layout (`/case/` mount): HIGH — confirmed in `container/manager.py`
- Red Hat API `fetch_case_details` fields: HIGH for typed fields; MEDIUM for `openshiftClusterID`
- Comments endpoint exists: MEDIUM — confirmed by docs search, not by code inspection
- OCM CLI available in container: HIGH — confirmed in `Containerfile`
- Insertion point (exec vs entrypoint): HIGH reasoning, MEDIUM on exact form
- Salesforce `Cluster_ID__c` → `MC_CLUSTER_EXTERNAL_ID`: HIGH — both CONTEXT.md and existing code confirm this

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable internal codebase; Red Hat API field names may change)
