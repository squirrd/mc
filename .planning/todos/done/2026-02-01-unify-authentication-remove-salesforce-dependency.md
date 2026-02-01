---
created: 2026-02-01T18:26
title: Unify authentication - remove direct Salesforce dependency from container commands
area: auth
files:
  - src/mc/terminal/attach.py:90-143
  - src/mc/cli/commands/container.py:161-214
  - src/mc/integrations/salesforce_api.py
  - src/mc/utils/cache.py:206-243
---

## Problem

Container commands (`mc case <number>`, `mc <number>`) use direct Salesforce API authentication while workspace commands (`mc create`, `mc check`) use Red Hat API authentication. This creates two separate authentication paths that are redundant and confusing:

**Current behavior:**
- `mc create 04363690` - ✅ Works with `api.offline_token` in config.toml
- `mc 04363690` - ❌ Fails with "Salesforce credentials not configured" error

**Why this happened:**
Phase 10 (Salesforce Integration) implemented direct `SalesforceAPIClient` for container features, but v1.0 commands already had working Red Hat API integration. The container features created a parallel authentication system instead of reusing the existing `get_case_metadata()` function.

**Technical details:**
- `attach_terminal()` in `src/mc/terminal/attach.py` lines 132-142 calls `salesforce_client.get_case(case_number)` directly
- `case_terminal()` in `src/mc/cli/commands/container.py` lines 175-197 requires separate Salesforce credentials (username, password, security_token)
- Red Hat API already provides access to the same Salesforce case metadata through their API gateway
- `get_case_metadata()` in `src/mc/utils/cache.py` uses `RedHatAPIClient` with caching - already implemented and working

**User impact:**
Users need to configure both `api.offline_token` AND `salesforce.username/password/security_token` even though they access the same data through different paths.

## Solution

Unify authentication to use only Red Hat API with offline_token:

1. **Refactor `attach_terminal()` function:**
   - Replace `SalesforceAPIClient` parameter with `RedHatAPIClient`
   - Call `get_case_metadata(case_number, api_client)` instead of `salesforce_client.get_case()`
   - Reuse existing caching infrastructure (5-minute TTL, SQLite cache)

2. **Update `case_terminal()` in container.py:**
   - Remove Salesforce credential validation (lines 175-190)
   - Initialize RedHatAPIClient with offline_token (same pattern as `mc create`)
   - Pass RedHatAPIClient to `attach_terminal()`

3. **Remove Salesforce config requirement:**
   - Update `src/mc/config/models.py` to make `salesforce` section optional
   - Document that Salesforce credentials only needed for future direct integrations (if any)

4. **Update tests:**
   - Update mocks in terminal/attach tests to use RedHatAPIClient
   - Verify integration tests pass with only offline_token configured

**Benefits:**
- Single authentication path (Red Hat API)
- Single credential to configure (offline_token)
- Consistent error messages
- Reuse existing caching infrastructure
- Simpler onboarding for new users

**Follow-up work:**
After this change, evaluate if todo "2026-02-01-rename-offline-token-to-salesforce-offline-token.md" is still needed, as "offline_token" becomes unambiguous when it's the only auth method.
