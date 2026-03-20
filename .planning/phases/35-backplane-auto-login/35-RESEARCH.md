# Phase 35: Backplane Auto-Login - Research

**Researched:** 2026-03-20
**Domain:** Agent-mode Python CLI, SQLite schema migration, subprocess streaming, sfdc-case.json file I/O
**Confidence:** HIGH (all findings from direct source code inspection)

## Summary

Phase 35 adds `mc agent backplane-login` — a command that runs inside the container, reads the cluster ID from `/case/sfdc-case.json` (written by Phase 34), falls back to a StateDatabase-stored ID, prompts the user if neither is available, then runs `ocm backplane login <cluster-id>` with live output passthrough. Login failure is non-fatal.

**Critical dependency:** Phase 34 has NOT been executed yet. `src/mc/agent/case_data.py`, `src/mc/cli/commands/agent.py`, and the `mc agent` CLI subcommand do not exist in the codebase. Phase 35 depends on all of Phase 34's implementation being complete.

**Critical architectural constraint:** The StateDatabase (`~/mc/state/containers.db`) is NOT mounted inside the container. Only the workspace (`/case`), `~/mc/config` (read-only), optionally `~/.config/ocm/ocm.json` (read-only), and optionally `~/.claude` (read-write) are mounted. StateDatabase persistence for cluster_id must happen on the HOST side, not from inside the container.

**Design decision this forces:** The `backplane-login` command runs inside the container. It can read `sfdc-case.json` (at `/case/sfdc-case.json`) and prompt the user. But it cannot write to StateDatabase directly. To persist a user-entered cluster_id, one of two approaches must be used:

1. **Write a sentinel file to `/case/`**: e.g., `/case/.cluster_id` — the host reads this after `mc case N` to update StateDatabase. Simple but asynchronous.
2. **Mount `~/mc/state` into the container**: Add `~/mc/state` as a read-write volume. StateDatabase then accessible from container. Direct write to StateDatabase from agent code.

**Recommendation:** Mount `~/mc/state` read-write (Option 2). This is the most consistent approach and matches the CONTEXT.md requirement that the user-entered cluster_id "stored in StateDatabase `containers` table — reused on subsequent `mc case N`". Mounting one additional directory is low risk and follows the established pattern of `~/mc/config` already being mounted.

**Primary recommendation:** Add `~/mc/state` mount to `ContainerManager.create()`, add `cluster_id` column to StateDatabase, implement `mc agent backplane-login` to read sfdc-case.json, check StateDB, prompt if needed, run `ocm backplane login`, and persist on success.

---

## StateDatabase Schema and Migration Pattern

### Current Schema (HIGH confidence — verified by reading `src/mc/container/state.py`)

```sql
CREATE TABLE IF NOT EXISTS containers (
    case_number TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL
)
```

Indexes: `idx_container_id` on `container_id`, `idx_created_at` on `created_at`.

**No `cluster_id` column exists.** It must be added.

### Migration Approach (HIGH confidence — examined `_ensure_schema()` pattern)

There is **no migration framework** in the codebase. The `_ensure_schema()` method uses `CREATE TABLE IF NOT EXISTS`, which is idempotent for initial creation but cannot add new columns to existing tables.

The correct approach for adding `cluster_id` to an existing production database is `ALTER TABLE ... ADD COLUMN`:

```python
def _ensure_schema(self) -> None:
    """Create containers table and indices if they don't exist.

    Also runs any pending schema migrations.
    """
    with self._connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS containers (
                case_number TEXT PRIMARY KEY,
                container_id TEXT NOT NULL,
                workspace_path TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)
        # Migration: add cluster_id column (idempotent via try/except)
        try:
            conn.execute("ALTER TABLE containers ADD COLUMN cluster_id TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists — normal for existing databases

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_container_id ON containers(container_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_created_at ON containers(created_at)"
        )
```

The `try/except OperationalError` pattern is the standard SQLite migration technique when no migration table is maintained. SQLite raises `OperationalError: duplicate column name: cluster_id` if the column already exists.

### `update_container()` Already Works for cluster_id

`update_container(case_number, **kwargs)` uses a dynamic `SET field = ?` builder. After the column is added, calling `state_db.update_container("12345678", cluster_id="abc-123")` works without any additional method changes.

### `get_container()` and `ContainerMetadata` — Need Extension

`get_container()` currently reads 5 columns: `case_number, container_id, workspace_path, created_at, updated_at`. After adding the column it must read `cluster_id` too. `ContainerMetadata` dataclass needs a `cluster_id: str` field (with default `""` for backwards compatibility).

