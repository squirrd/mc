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

#### 1.1 Fresh Install - Lazy Initialization
1. Delete existing MC directories (if present):
   ```bash
   ls -lad ~/.mc*; echo; ls -lad ~/mc*; echo; ls -lad ~/Library/Application\ Support/mc*

   mv ~/.mc ~/.mc.$(date '+%y%m%d-%H%M')
   mv ~/mc ~/mc.$(date '+%y%m%d-%H%M')

   # macOS only
   mv ~/Library/Application\ Support/mc ~/Library/Application\ Support/mc.$(date '+%y%m%d-%H%M')
   
   # Linux only
   mv ~/.config/mc ~/.config/mc.$(date '+%y%m%d-%H%M')
   mv ~/.local/share/mc ~/.config/mc.$(date '+%y%m%d-%H%M')

   ---

   rm -rf ~/mc
   rm -rf ~/Library/Application\ Support/mc  # macOS only
   rm -rf ~/.config/mc  # Linux only
   rm -rf ~/.local/share/mc  # Linux only
   ```
2. Verify `--version` creates NO directories (fast, no side effects):
   ```bash
   mc --version
   ls ~/mc 2>&1
   ```
   - **Expected:** `ls: ~/mc: No such file or directory` (or empty)

3. Create first container to trigger full initialization:
   ```bash
   mc case 04347611
   ```

4. Verify complete directory structure created:
   ```bash
   ls -R ~/mc/
   ```

**Expected Result:**
- `mc --version` creates no directories (instant, no side effects)
- `mc case <number>` creates complete structure on first use:
  ```
  ~/mc/
  ├── config/
  │   ├── config.toml
  │   └── cache/
  │       └── case_metadata.db
  ├── state/
  │   └── containers.db
  └── cases/
      └── <Customer_Name>/
          └── <case>-<description>/
  ```
- Directories created only when needed (lazy initialization)

**Actual Result:** ☒ Fail → ☑ Automated

**Automated Tests:**
1. `test_fresh_install_missing_config_base_directory_regression()` in `tests/integration/test_case_terminal.py`
   - **Created:** 2026-02-02
   - **Status:** Failing (reproduces bug - will pass once bug is fixed)
   - **Bug:** "Podman error: 'base_directory'" when config file missing base_directory key

2. `test_fresh_install_no_old_directories_created_regression()` in `tests/integration/test_case_terminal.py`
   - **Created:** 2026-02-04
   - **Status:** ✅ Passing (bug fixed!)
   - **Fixed:** 2026-02-04
   - **Bug:** Directories created in old platformdirs locations during fresh install
   - **Details:** `~/Library/Application Support/mc/bashrc` created on macOS (should be `~/mc/config/bashrc`)
   - **Root cause:** `src/mc/terminal/shell.py:84` used `platformdirs.user_data_dir()` instead of consolidated location
   - **Fix applied:** Updated `get_bashrc_path()` to use `~/mc/config/bashrc/` instead

---

#### 1.2 Auto-Migration from Old Locations
1. Clean slate:
   ```bash
   ls -lad ~/.mc*; echo; ls -lad ~/mc*; echo; ls -lad ~/Library/Application\ Support/mc*

   mv ~/.mc ~/.mc.$(date '+%y%m%d-%H%M')
   mv ~/mc ~/mc.$(date '+%y%m%d-%H%M')

   # macOS only
   mv ~/Library/Application\ Support/mc ~/Library/Application\ Support/mc.$(date '+%y%m%d-%H%M')
   
   # Linux only
   mv ~/.config/mc ~/.config/mc.$(date '+%y%m%d-%H%M')
   mv ~/.local/share/mc ~/.config/mc.$(date '+%y%m%d-%H%M')

   ---
   XXXX

   rm -rf ~/mc
   ```

