# UAT Feature: `mc comments` (CMT)

**Command:** `mc comments <case>` / `mc cmt <case>`
**Source:** `src/mc/cli/commands/case.py`, `src/mc/integrations/salesforce.py`
**Prefix:** CMT

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Network available (unless test specifies offline)
- Valid Red Hat case number with comments

---

## Story 1 — Display Case Comments

### TC-CMT-01: Display comments for case with comments

**Pre-requires:** none
**Cross-deps:** none
**Tags:** comments, happy-path, network, mode: host

**Goal:** `mc cmt <case>` retrieves and displays case comments.

**Steps:**
1. Choose a case number with known comments
2. Run `mc cmt <case>`

**Expected:**
- Case comments displayed in log output
- Comments include JSON-formatted data with comment text, author, timestamps
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CMT-02: Comments output is valid JSON

**Pre-requires:** none
**Cross-deps:** none
**Tags:** comments, output-format, network, mode: host

**Goal:** The comments output is valid JSON that can be piped to `jq`.

**Steps:**
1. Run `mc cmt <case> 2>&1 | grep -A 9999 'Case comments:'`
2. Pipe the JSON portion through `jq .`

**Expected:**
- JSON is well-formed (jq exits 0)
- Contains comment entries with expected fields
- No truncation or malformed output

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CMT-03: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** comments, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected immediately.

**Steps:**
1. Run `mc cmt abc`
2. Run `mc cmt 123`

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

### TC-CMT-04: Cached data indicator shown on repeat

**Pre-requires:** none
**Cross-deps:** none
**Tags:** comments, cache, ux, mode: host

**Goal:** When case metadata is cached, `mc cmt` shows the cache age.

**Steps:**
1. Run `mc cmt <case>` (populates cache)
2. Run `mc cmt <case>` again immediately

**Expected:**
- Second run shows: `Using cached data (cached Xm ago)`
- Comments still displayed correctly
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CMT-05: Network failure handled gracefully

**Pre-requires:** none
**Cross-deps:** none
**Tags:** comments, offline, negative, network, mode: host

**Goal:** Network loss produces a clear error without hanging.

**Steps:**
1. Disable network
2. Run `mc cmt <case>` (use a case not in cache)
3. Re-enable network

**Expected:**
- Error message about network/API failure
- Exits 1
- Does not hang longer than ~10 seconds

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Display comments happy path | CMT-01 |
| Comments output is valid JSON | CMT-02 |
| Invalid case number rejected | CMT-03 |
| Cached data indicator shown | CMT-04 |
| Network failure handled gracefully | CMT-05 |
