---
name: fix-integration-tests
description: Automatically fix failing integration tests using parallel subagents
argument-hint: "optional: specific test file or --all"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - Task
  - AskUserQuestion
  - TodoWrite
---

<objective>
Systematically fix all failing integration tests by:
1. Running full integration test suite and collecting failures
2. Spawning parallel subagents to analyze and fix bugs
3. Creating separate git branches for independent fixes
4. Verifying all fixes work together
5. Optionally creating GSD phases for complex fix scenarios

Works standalone OR integrates with GSD for state management and parallel execution.
</objective>

<context>
@tests/integration/
@docs/INTEGRATION_TEST_BEST_PRACTICES.md
@docs/USING_BUG_TO_TEST.md
@.planning/UAT-TESTS-BATCH-ABCE.md
</context>

<configuration>
# Parallel execution settings
MAX_PARALLEL_ANALYSIS: 5    # Max agents analyzing failures simultaneously
MAX_PARALLEL_FIXES: 3        # Max agents fixing bugs simultaneously (separate branches)

# Git settings
BRANCH_PREFIX: "fix/"        # Branch naming: fix/test-name
CLEANUP_BRANCHES: false      # Keep branches after merging for review

# GSD integration
USE_GSD_PHASES: "ask"        # "always", "never", "ask" (default)
CREATE_PHASE_PER_FIX: true   # Create GSD phase for each fix when using GSD
</configuration>

<process>

<step name="initialize">
**Welcome and Setup**

1. Display welcome message:
```
🔧 Integration Test Fix Orchestrator

This skill will:
✓ Run all integration tests
✓ Identify failures
✓ Spawn parallel agents to fix bugs
✓ Create separate git branches
✓ Verify all fixes together

Use real components following best practices from:
docs/INTEGRATION_TEST_BEST_PRACTICES.md
```

2. Check current state:
```bash
# Get current branch
git branch --show-current

# Check for uncommitted changes
git status --porcelain
```

3. If uncommitted changes, ask user:
   - "You have uncommitted changes. Should I stash them first?"
   - Options: "Yes - stash changes", "No - proceed anyway", "Cancel"

4. Create TodoWrite list for tracking:
```
- Run integration test suite
- Collect and analyze failures
- Spawn parallel fix agents
- Verify all fixes together
- Generate final report
```
</step>

<step name="run_tests">
**Phase 1: Test Discovery** (Sequential)

1. Run full integration test suite:
```bash
cd /Users/dsquirre/Repos/mc
uv run pytest tests/integration/ -v --no-cov --tb=short 2>&1 | tee /tmp/integration_test_results.txt
```

2. Parse test output to identify failures:
   - Extract test IDs (e.g., `test_case_terminal.py::test_fresh_install`)
   - Extract error messages
   - Extract error types (KeyError, AssertionError, RuntimeError, etc.)

3. If NO failures:
   ```
   ✅ All integration tests PASSED!

   Total tests: N
   All green! 🎉

   Nothing to fix. Exiting.
   ```
   Exit successfully.

4. If failures found, display summary:
   ```
   ❌ Found N failing test(s):

   1. test_case_terminal.py::test_fresh_install
      Error: KeyError: 'base_directory'

   2. test_container_create.py::test_workspace_path
      Error: AssertionError: Expected /path/to/workspace

   3. test_config_migration.py::test_migrate_from_old
      Error: FileNotFoundError: Config file not found
   ```

5. Update TodoWrite: Mark "Run integration test suite" as completed

6. Ask user about GSD integration (if USE_GSD_PHASES is "ask"):
```
Would you like to use GSD for managing these fixes?

Options:
- Use GSD phases (recommended for >5 failures)
  Creates phases, better state management, checkpoints

- Standalone mode (simpler, faster for <=5 failures)
  Just fix bugs, no GSD overhead
```
</step>

<step name="analyze_failures">
**Phase 2: Parallel Analysis** (Concurrent Agents)

1. For each failure, create analysis task structure:
```json
{
  "test_id": "test_case_terminal.py::test_fresh_install",
  "test_file": "tests/integration/test_case_terminal.py",
  "test_name": "test_fresh_install",
  "error_message": "KeyError: 'base_directory'",
  "error_type": "KeyError"
}
```

2. Spawn parallel analysis agents (MAX_PARALLEL_ANALYSIS at a time):

