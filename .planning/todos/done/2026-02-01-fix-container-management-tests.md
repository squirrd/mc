---
created: 2026-02-01T23:44
title: Fix container management tests
area: testing
files:
  - tests/integration/test_container_create_integration.py:54
  - tests/unit/test_container_manager_create.py
  - tests/unit/test_container_manager_list.py
  - tests/unit/test_cli_container_commands.py
  - src/mc/container/manager.py
---

## Problem

6 test failures in container management functionality:

**test_container_create_integration.py (2 failures):**
- `test_create_container_e2e` - Expected container state 'running', got 'created'
- `test_reconciliation_with_real_podman` - Similar state mismatch
- Line 54: `assert 'created' == 'running'`

**test_container_manager_create.py (1 failure):**
- `test_create_new_container` - Container creation test failure

**test_container_manager_list.py (1 failure):**
- `test_uptime_calculation_days` - Uptime calculation for multi-day containers

**test_cli_container_commands.py (2 failures):**
- `TestQuickAccess::test_quick_access_creates_missing_container`
- `TestQuickAccess::test_quick_access_existing_container`

Root cause appears to be container state expectations - tests expect 'running' but containers are in 'created' state.

## Solution

1. Investigate ContainerManager.create() behavior - does it start containers or just create them?
2. Update tests to match actual container lifecycle states
3. Fix uptime calculation edge cases for multi-day containers
4. Review QuickAccess pattern implementation
