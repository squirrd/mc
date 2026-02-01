---
created: 2026-02-01T21:29
title: Fix terminal attachment Salesforce API method call
area: api
priority: P0
milestone: v2.0.1
files:
  - src/mc/terminal/attach.py:136
  - src/mc/integrations/salesforce_api.py:120
---

## Problem

**CRITICAL BUG found during v2.0 milestone audit:**

Primary user flow `mc case 12345678` is completely broken due to method name mismatch in terminal attachment code.

**Location:** `/Users/dsquirre/Repos/mc/src/mc/terminal/attach.py:136`

**Current code (WRONG):**
```python
case_data = salesforce_client.get_case(case_number)
```

**Error at runtime:**
```
AttributeError: 'SalesforceAPIClient' object has no attribute 'get_case'
```

**Root cause:** The `SalesforceAPIClient` class provides `query_case()` method, not `get_case()`. The caller uses the wrong method name.

**Available methods in SalesforceAPIClient:**
- ✅ `query_case(case_number)` - EXISTS
- ✅ `close()` - EXISTS
- ❌ `get_case(case_number)` - DOES NOT EXIST

**Impact:**
- Primary containerized workflow unusable
- User cannot launch terminal windows for cases
- Affects both `mc case 12345678` and `mc 12345678` (quick access)
- Breaks at step 5 of 7-step workflow (after validation, before container creation)

**Discovered:** v2.0 milestone audit (2026-02-01T21:25:31)

**Why it wasn't caught:**
- No end-to-end integration test for full `mc case <number>` flow
- Unit tests mock the Salesforce client, so method name mismatch not detected
- Phase 12 verification tested terminal launcher in isolation, not full workflow

## Solution

**Primary fix (5 minutes):**

Change line 136 in `attach.py`:
```python
# Before:
case_data = salesforce_client.get_case(case_number)

# After:
case_data = salesforce_client.query_case(case_number)
```

**Verification needed:**

1. Check response format compatibility:
   - `get_case()` (expected but doesn't exist) might have returned different field names
   - `query_case()` (actual method) returns specific SOQL fields
   - Verify downstream code in attach.py handles query_case response correctly

2. Test end-to-end:
   ```bash
   # With Salesforce credentials configured:
   mc case 12345678
   # Should: fetch metadata, create container, launch terminal
   ```

3. Check for other callers:
   ```bash
   grep -r "\.get_case(" src/
   # Verify no other code calls the non-existent method
   ```

**Additional improvements (30 minutes):**

Add E2E integration test to prevent regression:
```python
# tests/integration/test_case_terminal_e2e.py
def test_mc_case_full_flow(mock_salesforce, mock_podman, mock_terminal):
    """Test complete mc case <number> workflow."""
    # Mock Salesforce API
    mock_salesforce.query_case.return_value = {...}

    # Mock container doesn't exist
    mock_podman.containers.get.side_effect = NotFound

    # Run command
    result = subprocess.run(['mc', 'case', '12345678'], ...)

    # Verify flow
    assert mock_salesforce.query_case.called
    assert mock_podman.containers.create.called
    assert mock_terminal.launch.called
```

**Related audit findings:**
- See `.planning/v2.0-MILESTONE-AUDIT.md` for full details
- This is 1 of 2 unsatisfied requirements blocking v2.0.0 release
- Affects SF-01 and TERM-01 requirements
