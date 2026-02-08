# GSD Quick Start - Integration Test Fixes

**Created:** 2026-02-04
**Context:** Automated integration test fix session completed

---

## 📋 What Happened

Ran `/fix-integration-tests --all` which:
- ✅ Fixed 1 of 2 failing integration tests (terminal title format)
- ⚠️ Identified 1 test requiring architectural changes (duplicate terminal prevention)
- 📊 Created detailed analysis and proposals for next steps

---

## 🚀 Recommended GSD Commands

### Option 1: Add as a New Phase to Current Milestone

If you're already working in GSD mode and want to add this fix:

```bash
/gsd:add-phase
```

**When prompted:**
- **Phase name:** "Implement iTerm2 Window Tracking"
- **Description:** "Fix duplicate terminal prevention by tracking window IDs instead of searching by title"
- **Reference:** `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md`

This will add the phase to your current milestone roadmap.

---

### Option 2: Create Dedicated Milestone for Bug Fixes

If you want to treat this as a separate milestone:

```bash
/gsd:new-milestone
```

**When prompted:**
- **Milestone name:** "Integration Test Fixes v2"
- **Goal:** "Achieve 100% integration test pass rate"

Then add phases:
1. "Implement iTerm2 Window Tracking" (Bug #2 fix)
2. Any other failing tests discovered

---

### Option 3: Quick Fix Without Full GSD Workflow

If you just want to fix it quickly without GSD structure:

```bash
# Review the detailed analysis
cat .planning/INTEGRATION_TEST_FIX_REPORT.md

# Review the implementation plan
cat .planning/PHASE_PROPOSAL_WINDOW_TRACKING.md

# Implement following the tasks section
# Test with:
uv run pytest tests/integration/test_case_terminal.py::test_duplicate_terminal_prevention_regression -v
```

---

## 📁 Files Created for You

### 1. INTEGRATION_TEST_FIX_REPORT.md (Detailed Analysis)
**Location:** `.planning/INTEGRATION_TEST_FIX_REPORT.md`

**Contains:**
- Full root cause analysis for both bugs
- What was fixed (Bug #1: Terminal Title Format)
- Why Bug #2 couldn't be fixed automatically
- Extensive AppleScript experimentation results
- 5+ attempted solutions and why they failed
- Technical debt created
- Lessons learned

**Use this for:** Understanding what happened, explaining to team, documentation

---

### 2. PHASE_PROPOSAL_WINDOW_TRACKING.md (Implementation Plan)
**Location:** `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md`

**Contains:**
- Clear goal statement
- Detailed task breakdown (9 tasks)
- Code examples and AppleScript snippets
- Success criteria
- Testing strategy
- Estimated timeline (8 hours)
- Risk analysis and mitigations
- Alternative approaches considered

**Use this for:** Implementing the fix, GSD phase planning, task tracking

---

### 3. This File (GSD_QUICK_START.md)
**Location:** `.planning/GSD_QUICK_START.md`

**Contains:**
- Quick reference for GSD commands
- Summary of what to do next

---

## 🎯 Current Status

### What's Working ✅
- 61 of 62 integration tests passing (98.4%)
- Bug #1 (terminal title format) fixed and committed
- Comprehensive analysis of Bug #2 completed
- Clear implementation path identified

### What Needs Work ⚠️
- 1 test still failing: `test_duplicate_terminal_prevention_regression`
- Requires architectural change (window ID tracking)
- Estimated 8 hours to implement
- Not a simple code fix - needs design decision

### Next Decision Point 🤔
Do you want to:
1. **Fix it now** → Use one of the GSD commands above
2. **Fix it later** → Create a GitHub issue and add to backlog
3. **Defer indefinitely** → Accept 98.4% pass rate, document limitation

---

## 📝 Recommended Next Steps (In Order)

### Immediate (Today)
1. **Review the analysis:**
   ```bash
   cat .planning/INTEGRATION_TEST_FIX_REPORT.md | less
   ```

2. **Decide on approach:**
   - Quick fix (8 hours)?
   - GSD phase (better tracking)?
   - Defer to backlog?

3. **Clean up uncommitted changes:**
   ```bash
   # Experimental changes in macos.py aren't committed
   git status
   # Either commit the experimental work or reset:
   git checkout src/mc/terminal/macos.py
   ```

### Short-term (This Week)
1. **If fixing now:**
   ```bash
   /gsd:add-phase
   # Name: Implement iTerm2 Window Tracking
   # Then: /gsd:plan-phase
   # Then: /gsd:execute-phase
   ```

2. **If deferring:**
   - Create GitHub issue with `.planning/INTEGRATION_TEST_FIX_REPORT.md` content
   - Reference issue in test docstring
   - Continue with other work

### Medium-term (Next Sprint)
1. Implement window registry system
2. Update MacOSLauncher to use window IDs
3. Add cleanup mechanism
4. Verify test passes
5. Document new architecture

---

## 🔍 Key Insights from Analysis

### Why Automated Fix Failed
iTerm2's AppleScript has a **fundamental limitation**: the session `name` property gets completely replaced when a command executes. No amount of clever searching can find a window whose title has been overwritten.

**This is not a bug in your code** - it's an API limitation that requires a different approach (window ID tracking).

### Why This Is Important
Users running `mc case XXXXX` multiple times will create multiple terminal windows, causing:
- Terminal clutter
- Confusion about which window is which
- Resource waste (multiple containers)
- Poor user experience

### Why Window ID Tracking Solves It
Window/tab IDs don't change when commands execute. By storing the ID at creation time, we can find the window even when its title has been replaced by "podman (exec)".

---

## 💡 Pro Tips

### Using GSD for This Fix

**Advantages:**
- State persistence if you get interrupted
- Better task tracking and progress visibility
- Automatic checkpointing
- Integration with your project workflow

**When to use GSD:**
- You want structured approach
- Might get interrupted mid-work
- Want to track this as part of larger milestone
- Like the phase-based organization

**When NOT to use GSD:**
- Just want to quickly fix it
- Prefer freeform implementation
- Already have your own task tracking

### Quick Fix Strategy (No GSD)

```bash
# 1. Read the implementation plan
cat .planning/PHASE_PROPOSAL_WINDOW_TRACKING.md

# 2. Implement WindowRegistry class
#    Follow "Tasks" section step-by-step

# 3. Test as you go
uv run pytest tests/integration/test_case_terminal.py::test_duplicate_terminal_prevention_regression -v

# 4. Commit when test passes
git add src/mc/terminal/macos.py src/mc/state/registry.py
git commit -m "fix: implement window ID tracking for duplicate terminal prevention"
```

---

## 📞 Questions to Consider

### Before Starting Implementation

1. **Where should window registry live?**
   - Option A: Extend existing StateDatabase (cleaner, one DB)
   - Option B: Separate registry.db file (isolated, simpler)

2. **What happens to existing users?**
   - Registry starts empty, populated as they use mc
   - No migration needed (additive feature)

3. **How to handle cleanup?**
   - Cleanup on startup? (might be slow)
   - Periodic background cleanup? (more complex)
   - Manual `mc container reconcile` command? (user control)

4. **Fallback behavior if registry fails?**
   - Try title search anyway? (might work if window idle)
   - Just create new window? (safer)
   - Show error and ask user? (more transparent)

### During Implementation

1. **Testing strategy:**
   - Unit tests for WindowRegistry class?
   - Integration test with real iTerm2?
   - Both?

2. **Performance considerations:**
   - How many entries can registry hold?
   - Index on case_number?
   - Cleanup threshold?

3. **Error handling:**
   - What if window ID doesn't exist anymore?
   - What if registry is corrupted?
   - What if concurrent access conflicts?

---

## 🎓 What You Learned

From this automated fix session:

1. **Some bugs need architecture changes** - Not all bugs can be fixed with simple code tweaks
2. **Integration tests catch real issues** - Mocking would have hidden the iTerm2 API limitation
3. **Automated analysis is thorough** - Agent tested 10+ approaches to understand the problem
4. **Documentation matters** - Well-documented tests made analysis much easier
5. **Parallel agents are efficient** - Two bugs analyzed simultaneously saved time

---

## 📚 Related Documentation

- **Full Analysis:** `.planning/INTEGRATION_TEST_FIX_REPORT.md`
- **Implementation Plan:** `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md`
- **Integration Test Best Practices:** `docs/INTEGRATION_TEST_BEST_PRACTICES.md`
- **Bug to Test Guide:** `docs/USING_BUG_TO_TEST.md`
- **UAT Test Plan:** `.planning/UAT-TESTS-BATCH-ABCE.md`
- **Regression Tests:** `tests/integration/REGRESSION_TESTS.md`

---

## ✅ Checklist: What to Do Now

- [ ] Read `.planning/INTEGRATION_TEST_FIX_REPORT.md` (detailed analysis)
- [ ] Read `.planning/PHASE_PROPOSAL_WINDOW_TRACKING.md` (implementation plan)
- [ ] Decide: GSD phase, quick fix, or defer?
- [ ] Clean up experimental changes in `src/mc/terminal/macos.py`
- [ ] Update documentation if deferring (mark as known limitation)
- [ ] If fixing: Create GitHub issue for tracking
- [ ] If fixing: Choose storage approach (SQLite vs JSON)
- [ ] If fixing: Run `/gsd:add-phase` or start implementing
- [ ] Push Bug #1 fix: `git push origin main`

---

**Created:** 2026-02-04
**Last Updated:** 2026-02-04
**Status:** Active - Awaiting your decision on next steps
