---
name: bug-to-test
description: Convert UAT failure or production bug into automated integration test
argument-hint: "optional: test-number or bug description"
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - AskUserQuestion
---

<objective>
Transform UAT test failures or production bugs into automated integration tests through guided investigation, manual reproduction, and test creation.

Ensures every real-world failure builds a stronger test suite with proper documentation and traceability.
</objective>

<context>
@.planning/UAT-TESTS-BATCH-ABCE.md
@tests/integration/
</context>

<process>

<step name="gather_information">
Ask the user about the bug using AskUserQuestion:

**Question 1: Source**
- header: "Bug Source"
- question: "Where was this issue discovered?"
- options:
  - label: "UAT Test Failure"
    description: "Issue found during manual UAT testing from .planning/UAT-TESTS-BATCH-ABCE.md"
  - label: "Production Bug"
    description: "Issue discovered in real-world usage or production environment"
  - label: "Development Testing"
    description: "Bug found during development or ad-hoc testing"

**If UAT Test Failure**, ask:
- header: "Test Number"
- question: "Which UAT test failed? (e.g., '1.1', '4.1', '9.2')"
- Provide text input option

**If Production/Development Bug**, ask:
- "Please describe the bug in detail"
- "What were the steps to reproduce?"
- "What was the expected vs actual behavior?"

**Question 2: Environment**
- header: "Platform"
- question: "What platform did this occur on?"
- options:
  - label: "macOS"
  - label: "Linux"
  - label: "Both/Unknown"

**Question 3: Severity**
- header: "Impact"
- question: "How severe is this issue?"
- options:
  - label: "Critical - Blocks core functionality"
  - label: "Major - Significant feature broken"
  - label: "Minor - Edge case or cosmetic issue"
</step>

<step name="analyze_uat">
**If UAT Test:**

1. Read the UAT test document:
```bash
cat .planning/UAT-TESTS-BATCH-ABCE.md | grep -A 30 "^#### ${test_number}"
```

2. Extract:
   - Test name/feature
   - Test steps
   - Expected result
   - Actual result (if documented)

3. Summarize for user:
   - "Found UAT Test ${test_number}: ${test_name}"
   - "Feature being tested: ${feature}"
   - Show the test steps and expected behavior

**If Wild Bug:**

1. Ask clarifying questions:
   - What component/feature was being used?
   - What command was run?
   - What files or configuration were involved?
   - Full error message or unexpected output?

2. Search codebase for related files:
```bash
# Find relevant source files based on bug description
```

3. Read relevant source to understand context
</step>

<step name="attempt_reproduction">
**IMPORTANT:** Only attempt manual reproduction if it's safe and feasible in this environment.

Ask user: "Can I attempt to reproduce this issue now?"
- If yes, attempt reproduction following the exact steps
- If no, ask user to provide detailed reproduction steps

**Safe reproduction checklist:**
- [ ] Won't modify user's real data
- [ ] Won't require external credentials
- [ ] Can use test/temporary resources
- [ ] Won't break existing setup

**If attempting reproduction:**

1. Setup temporary environment if needed:
```bash
# Create temp directories, test databases, etc.
```

2. Execute reproduction steps one by one

3. Capture outputs:
   - Error messages
   - Stack traces
   - Log output
   - Unexpected behavior

4. Document findings:
   - "✓ Successfully reproduced the bug"
   - OR "✗ Could not reproduce - may need specific conditions"

**If cannot reproduce:**
- Document why (missing credentials, platform-specific, etc.)
- Proceed with test creation based on description
</step>

<step name="identify_test_type">
Determine the appropriate test type and location:

**Integration Test Categories:**
1. **Container Operations** → `tests/integration/test_container_*.py`
   - Container creation, lifecycle, exec, image pulling

2. **API Integration** → `tests/integration/test_api_*.py`
   - Salesforce, Red Hat API, external service calls

3. **Terminal/Shell** → `tests/integration/test_terminal_*.py`
   - Terminal launching, attachment, shell customization

4. **Configuration** → `tests/integration/test_config_*.py`
   - Config loading, migration, validation

5. **End-to-End** → `tests/integration/test_e2e_*.py`
   - Full workflows spanning multiple components

