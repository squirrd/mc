---
created: 2026-01-22T20:05
title: Fix Phase 8 type annotation cosmetic gaps
area: config
files:
  - src/mc/config/manager.py:19
  - src/mc/config/models.py
  - src/mc/config/wizard.py
---

## Problem

Phase 8 (Type Safety & Modernization) verification found 2 minor cosmetic issues that prevent 100% type coverage and full modern syntax adoption:

1. **Missing return type**: ConfigManager.__init__ (src/mc/config/manager.py:19) lacks `-> None` return type annotation, leaving type coverage at 98% (63/64 functions) instead of 100%

2. **Old-style typing syntax**: Config module files (manager.py, models.py, wizard.py) still use `Dict[str, Any]` instead of modern Python 3.11+ syntax `dict[str, Any]`, creating inconsistency with the rest of the codebase

**Impact**: Cosmetic only - mypy passes with zero errors, code works correctly. These are style consistency issues discovered during Phase 8 VERIFICATION.md review (score: 4/5).

## Solution

Update 3 config module files to use modern syntax:

1. Change `from typing import Dict, Any` to `from typing import Any`
2. Replace all `Dict[str, Any]` with `dict[str, Any]` in type annotations
3. Add `-> None` return type to ConfigManager.__init__ method

This achieves 100% type coverage and full modern syntax consistency across the codebase.