```python
# In get_container():
return ContainerMetadata(
    case_number=row["case_number"],
    container_id=row["container_id"],
    workspace_path=row["workspace_path"],
    created_at=row["created_at"],
    updated_at=row["updated_at"],
    cluster_id=row["cluster_id"] or "",  # coerce NULL to ""
)
```

### `add_container()` — Can remain unchanged

The INSERT does not need `cluster_id` — new rows will get `NULL` which is fine (coerced to `""` at read time).

---

## Volume Mounts — Critical Architectural Finding

### Current mounts (HIGH confidence — verified by reading `src/mc/container/manager.py` lines 151-159)

```python
volumes: dict[str, dict[str, str]] = {
    workspace_path: {"bind": "/case", "mode": "rw"},
    str(mc_config): {"bind": "/home/mcuser/mc/config", "mode": "ro"},
}
# Optional: ocm.json (ro), ~/.claude (rw)
```

The host path `~/mc/state/` is NOT mounted. The StateDatabase at `~/mc/state/containers.db` is therefore NOT accessible from inside the container.

### Required change to support StateDatabase access from agent code

Add `~/mc/state` as a read-write mount in `ContainerManager.create()`:

```python
mc_state = Path.home() / "mc" / "state"
mc_state.mkdir(parents=True, exist_ok=True)  # ensure directory exists
volumes[str(mc_state)] = {"bind": "/home/mcuser/mc/state", "mode": "rw"}
```

**Note:** This mount uses `rw` because `mc agent backplane-login` must write to the database from inside the container. The `~/mc/config` mount is `ro` (config is read-only from container).

**Path resolution inside container:** After this mount, `Path.home() / "mc" / "state" / "containers.db"` inside the container (where `~` = `/home/mcuser`) resolves to `/home/mcuser/mc/state/containers.db`, which is the mounted host database. The `_get_manager()` helper in `container.py` uses exactly `os.path.join(os.path.expanduser("~"), "mc", "state", "containers.db")` — this works correctly inside the container.

**Existing containers:** Adding this mount to `create()` only affects newly-created containers. Existing containers that were created without this mount will not have StateDatabase access. For Phase 35, this means cluster_id persistence via StateDatabase only works for containers created after Phase 35 is deployed. This is acceptable — missing persistence degrades gracefully to re-prompting.

---

## attach_terminal and exec Command Flow

### `build_exec_command()` Current Output (HIGH confidence — read `src/mc/terminal/attach.py`)

**Current code (Phase 34 NOT YET EXECUTED — actual current code):**
```python
return (
    f"podman exec -it "
    f"--env 'BASH_ENV={bashrc_path}' "
    f"--env 'PS1=[MC-{case_number}] \\w\\$ ' "
    f"{proxy_env}"
    f"{container_id} /bin/bash; exit"
)
```

**Phase 34 target (from 34-03-PLAN.md, after Phase 34 executes):**
```python
return (
    f"podman exec -it "
    f"--env 'BASH_ENV={bashrc_path}' "
    f"--env 'PS1=[MC-{case_number}] \\w\\$ ' "
    f"{proxy_env}"
    f"{container_id} /bin/bash -c 'mc agent init-case || true; exec bash'; exit"
)
```

### Phase 35 Target Insertion Point

Phase 35's `mc agent backplane-login` must run AFTER `mc agent init-case` (so `sfdc-case.json` exists) and BEFORE `exec bash`. The target exec command after both Phase 34 and Phase 35 are complete:

```python
return (
    f"podman exec -it "
    f"--env 'BASH_ENV={bashrc_path}' "
    f"--env 'PS1=[MC-{case_number}] \\w\\$ ' "
    f"{proxy_env}"
    f"{container_id} /bin/bash -c 'mc agent init-case || true; mc agent backplane-login || true; exec bash'; exit"
)
```

Key points:
- `mc agent backplane-login || true` — non-fatal; shell opens regardless
- `exec bash` — replaces the bash -c subshell with an interactive shell (BASH_ENV honoured)
- `; exit` at the end closes the terminal window when the user exits
- The `|| true` ensures a non-zero exit from `backplane-login` does not abort the chain

**Sequence dependency:** Phase 35 modifies the same line that Phase 34 modifies. Phase 35 plan tasks must take Phase 34's new format as the starting point, not the original `/bin/bash; exit` format.

---

## Agent CLI Structure