For each failure, use Task tool:
```
Task(
  subagent_type="general-purpose",
  description="Analyze test failure: {test_name}",
  prompt="""
Analyze integration test failure: {test_name}

**Test ID:** {test_id}
**Error:** {error_message}

**Your task:**
1. Read the test file: {test_file}
2. Understand what the test expects
3. Run the test to see full error:
   ```
   cd /Users/dsquirre/Repos/mc
   uv run pytest {test_id} -v -s --no-cov
   ```

4. Categorize the failure:
   - **REAL_BUG**: Bug in source code (needs code fix)
   - **TEST_ISSUE**: Test has wrong expectations (needs test fix)
   - **ENV_ISSUE**: Missing credentials/environment (needs skip condition)

5. Identify root cause:
   - Which source file(s) have the bug?
   - What line(s) of code are problematic?
   - What's the fix strategy?

**Output format (JSON):**
```json
{{
  "category": "REAL_BUG|TEST_ISSUE|ENV_ISSUE",
  "root_cause": "One sentence explanation",
  "files_to_fix": ["src/mc/file.py:123"],
  "fix_strategy": "Use config.get() with default fallback",
  "confidence": "high|medium|low"
}}
```

Read docs/INTEGRATION_TEST_BEST_PRACTICES.md for guidance.
""",
  run_in_background=True
)
```

3. Wait for all analysis agents to complete (use TaskOutput)

4. Collect results from each agent:
   - Parse JSON outputs
   - Categorize failures: REAL_BUG, TEST_ISSUE, ENV_ISSUE
   - Prioritize by confidence (high → medium → low)

5. Display analysis summary:
   ```
   📊 Analysis Complete

   REAL_BUG (needs code fix): 5 failures
   - test_fresh_install → src/mc/terminal/attach.py:165
   - test_workspace_path → src/mc/container/manager.py:89
   - ...

   TEST_ISSUE (needs test fix): 2 failures
   - test_old_api_format → tests/integration/test_api.py:45

   ENV_ISSUE (needs skip condition): 1 failure
   - test_ldap_integration → Missing LDAP server
   ```

6. Update TodoWrite: Mark "Collect and analyze failures" as completed

7. Ask user to confirm fixes:
```
Proceed with fixing {N} bugs?

Will create {N} parallel agents in separate git branches.

Options:
- Yes - Fix all {N} bugs in parallel
- Select specific bugs to fix
- Cancel
```
</step>

<step name="create_gsd_phases" condition="if GSD mode enabled">
**Optional: Create GSD Phases**

If user chose to use GSD:

1. For each REAL_BUG, create a GSD phase:
```bash
# This would integrate with GSD's phase creation
# Each phase represents fixing one bug

Phase N: Fix {test_name}
- Analyze: {test_id}
- Identify root cause: {root_cause}
- Fix: {files_to_fix}
- Verify: Test passes
- Commit: With proper message
```

2. GSD benefits:
   - State persistence across context resets
   - Checkpoint/resume capability
   - Better progress tracking
   - Phase dependencies (if fixes conflict)

3. Create `.fix-integration-tests/` directory:
```bash
mkdir -p .fix-integration-tests
```

4. Write state file:
```json
{
  "mode": "gsd",
  "original_branch": "main",
  "total_failures": 5,
  "fixes_in_progress": [],
  "fixes_completed": [],
  "fixes_failed": []
}
```
</step>

<step name="parallel_fixing">
**Phase 3: Parallel Fixing** (Concurrent Agents, Separate Branches)

1. For each REAL_BUG (up to MAX_PARALLEL_FIXES at a time):

Create unique branch name:
```
Branch: fix/{test-name}-{timestamp}
Example: fix/fresh-install-1738540800
```

2. Spawn fix agent for each bug using Task tool:
```
Task(
  subagent_type="general-purpose",
  description="Fix bug: {test_name}",
  prompt="""
Fix integration test bug: {test_name}

**Context from analysis:**
- Root cause: {root_cause}
- Files to fix: {files_to_fix}
- Fix strategy: {fix_strategy}
- Test: {test_id}

**Workflow:**

1. Create fix branch:
   ```bash
   cd /Users/dsquirre/Repos/mc
   git checkout -b {branch_name}
   ```

2. Read the source files:
   - {files_to_fix}
   - Understand current implementation

3. Apply the fix:
   - Use Edit tool to fix the bug
   - Follow fix strategy: {fix_strategy}
   - Apply best practices from docs/INTEGRATION_TEST_BEST_PRACTICES.md

4. Verify fix:
   ```bash
   uv run pytest {test_id} -v -s --no-cov
   ```

5. If test PASSES:
   - Commit the fix:
     ```bash
     git add {files_to_fix}
     git commit -m "fix: {description}

     Fixes integration test: {test_name}
     Root cause: {root_cause}

     Changes:
     - {files_to_fix}

     Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
     ```
   - Return to original branch:
     ```bash
     git checkout {original_branch}
     ```
   - Output: SUCCESS with commit SHA

6. If test STILL FAILS:
   - Document what was tried
   - Return to original branch (don't commit broken fix)
   - Output: FAILED with details

**Output format (JSON):**
```json
{{
  "status": "SUCCESS|FAILED",
  "branch": "{branch_name}",
  "commit_sha": "abc123f" (if SUCCESS),
  "test_passed": true|false,
  "details": "What was fixed or why it failed"
}}
```

**IMPORTANT:**
- Use REAL components in tests (docs/INTEGRATION_TEST_BEST_PRACTICES.md)
- Minimal mocking (only TTY, time, external services)
- Real API clients, Podman, databases
- Proper cleanup in finally blocks
""",
  run_in_background=True
)
```

