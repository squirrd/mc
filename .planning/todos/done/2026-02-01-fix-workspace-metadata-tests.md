---
created: 2026-02-01T23:44
title: Fix workspace and metadata tests
area: testing
files:
  - tests/unit/test_workspace.py
  - tests/unit/test_version.py
  - src/mc/controller/workspace.py
  - src/mc/version.py
---

## Problem

5 test failures in workspace and metadata functionality:

**test_workspace.py (4 failures):**
- `test_workspace_check_status_ok` - Assertion error on workspace status check
- `test_workspace_check_status_warn` - Assertion error on warning conditions
- `test_workspace_check_status_fatal` - Assertion error on fatal conditions
- `test_get_attachment_dir` - AttributeError accessing attachment directory

**test_version.py (1 failure):**
- `test_get_version_fallback_to_pyproject` - AssertionError on version fallback logic
- Version detection should fall back to pyproject.toml when package metadata unavailable

Test failures suggest API changes in workspace.py or version.py that tests haven't been updated for.

## Solution

1. Review workspace status check API in src/mc/controller/workspace.py
2. Update test assertions to match current status check return values/types
3. Fix attachment directory access (API change or attribute rename?)
4. Debug version fallback logic in src/mc/version.py for editable installs
