---
created: 2026-02-01T12:30
title: Fix workspace path structure to use cases/<customer>/<case>-<description>
area: containers
files:
  - src/mc/container/manager.py
  - src/mc/cli/commands/container.py
---

## Problem

Container workspace paths are currently created as `/Users/dsquirre/mc/<case>` but should follow the structure `/Users/dsquirre/mc/cases/<customer>/<case>-<description>`.

Current output from `mc container list`:
```
CASE         STATUS     CUSTOMER             WORKSPACE PATH                           CREATED
------------------------------------------------------------------------------------------------------
04347611     running    IBM                  /Users/dsquirre/mc/04347611              2026-02-01 12:23:36
```

Expected:
```
04347611     running    IBM                  /Users/dsquirre/mc/cases/IBM/04347611-<description>
```

This affects workspace organization and makes it harder to navigate cases by customer.

## Solution

Update workspace path generation in container manager to:
1. Include `cases/` subdirectory
2. Nest under customer name
3. Append case description to directory name (from Salesforce metadata)

Likely needs changes to:
- Path resolution logic in container manager
- Directory creation in container lifecycle
- Display formatting in `mc container list` command
