---
created: 2026-02-01T18:41
title: Fix UAT test plan - mc container ls should be mc container list
area: docs
files:
  - .planning/UAT-TEST-PLAN.md:139,159,168,528
---

## Problem

The UAT test plan documentation uses the command `mc container ls` but the actual CLI command is `mc container list`. The `ls` subcommand does not exist and causes confusion during manual testing.

**Discovered during:** Test 2.2 (List Containers) in manual UAT testing

**Occurrences in UAT-TEST-PLAN.md:**
- Line 139: Test 2.2 command example
- Line 159: Test 2.3 verification step
- Line 168: Test 2.3 verification step
- Line 528: Test 8.1 end-to-end workflow step

**User impact:**
Testers following the UAT test plan encounter command not found errors and need to discover the correct command through trial and error or by running `mc container --help`.

## Solution

Update all 4 occurrences in `.planning/UAT-TEST-PLAN.md` to use the correct command:

```bash
# Change from:
mc container ls

# To:
mc container list
```

This is a straightforward find-and-replace operation with no code changes needed.