2. Create old-style config in platform-specific location:
   - **macOS:**
     ```bash
     cp -pr /Users/dsquirre/Library/Application\ Support/mc.20260202/ /Users/dsquirre/Library/Application\ Support/mc

     ----
     XXXX

     mkdir -p ~/Library/Application\ Support/mc
     cat > ~/Library/Application\ Support/mc/config.toml <<EOF
     [api]
     rh_api_offline_token = "test_token_12345"

     base_directory = "$HOME/mc"
     EOF
     ```
   - **Linux:**
     ```bash
     mkdir -p ~/.config/mc
     cat > ~/.config/mc/config.toml <<EOF
     [api]
     rh_api_offline_token = "test_token_12345"

     base_directory = "$HOME/mc"
     EOF
     ```

3. Create old-style state database in platformdirs location (if exists):
   - **macOS:**
     ```bash
     ----
     XXXX
     mkdir -p ~/Library/Application\ Support/mc
     touch ~/Library/Application\ Support/mc/containers.db
     ```
   - **Linux:**
     ```bash
     ----
     XXXX
     mkdir -p ~/.local/share/mc
     touch ~/.local/share/mc/containers.db
     ```

4. Run a command that needs state database (triggers migration):
   ```bash
   mc container list
   ```

5. Verify auto-migration of config and state:
   ```bash
   # Check config migrated
   cat ~/mc/config/config.toml | grep test_token_12345

   # Check state directory exists
   ls -la ~/mc/state/

   # Verify migration message in output
   echo "Look for migration messages in output above"
   ```

**Expected Result:**
- Config migrated to `~/mc/config/config.toml`
- Token preserved: `rh_api_offline_token = "test_token_12345"`
- Base directory preserved: `base_directory = "/Users/username/mc"` (or `/home/username/mc` on Linux)
- State directory created: `~/mc/state/containers.db`
- Migration messages displayed: "Migrated config from ..."
- No errors or warnings

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
1. Inside the container terminal (from test 2.1), verify mount point:
   ```bash
   # In container terminal
   pwd
   ls -la /case
   ```

2. Create a test file in the container:
   ```bash
   # In container terminal
   echo "Test from container" > /case/test_file.txt
   cat /case/test_file.txt
   ```

3. From host terminal (in a different window), verify file appears on host:
   ```bash
   # In host terminal
   ls ~/mc/cases/*/04347611-*/
   cat ~/mc/cases/*/04347611-*/test_file.txt
   ```

**Expected Result:**
- Container working directory: `/case`
- Container `/case` directory is empty initially (or contains any existing files)
- File created in container immediately visible on host
- File contents match: "Test from container"
- Bidirectional sync works (files created on host visible in container)

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

## Test 3: Container Image Auto-Pull from Quay.io

**Feature:** Automatic image pull and tag from quay.io registry
**Related Todo:** Use pre-built container images from quay.io instead of local builds

### Prerequisites
- Podman running
- Internet connection
- No local `mc-rhel10:latest` image present

### Test Steps

#### 3.1 First-Time Container Creation - Auto Pull and Tag
1. Remove local images if present:
   ```bash
   podman rmi mc-rhel10:latest 2>/dev/null || true
   podman rmi quay.io/rhn_support_dsquirre/mc-container:latest 2>/dev/null || true
   ```
2. Create container (triggers auto-pull):
   ```bash
   mc case 04347611
   ```
3. Observe output for pull messages

**Expected Result:**
- Message: `Pulling container image from quay.io/rhn_support_dsquirre/mc-container:latest...`
- Message: `Successfully pulled image from registry`
- Image automatically pulled from `quay.io/rhn_support_dsquirre/mc-container:latest`
- Image tagged as `mc-rhel10:latest` locally
- Container created successfully
- Terminal launched

**Actual Result:** ☒ Fail → ☑ Automated

**Automated Test:** `test_image_pull_and_tag_regression()` in `tests/integration/test_container_image.py`
**Created:** 2026-02-04
**Status:** Failing (reproduces bug - will pass once bug is fixed)
**Bug:** Image pull succeeds but tagging fails with `Image.tag() missing 1 required positional argument: 'tag'`
**Root cause:** `src/mc/container/manager.py:201` calls `pulled_image.tag(image_name)` but should split image_name into repository and tag
**Fix needed:** Split `"mc-rhel10:latest"` into `("mc-rhel10", "latest")` before calling `tag(repo, tag)`

