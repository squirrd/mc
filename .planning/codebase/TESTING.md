# Testing Patterns

**Analysis Date:** 2026-01-20

## Test Framework

**Runner:**
- pytest 7.0.0+
- Config: `pyproject.toml`

**Assertion Library:**
- pytest built-in assertions

**Coverage Tool:**
- pytest-cov 4.0.0+

**Run Commands:**
```bash
pytest                 # Run all tests
pytest -v              # Verbose mode
pytest --cov           # With coverage
pytest tests/unit      # Run unit tests only
pytest tests/integration  # Run integration tests only
```

**Configuration in** `pyproject.toml`:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
```

## Test File Organization

**Location:**
- Separate `tests/` directory at project root (not co-located with source)

**Structure:**
```
tests/
├── __init__.py
├── unit/
│   └── __init__.py
├── integration/
│   └── __init__.py
├── fixtures/
│   ├── __init__.py
│   └── test_data/
├── run_all_tests.sh
├── test_case_comments.sh
├── test_check.sh
├── test_create.sh
├── test_go.sh
└── test_ls.sh
```

**Naming:**
- Python tests: `test_*.py` (standard pytest pattern)
- Shell integration tests: `test_*.sh`

**Current State:**
- Unit test directory exists but contains no test files (only `__init__.py`)
- Integration test directory exists but contains no test files (only `__init__.py`)
- Main testing approach uses bash shell scripts for end-to-end command testing

## Test Structure

**Bash Integration Tests:**

Shell scripts follow this pattern (from `tests/test_check.sh`):
```bash
#!/bin/bash
set -e

MC_CMD="./mc"
TEST_CASE="04349708"
WORKSPACE_PATH="/Users/dsquirre/Cases/IBM_Netherl_B_V/04349708-..."

echo "========================================="
echo "Testing: mc check command"
echo "========================================="

# Test 1: Check non-existent workspace
echo "Test 1: Check non-existent workspace"
OUTPUT=$(${MC_CMD} check ${TEST_CASE})
if echo "$OUTPUT" | grep -q "CheckStaus: WARN"; then
    echo "✓ PASS: Non-existent workspace returns WARN status"
else
    echo "✗ FAIL: Expected WARN status"
    exit 1
fi
```

**Patterns:**
- Use `set -e` to exit on first failure
- Define test case and paths as variables at top
- Number tests sequentially: "Test 1:", "Test 2:", etc.
- Output validation using `grep -q` with conditionals
- Visual pass/fail indicators: "✓ PASS" and "✗ FAIL"
- Cleanup in setup phase: `rm -rf "${WORKSPACE_PATH}"`

**Test Organization Runner:**
`tests/run_all_tests.sh` executes all test scripts:
```bash
#!/bin/bash
set -e

echo "Running all MC CLI tests..."
./tests/test_create.sh
./tests/test_check.sh
./tests/test_go.sh
./tests/test_ls.sh
./tests/test_case_comments.sh
```

## Mocking

**Framework:** Not currently implemented

**Current Approach:**
- Integration tests use real API calls
- Require `RH_API_OFFLINE_TOKEN` environment variable
- Use actual test case: "04349708"

**Opportunities:**
- No mocking framework configured
- Could use `pytest-mock` or `unittest.mock` for unit tests
- HTTP requests could be mocked with `responses` or `requests-mock`

## Fixtures and Factories

**Test Data:**
- Directory: `tests/fixtures/test_data/` (currently empty)
- No fixture files currently defined

**Fixtures Not Used:**
- No pytest fixtures observed
- No factory pattern for test objects

**Test Case IDs:**
Hardcoded in shell scripts:
```bash
TEST_CASE="04349708"
WORKSPACE_PATH="/Users/dsquirre/Cases/IBM_Netherl_B_V/04349708-Transfe_of_ownersh_a_c"
```

## Coverage

**Requirements:** Not enforced

**Tool Configuration:**
- pytest-cov installed in dev dependencies
- No minimum coverage threshold set

**View Coverage:**
```bash
pytest --cov=mc              # Coverage for mc package
pytest --cov=mc --cov-report=html  # HTML report
```

## Test Types

**Unit Tests:**
- Directory: `tests/unit/`
- Current state: Directory exists but no tests implemented
- Intended scope: Test individual functions/classes in isolation

**Integration Tests:**
- Directory: `tests/integration/`
- Current state: Directory exists but no Python tests
- Actual tests: Bash scripts in `tests/` root
- Scope: End-to-end command execution against live APIs

**E2E Tests:**
- Framework: Bash shell scripts
- Location: `tests/*.sh`
- Approach: Execute actual CLI commands and validate output
- Coverage:
  - `test_create.sh` - Workspace creation
  - `test_check.sh` - Workspace validation
  - `test_go.sh` - URL generation and launching
  - `test_ls.sh` - LDAP search functionality
  - `test_case_comments.sh` - Case comment retrieval

## Common Patterns

**Shell Test Assertions:**

Output validation:
```bash
OUTPUT=$(${MC_CMD} check ${TEST_CASE})
if echo "$OUTPUT" | grep -q "expected_string"; then
    echo "✓ PASS: Test description"
else
    echo "✗ FAIL: Error message"
    exit 1
fi
```

File existence checks:
```bash
if [ -f "${WORKSPACE_PATH}/00-caseComments.md" ]; then
    echo "✓ PASS: File created"
else
    echo "✗ FAIL: File not created"
    exit 1
fi
```

Multiple condition validation:
```bash
if echo "$OUTPUT" | grep -q "string1" && \
   echo "$OUTPUT" | grep -q "string2"; then
    echo "✓ PASS"
fi
```

Silent execution for auth checks:
```bash
${MC_CMD} case-comments ${TEST_CASE} > /dev/null 2>&1 && \
    echo "✓ PASS" || echo "✗ FAIL"
```

## Testing Gaps

**No Python Unit Tests:**
- `tests/unit/` is empty
- No tests for individual functions in `utils/`, `controller/`, `integrations/`
- All testing currently end-to-end via bash scripts

**No Mocking:**
- All tests hit live APIs
- No isolation of units under test
- Tests depend on external services and specific test data

**No Fixtures:**
- Test data hardcoded in scripts
- No reusable test objects or factories

**No Coverage Tracking:**
- Coverage tools installed but not used in test runs
- No coverage requirements or gates

**Missing Test Documentation:**
- No README in `tests/` directory
- No documentation of test setup requirements beyond inline comments

## Current Testing Philosophy

The project uses **end-to-end bash testing** as the primary testing approach:
- Tests validate complete user workflows
- Real API integration ensures compatibility
- Visual output makes test results easy to interpret
- Quick to write and execute

This approach trades test isolation for integration confidence but lacks:
- Fast unit test feedback
- Ability to test edge cases without live data
- Clear separation of unit vs. integration concerns

---

*Testing analysis: 2026-01-20*
