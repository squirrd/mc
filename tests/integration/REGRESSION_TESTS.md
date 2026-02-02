# Regression Test Index

Tests created from real bugs and UAT failures to prevent regressions.

## Overview

This document tracks integration tests that were created in response to actual bugs discovered during UAT testing or production usage. Each test reproduces the original bug scenario and verifies the fix.

## Tests

| Test | Bug Source | Date Added | Status | File |
|------|------------|------------|--------|------|
| `test_fresh_install_missing_config_base_directory_regression` | UAT 1.1 | 2026-02-02 | Failing (reproduces bug) | `test_case_terminal.py` |

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
