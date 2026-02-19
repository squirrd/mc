---
created: 2026-02-19T21:23
title: Address orphaned helper functions from v2.0.4
area: planning
files:
  - src/mc/config/manager.py:172-218
  - src/mc/runtime.py:147-176
  - src/mc/version_check.py:318-332
---

## Problem

The v2.0.4 Foundation milestone audit identified 3 orphaned helper functions that are exported but not currently used in production code. These functions are fully tested and functional, but represent potential API surface that could confuse future developers.

**Orphaned functions:**

1. **ConfigManager.update_version_config()** (manager.py:172-218)
   - Designed for simple 2-field updates (pinned_mc, last_check)
   - VersionChecker needs 5-field updates (etag, latest_known, latest_known_at, last_notification, last_status_code)
   - Currently, VersionChecker manually constructs config dict and calls save_atomic() directly

2. **should_check_for_updates()** (runtime.py:147-176)
   - Wrapper around get_runtime_mode() with Rich Console messaging
   - CLI uses direct `get_runtime_mode() != 'agent'` check instead
   - Provides better UX with informational message "Updates managed via container builds"

3. **check_for_updates()** (version_check.py:318-332)
   - Convenience wrapper around VersionChecker instantiation
   - CLI instantiates VersionChecker() directly and calls start_background_check()

All functions have 100% test coverage and are production-ready, just not currently called.

## Solution

Options to consider for v2.0.5 or later:

**Option A: Document and keep** (lowest effort)
- Add docstring notes explaining when to use each function
- Document in PROJECT.md design decisions
- Keep as available utilities for future features

**Option B: Use in production** (better UX)
- Replace `get_runtime_mode() != 'agent'` with `should_check_for_updates()` in main.py:182
- Benefit: Shows informational message to users in agent mode
- Cost: Minimal - just changing function call

**Option C: Remove unused exports** (cleaner API)
- Keep functions as internal helpers (remove from __all__ or mark private with _)
- update_version_config() stays for simple use cases
- check_for_updates() made internal convenience
- Benefit: Cleaner public API surface
- Cost: Breaking change if anyone depends on these

**Option D: Extend for v2.0.5 needs**
- Enhance update_version_config() to support arbitrary fields
- Use should_check_for_updates() in CLI for better messaging
- Extend check_for_updates() to support pinning/unpinning workflow

**Recommendation:** Start with Option A (document) for v2.0.4 completion, then revisit Option B or D during v2.0.5 planning when auto-update UX requirements are clearer.

## Context

From v2.0.4 milestone audit (.planning/v2.0.4-MILESTONE-AUDIT.md):
- Tech debt items identified as non-critical
- All functions fully tested (Phase 26: 11 tests, Phase 27: 27 tests, Phase 28: 29 tests)
- No blocking issues for milestone completion
- Noted as "available for future use"

This is an API design question, not a bug. Functions work correctly, just not currently needed in the execution paths.
