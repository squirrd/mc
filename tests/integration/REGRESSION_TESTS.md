# Regression Test Index

Tests created from real bugs and UAT failures to prevent regressions.

## Overview

This document tracks integration tests that were created in response to actual bugs discovered during UAT testing or production usage. Each test reproduces the original bug scenario and verifies the fix.

## Tests

| Test | Bug Source | Date Added | Status | File |
|------|------------|------------|--------|------|
| `test_fresh_install_missing_config_base_directory_regression` | UAT 1.1 | 2026-02-02 | Failing (reproduces bug) | `test_case_terminal.py` |
| `test_fresh_install_no_old_directories_created_regression` | UAT 1.1 | 2026-02-04 | Failing (reproduces bug) | `test_case_terminal.py` |
| `test_image_pull_and_tag_regression` | UAT 3.1 | 2026-02-04 | Failing (reproduces bug) | `test_container_image.py` |
| `test_terminal_title_format_regression` | UAT 5.1 | 2026-02-04 | Failing (reproduces bug) | `test_case_terminal.py` |
| `test_duplicate_terminal_prevention_regression` | UAT 5.2 | 2026-02-04 | Failing (reproduces real bug - no mocking!) | `test_case_terminal.py` |
| `test_github_404_no_releases_regression` | Production Bug | 2026-02-23 | Passing (reproduces bug) | `test_version_check.py` |

## Test Details

### test_fresh_install_missing_config_base_directory_regression

**Source:** UAT Test 1.1 - Fresh Install - Lazy Initialization
**Platform:** macOS (reproduced), likely affects Linux too
**Severity:** Critical - Blocks core functionality on fresh install

**Bug Description:**
On a fresh install with no existing `base_directory` key in config file, running `mc case <number>` fails with confusing error:
```
Failed to create container for case 04347611. Podman error: 'base_directory'
```

**Root Cause:**
Lines 165 and 200 in `src/mc/terminal/attach.py` use:
```python
base_dir = config_manager.load()["base_directory"]
```

This raises `KeyError` when the config file exists but doesn't have the `base_directory` key (common after running config wizard which only sets API token). The KeyError is caught generically and shows misleading error message.

**Fix:** Use `config_manager.get("base_directory", os.path.expanduser("~/mc"))` with proper default fallback.

**Test Approach:**
- Creates minimal config file with only API token (no base_directory key)
- Uses real Red Hat API client for case metadata fetch
- Uses real Podman client and container manager
- Attempts to create container via `attach_terminal()`
- Currently fails with the bug (will pass once bug is fixed)

**How to Run:**
```bash
uv run pytest tests/integration/test_case_terminal.py::test_fresh_install_missing_config_base_directory_regression -v
```

---

### test_fresh_install_no_old_directories_created_regression

**Source:** UAT Test 1.1 - Fresh Install - Lazy Initialization
**Platform:** macOS (reproduced), likely affects Linux too
**Severity:** Minor - Creates directories in wrong locations

**Bug Description:**
During fresh install, when running `mc case <number>`, directories are being created in OLD platform-specific locations instead of the new consolidated `~/mc/` structure:
- **macOS:** `~/Library/Application Support/mc/bashrc/`
- **Linux:** `~/.local/share/mc/bashrc/` or `~/.config/mc/`

The directories should ONLY be created under `~/mc/config/bashrc/` according to the consolidated config design.

**Root Cause:**
`src/mc/terminal/shell.py:84` in the `get_bashrc_path()` function uses:
```python
data_dir = user_data_dir("mc", "redhat")
bashrc_dir = Path(data_dir) / "bashrc"
```

This uses `platformdirs.user_data_dir()` which returns platform-specific paths like:
- macOS: `~/Library/Application Support/mc`
- Linux: `~/.local/share/mc`

Instead, it should use the new consolidated location: `~/mc/config/bashrc/`

**Fix:** Update `get_bashrc_path()` to use `Path.home() / "mc" / "config" / "bashrc"` instead of platformdirs.

**Test Approach:**
- Backs up and removes all existing MC directories (old and new locations)
- Creates minimal config in NEW location with API credentials
- Runs container creation workflow (which triggers bashrc generation)
- Verifies NO directories created in old platformdirs locations
- Verifies bashrc IS created in new `~/mc/config/bashrc/` location
- Automatically restores backed-up directories after test completes
- Currently fails with the bug (will pass once bug is fixed)

**How to Run:**
```bash
uv run pytest tests/integration/test_case_terminal.py::test_fresh_install_no_old_directories_created_regression -v -s
```

**Note:** This test manipulates real directories in your home folder but automatically backs them up and restores them. Use `-s` flag to see backup/restore progress.

---

### test_image_pull_and_tag_regression

