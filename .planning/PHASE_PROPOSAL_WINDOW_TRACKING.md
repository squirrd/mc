# Phase Proposal: iTerm2 Window Tracking System

**Status:** Proposed
**Priority:** Medium
**Estimated Effort:** 4-6 hours
**Depends On:** None
**Related Issue:** Integration test `test_duplicate_terminal_prevention_regression` failing

---

## Goal

Enable duplicate terminal prevention by tracking window IDs instead of searching by title, solving the iTerm2 AppleScript limitation where session names are overwritten when commands execute.

---

## Problem Statement

Currently, `mc case XXXXX` creates duplicate terminal windows when run multiple times because:

1. iTerm2's session `name` property gets completely replaced when `podman exec` runs
2. Search by title fails because original title is gone
3. AppleScript has no property that persists the custom title during command execution

**Evidence:** Analysis agent tested 5+ approaches, all failed due to iTerm2 API limitations.

---

## Solution Approach

Implement window registry system that tracks window/tab IDs at creation time:

```python
# When creating window:
window_id = create_iterm_window(title, command)
registry.store(case_number, window_id)

# When searching for window:
window_id = registry.lookup(case_number)
if window_exists(window_id):
    focus_window(window_id)
else:
    create_new_window()
```

---

## Tasks

### 1. Design Window Registry Schema
- [ ] Define registry structure (SQLite table or JSON file)
- [ ] Schema: `(case_number TEXT PRIMARY KEY, window_id TEXT, tab_id TEXT, created_at INTEGER)`
- [ ] Location: `~/mc/state/window_registry.db` or integrate with existing StateDatabase
- [ ] Decide: Separate file or extend StateDatabase?

### 2. Implement Registry Storage
- [ ] Create WindowRegistry class
- [ ] Methods: `store(case, window_id)`, `lookup(case)`, `remove(case)`, `cleanup_stale()`
- [ ] Handle concurrent access (file locking or database transaction)
- [ ] Add tests for registry operations

### 3. Capture Window IDs on Creation
- [ ] Update `_build_iterm_script()` to return window ID
- [ ] AppleScript: `tell application "iTerm" ... return id of current window`
- [ ] Store captured ID in registry immediately after launch
- [ ] Handle errors if ID capture fails

### 4. Update Search to Use Registry
- [ ] Modify `find_window_by_title()`:
  ```python
  def find_window_by_title(self, title):
      case = extract_case_number(title)
      window_id = self.registry.lookup(case)
      if window_id:
          return self._window_exists_by_id(window_id)
      return False  # Fallback to old search?
  ```
- [ ] Add `_window_exists_by_id(window_id)` AppleScript helper
- [ ] Decide: Fallback to title search if ID not in registry?

### 5. Update Focus to Use Registry
- [ ] Modify `focus_window_by_title()` similarly
- [ ] Focus by ID instead of title
- [ ] Return to title-based focus if ID fails

### 6. Implement Cleanup Mechanism
- [ ] Detect when windows are closed
- [ ] Remove stale entries from registry
- [ ] Run cleanup on startup or periodically
- [ ] AppleScript: Check if window ID still exists

### 7. Handle Edge Cases
- [ ] What if user manually closes window?
- [ ] What if registry file is deleted?
- [ ] What if window exists but is in different space/desktop?
- [ ] Migration path for existing users

### 8. Update Tests
- [ ] Verify `test_duplicate_terminal_prevention_regression` passes
- [ ] Add unit tests for WindowRegistry class
- [ ] Test cleanup mechanism
- [ ] Test edge cases (deleted registry, stale entries)

### 9. Documentation
- [ ] Update docstrings for modified functions
- [ ] Document window registry architecture
- [ ] Add troubleshooting guide
- [ ] Update INTEGRATION_TEST_BEST_PRACTICES.md with case study

---

## Success Criteria

- [ ] `test_duplicate_terminal_prevention_regression` passes
- [ ] Running `mc case XXXXX` twice focuses existing window, doesn't create duplicate
- [ ] Window registry persists across mc process restarts
- [ ] Stale entries are cleaned up automatically
- [ ] No regressions in other integration tests
- [ ] Performance: Window lookup is fast (< 100ms)

---

## Implementation Notes

### AppleScript for Window ID Capture

```applescript
tell application "iTerm"
    activate
    create window with default profile
    tell current session of current window
        set name to "CASE:Customer:Description:/path"
        write text "podman exec ..."
    end tell
    -- Capture and return window ID
    return id of current window
end tell
```