### Current State (HIGH confidence — verified by file inspection)

The `mc agent` subcommand **does not exist** in the current codebase. Only `src/mc/agent/__init__.py` exists (empty file, 1 line).

Phase 34 will create:
- `src/mc/cli/commands/agent.py` — with `init_case(args)` function reading `CASE_NUMBER` env var
- Registration in `src/mc/cli/main.py`:
  ```python
  agent_parser = subparsers.add_parser('agent', help='Agent-mode commands (container-internal)')
  agent_subparsers = agent_parser.add_subparsers(dest='agent_command')
  agent_subparsers.add_parser('init-case', help='Initialize case data files in container workspace')
  ```
- Routing:
  ```python
  elif args.command == 'agent':
      from mc.cli.commands.agent import init_case
      if args.agent_command == 'init-case':
          init_case(args)
      else:
          agent_parser.print_help()
  ```

### What Phase 35 Adds to the Agent CLI

1. In `src/mc/cli/main.py`:
   - Add: `agent_subparsers.add_parser('backplane-login', help='Run ocm backplane login for case cluster')`
   - Add routing: `elif args.agent_command == 'backplane-login': backplane_login(args)`

2. In `src/mc/cli/commands/agent.py`:
   - Add `backplane_login(args)` function that reads `CASE_NUMBER` env var and calls `run_backplane_login(case_number)`

### How `backplane_login` gets case_number

Like `init_case`, reads `CASE_NUMBER` from the container environment variable (set by `ContainerManager.create()`):
```python
case_number = os.environ.get("CASE_NUMBER", "").strip()
```

---

## sfdc-case.json Format

### What Phase 34 Writes (HIGH confidence — verified via 34-02-PLAN.md)

`sfdc-case.json` is the raw, unmodified response from `RedHatAPIClient.fetch_case_details()` serialized as JSON with `indent=2`. It is the complete API response dict.

The key for cluster ID in this file is `openshiftClusterID` (the raw API field name):
```python
cluster_external_id = str(case_details.get("openshiftClusterID") or "")
```

### Reading sfdc-case.json in Phase 35

```python
import json
import os

sfdc_case_path = os.path.join("/case", "sfdc-case.json")
try:
    with open(sfdc_case_path) as f:
        sfdc_data = json.load(f)
    cluster_id = str(sfdc_data.get("openshiftClusterID") or "").strip()
except (FileNotFoundError, json.JSONDecodeError, OSError):
    cluster_id = ""
```

The file may not exist (if `mc agent init-case` failed or the case has no API data). Always handle `FileNotFoundError`.

---

## Full Implementation Flow (inside container)

```
1. Read /case/sfdc-case.json → sfdc_cluster_id (empty string if file missing or field absent)
2. If sfdc_cluster_id is non-empty → use it (sfdc wins); skip prompt
3. If sfdc_cluster_id is empty → query StateDatabase for stored cluster_id
4. If StateDatabase has non-empty cluster_id → use it (no prompt)
5. If still no cluster_id → prompt user: "Enter cluster ID (or press Enter to skip): "
6. Validate input format
7. If user enters blank → return immediately (shell opens without login)
8. Run: ocm backplane login <cluster_id> (capture_output=True, then print)
9. If exit code 0 AND cluster_id came from user input → persist to StateDatabase
10. If exit code non-zero:
    - Inspect stderr for token expiry signals
    - Print targeted message or generic warning
    - Clear StateDatabase cluster_id if one was stored (force re-prompt next time)
    - Return (shell still opens)
```

**Source priority (CONTEXT.md locked):** sfdc-case.json cluster_id wins over StateDatabase. User-entered IDs (successful login only) persist to StateDatabase. Cluster IDs sourced from sfdc-case.json or StateDatabase are NOT re-persisted.

---

## Cluster ID Validation Approach

### Case number validation pattern (HIGH confidence — read `src/mc/utils/validation.py`)

```python
def validate_case_number(case_number: str | int) -> str:
    case_str = str(case_number).strip()
    if not re.match(r'^\d{8}$', case_str):
        raise ValueError(...)
    return case_str
```

### Cluster ID validation (Claude's Discretion per CONTEXT.md)

OpenShift cluster IDs are typically alphanumeric strings with hyphens, often UUID-like. A reasonable validation function:

