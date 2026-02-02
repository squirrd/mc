# UAT Test Plan - Batches A, B, C, E.1

**Test Date:** _________________
**Tester:** _________________
**MC Version:** 2.0.1+
**Platform:** macOS / Linux (circle one)

---

## Test 1: Consolidated Config Directory

**Feature:** Config directory consolidated under `~/mc/config/`
**Related Todo:** Consolidate config directory under ~/mc workspace

### Prerequisites
- MC CLI installed via `uv tool install`
- No existing `~/mc/` directory (for fresh install test)

### Test Steps

#### 1.1 Fresh Install - Verify Directory Structure
1. Delete existing MC directories (if present):
   ```bash
   rm -rf ~/mc
   rm -rf ~/Library/Application\ Support/mc  # macOS only
   rm -rf ~/.config/mc  # Linux only
   ```
2. Run any MC command to trigger initialization:
   ```bash
   mc --version
   ```
3. Verify directory structure:
   ```bash
   ls -la ~/mc/
   ```

**Expected Result:**
```
~/mc/
├── config/
│   ├── config.toml
│   └── cache/
│       └── case_metadata.db
├── state/
│   └── containers.db
└── cases/
```

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 1.2 Auto-Migration from Old Locations
1. Create old-style config in platform-specific location:
   - **macOS:** `mkdir -p ~/Library/Application\ Support/mc && echo '[api]\nrh_api_offline_token = "test_token"' > ~/Library/Application\ Support/mc/config.toml`
   - **Linux:** `mkdir -p ~/.config/mc && echo '[api]\nrh_api_offline_token = "test_token"' > ~/.config/mc/config.toml`
2. Run MC command:
   ```bash
   mc --version
   ```
3. Verify auto-migration:
   ```bash
   cat ~/mc/config/config.toml | grep test_token
   ls ~/mc/config/
   ```

**Expected Result:**
- Config migrated to `~/mc/config/config.toml`
- Token preserved: `rh_api_offline_token = "test_token"`
- Cache directory exists: `~/mc/config/cache/`

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test 2: Workspace Path Structure

**Feature:** Structured workspace paths `cases/<customer>/<case>-<description>`
**Related Todo:** Fix workspace path structure to use cases/<customer>/<case>-<description>

### Prerequisites
- Valid Red Hat API offline token configured
- Valid case number (e.g., 12345678)
- Podman installed and running

### Test Steps

#### 2.1 New Container Creation - Workspace Path Format
1. Create container for a case:
   ```bash
   mc case 04347611
   ```
2. Verify workspace path structure:
   ```bash
   ls -la ~/mc/cases/
   ```

**Expected Result:**
- Directory structure: `~/mc/cases/<customer>/<case>-<description>/`
- Example: `~/mc/cases/IBM_Corpora_Limited/04347611-Server_Down_Critica_Pr/`
- Customer name formatted (spaces → underscores, special chars removed)
- Description formatted and truncated to ~22 chars max

**Actual Result:** ☐ Pass ☐ Fail
**Actual Path:**
**Notes:**

---

#### 2.2 Workspace Path in Container Mount
1. Inside the container terminal, verify mount point:
   ```bash
   # In container
   pwd
   ls -la /case
   ```

**Expected Result:**
- Working directory: `/case`
- Contents match host workspace path
- Files created in container appear in `~/mc/cases/<customer>/<case>-<description>/`

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test 3: Container Image Detection

**Feature:** Improved error messaging for missing images
**Related Todo:** Fix container create image detection failure

### Prerequisites
- Podman installed
- No `mc-rhel10:latest` image present locally

### Test Steps

#### 3.1 Missing Image - Clear Error Message
1. Remove local image if present:
   ```bash
   podman rmi mc-rhel10:latest 2>/dev/null || true
   podman rmi quay.io/rhn_support_dsquirre/mc-container:latest 2>/dev/null || true
   ```
2. Attempt to create container with Podman running:
   ```bash
   mc case 12345678
   ```

**Expected Result:**
- Error message indicates image pull attempted from `quay.io/rhn_support_dsquirre/mc-container:latest`
- Provides fallback instructions for local build
- Does NOT confuse with Podman connection errors