**Source:** UAT Test 3.1 - Missing Image - Clear Error Message
**Platform:** macOS (reproduced), likely affects all platforms
**Severity:** Critical - Blocks core functionality when image not cached locally

**Bug Description:**
When `mc-rhel10:latest` image is not available locally, the code attempts to automatically pull from `quay.io/rhn_support_dsquirre/mc-container:latest` and tag it as `mc-rhel10:latest`. However, the tagging step fails with:

```
TypeError: Image.tag() missing 1 required positional argument: 'tag'
```

The image is successfully pulled (visible in `podman images` as `quay.io/rhn_support_dsquirre/mc-container:latest`) but the container creation fails because the local tag cannot be created.

**User Impact:**
- Fresh installs fail when creating first container
- Any user without cached `mc-rhel10:latest` image cannot create containers
- Error message is confusing and suggests building locally even though pull succeeded
- Blocks core "mc case" workflow

**Root Cause:**
`src/mc/container/manager.py:201` in the `_ensure_image()` method calls:
```python
pulled_image = self.podman.client.images.get(registry_image)
pulled_image.tag(image_name)  # image_name = "mc-rhel10:latest"
```

But the Podman SDK's `image.tag()` method signature requires TWO arguments:
```python
def tag(self, repository: str, tag: str = None) -> bool:
    ...
```

The code passes `"mc-rhel10:latest"` as a single argument, but it should be split into:
- `repository = "mc-rhel10"`
- `tag = "latest"`

**Fix:**
Update line 201 to split the image name before calling tag():
```python
# Split image_name into repository and tag
if ':' in image_name:
    repo, tag = image_name.split(':', 1)
else:
    repo, tag = image_name, 'latest'

# Tag the pulled image with local name
pulled_image.tag(repo, tag)
```

**Test Approach:**
- Removes both `mc-rhel10:latest` and `quay.io/.../mc-container:latest` images
- Attempts to create container (triggers `_ensure_image()`)
- Verifies image is pulled, tagged, and container created successfully
- Currently fails with the bug (will pass once bug is fixed)
- Real Podman integration - no mocking of image operations

**How to Run:**
```bash
MC_TEST_INTEGRATION=1 uv run pytest tests/integration/test_container_image.py::TestImagePullAndTag::test_image_pull_and_tag_regression -v -s
```

**Note:** This test pulls a real image from quay.io (~549 MB). It may take 30-60 seconds on first run.

---

### test_terminal_title_format_regression

**Source:** UAT Test 5.1 - Initial Terminal Launch
**Platform:** macOS (reproduced)
**Severity:** Minor - Cosmetic issue affecting usability

**Bug Description:**
Terminal window title uses old format with hyphen separators instead of the new colon-separated format that includes the vm-path. When launching a container terminal with `mc case <number>`, the window title should be in the format `{case}:{customer}:{description}:/{vm-path}` but instead shows `{case} - {customer} - {description}`.

Example:
- **Expected:** `04347611:IBM:Transfer Cluster ownership:/case`
- **Actual:** `04347611 - IBM - Transfer Cluster ownership`

Additionally, users reported seeing a pod/container reference like `@38d5d5580c057c/case` as the window title in some cases, suggesting the title may not be properly set at all in certain terminal emulators.

**Root Cause:**
`src/mc/terminal/attach.py:66-93` in the `build_window_title()` function generates the old format:
```python
def build_window_title(case_number: str, customer_name: str, description: str) -> str:
    # Build base title
    base = f"{case_number} - {customer_name} - "
    # ... truncation logic ...
    return base + description
```

**Fix Required:**
Update `build_window_title()` to:
1. Use colon (`:`) separators instead of ` - `
2. Include the vm-path component (typically `/case`)
3. Format: `{case_number}:{customer_name}:{description}:/{vm_path}`

Example implementation:
```python
def build_window_title(case_number: str, customer_name: str, description: str, vm_path: str = "/case") -> str:
    # Build title with colon separators
    base = f"{case_number}:{customer_name}:{description}:"
    # Truncate if needed to keep under 100 chars total
    max_total_len = 100
    vm_path_component = f"{vm_path}"
    # ... truncation logic ...
    return base + vm_path_component
```

**Test Approach:**
- Creates real container with Red Hat API metadata
- Uses real Podman client and state database
- Mocks only terminal launcher to capture title that would be passed
- Verifies title format has:
  - Case number present
  - Colon separators (not " - ")
  - VM path component (:/case)
  - At least 3 colons in format
  - Does not start with "@" (pod reference)
- Currently fails with the old format bug (will pass once bug is fixed)

**How to Run:**
```bash
uv run pytest tests/integration/test_case_terminal.py::test_terminal_title_format_regression -v -s
```