**Notes:** The image is successfully pulled from quay.io (visible in `podman images` as `quay.io/rhn_support_dsquirre/mc-container:latest`) but the code fails when trying to tag it with the local name `mc-rhel10:latest`. Once fixed, this test validates the complete first-time container creation workflow with auto-pull.

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

## Test 4: Image Caching and Performance

**Feature:** Local image caching after first pull
**Related Todo:** Verify image caching works correctly after auto-pull

**Note:** Test 3.1 validates the initial auto-pull. This test validates caching behavior.

### Prerequisites
- Podman running
- `mc-rhel10:latest` image already pulled (run Test 3.1 first)

### Test Steps

#### 4.1 Second Container Creation - Use Local Cache
1. Ensure image is already cached from Test 3.1:
   ```bash
   podman images | grep mc-rhel10
   ```
2. Create another container:
   ```bash
   mc case 87654321
   ```
3. Observe creation time

**Expected Result:**
- No pull message (uses local cached image)
- Container created immediately
- Much faster than first creation (< 5 seconds vs 30-60 seconds for pull)

**Actual Result:** ☐ Pass ☐ Fail
**Creation Duration:** _____ seconds
**Notes:**

---

#### 4.2 Verify Image Details and Tagging
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
2. Observe: New terminal window opens with title `04347611:<Customer>:<Description>:/case`

**Expected Result:**
- New terminal window opened
- Window title format: `<case>:<customer>:<description>:/<vm-path>`
- Shell prompt: `[MC-04347611] /case$`

**Actual Result:** ☒ Fail → ☑ Automated

**Automated Test:** `test_terminal_title_format_regression()` in `tests/integration/test_case_terminal.py`
**Created:** 2026-02-04
**Status:** Failing (reproduces bug - will pass once bug is fixed)
**Bug:** Title uses old format with " - " separators instead of new colon-separated format
**Root cause:** `src/mc/terminal/attach.py:66-93` build_window_title() generates old format `{case} - {customer} - {description}` instead of `{case}:{customer}:{description}:/{vm-path}`
**Fix needed:** Update build_window_title() to use colon separators and include vm-path component

**Notes:** Test shows actual title: "04347611 - IBM - Transfer Cluster ownership"
         Expected: "04347611:IBM:Transfer Cluster ownership:/case"

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

**Actual Result:** ☒ Fail → ☑ Automated (Logic Test Passes, Real-world Integration Fails)

**Automated Test:** `test_duplicate_terminal_prevention_regression()` in `tests/integration/test_case_terminal.py`
**Created:** 2026-02-04
**Status:** Passing (Python logic works) but bug exists in real iTerm2 integration
**Bug:** Running `mc case 04347611` multiple times creates multiple terminal windows instead of focusing existing one
**Root cause:** iTerm2 AppleScript `find_window_by_title()` not finding existing windows. The Python logic (lines 241-257 in attach.py) is correct, but the AppleScript search in `src/mc/terminal/macos.py:69-117` doesn't match real iTerm2 session names
**Fix needed:** Investigate iTerm2 AppleScript - session name search may need adjustment. Test with real iTerm2 to debug why `name of current session` doesn't match what we set with `set name to "..."`

**Notes:** Test validates logic works (mock passes all assertions) but real-world iTerm2 behavior differs. Possible issues:
- Session name vs tab name vs window title confusion in iTerm2
- Timing issue - title not set when search happens
- AppleScript property mismatch

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

## Test 9: Error Handling and Validation

**Feature:** Robust error handling and input validation across all components
**Related Todos:** Fixed HTTP error handling, validation, workspace, and metadata tests

### Prerequisites
- MC installed with valid configuration
- Internet connectivity for API tests
- Podman running

### Test Steps

#### 9.1 Authentication Error Handling - Invalid Token
1. Backup current config:
   ```bash
   cp ~/mc/config/config.toml ~/mc/config/config.toml.backup
   ```
2. Set invalid offline token:
   ```bash
   mc config set rh_api_offline_token "invalid_token_12345"
   ```
3. Attempt to create container:
   ```bash
   mc case 04347611
   ```
4. Restore config:
   ```bash
   mv ~/mc/config/config.toml.backup ~/mc/config/config.toml
   ```

