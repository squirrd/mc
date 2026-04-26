# UAT Feature: `mc attachments` (ATT)

**Command:** `mc attachments <case>` / `mc att <case>`
**Source:** `src/mc/cli/commands/case.py`, `src/mc/utils/downloads.py`, `src/mc/integrations/redhat.py`
**Prefix:** ATT

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Network available (unless test specifies offline)
- Valid Red Hat case number with attachments

---

## Story 1 — Download Attachments

### TC-ATT-01: Download attachments — happy path parallel

**Pre-requires:** none
**Cross-deps:** none
**Tags:** attachments, happy-path, network, parallel, mode: host

**Goal:** `mc att <case>` downloads all attachments in parallel and prints a success summary.

**Steps:**
1. Choose a case number with known attachments (at least 2 files)
2. Ensure the attachment directory does not already exist: `rm -rf ~/mc/cases/*/<case>*/sfdc/atts/*`
3. Run `mc att <case>`

**Expected:**
- Attachments download with progress output
- Summary: `✓ Successfully downloaded N file(s)`
- Files appear in the case workspace attachments directory
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-ATT-02: Download attachments — serial mode

**Pre-requires:** none
**Cross-deps:** none
**Tags:** attachments, happy-path, network, serial, mode: host

**Goal:** `mc att <case> --serial` downloads attachments one at a time with per-file output.

**Steps:**
1. Choose a case number with known attachments
2. Clear any previously downloaded attachments for this case
3. Run `mc att <case> --serial`

**Expected:**
- Each file prints `Downloading <filename>...` sequentially
- No parallel progress bars
- All files downloaded to workspace attachments directory
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-ATT-03: Skip already-downloaded files

**Pre-requires:** TC-ATT-01 (attachments must already exist)
**Cross-deps:** none
**Tags:** attachments, idempotent, fast, mode: host

**Goal:** Re-running `mc att` skips files that already exist on disk.

**Steps:**
1. Ensure attachments for a case are already downloaded (from ATT-01)
2. Run `mc att <case> --serial`

**Expected:**
- Each file prints `Skipping <filename> (already exists)`
- No files re-downloaded
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-ATT-04: Case with no attachments

**Pre-requires:** none
**Cross-deps:** none
**Tags:** attachments, edge-case, network, mode: host

**Goal:** `mc att` for a case with no attachments prints a clear message and exits cleanly.

**Steps:**
1. Find or use a case number that has zero attachments
2. Run `mc att <case>`

**Expected:**
- Output: `No attachments found for this case`
- Exits 0
- No directories created for attachments

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-ATT-05: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** attachments, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected immediately without a network call.

**Steps:**
1. Run `mc att abc`
2. Run `mc att 123`
3. Run `mc att 123456789`

**Expected:**
- Each prints: `Invalid case number: '...'. Case number must be exactly 8 digits.`
- Exits 1 for each
- No network call made

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Parallel download happy path | ATT-01 |
| Serial download mode | ATT-02 |
| Skip already-downloaded files (idempotent) | ATT-03 |
| No attachments — clear message | ATT-04 |
| Invalid case number rejected | ATT-05 |