**Test Output When Bug Exists:**
```
✗ BUG FOUND: Title uses old format with ' - ' separators
Actual: 04347611 - IBM - Transfer Cluster ownership
Expected format: {case}:{customer}:{description}:/{vm-path}
Example: 04347611:IBM Corpora Limited:Server Down Critical Pr:/case
Fix needed in: src/mc/terminal/attach.py build_window_title()
```

---

### test_duplicate_terminal_prevention_regression

**Source:** UAT Test 5.2 - Duplicate Launch Detection
**Platform:** macOS with iTerm2 (reproduced)
**Severity:** Major - Affects usability, creates terminal clutter

**Bug Description:**
Running `mc case 04347611` multiple times incorrectly allows multiple terminal windows to be created instead of focusing the existing window for the case.

Expected behavior:
1. First call: `mc case 04347611` creates new terminal window
2. Second call: `mc case 04347611` finds existing window, focuses it, and shows message "Focused existing terminal for case 04347611"
3. No new terminal window created on subsequent calls

Actual behavior:
1. First call: Creates new terminal window
2. Second call: Creates ANOTHER new terminal window (duplicate)
3. No "Focused existing terminal" message shown
4. Multiple terminal windows accumulate for the same case

**Root Cause:**
The iTerm2 AppleScript integration in `src/mc/terminal/macos.py:69-117` cannot find windows immediately after creating them.

**Verified with REAL integration test (no mocking):**

The test creates a REAL iTerm2 window using REAL AppleScript:
```applescript
tell current session of current window
    set name to "04347611 - IBM - Transfer Cluster ownership"
end tell
```

Then immediately searches for it using REAL AppleScript:
```applescript
tell application "iTerm"
    repeat with theWindow in windows
        repeat with theTab in tabs of theWindow
            if name of current session of theTab contains "04347611 - IBM - Transfer Cluster ownership" then
                return true
            end if
        end repeat
    end repeat
    return false
end tell
```

**Result:** Search returns `False` even though window was just created.

**Test output:**
```
iTerm2 windows before first call: 13
Creating container...
iTerm2 windows after first call: 14  (window WAS created)

Searching for window with title: 04347611 - IBM - Transfer Cluster ownership
find_window_by_title result: False  (BUG: cannot find it!)
```

**Possible Causes:**
1. **Property mismatch:** `set name` and `name of current session` may access different properties
2. **Timing issue:** Session name not queryable immediately after setting (need delay?)
3. **iTerm2 AppleScript quirk:** Session name vs tab name vs window title confusion

**Test Approach - NO MOCKING:**
This test uses REAL components to catch the REAL bug:
- ✅ Real Podman client (creates actual containers)
- ✅ Real Red Hat API client (makes actual HTTP calls)
- ✅ Real MacOSLauncher (executes actual AppleScript)
- ✅ Real iTerm2 windows (launches actual terminal windows)
- ⚠️ Only mocks TTY detection (pytest limitation)

The test FAILS when the bug exists and will PASS when the bug is fixed. No mocks hiding the issue.

**Fix Required:**
Debug the iTerm2 AppleScript integration:
1. Test setting and retrieving session names in iTerm2
2. Try alternative properties: tab name, window title, etc.
3. Add timing delays if needed
4. Consider using AppleScript debugging to see actual property values

Example debugging approach:
```applescript
# After setting name, immediately retrieve it to verify
tell current session of current window
    set name to "Test Title"
    delay 0.5
    get name
end tell
```

**How to Run:**
```bash
uv run pytest tests/integration/test_case_terminal.py::test_duplicate_terminal_prevention_regression -v -s
```

**Test Output (Currently Fails - Catches Real Bug):**
```
iTerm2 windows before first call: 13
Creating container...
iTerm2 windows after first call: 14

✓ First call completed - iTerm2 window should be open

Searching for window with title: 04347611 - IBM - Transfer Cluster ownership
find_window_by_title result: False
FAILED

✗ BUG FOUND: find_window_by_title returned False immediately after creating window!
Expected title: 04347611 - IBM - Transfer Cluster ownership
Window was just created but AppleScript search cannot find it.
This is the iTerm2 AppleScript integration bug.
Root cause: Search uses 'name of current session' but create uses 'set name'
Fix needed in: src/mc/terminal/macos.py find_window_by_title() and _build_iterm_script()
```

**Important Note:**
This test uses REAL iTerm2 integration (no mocking!) and successfully reproduces the bug. When you run this test:
- It will launch an actual iTerm2 window on your machine
- The test will FAIL (expected - bug exists)
- You'll need to manually close the iTerm2 window after the test

**Why no mocking?**
See `docs/INTEGRATION_TEST_NO_MOCKING.md` for the full explanation. In short: mocking hides bugs. We initially wrote this test with mocks - it passed while the bug existed. After removing mocks and using real iTerm2, the test immediately caught the bug.

