# UAT Feature: `mc create` (NEW)

**Command:** `mc create <case>` / `mc new <case>`
**Source:** `src/mc/cli/commands/container.py`, `src/mc/cli/commands/case.py`, `src/mc/container/manager.py`, `src/mc/integrations/podman.py`
**Prefix:** NEW

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Podman running
- Network available (unless test specifies offline)
- Valid Red Hat case number

---

## Story 1 — Container Creation

### TC-NEW-01: Create container for valid case — happy path

**Pre-requires:** none
**Cross-deps:** none
**Tags:** create, happy-path, podman, network, mode: host

**Goal:** `mc new <case>` creates a Podman container and workspace directory.

**Setup:**
```bash
# Ensure no container exists for this case
mc container delete <case> 2>/dev/null || true
```

**Steps:**
1. Run `mc new <case>` (use a valid case number)
2. Run `mc container list`

**Expected:**
- Output: `Created container for case <case>`
- Output includes Container ID and Workspace path
- `mc container list` shows the container with status `running`
- Workspace directory exists on disk
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-NEW-02: Create with --download also fetches attachments

**Pre-requires:** none
**Cross-deps:** none
**Tags:** create, download, happy-path, network, mode: host

**Goal:** `mc new <case> --download` creates workspace files and downloads attachments in one step.

**Setup:**
```bash
mc container delete <case> 2>/dev/null || true
```

**Steps:**
1. Choose a case number with known attachments
2. Run `mc new <case> --download`
3. Check workspace attachments directory

**Expected:**
- Workspace files created
- Attachments downloaded to workspace attachments directory
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-NEW-03: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** create, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected before any Podman or network call.

**Steps:**
1. Run `mc new abc`
2. Run `mc new 123`

**Expected:**
- Error: `Invalid case number: '...'. Case number must be exactly 8 digits.`
- Exits 1
- No container created, no network call

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 2 — Container Lifecycle

### TC-NEW-04: Container list shows created container

**Pre-requires:** TC-NEW-01 (container must exist)
**Cross-deps:** none
**Tags:** list, happy-path, podman, mode: host

**Goal:** `mc container list` displays all containers with case number, status, customer, description, and created date.

**Steps:**
1. Ensure at least one container exists (from NEW-01)
2. Run `mc container list`

**Expected:**
- ASCII table with columns: CASE, STATUS, CUSTOMER, DESCRIPTION, CREATED
- Container from NEW-01 appears with correct case number
- Status shows `running` or `exited`
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-NEW-05: Stop and delete container lifecycle

**Pre-requires:** TC-NEW-01 (container must exist)
**Cross-deps:** none
**Tags:** stop, delete, lifecycle, podman, mode: host

**Goal:** Containers can be stopped and deleted cleanly.

**Steps:**
1. Ensure a running container exists (from NEW-01)
2. Run `mc container stop <case>`
3. Run `mc container list` — confirm status is stopped/exited
4. Run `mc container delete <case>`
5. Run `mc container list` — confirm container is gone

**Expected:**
- Stop: `Stopped container for case <case>`, exits 0
- Delete: preserves workspace, exits 0
- List after delete: container no longer shown
- Workspace directory still exists on disk

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Create container happy path | NEW-01 |
| Create with --download fetches attachments | NEW-02 |
| Invalid case number rejected | NEW-03 |
| Container list shows correct columns | NEW-04 |
| Stop and delete lifecycle | NEW-05 |
