# UAT Test Plan - MC CLI v2.0

**Milestone:** v2.0 Containerization + Distribution
**Version:** 2.0.0
**Date:** 2026-02-01

## Overview

This test plan validates the core v2.0 containerization features and backwards compatibility with v1.0 commands. Focus is on real-world user workflows with actual case data.

## Prerequisites

Before starting:
- [ ] Podman installed and running (`podman --version`)
- [ ] MC container image built (`podman images | grep mc-rhel10`)
- [ ] Salesforce credentials configured (see config path below)
- [ ] At least one active Red Hat support case number available for testing

**Platform-specific paths:**
- **macOS**: `~/Library/Application Support/mc/config.toml`
- **Linux**: `~/.config/mc/config.toml`

**Build container image if needed:**
```bash
# From project root directory
podman build -t mc-rhel10:latest -f container/Containerfile .
```

---

## Test Suite 1: Installation Workflows (Phase 14)

### Test 1.1: Development Workflow
**Objective:** Verify `uv run` workflow for development

```bash
# Run mc via uv
uv run mc --version
uv run mc --help
```

**Expected:**
- Version shows `mc 2.0.0`
- Help displays all commands (attach, case, container, create, etc.)

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 1.2: UAT Installation Workflow
**Objective:** Verify editable install for UAT testing

```bash
# Install in editable mode
uv tool install -e .

# Verify command accessible
which mc
mc --version

# Make a trivial change to verify editable mode
# (Optional - skip if already validated)

# Uninstall
uv tool uninstall mc-cli
```

**Expected:**
- `mc` command available at `~/.local/bin/mc`
- Version shows `mc 2.0.0`
- Uninstall succeeds

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 2: Container Lifecycle (Phase 11)

### Test 2.1: Create Container from Case Number
**Objective:** Create isolated workspace container for a case

```bash
# Use a real 8-digit case number
mc create <case_number>

# Or use quick access pattern
mc <case_number>
```

**Expected:**
- Container created successfully
- Workspace directory created at `~/cases/<customer_name>/<case_number>/`
- Terminal window opens automatically (if TTY available)
- Container shell shows custom prompt: `[MC-<case_number>]`
- Welcome banner displays case metadata (customer, severity, etc.)

**Result:** ⬜ Pass / ⬜ Fail
**Case number used:** ________________

---

### Test 2.2: List Containers
**Objective:** View all case containers

```bash
mc container ls
```

**Expected:**
- Table showing container ID, case number, customer name, status, uptime
- Container from Test 2.1 appears in list
- Status shows "running" or "exited"

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 2.3: Container Operations
**Objective:** Stop, restart, and delete containers

```bash
# Stop the container
mc container stop <case_number>

# Verify stopped
mc container ls

# Restart by accessing case again
mc case <case_number>

# Delete container (preserving workspace)
mc container delete <case_number>

# Verify deletion
mc container ls
```

**Expected:**
- Stop: Container status changes to "exited"
- Restart: Container auto-starts, new terminal opens
- Delete: Container removed from list
- Workspace still exists at `~/cases/<customer_name>/<case_number>/`

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 2.4: Workspace Persistence
**Objective:** Verify workspace data persists across container lifecycle

```bash
# Create container and add test file
mc <case_number>
# Inside container:
echo "test data" > /case/test.txt
exit

# Stop and remove container
mc container stop <case_number>
mc container delete <case_number>

# Recreate container from same case
mc <case_number>
# Inside container:
cat /case/test.txt

# Cleanup
mc container delete <case_number> --remove-workspace
```

**Expected:**
- test.txt file persists after container deletion
- File accessible when container recreated
- `--remove-workspace` flag deletes workspace directory

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 3: Salesforce Integration (Phase 10)

### Test 3.1: Case Metadata Resolution
**Objective:** Verify Salesforce API queries and caching

```bash
# Create container (triggers Salesforce lookup)
mc create <case_number>

# Check workspace path uses customer name
ls -la ~/cases/

# Verify metadata cached (macOS path shown, use ~/.cache/mc/case_metadata.db on Linux)
sqlite3 ~/Library/Caches/mc/case_metadata.db "SELECT case_number, account_name, severity FROM cases WHERE case_number = '<case_number>';"
```

**Expected:**
- Workspace created under customer name directory
- SQLite cache contains case metadata
- Customer name, severity, description populated

**Result:** ⬜ Pass / ⬜ Fail
**Customer name resolved:** ________________

---

### Test 3.2: Cache Expiration and Refresh
**Objective:** Verify cache TTL and refresh behavior

```bash
# Set cache path based on platform
# macOS:
CACHE_DB=~/Library/Caches/mc/case_metadata.db
# Linux:
# CACHE_DB=~/.cache/mc/case_metadata.db

# Check cache timestamp
sqlite3 "$CACHE_DB" "SELECT case_number, datetime(cached_at, 'unixepoch', 'localtime') FROM cases WHERE case_number = '<case_number>';"

# Wait 6 minutes (beyond 5-minute TTL) or manually expire:
sqlite3 "$CACHE_DB" "UPDATE cases SET cached_at = cached_at - 400 WHERE case_number = '<case_number>';"

# Access case again (should trigger refresh)
mc case <case_number>

# Verify timestamp updated
sqlite3 "$CACHE_DB" "SELECT case_number, datetime(cached_at, 'unixepoch', 'localtime') FROM cases WHERE case_number = '<case_number>';"
```

**Expected:**
- Timestamp updates after TTL expiration
- No errors during refresh
- Case still accessible

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 4: Terminal Automation (Phase 12)

