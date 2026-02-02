---
created: 2026-02-01T23:44
title: Fix test dependencies and imports
area: testing
files:
  - tests/integration/test_entry_points.py:6
  - tests/unit/test_cache.py:8-16
  - pyproject.toml:37-49
---

## Problem

Test suite has 2 import/collection errors preventing tests from running:

1. **test_entry_points.py** - Missing `pytest-console-scripts` dependency
   - Error: `ModuleNotFoundError: No module named 'pytest_console_scripts'`
   - Imported at line 6
   - Not in pyproject.toml dev dependencies

2. **test_cache.py** - Outdated imports using v1.0 API
   - Error: `ImportError: cannot import name 'get_cache_path' from 'mc.utils.cache'`
   - Imports at lines 8-16: `get_cache_path`, `is_cache_expired`, `load_cache`, `cache_case_metadata`
   - These were v1.0 JSON file-based caching functions
   - Need to update to use new v2.0 `CaseMetadataCache` class API

## Solution

1. Add `pytest-console-scripts` to pyproject.toml `[project.optional-dependencies.dev]`
2. Update test_cache.py to use CaseMetadataCache class instead of removed helper functions
3. Verify all tests can be collected successfully