**Actual Result:** ☐ Pass ☐ Fail
**Error Message:**
**Notes:**

---

#### 3.2 Podman Connection Error - Specific Messaging
1. Stop Podman:
   - **macOS:** `podman machine stop`
   - **Linux:** `sudo systemctl stop podman` (if applicable)
2. Attempt to create container:
   ```bash
   mc case 12345678
   ```
3. Restart Podman:
   - **macOS:** `podman machine start`
   - **Linux:** `sudo systemctl start podman`

**Expected Result:**
- Error clearly states Podman connection failure
- Suggests checking Podman is running and accessible
- Does NOT suggest building image

**Actual Result:** ☐ Pass ☐ Fail
**Error Message:**
**Notes:**

---

## Test 4: Quay.io Auto-Pull

**Feature:** Automatic image pull from quay.io registry
**Related Todo:** Use pre-built container images from quay.io instead of local builds

### Prerequisites
- Podman running
- Internet connection
- No local `mc-rhel10:latest` image

### Test Steps

#### 4.1 First-Time Container Creation - Auto Pull
1. Remove local image:
   ```bash
   podman rmi mc-rhel10:latest 2>/dev/null || true
   ```
2. Create container:
   ```bash
   mc case 04347611
   ```
3. Observe output

**Expected Result:**
- Message: `Pulling container image from quay.io/rhn_support_dsquirre/mc-container:latest...`
- Message: `Successfully pulled image from registry`
- Container created and terminal launched
- Image tagged as `mc-rhel10:latest` locally

**Actual Result:** ☐ Pass ☐ Fail
**Pull Duration:** _____ seconds
**Notes:**

---

#### 4.2 Second Container Creation - Use Local Cache
1. Create another container:
   ```bash
   mc case 87654321
   ```

**Expected Result:**
- No pull message (uses local cached image)
- Container created immediately
- Much faster than first creation

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 4.3 Verify Image Details
1. Check image exists:
   ```bash
   podman images | grep mc-rhel10
   ```

**Expected Result:**
- Image `mc-rhel10:latest` present
- Size approximately 549 MB
- Tagged correctly

**Actual Result:** ☐ Pass ☐ Fail
**Image Size:** _____ MB
**Notes:**

---

## Test 5: Duplicate Terminal Prevention

**Feature:** Focus existing terminal instead of launching duplicates
**Related Todo:** Prevent duplicate terminal launches and focus existing terminals

### Prerequisites
- macOS (iTerm2 or Terminal.app)
- Valid case with container already created

### Test Steps

#### 5.1 Initial Terminal Launch
1. Launch terminal for case:
   ```bash
   mc case 04347611
   ```
2. Observe: New terminal window opens with title `04347611 - <Customer> - <Description>`

**Expected Result:**
- New terminal window opened
- Window title format: `<case> - <customer> - <description>`
- Shell prompt: `[MC-04347611] /case$`

**Actual Result:** ☐ Pass ☐ Fail
**Window Title:**
**Notes:**

---

#### 5.2 Duplicate Launch Detection
1. Return to host terminal (where you ran `mc case`)
2. Run same command again:
   ```bash
   mc case 04347611
   ```

**Expected Result:**
- No new terminal window opened
- Existing terminal window brought to front/focused
- Message: `Focused existing terminal for case 04347611`

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 5.3 Multiple Different Cases
1. Launch terminal for different case:
   ```bash
   mc case 87654321
   ```
2. Verify both terminals exist separately

**Expected Result:**
- New terminal opened for case 87654321
- Both terminals remain separate
- Each can be focused independently by running `mc case <number>`

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test 6: Auto-Close Terminal

**Feature:** Terminal auto-closes when shell exits
**Related Todo:** Auto-close terminal when shell exits

### Prerequisites
- Container created and terminal launched

### Test Steps

#### 6.1 Exit Shell - Terminal Closes
1. Launch container terminal:
   ```bash
   mc case 04347611
   ```
