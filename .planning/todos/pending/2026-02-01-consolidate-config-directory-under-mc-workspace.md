---
created: 2026-02-01T20:56
title: Consolidate config directory under ~/mc workspace
area: config
files:
  - src/mc/config/manager.py
  - platformdirs usage in codebase
---

## Problem

MC currently scatters files across multiple locations:
- Config: `~/.mc/config.toml` (via platformdirs user_config_dir)
- State database: `~/Library/Application Support/mc/containers.db` on macOS (via platformdirs user_data_dir)
- Cache: `~/.mc/cache/case_metadata.db` (custom location)
- Workspaces: `~/mc/<customer>/<case>/` (configurable base_directory)

This creates a fragmented user experience where MC-related files are scattered. Users need to know multiple locations to find MC data, config, and state.

**User request:** Move everything under `~/mc/` to consolidate all MC-related files in one discoverable location.

## Solution

Consolidate to single directory structure:

```
~/mc/
├── config/
│   ├── config.toml          (moved from ~/.mc/config.toml)
│   └── cache/
│       └── case_metadata.db (moved from ~/.mc/cache/)
├── state/
│   └── containers.db        (moved from ~/Library/Application Support/mc/)
└── cases/
    └── <customer>/
        └── <case>/
```

**Implementation approach:**

1. **Config migration:**
   - Update ConfigManager to use `~/mc/config/config.toml` instead of platformdirs
   - Add migration logic to auto-move existing `~/.mc/config.toml` on first run
   - Fall back to old location if new location doesn't exist (backwards compatibility)

2. **State database migration:**
   - Update state database path from platformdirs.user_data_dir() to `~/mc/state/`
   - Auto-migrate existing database on first run
   - Preserve database contents during migration

3. **Cache migration:**
   - Update cache path from `~/.mc/cache/` to `~/mc/config/cache/`
   - Auto-migrate on first run

4. **Documentation updates:**
   - Update INSTALL.md, README.md with new paths
   - Update UAT test plan with new config location
   - Document migration behavior

**Benefits:**
- Single `~/mc/` directory to backup/restore
- Easier for users to find config and troubleshoot
- Cleaner directory structure
- Aligns workspace and config in same hierarchy

**Backwards compatibility:**
- Auto-migration on first run after upgrade
- Fallback reads from old locations if new locations don't exist
- Deprecation warnings logged when old locations used

**Testing:**
- Test fresh install to new location
- Test migration from old location
- Test fallback when new location missing
- Test on both macOS and Linux
