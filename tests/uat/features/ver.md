# UAT Feature: `mc version` (VER)

**Command:** `mc version` / `mc ver`
**Source:** `src/mc/version_check.py`, `src/mc/banner.py`, `src/mc/cli/commands/other.py`
**Prefix:** VER

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists

---

## Story 1 — Version Visibility & Update Awareness

### TC-VER-01: Basic version display (offline)

**Pre-requires:** none
**Cross-deps:** none
**Tags:** version, offline, happy-path, fast

**Goal:** `mc version` prints the installed version without a network call and exits in under 1 second.

**Steps:**
1. Disable network (Wi-Fi off or `networksetup -setairportpower en0 off`)
2. Run `mc version`
3. Re-enable network

**Expected:**
- Output matches `mc version <semver>` (e.g., `mc version 2.0.17`)
- No error, no network timeout hang
- Exits 0 in under 1 second

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:** <!-- tester notes — required if FAIL or BLOCKED -->

---

### TC-VER-02: Forced update check writes config

**Pre-requires:** none
**Cross-deps:** none
**Tags:** version, network, config, update-check
**Note:** `--update` flag forces a live GitHub check. If the flag is removed in future, use `mc-update check` (see UCHK-01).

**Goal:** `mc version --update` makes a live GitHub check and persists metadata to config.

**Steps:**
1. Run `mc version --update`
2. Observe stderr output
3. Inspect config: `grep -A5 '\[version\]' ~/mc/config/config.toml`

**Expected:**
- `Checking for updates...` on stderr
- `Version check complete.` on stderr
- Exits 0
- `~/mc/config/config.toml` `[version]` section has `latest_known`, `last_check`, and `etag` populated

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-VER-03: Update banner shown once per day, suppressed on repeat

**Pre-requires:** none
**Cross-deps:** UPIN-01 (used in setup to pin to older version)
**Tags:** version, banner, daily-throttle, stderr

**Goal:** Rich panel banner appears when behind latest, shown at most once per calendar day.

**How the banner works:** `banner.py` fetches the latest version live from GitHub on each run. Two config fields control suppression:
- `last_banner_shown` — banner skipped if it matches today's calendar date
- `last_failed_fetch` — fetch skipped for 1 hour after any network/API failure

**Setup:**
```bash
# Pin to an older version so live GitHub fetch returns something newer
mc-update pin 2.0.15

# Remove suppression fields so banner is not throttled
# Edit ~/mc/config/config.toml [version] section and delete:
#   last_banner_shown
#   last_failed_fetch
```

**Steps:**
1. Run `mc version` interactively
2. Run `mc version` again immediately
3. Run `mc version | cat` (piped)
4. Run `mc --version`

**Expected:**
- First run: Rich panel banner appears on stderr mentioning newer version + `Run: mc-update upgrade`
- Second run: Banner **suppressed** (`last_banner_shown` written to config)
- Piped run (`| cat`): Banner **never appears**
- `mc --version`: Banner **never appears**

**Cleanup:**
```bash
mc-update unpin
```

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-VER-04: Offline degradation — `--update` fails gracefully

**Pre-requires:** none
**Cross-deps:** none
**Tags:** version, offline, negative, network

**Goal:** Network loss on an explicit `--update` call fails clearly without hanging.

**Steps:**
1. Disable network
2. Run `mc version --update`
3. Re-enable network

**Expected:**
- Prints error: `"Error checking for updates: ..."` (or similar)
- Exits 1 (user explicitly requested a check — failure is expected)
- Does **not** hang longer than ~10 seconds

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Version display format correct | VER-01 |
| No network call on plain `version` | VER-01 |
| No hang offline | VER-01 |
| `--update` flag forces live GitHub check | VER-02 |
| Config written after check (`latest_known`, `etag`, `last_check`) | VER-02 |
| Daily banner throttle (shown once, suppressed on repeat) | VER-03 |
| Banner suppressed on `--version` and piped runs | VER-03 |
| Offline `--update` fails clearly, no hang | VER-04 |
