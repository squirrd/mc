---
created: 2026-02-01T21:54
title: Improve container list output - replace workspace path with description
area: ui
files:
  - src/mc/cli/commands/container.py:79
---

## Problem

The `mc container list` command currently displays the workspace path, which is not particularly useful to users since they can infer it from the case number. The output would be more helpful if it showed the case's short description instead.

**Current output:**
```
CASE         STATUS     CUSTOMER             WORKSPACE PATH                           CREATED
------------------------------------------------------------------------------------------------------
04347611     running    IBM                  /Users/dsquirre/mc/04347611              2026-02-01 12:23:36
```

**Desired output:**
```
CASE         STATUS     CUSTOMER             DESCRIPTION                              CREATED
------------------------------------------------------------------------------------------------------
04347611     running    IBM                  Cannot upload attachments                2026-02-01 12:23:36
```

**Benefits:**
- More useful at-a-glance information (what each container is for)
- Users can identify containers by problem description, not just case number
- Workspace path is predictable and doesn't need to be displayed
- Better user experience when managing multiple containers

## Solution

Update `list_containers()` in `src/mc/cli/commands/container.py`:

**Line 79 - Update header:**
```python
# Change from:
print(f"{'CASE':<12} {'STATUS':<10} {'CUSTOMER':<20} {'WORKSPACE PATH':<40} {'CREATED':<20}")

# To:
print(f"{'CASE':<12} {'STATUS':<10} {'CUSTOMER':<20} {'DESCRIPTION':<40} {'CREATED':<20}")
```

**Update row formatting (likely around line 82-85):**
```python
# Current (approximate):
print(f"{container.case_number:<12} {container.status:<10} {customer:<20} {workspace_path:<40} {created:<20}")

# Change to:
print(f"{container.case_number:<12} {container.status:<10} {customer:<20} {description:<40} {created:<20}")
```

**Data source considerations:**
- Check if `description` is already available in container metadata or needs to be fetched
- May need to query Salesforce API for case short description
- Consider caching descriptions to avoid repeated API calls
- Handle cases where description is unavailable (show "N/A" or truncated case number)

**Edge cases:**
- Long descriptions may need truncation to fit 40-char column width
- Missing/unavailable descriptions should show graceful fallback
- Ensure column alignment works with variable-length descriptions

**Testing:**
- Test with containers that have descriptions
- Test with containers missing descriptions
- Test with very long descriptions (>40 chars)
- Verify column alignment with multiple containers