3. Track agent progress with TodoWrite:
   - One todo per fix
   - Update status as agents report back

4. Wait for all fix agents to complete

5. Collect results:
   - Parse JSON outputs
   - Track successful vs failed fixes
   - Store commit SHAs for successful fixes

6. Display fix summary:
   ```
   🔧 Fix Results

   ✅ Successfully fixed: 4/5
   - test_fresh_install → Branch: fix/fresh-install-1738540800
     Commit: abc123f

   - test_workspace_path → Branch: fix/workspace-path-1738540801
     Commit: def456a

   ❌ Failed to fix: 1/5
   - test_config_migration → Error: Still failing after fix attempt
     Needs manual investigation
   ```

7. Update TodoWrite: Mark "Spawn parallel fix agents" as completed
</step>

<step name="integration_verification">
**Phase 4: Integration & Verification** (Sequential)

1. Collect all successful fixes:
   - List of branches
   - List of commit SHAs

2. Strategy for merging:

**Option A: Cherry-pick commits (cleaner)**
```bash
# Stay on main/original branch
git checkout {original_branch}

# Cherry-pick each successful fix
git cherry-pick {commit_sha_1}
git cherry-pick {commit_sha_2}
...
```

**Option B: Merge branches (preserves branch history)**
```bash
git checkout {original_branch}
git merge --no-ff {branch_1}
git merge --no-ff {branch_2}
...
```

3. Run full integration test suite:
```bash
uv run pytest tests/integration/ -v --no-cov
```

4. Analyze results:

**If ALL tests pass:**
```
✅ SUCCESS! All fixes integrated successfully

Original failures: {N}
Fixed: {M}
All tests now passing: {total_tests}

Fixes applied:
- {commit_sha_1}: Fix fresh install base_directory bug
- {commit_sha_2}: Fix workspace path formatting
...

All changes are on branch: {original_branch}
```

**If some tests FAIL:**
```
⚠️ Some tests still failing after integration

Passed: {X}/{total_tests}
Failed: {Y}

Conflicts or regressions detected:
- {test_id_1} → Was passing, now failing (regression!)
- {test_id_2} → Still failing (fix didn't work in integration)

Action needed:
1. Review conflicts between fixes
2. May need manual resolution
3. Some fixes might conflict with each other
```

5. Clean up branches (optional):
```bash
# If CLEANUP_BRANCHES is true and all tests pass
git branch -d {branch_1}
git branch -d {branch_2}
...
```

6. Update TodoWrite: Mark "Verify all fixes together" as completed
</step>

<step name="update_documentation">
**Update Documentation**

1. Update tests/integration/REGRESSION_TESTS.md:

For each successfully fixed test:
```markdown
| test_{name} | UAT X.Y | {date} | Passing ✓ | test_{file}.py |

**Fixed in:** v{version} (or commit {sha})
```

2. Update .planning/UAT-TESTS-BATCH-ABCE.md:

If fixes relate to UAT tests, update status:
```markdown
**Actual Result:** ☒ Fail → ✅ Pass (automated)
**Fixed:** {date}
**Commit:** {sha}
```

3. Create fix report in .fix-integration-tests/REPORT.md:
```markdown
# Integration Test Fix Report

**Date:** {timestamp}
**Original Branch:** {original_branch}
**Mode:** {standalone|GSD}

## Summary

- Total failures found: {N}
- Bugs fixed: {M}
- Tests now passing: {total_tests}
- Fix success rate: {M/N * 100}%

## Fixes Applied

### 1. test_fresh_install_missing_config_base_directory_regression

**Branch:** fix/fresh-install-1738540800
**Commit:** abc123f
**Files changed:** src/mc/terminal/attach.py:165,200

**Root cause:** Used config.load()["base_directory"] without default fallback

**Fix:** Changed to config.get("base_directory", os.path.expanduser("~/mc"))

**Test result:** ✅ PASSED

### 2. test_container_workspace_path_formatting

...

## Remaining Issues

- test_config_migration → Needs manual investigation
  Error: ...

## Next Steps

- [ ] Review merged commits
- [ ] Run full test suite (including unit tests)
- [ ] Update version number if releasing
- [ ] Push changes to remote
```

