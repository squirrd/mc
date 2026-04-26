# UAT Feature: `mc ldap` (WHO)

**Command:** `mc ldap <uid>` / `mc who <uid>`
**Source:** `src/mc/cli/commands/other.py`, `src/mc/integrations/ldap.py`
**Prefix:** WHO

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists
- Network available (LDAP reachable at ldaps://ldap.corp.redhat.com)
- `ldapsearch` binary installed and in PATH
- Valid Red Hat UID (unless test specifies otherwise)

---

## Story 1 — User Lookup

### TC-WHO-01: Lookup valid UID — card output

**Pre-requires:** none
**Cross-deps:** none
**Tags:** ldap, happy-path, network, mode: host

**Goal:** `mc who <uid>` displays a formatted user information card.

**Steps:**
1. Run `mc who <your-uid>` (use your own Red Hat UID)

**Expected:**
- Formatted card with separator lines (`--------`)
- Fields displayed: Name, RH Title, Title, Manager (as UID, not full DN), City, State, Country, UID, Hire Date, Mobile (if present)
- Manager field shows extracted UID (e.g., `jsmith`) not full LDAP DN
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-WHO-02: Lookup with --show-all shows raw LDAP

**Pre-requires:** none
**Cross-deps:** none
**Tags:** ldap, raw-output, network, mode: host

**Goal:** `mc who <uid> --show-all` displays the raw LDAP output instead of formatted cards.

**Steps:**
1. Run `mc who <your-uid> --show-all`

**Expected:**
- Raw LDAP attributes displayed (dn:, cn:, uid:, etc.)
- No card formatting (no separator lines)
- Full LDAP DN shown for manager field
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-WHO-03: Search term too short rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** ldap, validation, negative, fast, mode: host

**Goal:** Search terms shorter than 4 characters are rejected without an LDAP call.

**Steps:**
1. Run `mc who ab`
2. Run `mc who x`

**Expected:**
- Error: `Search term '...' must be between 4 and 15 characters`
- Exits 1
- No `ldapsearch` subprocess spawned

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-WHO-04: No results found message

**Pre-requires:** none
**Cross-deps:** none
**Tags:** ldap, edge-case, network, mode: host

**Goal:** A valid but non-existent UID returns a clear "no results" message.

**Steps:**
1. Run `mc who zzzzzzzzzz` (a UID unlikely to exist)

**Expected:**
- Output: `No results found.`
- Exits 1
- No crash or traceback

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-WHO-05: ldapsearch not installed handled

**Pre-requires:** none
**Cross-deps:** none
**Tags:** ldap, missing-dependency, negative, mode: host

**Goal:** When `ldapsearch` is not in PATH, a clear error is shown.

**Steps:**
1. Temporarily rename or remove `ldapsearch` from PATH (e.g., `PATH=/usr/bin mc who <uid>`)
2. Run `mc who <uid>`

**Expected:**
- Error: `'ldapsearch' command not found. Is it installed and in your PATH?`
- Exits 1
- No traceback

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Lookup valid UID — formatted card | WHO-01 |
| Raw LDAP output with --show-all | WHO-02 |
| Search term too short rejected | WHO-03 |
| No results found message | WHO-04 |
| ldapsearch not installed handled | WHO-05 |