---

### test_github_404_no_releases_regression

**Source:** Production Bug - Post v2.0.4 deployment
**Platform:** All platforms (GitHub API independent)
**Severity:** Minor - Doesn't block core functionality

**Bug Description:**
After deploying v2.0.4 with the new version check feature, running any `mc` command triggers a background version check that fails with an ERROR log:

```
2026-02-23 10:34:32 [ERROR] mc.version_check: Failed to perform version check: 404 Client Error: Not Found for url: https://api.github.com/repos/squirrd/mc/releases/latest
```

The issue occurs because the GitHub repository `squirrd/mc` doesn't have any published releases yet. The version checker attempts to fetch the latest release and receives a 404 response, which is treated as an error.

**User Impact:**
- Error logs on every command execution (confusing)
- Users may think something is broken
- Logs polluted with ERROR level messages for normal condition
- No actual functionality broken (version check is optional)

**Root Cause:**
`src/mc/version_check.py:156-157` in the `_fetch_latest_release()` method raises HTTPError for 404 responses:

```python
# Fail fast on 4xx errors (don't retry)
if 400 <= response.status_code < 500:
    response.raise_for_status()
```

The 404 response is a normal condition for repositories without published releases, but the code treats it as an exceptional error. The exception propagates to `_perform_version_check()` which logs it at ERROR level (line 226).

**Expected Behavior:**
- 404 should be handled gracefully as "no releases published yet"
- Log at INFO or DEBUG level, not ERROR
- Save `last_status_code=404` in config for smart throttling
- Save `last_check` timestamp to prevent repeated failed attempts
- Perhaps extend throttle period for 404 (similar to 403 rate limit handling)

**Fix Required:**
Update `_fetch_latest_release()` to handle 404 specially:

```python
# Handle 404 Not Found (repository has no releases yet)
if response.status_code == 404:
    return None, etag, 404  # Return gracefully, no exception

# Fail fast on other 4xx errors (don't retry)
if 400 <= response.status_code < 500:
    response.raise_for_status()
```

And update `_perform_version_check()` to handle 404 status_code gracefully:

```python
# Handle 404 Not Found - repository has no releases yet
if status_code == 404:
    logger.info("No releases published yet for this repository")
    self._config_manager.save_atomic(config)
    return  # Exit gracefully
```

**Test Approach:**
This is a TRUE integration test with REAL GitHub API calls:
- ✅ Makes actual HTTP request to `https://api.github.com/repos/squirrd/mc/releases/latest`
- ✅ Verifies real 404 response from GitHub
- ✅ Uses real ConfigManager with tmp_path for isolation
- ✅ No mocks - catches real-world API behavior
- ⚠️ Only mocks `get_version()` for stable test version

The test currently PASSES by verifying the exception is raised (documenting current buggy behavior). After the fix is applied, the test assertions should be updated to verify graceful 404 handling.

**How to Run:**
```bash
uv run pytest tests/integration/test_version_check.py::TestGitHubAPIIntegration::test_github_404_no_releases_regression -v -s
```

**Test Output (Current - Catches Bug):**
```
PASSED - HTTPError raised for 404 (documents current behavior)
```

**Test Output (After Fix):**
The test should be updated to verify:
- No ERROR level logs
- Config updated with `last_status_code=404`
- Config updated with `last_check` timestamp
- No exception raised

**Related Tests:**
- `test_github_api_with_valid_repo_has_releases` - Validates happy path with real repo
- `test_github_api_respects_rate_limits` - Documents 403 handling

**Note on Real GitHub API Usage:**
This test makes real HTTP calls to GitHub. It's fast (<1 second) and doesn't require authentication for public API endpoints. The 404 response is consistent and stable (repo has no releases), making it a reliable test case. We prefer real API calls over mocks to catch real-world issues like this one.

---

## Adding New Regression Tests

When creating a new regression test from a bug:

1. **Document the bug thoroughly:**
   - Include date discovered, platform, severity
   - Exact error message or unexpected behavior
   - Root cause analysis with file/line references
   - Steps to reproduce

2. **Use real components:**
   - Minimize mocking - only mock what's necessary for test isolation
   - Use real API clients, database, Podman when possible
   - Only mock external dependencies that can't run in CI (like terminal launching)

3. **Make test verify the fix:**
   - Test should fail when bug exists
   - Test should pass when bug is fixed
   - Use clear assertion messages

4. **Update documentation:**
   - Add entry to this index file
   - Link from UAT document if applicable
   - Include "Fixed in: vX.Y.Z" once bug is resolved

5. **Commit with context:**
   - Reference UAT test number or production bug report
   - Include the full error message in commit
   - Explain what the test verifies
