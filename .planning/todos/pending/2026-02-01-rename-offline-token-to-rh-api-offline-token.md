---
created: 2026-02-01T15:22
title: Rename offline_token config to rh_api_offline_token
area: config
files:
  - src/mc/config/models.py
  - README.md:59
  - INSTALL.md:287
  - .planning/UAT-TEST-PLAN.md:54-56
---

## Problem

The config variable `offline_token` in `config.toml` is too generic and doesn't clearly indicate it's specifically for Red Hat API authentication. This creates ambiguity:

1. **Unclear purpose**: New users may not understand what service this token is for
2. **Future extensibility**: If other services require offline tokens (LDAP, OpenShift, etc.), the generic name causes confusion
3. **Documentation mismatch**: Docs refer to "Red Hat API offline token" but config uses generic `offline_token`
4. **Misleading name**: Previously considered `salesforce_offline_token`, but this is incorrect - the token is for Red Hat API (which happens to provide access to Salesforce data through their gateway)

Current config structure:
```toml
[api]
offline_token = "your_token_here"
```

## Solution

Rename to `rh_api_offline_token` for clarity (reflects actual API being accessed):

```toml
[api]
rh_api_offline_token = "your_token_here"
```

**Changes required:**
1. Update `src/mc/config/models.py` to use new field name
2. Add backwards compatibility: Check for old `offline_token` name and migrate/warn
3. Update all documentation (README.md, INSTALL.md, UAT-TEST-PLAN.md)
4. Update config wizard in `src/mc/config/wizard.py` to use new name
5. Consider adding migration helper that renames field in existing config files

**Alternative considered:** Nested structure like `[api.salesforce]` with `offline_token` underneath, but this may be over-engineering for current needs.
