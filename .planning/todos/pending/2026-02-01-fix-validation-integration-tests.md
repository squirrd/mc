---
created: 2026-02-01T23:44
title: Fix validation and integration tests
area: testing
files:
  - tests/unit/test_ldap.py
  - tests/integration/test_ldap_docker.py
  - tests/unit/test_podman_client.py
  - src/mc/integrations/ldap.py
  - src/mc/integrations/podman.py
---

## Problem

5 test failures/errors across validation and integration tests:

**test_ldap.py (2 failures):**
- `test_ldap_search_input_too_short` - mc.exceptions raised unexpectedly
- `test_ldap_search_input_too_long` - mc.exceptions raised unexpectedly
- Input validation tests failing on exception type/behavior

**test_ldap_docker.py (2 errors):**
- `test_ldap_docker_integration_real_search` - Collection/runtime error
- `test_ldap_docker_parsing_validation` - Collection/runtime error
- Integration tests with Docker LDAP server

**test_podman_client.py (1 failure):**
- `TestPlatformIntegration::test_macos_platform_integration`
- macOS-specific Podman platform detection/integration

## Solution

1. Review LDAP input validation exception types in src/mc/integrations/ldap.py
2. Update test assertions to match actual validation behavior
3. Investigate LDAP Docker integration test setup (requires Docker daemon?)
4. Debug macOS platform detection logic in podman.py