**Expected Result:**
- Clear error message: `Authentication failed: Invalid or expired offline token`
- Error type: `AuthenticationError` (visible in debug mode)
- Suggests checking token validity
- No crash or stack trace shown to user

**Actual Result:** ☐ Pass ☐ Fail
**Error Message:**
**Notes:**

---

#### 9.2 API Error Handling - Invalid Case Number
1. Attempt to access non-existent case:
   ```bash
   mc case 99999999
   ```

**Expected Result:**
- Error message indicates case not found or access denied
- Error type: `HTTPAPIError` with status code 404 or 403
- Clean error presentation (no raw stack trace)
- Helpful suggestion (check case number, verify access permissions)

**Actual Result:** ☐ Pass ☐ Fail
**Error Message:**
**Notes:**

---

#### 9.3 API Error Handling - Network/Server Errors
1. Simulate network failure (optional - disconnect network temporarily):
   ```bash
   # Turn off WiFi or run while offline
   mc case 04347611
   ```

**Expected Result:**
- Error message indicates network connectivity issue or API unavailable
- Suggests checking network connection and Red Hat API status
- No confusing error messages

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (cannot test offline)
**Error Message:**
**Notes:**

---

#### 9.4 LDAP Input Validation - Search String Too Short
1. Test short search string (requires LDAP configuration):
   ```bash
   # If LDAP search command exists
   mc ldap search "ab"
   ```

**Expected Result:**
- Validation error: Input too short (minimum 3 characters)
- Returns error tuple: `(False, "Search string too short")`
- No exception raised
- Clean user-facing error message

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (no LDAP configured)
**Error Message:**
**Notes:**

---

#### 9.5 LDAP Input Validation - Search String Too Long
1. Test overly long search string:
   ```bash
   # Create 257+ character string
   mc ldap search "$(python3 -c 'print("a" * 300)')"
   ```

**Expected Result:**
- Validation error: Input too long (maximum 256 characters)
- Returns error tuple: `(False, "Search string too long")`
- No exception raised
- Clean user-facing error message

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (no LDAP configured)
**Error Message:**
**Notes:**

---

#### 9.6 Container State Management - Start Stopped Container
1. Create and stop a container:
   ```bash
   mc case 04347611
   # In container terminal:
   exit
   # Wait for terminal to close
   ```
2. Stop the container explicitly:
   ```bash
   podman stop mc-04347611
   ```
3. Verify container is stopped:
   ```bash
   mc container list
   ```
4. Relaunch container:
   ```bash
   mc case 04347611
   ```

**Expected Result:**
- Container list shows `STATUS: stopped` before relaunch
- `mc case 04347611` starts the stopped container
- Container status updates to `running` after start
- Terminal opens successfully
- Container object status reflects actual Podman state

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 9.7 Container Uptime Calculation - Multi-Day Containers
1. Check container list with uptime:
   ```bash
   mc container list
   ```
2. Verify uptime calculation for containers created 1+ days ago (if available)

**Expected Result:**
- Uptime shows days correctly (e.g., "2d 5h" for 2 days, 5 hours)
- No calculation errors for multi-day uptimes
- Consistent formatting across all containers

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (no multi-day containers)
**Uptime Format Examples:**
**Notes:**

---

#### 9.8 Workspace Status Check - Missing Directory
1. Create container and workspace:
   ```bash
   mc case 04347611
   exit
   ```
2. Manually delete workspace directory:
   ```bash
   rm -rf ~/mc/cases/*/04347611-*/
   ```
3. Check workspace status:
   ```bash
   mc workspace check
   ```

**Expected Result:**
- Warning logged: Workspace directory missing for container
- Status level: WARNING
- Suggests reconciliation or recreation
- No crash

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (no workspace check command)
**Warning Message:**
**Notes:**

---

#### 9.9 Workspace Status Check - File/Directory Conflict
1. Create file with container name:
   ```bash
   mkdir -p ~/mc/cases/TestCustomer/
   touch ~/mc/cases/TestCustomer/12345678-Test_Case
   ```
2. Check workspace status or attempt container creation

