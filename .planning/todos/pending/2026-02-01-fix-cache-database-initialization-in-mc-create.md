---
created: 2026-02-01T21:15
title: Fix cache database initialization in mc create command
area: api
files:
  - src/mc/cli/commands/case.py:230
  - src/mc/utils/cache.py:79
---

## Problem

The `mc create <case>` command crashes on execution with:

```
sqlite3.OperationalError: no such table: case_metadata
```

**Stack trace:**
```python
File "/Users/dsquirre/Repos/mc/src/mc/cli/commands/case.py", line 230, in create
    age_minutes = get_cached_age_minutes(case_number)
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
File "/Users/dsquirre/Repos/mc/src/mc/utils/cache.py", line 79, in _get_connection
    yield conn
sqlite3.OperationalError: no such table: case_metadata
```

**Root cause:** The cache database (`~/.mc/cache/case_metadata.db`) is not being initialized before first use. The `mc create` command calls `get_cached_age_minutes()` which expects the database schema to already exist.

**Reproduction:**
```bash
mc create 04363691  # Works first time (creates workspace)
mc create 04363691  # Crashes second time (tries to check cache age)
```

## Solution

**Option 1: Lazy initialization in cache module**
- Add schema creation to `_get_connection()` if database doesn't exist
- Use `CREATE TABLE IF NOT EXISTS` pattern
- Ensures cache database always has correct schema

**Option 2: Explicit initialization on first access**
- Add `initialize_cache_db()` function to cache.py
- Call from CacheManager constructor or first database operation
- More explicit but requires coordination

**Recommended: Option 1** - Lazy initialization is more robust and handles edge cases (database deleted, corrupted, etc.)

**Implementation:**
```python
# In src/mc/utils/cache.py _get_connection()
def _get_connection(self):
    conn = sqlite3.connect(self.db_path, timeout=30)
    conn.row_factory = sqlite3.Row

    # Ensure schema exists
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS case_metadata (
            case_number TEXT PRIMARY KEY,
            account_name TEXT,
            case_summary TEXT,
            cached_at INTEGER NOT NULL
        )
    ''')
    conn.commit()

    yield conn
    conn.close()
```

**Testing:**
- Test fresh install (no cache database)
- Test after cache database deletion
- Test normal operation (database exists)
- Verify both `mc create` runs succeed