Ask user to confirm test category or suggest one based on bug analysis.
</step>

<step name="design_test">
Design the integration test:

1. **Test name:** `test_<bug_description>_regression`
   - Example: `test_image_pull_fallback_auth_error_regression`

2. **Test docstring template:**
```python
"""Regression test for [UAT X.Y / Bug #123] - [Short description]

Bug discovered: [Date]
Platform: [macOS/Linux/Both]
Severity: [Critical/Major/Minor]

Problem:
[Description of what went wrong]

Steps to reproduce:
1. [Step 1]
2. [Step 2]
...

Expected: [Expected behavior]
Actual: [Actual behavior before fix]

This test ensures the bug does not regress.

[If UAT] UAT Test: [Test number and name]
[If applicable] Fixed in: [version/commit]
"""
```

3. **Test structure:**
   - Setup: Create necessary fixtures, temp resources
   - Action: Execute the exact steps that trigger the bug
   - Assert: Verify the bug is fixed (or fails if not yet fixed)
   - Cleanup: Remove temporary resources

4. **Consider:**
   - Does it need Podman? → Use `@pytest.mark.skipif(not _podman_available())`
   - Does it need credentials? → Use `MC_TEST_INTEGRATION` env var
   - Platform-specific? → Use platform detection
   - External dependencies? → Mock only what's necessary for isolation

Show test design to user for approval.
</step>

<step name="create_test_file">
1. **Check if test file exists:**
```bash
ls tests/integration/test_${category}_*.py 2>/dev/null
```

2. **If creating new file:**
   - Include proper imports
   - Add fixtures if needed
   - Follow existing integration test patterns

3. **If adding to existing file:**
   - Read the existing file
   - Add test in appropriate location
   - Reuse existing fixtures

4. **Write the test:**
   - Use Edit tool to add to existing file
   - Use Write tool for new file
   - Include comprehensive docstring
   - Add proper pytest marks (@pytest.mark.integration)
   - Include cleanup in finally blocks

5. **Verify syntax:**
```bash
python3 -m py_compile tests/integration/test_${filename}.py
```
</step>

<step name="run_test">
Attempt to run the new test:

```bash
cd /Users/dsquirre/Repos/mc
uv run pytest tests/integration/test_${filename}.py::test_${test_name} -v --no-cov
```

**Expected outcomes:**
- ✓ Test passes (if bug is already fixed)
- ✗ Test fails (if bug still exists - this is OK, shows test works!)
- ⚠ Test skipped (if prerequisites not met - document why)

Capture and show output to user.

If test has issues:
- Fix syntax errors
- Adjust assertions
- Add missing fixtures
- Handle platform differences
</step>

<step name="update_documentation">
**If UAT Test source:**

1. Update `.planning/UAT-TESTS-BATCH-ABCE.md`

Find the test section:
```bash
grep -n "^#### ${test_number}" .planning/UAT-TESTS-BATCH-ABCE.md
```

2. Add automated test reference after the test section:

```markdown
**Actual Result:** ☒ Fail → ☑ Automated
**Automated Test:** `test_${test_name}()` in `tests/integration/test_${filename}.py`
**Created:** [Date]
**Status:** [Passing/Failing/Skipped]
```

**For all bugs:**

