---
created: 2026-02-01T23:44
title: Fix HTTP error handling tests
area: testing
files:
  - tests/unit/test_auth.py
  - tests/unit/test_redhat_api.py
  - src/mc/utils/auth.py
  - src/mc/integrations/redhat_api.py
---

## Problem

14 test failures related to HTTP error handling (401, 403, 404, 500 status codes):

**test_auth.py (2 failures):**
- `test_get_access_token_http_401_unauthorized`
- `test_get_access_token_http_500_server_error`

**test_redhat_api.py (12 failures):**
- `test_fetch_case_details_http_errors[401-Unauthorized]`
- `test_fetch_case_details_http_errors[403-Forbidden]`
- `test_fetch_case_details_http_errors[404-Not Found]`
- `test_fetch_case_details_http_errors[500-Internal Server Error]`
- `test_fetch_account_details_http_errors[401-Unauthorized]`
- `test_fetch_account_details_http_errors[403-Forbidden]`
- `test_fetch_account_details_http_errors[404-Not Found]`
- `test_fetch_account_details_http_errors[500-Internal Server Error]`
- `test_list_attachments_http_errors[401-Unauthorized]`
- `test_list_attachments_http_errors[403-Forbidden]`
- `test_list_attachments_http_errors[404-Not Found]`
- `test_list_attachments_http_errors[500-Internal Server Error]`

Tests expect specific exception types or error handling behavior that isn't matching actual implementation.

## Solution

Review and align:
1. Test expectations with actual HTTP error handling in auth.py and redhat_api.py
2. Exception types raised for each HTTP status code
3. Error messages and exception attributes
