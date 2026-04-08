# UAT Feature: `mc-update` (UPD)

**Command:** `mc-update`
**Source:** `src/mc/update.py`, `src/mc/version_check.py`
**Subcommand prefixes:** `check`→UCHK · `upgrade`→UUPG · `pin`→UPIN · `unpin`→UUPN

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists
- Network available (unless test specifies offline)

---

## Story 1 — Version Status Check

### TC-UCHK-01: Check displays all version fields

**Pre-requires:** none
**Cross-deps:** none
**Tags:** check, happy-path, table, network

**Goal:** `mc-update check` shows all relevant version fields in a readable table.

**Steps:**
1. Run `mc-update check`

**Expected:**
```
Version status:
  Installed   : <current>
  Environment : prod
  Latest      : <version from GitHub>
  Pin         : none
  Update      : up to date  (or "available" if behind)
```
- Exits 0
- `Latest` field populated (not `unavailable`)
- `Environment` shows `prod` (not `dev` or `uat`)

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-UCHK-02: Offline — check degrades gracefully

**Pre-requires:** none
**Cross-deps:** none
**Tags:** check, offline, negative, network

**Goal:** Network loss does not crash `mc-update check` or produce a hang.

**Steps:**
1. Disable network
2. Run `mc-update check`
3. Re-enable network

**Expected:**
- `Latest: unavailable (network error)` shown
- Installed, Pin, Environment fields still shown correctly
- Exits 0 (check itself did not fail — network fetch failed gracefully)
- Does not hang longer than ~10 seconds

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 2 — Full Upgrade Workflow

### TC-UUPG-01: Full upgrade end-to-end

**Pre-requires:** none
**Cross-deps:** none
**Tags:** upgrade, happy-path, network, streaming

**Goal:** `mc-update upgrade` upgrades the tool, streams output live, and verifies the binary.

**Pre-condition:** No pin active — confirm with `mc-update check` showing `Pin: none`.

**Steps:**
1. Run `mc-update upgrade`
2. Watch streaming output
3. After completion, run `mc version`

**Expected:**
- `uv tool install --reinstall git+...` output streams live (not captured/buffered)
- On success: `Upgrade complete.`
- `mc version` shows the newly installed version
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 3 — Pin Management

### TC-UPIN-01: Pin to a specific valid version

**Pre-requires:** none
**Cross-deps:** none
**Tags:** pin, happy-path, config

**Goal:** Pin successfully installs and locks to a known released version.

**Steps:**
1. Run `mc-update pin 2.0.15`
2. Run `mc version`
3. Run `mc-update check`
4. Inspect config: `grep pinned_mc ~/mc/config/config.toml`

**Expected:**
- `Pinned to 2.0.15. Run mc-update unpin to remove.`
- `mc version` shows `2.0.15`
- `mc-update check` shows `Pin: 2.0.15` and `Update: pinned (run mc-update unpin to upgrade)`
- Config has `pinned_mc = "2.0.15"` under `[version]`

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-UPIN-02: Upgrade blocked by active pin

**Pre-requires:** TC-UPIN-01 (pin must be active)
**Cross-deps:** none
**Tags:** pin, upgrade, negative, blocked

**Goal:** `mc-update upgrade` is blocked when a pin is active.

**Steps:**
1. Run `mc-update upgrade`

**Expected:**
- Exits 1
- Error mentions the pin and instructs user to run `mc-update unpin`
- No installation attempted

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-UPIN-03: Invalid pin format rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** pin, negative, validation, fast

**Goal:** Non-semver input fails fast with a clear error before any network call.

**Steps:**
1. Run `mc-update pin not-a-version`

**Expected:**
- "Invalid version format" error, exits 1
- No network call made
- Config untouched

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-UPIN-04: Non-existent GitHub release rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** pin, negative, network, 404

**Goal:** A valid semver that does not exist on GitHub is caught with a clear error.

**Steps:**
1. Run `mc-update pin 99.99.99`

**Expected:**
- GitHub returns 404 → `"Version 99.99.99 not found on GitHub releases."`, exits 1
- Config untouched

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Story 4 — Unpin Workflow

### TC-UUPN-01: Unpin and upgrade

**Pre-requires:** TC-UPIN-01 (pin must be active)
**Cross-deps:** none
**Tags:** unpin, upgrade, happy-path

**Goal:** Removing a pin re-enables upgrades.

**Steps:**
1. Run `mc-update unpin`
2. Run `mc-update check`
3. Run `mc-update upgrade`

**Expected:**
- `unpin`: `Pin removed.` → exits 0
- `check`: `Pin: none`
- `upgrade`: Runs cleanly, exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-UUPN-02: Unpin when no pin exists is idempotent

**Pre-requires:** none
**Cross-deps:** none
**Tags:** unpin, idempotent, negative

**Goal:** `mc-update unpin` is safe to run when nothing is pinned.

**Setup:** Confirm no pin: `mc-update check` shows `Pin: none`.

**Steps:**
1. Run `mc-update unpin`

**Expected:**
- `No pin active.`
- Exits 0
- Config unchanged

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| `check` table — all fields present | UCHK-01 |
| `check` shows `prod` environment | UCHK-01 |
| Offline `check` degrades gracefully (no hang) | UCHK-02 |
| Full upgrade streams output live | UUPG-01 |
| Upgrade verifies binary post-install | UUPG-01 |
| Pin installs specific version | UPIN-01 |
| Config persists pin (`pinned_mc`) | UPIN-01 |
| `check` reflects active pin | UPIN-01 |
| Upgrade blocked by active pin | UPIN-02 |
| Invalid semver format rejected without network call | UPIN-03 |
| Non-existent GitHub release rejected (404) | UPIN-04 |
| Unpin re-enables upgrade | UUPN-01 |
| `unpin` is idempotent when no pin exists | UUPN-02 |