4. Commit documentation updates:
```bash
git add tests/integration/REGRESSION_TESTS.md
git add .planning/UAT-TESTS-BATCH-ABCE.md
git add .fix-integration-tests/REPORT.md

git commit -m "docs: update test status after automated fixes

Fixed {M} integration test failures via parallel agents.
See .fix-integration-tests/REPORT.md for details."
```
</step>

<step name="final_report">
**Phase 5: Final Report**

Generate comprehensive report for user:

```
═══════════════════════════════════════════════════════════
🎉 Integration Test Fix Complete
═══════════════════════════════════════════════════════════

📊 SUMMARY

Original failures:  {N}
Successfully fixed: {M}
Fix success rate:   {M/N * 100}%
All tests passing:  {total_tests passed}/{total_tests}

⏱️  EXECUTION TIME

Test discovery:     {time}
Parallel analysis:  {time} ({num_agents} agents)
Parallel fixing:    {time} ({num_agents} agents)
Integration verify: {time}
Total:              {total_time}

✅ FIXES APPLIED ({M})

1. test_fresh_install
   → Branch: fix/fresh-install-1738540800
   → Commit: abc123f
   → Files: src/mc/terminal/attach.py:165,200
   → Strategy: Use config.get() with default fallback

2. test_workspace_path
   → Branch: fix/workspace-path-1738540801
   → Commit: def456a
   → Files: src/mc/container/manager.py:89
   → Strategy: Format customer name with underscores

❌ FAILED TO FIX ({N-M})

1. test_config_migration
   → Reason: Still failing after fix attempt
   → Next: Manual investigation needed
   → See: .fix-integration-tests/REPORT.md

📝 DOCUMENTATION UPDATED

✓ tests/integration/REGRESSION_TESTS.md
✓ .planning/UAT-TESTS-BATCH-ABCE.md
✓ .fix-integration-tests/REPORT.md

🚀 NEXT STEPS

1. Review changes:
   git log --oneline -n {M}

2. Run full test suite (unit + integration):
   uv run pytest -v --no-cov

3. Push to remote (if satisfied):
   git push origin {original_branch}

4. For failed fixes, run:
   /bug-to-test {test_name}
   # Or investigate manually

═══════════════════════════════════════════════════════════
```

Update final TodoWrite item as completed.

If user opted for GSD mode:
```
GSD Integration:
- Created {N} phases
- State saved in .fix-integration-tests/
- Resume with: /gsd:resume-work
```
</step>

</process>

<output>
- Fixed integration tests (automated commits)
- Separate git branches for each fix (optional cleanup)
- Verification that fixes work together
- Updated documentation (REGRESSION_TESTS.md, UAT docs)
- Comprehensive fix report (.fix-integration-tests/REPORT.md)
- Optional: GSD phases for complex scenarios
</output>

<anti_patterns>
- Don't fix bugs without understanding root cause (analysis phase is critical)
- Don't merge fixes without integration verification (Phase 4 required)
- Don't use mocks in integration tests (follow INTEGRATION_TEST_BEST_PRACTICES.md)
- Don't commit broken fixes (must verify test passes first)
- Don't skip documentation updates (traceability is important)
- Don't delete branches before user confirmation (they may want to review)
</anti_patterns>

<success_criteria>
- [ ] All integration tests run successfully
- [ ] Failures identified and categorized (REAL_BUG vs TEST_ISSUE vs ENV_ISSUE)
- [ ] Parallel agents spawned for analysis (up to MAX_PARALLEL_ANALYSIS)
- [ ] Parallel agents spawned for fixing (up to MAX_PARALLEL_FIXES)
- [ ] Each fix in separate git branch
- [ ] All fixes verified individually (test passes)
- [ ] All fixes verified together (integration test suite passes)
- [ ] Documentation updated (REGRESSION_TESTS.md, UAT docs, REPORT.md)
- [ ] User provided with clear next steps
- [ ] GSD integration (if requested) with proper state management
</success_criteria>

<integration_with_gsd>
**When to use GSD mode:**
- Large number of failures (>5)
- Need state persistence across context resets
- Want checkpoint/resume capability
- Fixes have dependencies (need sequential execution)

**How it works:**
1. Create GSD phase for each fix
2. Use GSD's parallel execution framework
3. State stored in .fix-integration-tests/ + GSD's .planning/
4. Can resume with /gsd:resume-work if interrupted
5. GSD verification agents can validate each fix

**Standalone mode (default for <=5 failures):**
- Simpler, faster
- No GSD overhead
- Still uses parallel agents
- Still tracks state locally
- Good for quick fixes
</integration_with_gsd>