2. In container terminal, exit shell:
   ```bash
   exit
   ```
   OR press `Ctrl+D`

**Expected Result:**
- Terminal window closes immediately after shell exits
- No orphaned terminal windows left behind

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 6.2 Container Crash - Terminal Closes
1. Launch container terminal:
   ```bash
   mc case 04347611
   ```
2. Kill the shell process forcefully from host:
   ```bash
   podman exec mc-04347611 pkill bash
   ```

**Expected Result:**
- Terminal window closes when shell dies
- No zombie terminal processes

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test 7: Container List Output

**Feature:** Show case description instead of workspace path
**Related Todo:** Improve container list output - replace workspace path with description

### Prerequisites
- Multiple containers created with new workspace path structure

### Test Steps

#### 7.1 List Containers - Description Column
1. Create 2-3 containers:
   ```bash
   mc case 04347611
   mc case 87654321
   ```
2. List containers:
   ```bash
   mc container list
   ```

**Expected Result:**
- Header shows `DESCRIPTION` column (not `WORKSPACE PATH`)
- Descriptions extracted from workspace paths
- Underscores converted to spaces
- Long descriptions truncated with `...`
- Format:
  ```
  CASE         STATUS     CUSTOMER             DESCRIPTION                              CREATED
  ------------------------------------------------------------------------------------------------------
  04347611     running    IBM Corpora Limited  Server Down Critica Pr                   2026-02-02 12:23:36
  87654321     stopped    ACME Corp            Network Issue Prod Env                   2026-02-02 11:15:22
  ```

**Actual Result:** ☐ Pass ☐ Fail
**Screenshot/Output:**
**Notes:**

---

#### 7.2 Legacy Containers - Fallback to N/A
1. If any old containers exist (with simple paths like `~/mc/12345678`), list them:
   ```bash
   mc container list
   ```

**Expected Result:**
- Legacy containers show `N/A` in DESCRIPTION column
- No crashes or errors
- Graceful degradation

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (no legacy containers)
**Notes:**

---

## Test 8: Test Suite Fixes

**Feature:** Import errors resolved, all tests collect successfully
**Related Todo:** Fix test dependencies and imports - 2 import errors

### Prerequisites
- MC source code checked out
- uv installed
- Development environment setup

### Test Steps

#### 8.1 Test Collection - No Import Errors
1. Navigate to project directory
2. Run test collection:
   ```bash
   uv run pytest --collect-only
   ```

**Expected Result:**
- All tests collected successfully
- Output shows: `collected 513 items`
- No `ModuleNotFoundError` or `ImportError`
- No import failures for:
  - `pytest_console_scripts` (test_entry_points.py)
  - `CaseMetadataCache` (test_cache.py)

**Actual Result:** ☐ Pass ☐ Fail
**Tests Collected:** _____ items
**Notes:**

---

#### 8.2 Cache Tests - All Pass
1. Run cache test suite:
   ```bash
   uv run pytest tests/unit/test_cache.py -v --no-cov
   ```

**Expected Result:**
- All 13 tests pass:
  - test_cache_miss_no_entry
  - test_cache_hit_within_ttl
  - test_cache_expired
  - test_cache_update_replaces_existing
  - test_list_all_cached_cases
  - test_delete_cache_entry
  - test_get_cached_age_minutes_no_cache
  - test_get_cached_age_minutes_with_cache
  - test_get_case_metadata_cache_hit
  - test_get_case_metadata_cache_miss
  - test_get_case_metadata_cache_expired
  - test_get_case_metadata_force_refresh
  - test_concurrent_cache_access
- Output: `13 passed`

**Actual Result:** ☐ Pass ☐ Fail
**Passed:** _____ / 13
**Notes:**

---

#### 8.3 Entry Point Tests - Collect Successfully
1. Run entry point test collection:
   ```bash
   uv run pytest tests/integration/test_entry_points.py --collect-only
   ```

**Expected Result:**
- 3 tests collected:
  - test_mc_version
  - test_mc_help
  - test_mc_invalid_command
- No import errors for `pytest_console_scripts`

**Actual Result:** ☐ Pass ☐ Fail
**Tests Collected:** _____ items
**Notes:**

