# UAT Feature: `mc check` (CHK)

**Command:** `mc check <case>` / `mc chk <case>`
**Source:** `src/mc/cli/commands/case.py`, `src/mc/integrations/redhat.py`
**Prefix:** CHK

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Network available (unless test specifies offline)
- Valid Red Hat case number

---

## Story 1 — Workspace Status Check

### TC-CHK-01: Check existing workspace — all files OK

**Pre-requires:** none
**Cross-deps:** NEW-01 (workspace must exist)
**Tags:** check, happy-path, network, mode: host

**Goal:** `mc chk <case>` reports OK status when all workspace files exist.

**Steps:**
1. Create a workspace for a case: `mc new <case>`
2. Run `mc chk <case>`

**Expected:**
- Check completes without WARN or FATAL messages
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CHK-02: Check workspace with missing files (WARN)

**Pre-requires:** none
**Cross-deps:** none
**Tags:** check, degraded, negative, mode: host

**Goal:** `mc chk` reports WARN when workspace files are missing.

**Steps:**
1. Create a workspace for a case: `mc new <case>`
2. Delete one or more workspace files manually (e.g., `rm ~/mc/cases/*/<case>*/dt/*`)
3. Run `mc chk <case>`

**Expected:**
- Output includes WARN status indicating missing files
- Exits 0 (check itself succeeds, just reports issues)

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CHK-03: Check with --fix repairs missing files

**Pre-requires:** TC-CHK-02 (workspace must have missing files)
**Cross-deps:** none
**Tags:** check, fix, happy-path, mode: host

**Goal:** `mc chk <case> --fix` recreates missing workspace files.

**Steps:**
1. Ensure workspace has missing files (from CHK-02)
2. Run `mc chk <case> --fix`
3. Run `mc chk <case>` again

**Expected:**
- First run: logs fixing missing files
- Second run: reports OK status (files restored)
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CHK-04: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** check, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected immediately.

**Steps:**
1. Run `mc chk abc`
2. Run `mc chk 123`

**Expected:**
- Error: `Invalid case number: '...'. Case number must be exactly 8 digits.`
- Exits 1
- No network call made

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CHK-05: Check shows cached data indicator

**Pre-requires:** none
**Cross-deps:** none
**Tags:** check, cache, ux, mode: host

**Goal:** When case metadata is cached, `mc chk` shows the cache age.

**Steps:**
1. Run `mc chk <case>` (populates cache)
2. Run `mc chk <case>` again immediately

**Expected:**
- Second run shows: `Using cached data (cached Xm ago)`
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Workspace all files OK | CHK-01 |
| Missing files reported as WARN | CHK-02 |
| --fix recreates missing files | CHK-03 |
| Invalid case number rejected | CHK-04 |
| Cached data indicator shown | CHK-05 |
