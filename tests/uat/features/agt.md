# UAT Feature: `mc agent` (AGT)

**Command:** `mc agent <subcommand>` / `mc agt <subcommand>`
**Source:** `src/mc/cli/commands/agent.py`, `src/mc/runtime.py`
**Prefix:** AGT

**Pre-conditions (all TCs):**
- A case container running (create one with `mc container create 04433322` if none exists)
- Tests run **inside** the container: `podman exec -it mc-04433322 /bin/bash`
- `CASE_NUMBER` environment variable set (automatically set by ContainerManager)

---

## Story 1 — Case Initialization

### TC-AGT-01: init-case populates workspace from CASE_NUMBER

**Pre-requires:** none
**Cross-deps:** NEW-01 (container must exist)
**Tags:** agent, init-case, happy-path, mode: agent

**Goal:** `mc agent init-case` reads CASE_NUMBER from env and writes case metadata files to /case/.

**Setup:**
```bash
# Create a container if none exists
mc container create 04433322
```

**Steps:**
1. Enter the container: `podman exec -it mc-04433322 /bin/bash`
2. Verify: `echo $CASE_NUMBER` (should show `04433322`)
3. Run `mc agent init-case`
4. Check: `ls /case/`

**Expected:**
- Case metadata files written to `/case/` (e.g., `sfdc-case.json`)
- No error output
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-AGT-02: init-case fails when CASE_NUMBER not set

**Pre-requires:** none
**Cross-deps:** NEW-01 (container must exist)
**Tags:** agent, init-case, negative, mode: agent

**Goal:** `mc agent init-case` fails clearly when CASE_NUMBER environment variable is missing.

**Setup:**
```bash
# Create a container if none exists
mc container create 04433322
```

**Steps:**
1. Enter the container: `podman exec -it mc-04433322 /bin/bash`
2. Run `unset CASE_NUMBER`
3. Run `mc agent init-case`

**Expected:**
- Error on stderr: `Error: CASE_NUMBER environment variable not set`
- Exits 1

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 2 — Backplane Login

### TC-AGT-03: backplane-login runs for valid case

**Pre-requires:** TC-AGT-01 (init-case must have run to write sfdc-case.json)
**Cross-deps:** NEW-01 (container must exist)
**Tags:** agent, backplane-login, happy-path, network, mode: agent

**Goal:** `mc agent backplane-login` runs OCM backplane login using the cluster_id from case data.

**Setup:**
```bash
# Container should already exist from AGT-01
mc container create 04433322 2>/dev/null || true
```

**Steps:**
1. Enter the container: `podman exec -it mc-04433322 /bin/bash`
2. Ensure init-case has run (from AGT-01)
3. Run `mc agent backplane-login`

**Expected:**
- Attempts OCM backplane login
- If cluster_id found: runs `ocm backplane login <cluster_id>`
- If no cluster_id: prompts user or logs warning (non-fatal)
- Does not crash — failure is non-fatal by design

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-AGT-04: backplane-login skips when CASE_NUMBER not set

**Pre-requires:** none
**Cross-deps:** NEW-01 (container must exist)
**Tags:** agent, backplane-login, negative, mode: agent

**Goal:** `mc agent backplane-login` skips gracefully when CASE_NUMBER is not set.

**Setup:**
```bash
# Create a container if none exists
mc container create 04433322
```

**Steps:**
1. Enter the container: `podman exec -it mc-04433322 /bin/bash`
2. Run `unset CASE_NUMBER`
3. Run `mc agent backplane-login`

**Expected:**
- Warning logged: `CASE_NUMBER environment variable not set — skipping backplane login`
- Exits 0 (non-fatal, returns gracefully)
- No crash or traceback

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 3 — Runtime Mode Detection

### TC-AGT-05: Runtime mode detected as agent inside container

**Pre-requires:** none
**Cross-deps:** NEW-01 (container must exist)
**Tags:** agent, runtime, mode-detection, mode: agent

**Goal:** Inside a container, the runtime mode is correctly detected as `agent` via env var and container indicator file.

**Setup:**
```bash
# Create a container if none exists
mc container create 04433322
```

**Steps:**
1. Enter the container: `podman exec -it mc-04433322 /bin/bash`
2. Run `echo $MC_RUNTIME_MODE`
3. Run `ls /run/.containerenv`

**Expected:**
- `MC_RUNTIME_MODE` is `agent`
- `/run/.containerenv` exists (Podman container indicator)
- Both detection paths in `runtime.py` would return agent/container

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| init-case populates workspace | AGT-01 |
| init-case fails without CASE_NUMBER | AGT-02 |
| backplane-login runs for valid case | AGT-03 |
| backplane-login skips without CASE_NUMBER | AGT-04 |
| Runtime mode detected as agent | AGT-05 |
