# UAT Feature: `mc launch` (URL)

**Command:** `mc launch <case>` / `mc url <case>`
**Source:** `src/mc/cli/commands/other.py`
**Prefix:** URL

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists
- Valid Red Hat case number
- Google Chrome installed at `/Applications/Google Chrome.app` (for launch TCs)

---

## Story 1 — Salesforce URL Launch

### TC-URL-01: Launch opens Chrome with correct URL

**Pre-requires:** none
**Cross-deps:** none
**Tags:** launch, happy-path, browser, mode: host

**Goal:** `mc url <case>` opens the Salesforce case URL in Google Chrome.

**Steps:**
1. Run `mc url <case>`
2. Observe Chrome

**Expected:**
- Chrome opens (or focuses if already open)
- URL matches: `https://gss--c.vf.force.com/apex/Case_View?sbstr=<case>`
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-URL-02: Print URL without launching browser

**Pre-requires:** none
**Cross-deps:** none
**Tags:** launch, no-launch, fast, mode: host

**Goal:** `mc url <case> --no-launch` prints the URL to stdout without opening a browser.

**Steps:**
1. Run `mc url <case> --no-launch`
2. Capture stdout

**Expected:**
- Stdout contains exactly: `https://gss--c.vf.force.com/apex/Case_View?sbstr=<case>`
- No browser opened
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-URL-03: URL format is correct Salesforce pattern

**Pre-requires:** none
**Cross-deps:** none
**Tags:** launch, data-integrity, fast, mode: host

**Goal:** The generated URL uses the correct Salesforce domain and query parameter format.

**Steps:**
1. Run `mc url 12345678 --no-launch`
2. Run `mc url 87654321 --no-launch`

**Expected:**
- First: `https://gss--c.vf.force.com/apex/Case_View?sbstr=12345678`
- Second: `https://gss--c.vf.force.com/apex/Case_View?sbstr=87654321`
- Case number appears as `sbstr` query parameter value

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-URL-04: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** launch, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected immediately.

**Steps:**
1. Run `mc url abc`
2. Run `mc url 123`

**Expected:**
- Error: `Invalid case number: '...'. Case number must be exactly 8 digits.`
- Exits 1
- No browser opened

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Launch opens Chrome with correct URL | URL-01 |
| Print URL without launching browser | URL-02 |
| URL format is correct Salesforce pattern | URL-03 |
| Invalid case number rejected | URL-04 |