**Expected Result:**
- Error logged: Expected directory, found file
- Status level: ERROR
- Clear error message indicating conflict
- No crash or confusing state

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A
**Error Message:**
**Notes:**

---

#### 9.10 Version Detection - Installed Package
1. Check MC version:
   ```bash
   mc --version
   ```

**Expected Result:**
- Shows version in format: `mc version X.Y.Z`
- Version matches package metadata
- No errors or fallbacks

**Actual Result:** ☐ Pass ☐ Fail
**Version Output:**
**Notes:**

---

#### 9.11 Version Detection - Editable Install Fallback
1. If running from source with editable install:
   ```bash
   # From project directory
   uv pip install -e .
   mc --version
   ```

**Expected Result:**
- Falls back to pyproject.toml version
- Shows version: `2.0.0` (or current pyproject.toml version)
- No errors or "unknown version"

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (not editable install)
**Version Output:**
**Notes:**

---

#### 9.12 Terminal Attachment - Metadata Fallbacks
1. Create container with valid case:
   ```bash
   mc case 04347611
   ```
2. Observe terminal window title and shell prompt

**Expected Result:**
- Window title shows: `04347611 - <customer> - <description>`
- If metadata unavailable, graceful fallback to case number only
- Shell prompt: `[MC-04347611] /case$`
- No crashes due to missing metadata

**Actual Result:** ☐ Pass ☐ Fail
**Window Title:**
**Shell Prompt:**
**Notes:**

---

#### 9.13 Container Creation - Validation Before Launch
1. Attempt container creation with various scenarios:
   ```bash
   # Valid case
   mc case 04347611

   # Invalid case number format (if validation exists)
   mc case abc12345

   # Empty case number
   mc case ""
   ```

**Expected Result:**
- Valid case: Container created successfully
- Invalid format: Validation error before API call
- Empty case: Error message, no crash
- All errors handled gracefully

**Actual Result:** ☐ Pass ☐ Fail
**Notes:**

---

#### 9.14 Podman Platform Integration - macOS Detection
1. On macOS, verify platform-specific behavior:
   ```bash
   mc case 04347611
   ```

**Expected Result:**
- Podman client correctly detects macOS platform
- Uses appropriate Podman machine socket
- Container creation succeeds
- No platform-related errors

**Actual Result:** ☐ Pass ☐ Fail ☐ N/A (not macOS)
**Platform Detected:**
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
| 3.1 | Auto-pull and tag from quay.io | ☒ Automated | Covers initial image pull |
| 3.2 | Podman connection error message | ☐ Pass ☐ Fail | |
| 4.1 | Image caching - second container | ☐ Pass ☐ Fail | |
| 4.2 | Image details and tag verification | ☐ Pass ☐ Fail | |
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
| 9.1 | Authentication error - invalid token | ☐ Pass ☐ Fail | |
| 9.2 | API error - invalid case number | ☐ Pass ☐ Fail | |
| 9.3 | API error - network/server errors | ☐ Pass ☐ Fail | |
| 9.4 | LDAP validation - too short | ☐ Pass ☐ Fail | |
| 9.5 | LDAP validation - too long | ☐ Pass ☐ Fail | |
| 9.6 | Container state - start stopped | ☐ Pass ☐ Fail | |
| 9.7 | Container uptime - multi-day | ☐ Pass ☐ Fail | |
| 9.8 | Workspace status - missing dir | ☐ Pass ☐ Fail | |
| 9.9 | Workspace status - file conflict | ☐ Pass ☐ Fail | |
| 9.10 | Version detection - installed | ☐ Pass ☐ Fail | |
| 9.11 | Version detection - editable install | ☐ Pass ☐ Fail | |
| 9.12 | Terminal attachment - metadata fallbacks | ☐ Pass ☐ Fail | |
| 9.13 | Container creation - validation | ☐ Pass ☐ Fail | |
| 9.14 | Podman platform - macOS detection | ☐ Pass ☐ Fail | |
| E2E | Integration workflow | ☐ Pass ☐ Fail | |

**Total Pass Rate:** _____ / 33 tests

**Note:** Test 3.1 is automated and covers both initial image pull (original 3.1) and image availability verification (original 4.1 merged in).

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
