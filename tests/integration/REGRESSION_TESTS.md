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