```python
import re

def validate_cluster_id(cluster_id: str) -> bool:
    """Return True if cluster_id passes basic format check.

    Accepts alphanumeric strings with hyphens, length 8-64.
    Rejects empty strings and strings with spaces or special chars.
    """
    cluster_id = cluster_id.strip()
    if not cluster_id:
        return False
    return bool(re.match(r'^[a-zA-Z0-9][a-zA-Z0-9\-]{6,62}[a-zA-Z0-9]$', cluster_id))
```

This can be added to `src/mc/utils/validation.py` alongside `validate_case_number` to keep validation centralized, or kept local in `backplane_login.py`.

---

## Token Expiry Detection

### Claude's Discretion (per CONTEXT.md)

OCM's `backplane login` error output typically contains phrases indicating token expiry. A simple detection approach:

```python
def _is_token_expired(stderr_output: str) -> bool:
    """Check if OCM error output indicates token expiry."""
    lower = stderr_output.lower()
    return any(phrase in lower for phrase in [
        "token is expired",
        "token expired",
        "unauthorized",
        "please login",
        "re-authenticate",
        "401",
    ])
```

If token expiry detected, print:
`"OCM token expired — run 'ocm login' to re-authenticate"`

Otherwise, print generic:
`"Warning: backplane login failed (exit {code}) — continuing without cluster login"`

---

## subprocess Pattern for Live Output

### Phase 35 uses `capture_output=True` then manual print

CONTEXT.md requires "live output passthrough — stream `ocm backplane login` stdout/stderr directly to terminal." However, token expiry detection requires inspecting stderr content. The resolution is to capture output and print immediately after the subprocess completes.

```python
import subprocess
import sys

result = subprocess.run(
    ["ocm", "backplane", "login", cluster_id],
    capture_output=True,
    text=True,
    timeout=120,  # backplane login may take time
)

# Print output as if it were live (complete before shell prompt appears)
if result.stdout:
    sys.stdout.write(result.stdout)
    sys.stdout.flush()
if result.stderr:
    sys.stderr.write(result.stderr)
    sys.stderr.flush()
```

This satisfies "user waits for login to complete before shell prompt appears" while enabling token expiry inspection. The output is printed in full before `exec bash` runs.