### AppleScript for ID-based Search

```applescript
tell application "iTerm"
    repeat with theWindow in windows
        if id of theWindow is TARGET_ID then
            return true
        end if
    end repeat
    return false
end tell
```

### Registry Storage Options

**Option A: SQLite (Recommended)**
- Pro: Concurrent access, ACID guarantees, already using for StateDatabase
- Con: Slightly more complex
- File: `~/mc/state/window_registry.db`

**Option B: JSON File**
- Pro: Simple, human-readable
- Con: No concurrent access protection, manual locking needed
- File: `~/mc/state/window_registry.json`

**Recommendation:** Use SQLite, integrate with existing StateDatabase

---

## Risks and Mitigations

### Risk: Window ID format changes between iTerm2 versions
**Mitigation:** Test with multiple iTerm2 versions, add version detection

### Risk: Registry corruption
**Mitigation:** Add validation on load, rebuild from scratch if corrupted

### Risk: Performance degradation with many entries
**Mitigation:** Add index on case_number, implement periodic cleanup

### Risk: User confusion if registry out of sync
**Mitigation:** Add `mc container reconcile` command to rebuild registry

---

## Alternative Approaches (Considered and Rejected)

### Option B: Pre-Execution Search
**Rejected:** Race conditions, timing-dependent, fragile

### Option C: iTerm2 Python API
**Deferred:** Requires new dependency, async complexity, future enhancement

### Option D: AppleScript Property Tricks
**Rejected:** Extensive testing showed no properties persist during command execution

---

## Dependencies

- **Code:** None (self-contained change)
- **External:** iTerm2 must be installed (already required)
- **Data:** Existing StateDatabase at `~/mc/state/containers.db`

---

## Testing Strategy

### Unit Tests
```python
def test_registry_store_and_lookup():
    registry = WindowRegistry()
    registry.store("12345678", "window-id-abc")
    assert registry.lookup("12345678") == "window-id-abc"

def test_registry_cleanup_stale():
    # Create entries with old timestamps
    # Verify cleanup removes them
```

### Integration Tests
```python
def test_duplicate_prevention_with_registry():
    # First call: create window, check registry
    attach_terminal("12345678", ...)
    assert registry.lookup("12345678") is not None

    # Second call: should find and focus
    attach_terminal("12345678", ...)
    # Verify only one window exists (no duplicate)
```

### Manual Tests
1. Run `mc case XXXXX` - verify window opens
2. Run `mc case XXXXX` again - verify focus, no new window
3. Close window manually, run `mc case XXXXX` - verify new window created
4. Restart mc process, run `mc case XXXXX` - verify registry persists

---

## Rollback Plan

If implementation causes issues:

1. Revert commit(s)
2. Restore old `find_window_by_title()` behavior
3. Users experience old behavior (duplicate windows)
4. No data loss (registry is additive, doesn't modify existing data)

---

## Future Enhancements

### Phase 2: iTerm2 Python API Migration
- Use `iterm2` Python package
- More robust, modern API
- Better property access
- Async support

### Phase 3: Cross-Session Synchronization
- Sync registry across multiple mc instances
- Handle case where multiple users work on same machine

### Phase 4: Window Workspace Support
- Track which macOS Space/Desktop the window is on
- Focus window and switch to its Space

---

## Estimated Timeline

- **Design + Schema:** 1 hour
- **Registry Implementation:** 2 hours
- **MacOSLauncher Updates:** 2 hours
- **Cleanup Mechanism:** 1 hour
- **Testing:** 1.5 hours
- **Documentation:** 0.5 hours

**Total:** 8 hours (conservative estimate with buffer)

---

## Related Files

- Implementation: `src/mc/terminal/macos.py`
- Storage: `src/mc/state/database.py` (if integrating with StateDatabase)
- Tests: `tests/integration/test_case_terminal.py`
- Analysis: `.planning/INTEGRATION_TEST_FIX_REPORT.md`

---

## References

- Full Analysis: `.planning/INTEGRATION_TEST_FIX_REPORT.md`
- AppleScript Testing: See analysis agent output (extensive experimentation documented)
- Integration Test Best Practices: `docs/INTEGRATION_TEST_BEST_PRACTICES.md`
- UAT 5.2 Test: `.planning/UAT-TESTS-BATCH-ABCE.md`

---

**Proposal Date:** 2026-02-04
**Proposed By:** Automated analysis from `/fix-integration-tests`
**Confidence:** High (problem well-understood, solution validated conceptually)
**Complexity:** Medium (new component, multiple integration points)
