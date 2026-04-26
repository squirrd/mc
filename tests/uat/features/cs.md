# UAT Feature: `mc case` (CS)

**Command:** `mc case <case>` / `mc cs <case>`
**Source:** `src/mc/cli/commands/case.py`, `src/mc/terminal/launcher.py`, `src/mc/terminal/attach.py`
**Prefix:** CS

**Pre-conditions (all TCs):**
- `mc` installed via `uv tool install`
- `~/mc/config/config.toml` exists with valid `rh_api_offline_token`
- Podman running
- Terminal (iTerm2 or Terminal.app) available

---

## Story 1 — Terminal Attachment

### TC-CS-01: Open terminal for existing container

**Pre-requires:** none
**Cross-deps:** NEW-01 (container must exist)
**Tags:** case, happy-path, terminal, podman, mode: host

**Goal:** `mc case <case>` launches a new terminal window attached to an existing container.

**Setup:**
```bash
# Ensure container exists
mc new <case>
```

**Steps:**
1. Run `mc case <case>` from an interactive terminal
2. Observe the new terminal window

**Expected:**
- New terminal window opens (iTerm2 or Terminal.app)
- Window title contains case number, customer name, and description
- Shell prompt shows `[MC-<case>]`
- `mc agent init-case` and `mc agent backplane-login` run automatically
- Exits 0 in the original terminal (non-blocking)

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CS-02: Auto-create container when none exists

**Pre-requires:** none
**Cross-deps:** none
**Tags:** case, auto-create, terminal, podman, network, mode: host

**Goal:** `mc case <case>` automatically creates a container if none exists, then opens a terminal.

**Setup:**
```bash
# Ensure no container exists
mc container delete <case> 2>/dev/null || true
```

**Steps:**
1. Run `mc case <case>` (no container exists)
2. Observe output and new terminal window

**Expected:**
- Output: `Creating container...`
- Container created and started
- New terminal window opens with shell prompt `[MC-<case>]`
- Exits 0 in the original terminal

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CS-03: Quick access shorthand `mc 12345678`

**Pre-requires:** none
**Cross-deps:** CS-02 (same behavior as mc case)
**Tags:** case, quick-access, happy-path, mode: host

**Goal:** `mc <case>` (just the case number, no subcommand) behaves identically to `mc case <case>`.

**Steps:**
1. Run `mc <case>` (just the 8-digit number, no subcommand)
2. Observe terminal window

**Expected:**
- Behaves identically to `mc case <case>`
- Terminal window opens with correct title and prompt
- Auto-creates container if needed
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CS-04: Re-running focuses existing window (duplicate prevention)

**Pre-requires:** TC-CS-01 (terminal window must be open)
**Cross-deps:** none
**Tags:** case, duplicate-prevention, window-registry, mode: host

**Goal:** Running `mc case <case>` a second time focuses the existing window instead of opening a new one.

**Steps:**
1. Ensure a terminal window is open for the case (from CS-01)
2. Run `mc case <case>` again

**Expected:**
- Output: `Focused existing terminal for case <case>`
- Existing window is brought to front (not minimized, correct Space)
- No new window created
- Exits 0

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

### TC-CS-05: Invalid case number rejected

**Pre-requires:** none
**Cross-deps:** none
**Tags:** case, validation, negative, fast, mode: host

**Goal:** Non-8-digit case numbers are rejected before any terminal or container operations.

**Steps:**
1. Run `mc case abc`
2. Run `mc case 123`
3. Run `mc 999`

**Expected:**
- Error: `Invalid case number: '...'. Case number must be exactly 8 digits.`
- Exits 1
- No terminal launched, no container created

**Result:**
- [ ] PASS
- [ ] FAIL
- [ ] BLOCKED

**Notes:**

---

## Coverage Map

| Behavior | TC |
|---|---|
| Open terminal for existing container | CS-01 |
| Auto-create container when missing | CS-02 |
| Quick access shorthand `mc <case>` | CS-03 |
| Duplicate prevention — focus existing window | CS-04 |
| Invalid case number rejected | CS-05 |