3. Create/update test index (if doesn't exist):
```bash
[ -f tests/integration/REGRESSION_TESTS.md ] || cat > tests/integration/REGRESSION_TESTS.md <<EOF
# Regression Test Index

Tests created from real bugs and UAT failures.

| Test | Bug Source | Date Added | Status |
|------|------------|------------|--------|
EOF
```

4. Add entry to index:
```
| test_${test_name} | [UAT X.Y / Production Bug] | [Date] | [Status] |
```
</step>

<step name="commit_changes">
Commit the test and documentation:

```bash
git add tests/integration/test_${filename}.py
git add .planning/UAT-TESTS-BATCH-ABCE.md  # if modified
git add tests/integration/REGRESSION_TESTS.md  # if exists

git commit -m "$(cat <<'EOF'
test: add regression test for [bug description]

Regression test for [UAT X.Y / production bug discovered DATE].

Problem:
[Brief description]

Test verifies:
- [What it checks]
- [Expected behavior]

[If UAT] UAT Test: [Number and name]
Platform: [macOS/Linux/Both]
Severity: [Critical/Major/Minor]

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
EOF
)"
```
</step>

<step name="summary_report">
Provide summary to user:

```
✅ Regression Test Created

Test File: tests/integration/test_${filename}.py
Test Name: test_${test_name}
Status: [Passing ✓ / Failing ✗ / Skipped ⚠]

Source: [UAT Test X.Y / Production Bug]
Date: [Date]
Platform: [macOS/Linux/Both]
Severity: [Critical/Major/Minor]

What it tests:
[Brief description]

Documentation updated:
- [✓] UAT document (if applicable)
- [✓] Regression test index
- [✓] Committed to git

Next steps:
1. Run full test suite to ensure no regressions
2. [If failing] Fix the bug, then verify test passes
3. [If skipped] Document prerequisites needed to run test

Run this test with:
uv run pytest tests/integration/test_${filename}.py::test_${test_name} -v
```
</step>

</process>

<output>
- New integration test in `tests/integration/test_*.py`
- Updated `.planning/UAT-TESTS-BATCH-ABCE.md` (if UAT test)
- Updated `tests/integration/REGRESSION_TESTS.md` index
- Git commit with detailed bug/test context
</output>

<anti_patterns>
- Don't create tests that just mock everything - use real components (see best practices below)
- Don't skip reproduction if it's feasible in this environment
- Don't create overly complex tests - focus on reproducing the specific bug
- Don't forget cleanup code - integration tests must not leave artifacts
- Don't commit broken tests - mark as xfail if bug not yet fixed
</anti_patterns>

<best_practices>
**CRITICAL: Use Real Components in Integration Tests**

Integration tests should test how real components work together. See docs/INTEGRATION_TEST_BEST_PRACTICES.md for full guidance.

**✅ ALWAYS Keep Real:**
- Red Hat API client (real HTTP calls to real API)
- Podman client (real container operations)
- Config manager (real file I/O with tmp_path for isolation)
- State database (real SQLite with tmp_path for isolation)
- Container manager (real container lifecycle)
- Filesystem operations (real files with tmp_path)

**⚠️ ONLY Mock When Absolutely Necessary:**
- TTY detection (pytest doesn't run in TTY)
- Time-based operations (for deterministic test results)
- External services you don't control (payment processors, etc.)

**Example from UAT 1.1 (what we learned):**

❌ BAD - Over-mocked:
```python
def test_fresh_install(mocker):
    mock_api = mocker.MagicMock()  # Misses real API issues
    mock_config = mocker.MagicMock()  # Misses config parsing bugs
    mock_podman = mocker.MagicMock()  # Misses container issues
    # This tests mocks, not integration!
```

✅ GOOD - Real components:
```python
def test_fresh_install(mocker, tmp_path):
    # Real config (isolated path)
    config_manager = ConfigManager()
    config_manager._config_path = tmp_path / "config.toml"

    # Real API client (actual HTTP calls)
    access_token = get_access_token(real_token)
    api_client = RedHatAPIClient(access_token)

    # Real Podman (actual containers)
    podman_client = PodmanClient()

    # Only mock TTY (pytest limitation)
    mocker.patch("mc.terminal.attach.should_launch_terminal", return_value=True)

    # Test real workflow - catches real bugs!
```

**Why this matters:**
- Real API client caught authentication issues
- Real Podman caught container runtime issues
- Real config caught KeyError in production code
- Mocks would have hidden all these bugs!

**Golden Rule:** If it can be real, make it real.

See also:
- docs/INTEGRATION_TEST_BEST_PRACTICES.md - Complete guide
- docs/USING_BUG_TO_TEST.md - Project-specific patterns
</best_practices>

<success_criteria>
- [ ] Bug fully understood with reproduction steps documented
- [ ] Test created following integration test patterns
- [ ] Test has comprehensive docstring with bug context
- [ ] Test includes proper pytest marks and skip conditions
- [ ] Test runs without syntax errors
- [ ] Documentation updated with test reference
- [ ] Changes committed with detailed commit message
- [ ] User knows how to run the test and interpret results
</success_criteria>
