# Skill: fix-integration-tests

**Command:** `/fix-integration-tests`

**Description:** Automated integration test failure diagnosis and parallel bug fixing using subagents

## Objective

Systematically fix all failing integration tests by:
1. Running full integration test suite
2. Collecting failures
3. Spawning parallel subagents to analyze and fix bugs
4. Creating separate git branches for independent fixes
5. Verifying all fixes work together

## Context

Integration tests often fail for different reasons:
- Real bugs in source code (needs code fix)
- Outdated test expectations (needs test fix)
- Environment issues (needs skip conditions)

This skill parallelizes the debugging and fixing process.

## Process

### Phase 1: Test Discovery (Sequential Agent)

**Agent Type:** `general-purpose`
**Goal:** Run all integration tests and collect failures

**Tasks:**
1. Run integration tests:
   ```bash
   uv run pytest tests/integration/ -v --no-cov --tb=short
   ```

2. Parse output to identify:
   - Failed test names (e.g., `test_case_terminal.py::test_fresh_install`)
   - Error messages
   - Failure types (assertion, exception, etc.)

3. Create structured failure report:
   ```json
   {
     "failures": [
       {
         "test_id": "test_case_terminal.py::test_fresh_install",
         "error": "KeyError: 'base_directory'",
         "category": "bug"
       }
     ]
   }
   ```

4. If no failures → Success! Exit.
5. If failures → Continue to Phase 2

### Phase 2: Parallel Analysis (Concurrent Agents)

**Agent Type:** `general-purpose` (one per failure)
**Parallelism:** Launch N agents concurrently (max 5 at once)

**For each failure, spawn agent with task:**

```
Analyze integration test failure: {test_id}

**Test:** {test_file}::{test_name}
**Error:** {error_message}

**Your task:**
1. Read the test code: {test_file}
2. Understand what the test expects
3. Run the test to reproduce: uv run pytest {test_id} -v -s
4. Categorize the failure:
   - REAL_BUG: Bug in source code that needs fixing
   - TEST_ISSUE: Test has wrong expectations
   - ENV_ISSUE: Missing credentials/environment
5. Identify root cause
6. Determine files to fix

**Output format:**
- Category: [REAL_BUG|TEST_ISSUE|ENV_ISSUE]
- Root cause: [1-2 sentence explanation]
- Files to fix: [list of file paths]
- Confidence: [high|medium|low]
```

**Collect results from all analysis agents**

### Phase 3: Parallel Fixing (Concurrent Agents, Separate Branches)

**Agent Type:** `general-purpose` (one per REAL_BUG)
**Parallelism:** Launch N agents concurrently (max 3 at once)
**Git Strategy:** Each agent works in separate branch

**For each REAL_BUG, spawn agent with task:**

```
Fix integration test bug: {test_name}

**Context from analysis:**
- Root cause: {root_cause}
- Files to fix: {files_to_fix}
- Test: {test_id}

**Workflow:**
1. Create fix branch:
   git checkout -b {branch_name}

2. Fix the bug in source code
   - Edit: {files_to_fix}
   - Apply fix based on root cause

3. Verify fix locally:
   uv run pytest {test_id} -v -s

4. If test passes:
   - Commit fix with message:
     ```
     fix: {description}

     Fixes integration test: {test_name}
     Root cause: {root_cause}
     ```
   - Return SUCCESS

5. If test still fails:
   - Return FAILED with details

6. Return to main branch:
   git checkout {original_branch}

**Output:**
- Status: [SUCCESS|FAILED]
- Branch: {branch_name}
- Commit SHA: {sha} (if SUCCESS)
- Details: [what was fixed or why it failed]
```

**Collect results from all fix agents**

### Phase 4: Integration & Verification (Sequential Agent)

**Agent Type:** `general-purpose`
**Goal:** Merge all fixes and verify together

**Tasks:**

1. Checkout main branch
2. For each successful fix:
   - Cherry-pick or merge the commit

3. Run full integration test suite:
   ```bash
   uv run pytest tests/integration/ -v --no-cov
   ```

4. If all tests pass:
   - Success! All bugs fixed
   - Optionally push to remote

5. If some tests fail:
   - Identify conflicts or regressions
   - Report which fixes work together
   - May need manual intervention

### Phase 5: Report Generation (Sequential Agent)

**Generate final report:**

```markdown
# Integration Test Fix Report

**Date:** {timestamp}
**Original failures:** {N}
**Fixed:** {M}
**Remaining:** {N-M}

## Summary

- ✅ Fixed {M} bugs across {X} files
- ⚠️  {P} test issues identified (need test updates)
- ⏭️  {Q} environment issues (added skip conditions)

## Fixes Applied

1. **test_fresh_install_missing_config** → Branch: fix/fresh-install
   - File: src/mc/terminal/attach.py:165,200
   - Fix: Use config.get() with default fallback
   - Commit: abc123f

## Branches Created

- fix/fresh-install (MERGED)
- fix/container-workspace (MERGED)
- fix/config-migration (OPEN - needs review)

## Next Steps

- [ ] Review remaining {N-M} failures
- [ ] Merge open branches manually if needed
- [ ] Update REGRESSION_TESTS.md
```

## Usage Examples

### Basic Usage

```bash
# Run the skill
/fix-integration-tests

# The skill will:
# 1. Run all integration tests
# 2. Find failures
# 3. Spawn parallel agents to fix
# 4. Merge fixes
# 5. Verify all tests pass
```

### With Options

```bash
# Dry run (don't make changes)
/fix-integration-tests --dry-run

# Fix specific test file only
/fix-integration-tests tests/integration/test_case_terminal.py

# Limit parallelism
/fix-integration-tests --max-parallel 2
```

## Agent Communication

Agents communicate through:
- **Git branches** - Each fix in separate branch
- **Shared state file** - `.fix-integration-tests/state.json`
- **Main orchestrator** - Coordinates and merges results

## Safety Features

1. **Branch isolation** - Each fix in separate branch, no conflicts
2. **Rollback** - Original branch preserved, easy to rollback
3. **Verification** - Full test suite run after merging all fixes
4. **Manual fallback** - If automation fails, provides manual instructions

## Success Criteria

- [ ] All integration tests identified
- [ ] Failures categorized correctly
- [ ] Bugs fixed in parallel
- [ ] Fixes don't conflict
- [ ] All tests pass after merging
- [ ] Clean git history
- [ ] Report generated

## Implementation Notes

**Parallel Execution:**
- Use Task tool to spawn subagents
- Pass `run_in_background=True` for parallelism
- Use TaskOutput to collect results

**Example spawning parallel analysis agents:**
```python
# Spawn 3 analysis agents in parallel
Task(
  subagent_type="general-purpose",
  description="Analyze test failure 1",
  prompt="...",
  run_in_background=True
)
Task(
  subagent_type="general-purpose",
  description="Analyze test failure 2",
  prompt="...",
  run_in_background=True
)
Task(
  subagent_type="general-purpose",
  description="Analyze test failure 3",
  prompt="...",
  run_in_background=True
)
```

**Branch management:**
- Each fix agent creates unique branch: `fix/{test-name}-{timestamp}`
- Agents work independently, no race conditions
- Main orchestrator merges when ready

## Extension Points

This skill can be extended to:
- Fix unit tests (`/fix-unit-tests`)
- Fix E2E tests (`/fix-e2e-tests`)
- Auto-create regression tests for each bug
- Generate PR with all fixes
- Auto-deploy to staging for verification
