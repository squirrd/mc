# Shell.py Bashrc Directory Fix

**Date:** 2026-02-04
**Bug Source:** UAT 1.1 - Fresh Install Test
**Severity:** Minor
**Platform:** macOS (reproduced), likely affects Linux

---

## Problem

During fresh install, when running `mc case <number>`, bashrc files were being created in **old platform-specific locations** instead of the consolidated `~/mc/` directory:

- **macOS:** `~/Library/Application Support/mc/bashrc/`
- **Linux:** `~/.local/share/mc/bashrc/` or `~/.config/mc/`

**Expected:** All files under `~/mc/config/bashrc/`

---

## Root Cause

**File:** `src/mc/terminal/shell.py:84`

The `get_bashrc_path()` function was using `platformdirs.user_data_dir("mc", "redhat")` which returns platform-specific paths:

```python
# BEFORE (incorrect):
data_dir = user_data_dir("mc", "redhat")  # Returns platform-specific path
bashrc_dir = Path(data_dir) / "bashrc"
```

This violated the v2.0 directory consolidation design which requires all MC files to be under `~/mc/`.

---

## Fix Applied

Updated `get_bashrc_path()` to use the consolidated directory structure:

```python
# AFTER (correct):
bashrc_dir = Path.home() / "mc" / "config" / "bashrc"
```

**Changes:**
- Removed dependency on `platformdirs.user_data_dir()` for bashrc path
- Now uses `Path.home() / "mc" / "config" / "bashrc"` directly
- Maintains same directory creation logic (mkdir with parents=True)

---

## Test Coverage

**Regression Test:** `test_fresh_install_no_old_directories_created_regression()`
**Location:** `tests/integration/test_case_terminal.py`
**Status:** ✅ PASSING

The test:
1. Backs up any existing MC directories
2. Creates a clean slate
3. Runs `mc case 04347611` (triggers container creation and bashrc generation)
4. Verifies NO directories created in old platformdirs locations
5. Verifies bashrc created in new location: `~/mc/config/bashrc/`
6. Restores backed up directories

**Test Output:**
```
✓ Test PASSED: Fresh install creates directories ONLY in ~/mc/
✓ Verified no directories in old locations: [PosixPath('/Users/dsquirre/.mc'), PosixPath('/Users/dsquirre/Library/Application Support/mc')]
✓ Verified bashrc in new location: /Users/dsquirre/mc/config/bashrc
```

---

## Verification

**Full Integration Test Suite:**
```bash
uv run pytest tests/integration/ -v --no-cov
```

**Result:** ✅ 46 passed, 14 skipped in 30.22s

No regressions introduced. All previously passing tests still pass.

---

## Documentation Updated

1. ✅ `tests/integration/test_case_terminal.py` - Updated test docstring status
2. ✅ `.planning/UAT-TESTS-BATCH-ABCE.md` - Marked test as passing
3. ✅ Git commit with detailed context

---

## Impact

**Before Fix:**
- Fresh installs created directories in old platformdirs locations
- Violated consolidated directory design
- Could confuse users with multiple MC directories
- Migration code couldn't handle these "new but wrong" directories

**After Fix:**
- All directories created under `~/mc/`
- Consistent with v2.0 directory consolidation
- No confusion about which directory to use
- Clean separation between old (platformdirs) and new (consolidated) structures

---

## Git History

```
b2f40a3 fix: use consolidated directory for bashrc files
8599b4f test: update version assertion to match current version 2.0.1
ca01120 fix: correct Image.tag() call to use separate repo and tag args
```

---

## Related Documentation

- `docs/INTEGRATION_TEST_BEST_PRACTICES.md` - Integration test patterns
- `.planning/UAT-TESTS-BATCH-ABCE.md` - UAT Test 1.1
- `.fix-integration-tests/REPORT.md` - Complete fix session report

---

**Status:** ✅ FIXED
**Verified:** 2026-02-04
**Test:** Passing