**Timeout:** 120 seconds. Backplane login involves cluster discovery which can be slow. 30 seconds (used by Phase 34's `ocm get cluster`) may be too short for backplane login specifically.

---

## Test Patterns to Follow

### StateDatabase test pattern (HIGH confidence — verified `tests/unit/test_container_state.py`)

All tests use `:memory:` or `tmp_path` fixture for the database. No mocking of sqlite3 itself.

For the migration test:
```python
def test_cluster_id_column_added_to_existing_db(tmp_path):
    """Migration adds cluster_id to databases created before Phase 35."""
    import sqlite3
    db_path = str(tmp_path / "old.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE containers (
            case_number TEXT PRIMARY KEY,
            container_id TEXT NOT NULL,
            workspace_path TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
    """)
    conn.execute("INSERT INTO containers VALUES ('12345678','id1','/p',1,1)")
    conn.commit()
    conn.close()

    # Opening StateDatabase triggers migration
    db = StateDatabase(db_path)
    result = db.get_container("12345678")
    assert result is not None
    assert result.cluster_id == ""  # NULL coerced to ""
```

### Agent command test pattern (from 34-02-PLAN.md)

```python
# Mock at module path where imported in backplane_login.py
mocker.patch("mc.agent.backplane_login.subprocess.run", ...)
mocker.patch("mc.agent.backplane_login.StateDatabase", ...)

# Use capsys to capture print() output
def test_warns_on_failure(mocker, capsys):
    mocker.patch("mc.agent.backplane_login.subprocess.run",
                 return_value=MagicMock(returncode=1, stdout="", stderr="connection error"))
    run_backplane_login("12345678", case_dir="/tmp", state_db=StateDatabase(":memory:"))
    captured = capsys.readouterr()
    assert "Warning" in captured.out
```

### Test file: `tests/unit/test_agent_backplane_login.py`

Required test scenarios:
```python
# Source priority
def test_sfdc_case_json_cluster_id_wins_over_state_db(tmp_path, mocker)
def test_state_db_cluster_id_used_when_sfdc_absent(tmp_path, mocker)
def test_user_prompted_when_no_cluster_id_available(tmp_path, mocker)
def test_user_skip_opens_shell_without_login(tmp_path, mocker)

# Success path
def test_successful_login_persists_user_entered_id_to_state_db(tmp_path, mocker)
def test_sfdc_cluster_id_not_persisted_to_state_db(tmp_path, mocker)
def test_state_db_cluster_id_not_re_persisted(tmp_path, mocker)

# Failure paths
def test_failed_login_clears_state_db_cluster_id(tmp_path, mocker)
def test_failed_login_prints_warning(tmp_path, mocker, capsys)
def test_token_expiry_prints_targeted_message(tmp_path, mocker, capsys)
def test_ocm_not_found_warns_and_skips(tmp_path, mocker, capsys)
def test_timeout_warns_and_skips(tmp_path, mocker, capsys)

# Validation
def test_invalid_cluster_id_format_prompts_again_or_skips(tmp_path, mocker)

# StateDatabase migration (in test_container_state.py)
def test_cluster_id_column_added_to_existing_db(tmp_path)
def test_existing_rows_get_empty_cluster_id_after_migration(tmp_path)
def test_cluster_id_update_and_retrieve(tmp_path)
def test_cluster_id_clear_sets_empty_string(tmp_path)
```

---

## Key Files to Modify / Create

### Files to Modify

| File | Change | Notes |
|------|--------|-------|
| `src/mc/container/state.py` | Add `cluster_id` column migration in `_ensure_schema()`; add `cluster_id` to `get_container()` SELECT and ContainerMetadata construction | Core schema change |
| `src/mc/container/models.py` | Add `cluster_id: str = ""` field to `ContainerMetadata` dataclass | Default empty for backwards compat |
| `src/mc/container/manager.py` | Add `~/mc/state` volume mount in `create()` | Required for StateDB access from container |
| `src/mc/cli/commands/agent.py` | Add `backplane_login(args)` function | File created by Phase 34 |
| `src/mc/cli/main.py` | Add `backplane-login` to `agent_subparsers`; add routing case | File modified by Phase 34 |
| `src/mc/terminal/attach.py` | Update `build_exec_command()` to include `mc agent backplane-login || true` in the bash -c chain | File modified by Phase 34 |
| `tests/unit/test_container_state.py` | Add migration tests for `cluster_id` column | Extend existing test file |
| `tests/unit/test_terminal_attach.py` | Update exec command assertions to expect `backplane-login` | Phase 34 already updates this; Phase 35 extends |

### Files to Create

| File | Purpose |
|------|---------|
| `src/mc/agent/backplane_login.py` | Core logic: read sfdc-case.json, check StateDB, prompt, run ocm, persist |
| `tests/unit/test_agent_backplane_login.py` | Full unit test coverage |

### Files NOT to Modify

- `container/entrypoint.sh` — runs on container start only, not at terminal attach time
- `src/mc/integrations/podman.py` — no container management changes needed
- `src/mc/utils/validation.py` — optional: add `validate_cluster_id` here for consistency

---

## Risks and Open Questions

### Risk 1: Phase 34 not yet executed — Phase 35 cannot test the full chain until Phase 34 is complete

**What we know:** `mc agent init-case`, `src/mc/cli/commands/agent.py`, and the updated `build_exec_command()` do not yet exist in the codebase.

**Impact on Phase 35 planning:** Phase 35 plan tasks that modify `main.py` and `agent.py` assume those files exist in their Phase-34 form. Phase 35 must execute after Phase 34.

### Risk 2: Existing containers do not have `~/mc/state` mounted

**What we know:** Adding `~/mc/state` mount to `create()` only affects containers created after Phase 35 deployment.

**Impact:** Existing containers cannot persist cluster_id to StateDatabase. On existing containers, `mc agent backplane-login` can still read sfdc-case.json and prompt for cluster_id, but cannot write back. StateDatabase write would fail silently or raise an exception (FileNotFoundError or sqlite3 error).

**Recommendation:** The agent code should handle `StateDatabase` initialization failure gracefully — if the database file path is not accessible, skip persistence and warn. This degrades to re-prompting on every attach (acceptable).

### Risk 3: `openshiftClusterID` field may be absent from some case API responses

**What we know:** Phase 34 research rated this MEDIUM confidence. The field name is asserted by CONTEXT.md author.

**Impact on Phase 35:** If the field is absent, `sfdc-case.json` will have no `openshiftClusterID` key. Phase 35 handles this with `.get("openshiftClusterID") or ""` — safe. Falls back to StateDatabase or prompt.

### Risk 4: `exec bash` and BASH_ENV interaction with three sequential commands

**What we know:** Phase 34's planned exec command runs `bash -c 'mc agent init-case || true; exec bash'`. Phase 35 inserts `mc agent backplane-login || true` between these.

**What's unclear:** Whether `exec bash` properly replaces the `bash -c` subshell when preceded by two commands that may have interactive I/O (backplane-login prompts the user). The interactive prompt inside a `bash -c` subshell may not behave correctly if the subshell's stdin/stdout are not a TTY.

**Investigation needed:** The `podman exec -it` flags provide a TTY (`-t`) and keep stdin open (`-i`), which should make the subprocess a proper TTY context. The prompt in `mc agent backplane-login` uses `input()` which reads from stdin — this should work with `-it`. However, this should be manually tested before relying on it.

### Risk 5: subprocess timeout for backplane login

**What we know:** `ocm backplane login` involves cluster discovery and authentication. The timeout should be generous (120s recommended).

**Risk:** If backplane login takes longer than the timeout, the subprocess raises `subprocess.TimeoutExpired`. The code must catch this and handle as a non-fatal failure.

### Open Question: cluster_id state clearing on failure — race condition

If the StateDatabase has a stored cluster_id from a previous successful login, and a new session fails (e.g., cluster decommissioned), the stored ID is cleared. On the next `mc case N`, the user must enter a new cluster ID. This is the intended behavior (CONTEXT.md: "auto-clear from StateDatabase on login failure").

However, if the sfdc-case.json has a non-empty cluster_id AND login fails, the StateDatabase would have nothing to clear (the sfdc ID is not stored). The user would then be prompted on the next session even though sfdc-case.json still has the cluster_id — which means the sfdc ID would be tried again (and fail again if the cluster is decommissioned). This is a minor UX issue, not a code bug.

---

## Sources

### Primary (HIGH confidence)
- Direct inspection: `src/mc/container/state.py` — full StateDatabase implementation, `_ensure_schema()`, `update_container()`, `get_container()`
- Direct inspection: `src/mc/container/models.py` — ContainerMetadata dataclass (5 fields, no cluster_id)
- Direct inspection: `src/mc/container/manager.py` lines 150-159 — volumes dict, confirmed `~/mc/state` NOT mounted
- Direct inspection: `src/mc/terminal/attach.py` — `build_exec_command()` current form, `attach_terminal()` full flow
- Direct inspection: `src/mc/cli/main.py` — subcommand registration pattern, no `agent` subcommand currently
- Direct inspection: `src/mc/cli/commands/container.py` — `_get_manager()` StateDatabase path pattern
- Direct inspection: `src/mc/utils/validation.py` — `validate_case_number()` pattern for cluster_id validation by analogy
- Direct inspection: `src/mc/runtime.py` — `is_agent_mode()`, `MC_RUNTIME_MODE` env var
- Direct inspection: `tests/unit/test_container_state.py` — test patterns for StateDatabase
- Direct inspection: `tests/unit/test_terminal_attach.py` — test patterns for `build_exec_command()`
- Direct inspection: `.planning/phases/34-case-data-store/34-RESEARCH.md` — Phase 34 findings, confirmed exec command insertion point
- Direct inspection: `.planning/phases/34-case-data-store/34-02-PLAN.md` — Phase 34 agent CLI structure and `agent.py` content
- Direct inspection: `.planning/phases/34-case-data-store/34-03-PLAN.md` — Phase 34 `build_exec_command()` target format
- Direct inspection: `.planning/STATE.md` — confirmed Phase 34 not yet executed

### Secondary (MEDIUM confidence)
- Phase 34 RESEARCH.md Risk 4 conclusion: exec command (not entrypoint.sh) is the correct insertion point for per-attach operations

---

## Metadata

**Confidence breakdown:**
- StateDatabase schema (no cluster_id): HIGH — read actual source
- Migration pattern (ALTER TABLE + try/except): HIGH — standard SQLite, no existing framework
- Volume mounts / StateDB NOT mounted: HIGH — read actual `manager.py` volumes dict
- exec command insertion point: HIGH — Phase 34 plans are explicit; Phase 35 appends
- Agent CLI structure (Phase 34 not yet executed): HIGH — plans are clear and detailed
- sfdc-case.json key (`openshiftClusterID`): MEDIUM — inherited from Phase 34 MEDIUM confidence finding
- subprocess output approach: HIGH — standard Python subprocess with capture
- Token expiry detection strings: MEDIUM — common OCM patterns, not verified against live output

**Research date:** 2026-03-20
**Valid until:** 2026-04-20 (stable codebase; only invalidated if Phase 34 implementation deviates from its plans, or `manager.py` mounts change)