### Test 4.1: Auto-Attach Workflow
**Objective:** Verify terminal window launches automatically

```bash
# From regular terminal (not piped)
mc case <case_number>
```

**Expected:**
- New terminal window opens
- Inside container shell with custom prompt `[MC-<case_number>]`
- Welcome banner shows case metadata
- Original terminal returns to prompt immediately
- Working directory is `/case`

**Result:** ⬜ Pass / ⬜ Fail
**Terminal detected:** ⬜ iTerm2 / ⬜ Terminal.app / ⬜ gnome-terminal / ⬜ Other: ________

---

### Test 4.2: TTY Detection
**Objective:** Verify terminal launch disabled when output piped

```bash
# Pipe output (should NOT launch terminal)
mc case <case_number> | cat

# Redirect output (should NOT launch terminal)
mc case <case_number> > /dev/null
```

**Expected:**
- No terminal window opens
- Command completes without error
- Suitable for scripting/automation

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 4.3: Custom Shell Environment
**Objective:** Verify bashrc customization and helper functions

```bash
# Inside container
mc case <case_number>

# Test helper commands
case-info          # Should display case metadata
pwd               # Should be /case
echo $CASE_NUMBER # Should show case number
```

**Expected:**
- `case-info` function available
- Environment variables set (CASE_NUMBER, CUSTOMER_NAME, WORKSPACE_PATH)
- Prompt shows `[MC-<case_number>]`

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 5: Container Image (Phase 13)

### Test 5.1: Runtime Mode Detection
**Objective:** Verify MC CLI detects container environment

```bash
# Inside container
mc case <case_number>

# Run mc command (should detect agent mode)
mc --version
```

**Expected:**
- MC CLI accessible inside container
- Commands run without errors
- No attempts to spawn nested containers

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 5.2: Essential Tools Available
**Objective:** Verify container has required tooling

```bash
# Inside container
which vim
which curl
which openssl
which wget
python3 --version
```

**Expected:**
- All tools present
- Python 3.12+ available
- No errors

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 6: Backwards Compatibility (Phase 13)

### Test 6.1: Legacy v1.0 Commands
**Objective:** Verify v1.0 commands still work unchanged

```bash
# Create workspace (v1.0 style - non-containerized)
mc create <case_number> --no-container  # If flag exists, otherwise just verify create works

# Check workspace
mc check <case_number>

# Download attachments
mc attach <case_number>

# View case comments
mc case-comments <case_number>

# Open Salesforce case
mc go <case_number> --print
```

**Expected:**
- All v1.0 commands execute without errors
- Workspace structure unchanged
- Attachments download to workspace
- Comments display correctly
- Case URL printed

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 6.2: LDAP Search
**Objective:** Verify LDAP integration unchanged

```bash
mc ls <username>
```

**Expected:**
- User information displayed
- No errors or deprecation warnings

**Result:** ⬜ Pass / ⬜ Fail
**Username tested:** ________________

---

## Test Suite 7: Error Handling & Edge Cases

### Test 7.1: Invalid Case Number
**Objective:** Verify graceful error handling

```bash
# Invalid format
mc case 12345

# Non-existent case
mc case 99999999
```

**Expected:**
- Clear error message for invalid format
- Salesforce API error for non-existent case
- No crashes or stack traces

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 7.2: Podman Not Running
**Objective:** Verify helpful error when Podman unavailable

```bash
# Stop Podman (macOS)
podman machine stop

# Try to create container
mc case <case_number>

# Restart Podman
podman machine start
```

**Expected:**
- Clear error message: "Podman not available"
- Suggests running `podman machine start` (macOS) or installing Podman
- No confusing stack traces

**Result:** ⬜ Pass / ⬜ Fail

---

### Test 7.3: Salesforce Auth Failure
**Objective:** Verify handling of invalid Salesforce credentials

```bash
# Set config path based on platform
# macOS:
CONFIG_PATH=~/Library/Application\ Support/mc/config.toml
# Linux:
# CONFIG_PATH=~/.config/mc/config.toml

# Temporarily rename config
mv "$CONFIG_PATH" "${CONFIG_PATH}.bak"

# Try to access case
mc case <case_number>

# Restore config
mv "${CONFIG_PATH}.bak" "$CONFIG_PATH"
```

**Expected:**
- Clear error message about missing/invalid credentials
- Suggests checking config file
- No exposed passwords or tokens

**Result:** ⬜ Pass / ⬜ Fail

---

## Test Suite 8: End-to-End Workflow

### Test 8.1: Complete Case Workflow
**Objective:** Validate full user journey

```bash
# 1. Install MC CLI
uv tool install -e .

# 2. Access case (creates container, opens terminal)
mc <case_number>

# 3. Inside container: download attachments
mc attach <case_number>

# 4. Work with case files
ls -la /case/attachments/

# 5. Exit container
exit

# 6. Reattach later
mc case <case_number>

# 7. View other cases
mc container ls

# 8. Cleanup when done
mc container delete <case_number>
```

**Expected:**
- Smooth workflow with no manual intervention
- Container persists between sessions
- Attachments accessible inside container
- All operations succeed

**Result:** ⬜ Pass / ⬜ Fail

---

## Summary

**Total Tests:** 21
**Passed:** ____
**Failed:** ____
**Blocked:** ____

### Critical Issues Found

_(List any blocking issues discovered during testing)_

1.
2.
3.

### Notes

_(Any observations, suggestions, or non-critical issues)_

---

**Tester:** ________________
**Date Completed:** ________________
**Ready for Audit:** ⬜ Yes / ⬜ No (resolve critical issues first)