---

## Integration Test: End-to-End Workflow

**Test complete workflow combining all features**

### Test Steps

1. **Clean slate:**
   ```bash
   rm -rf ~/mc
   mc container delete 04347611 2>/dev/null || true
   podman rmi mc-rhel10:latest 2>/dev/null || true
   ```

2. **First case creation (auto-pull, structured path):**
   ```bash
   mc case 04347611
   ```
   - Verify: Image pulled from quay.io
   - Verify: Terminal opens with title `04347611 - <customer> - <description>`
   - Verify: Workspace created at `~/mc/cases/<customer>/04347611-<description>/`

3. **Create file in container:**
   ```bash
   # In container terminal
   echo "Test note" > test.txt
   cat test.txt
   ```
   - Verify: File visible in container

4. **Exit and verify auto-close:**
   ```bash
   # In container terminal
   exit
   ```
   - Verify: Terminal closes automatically

5. **Relaunch same case (duplicate prevention):**
   ```bash
   mc case 04347611
   ```
   - Verify: Terminal reopens (or focuses if still open)
   - Verify: File persists: `cat /case/test.txt`

6. **List containers (description shown):**
   ```bash
   mc container list
   ```
   - Verify: Description column shows case description
   - Verify: No workspace path shown

7. **Second case creation (local image, no pull):**
   ```bash
   mc case 87654321
   ```
   - Verify: No pull message (uses cached image)
   - Verify: New workspace created at `~/mc/cases/<customer>/87654321-<description>/`

8. **Final verification:**
   ```bash
   mc container list
   ls -R ~/mc/cases/
   ```

**Overall Integration Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test Summary

| Test | Feature | Result | Notes |
|------|---------|--------|-------|
| 1.1 | Fresh install directory structure | ☐ Pass ☐ Fail | |
| 1.2 | Auto-migration from old locations | ☐ Pass ☐ Fail | |
| 2.1 | Workspace path format | ☐ Pass ☐ Fail | |
| 2.2 | Container mount verification | ☐ Pass ☐ Fail | |
| 3.1 | Missing image error message | ☐ Pass ☐ Fail | |
| 3.2 | Podman connection error message | ☐ Pass ☐ Fail | |
| 4.1 | Auto-pull from quay.io | ☐ Pass ☐ Fail | |
| 4.2 | Second container uses cache | ☐ Pass ☐ Fail | |
| 4.3 | Image details verification | ☐ Pass ☐ Fail | |
| 5.1 | Initial terminal launch | ☐ Pass ☐ Fail | |
| 5.2 | Duplicate launch detection | ☐ Pass ☐ Fail | |
| 5.3 | Multiple different cases | ☐ Pass ☐ Fail | |
| 6.1 | Exit shell closes terminal | ☐ Pass ☐ Fail | |
| 6.2 | Container crash closes terminal | ☐ Pass ☐ Fail | |
| 7.1 | Description column shown | ☐ Pass ☐ Fail | |
| 7.2 | Legacy containers fallback | ☐ Pass ☐ Fail | |
| 8.1 | All tests collect (513 items) | ☐ Pass ☐ Fail | |
| 8.2 | Cache tests pass (13/13) | ☐ Pass ☐ Fail | |
| 8.3 | Entry point tests collect (3 items) | ☐ Pass ☐ Fail | |
| E2E | Integration workflow | ☐ Pass ☐ Fail | |

**Total Pass Rate:** _____ / 20 tests

---

## Issues Found

| Test # | Issue Description | Severity | Status |
|--------|------------------|----------|--------|
| | | ☐ Critical ☐ Major ☐ Minor | ☐ Open ☐ Fixed |
| | | ☐ Critical ☐ Major ☐ Minor | ☐ Open ☐ Fixed |
| | | ☐ Critical ☐ Major ☐ Minor | ☐ Open ☐ Fixed |

---

## Sign-off

**Tester Signature:** _________________
**Date:** _________________
**Overall Status:** ☐ Approved ☐ Approved with Minor Issues ☐ Rejected

**Notes:**
