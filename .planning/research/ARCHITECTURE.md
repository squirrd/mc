# Testing Architecture for Layered Python CLI

**Domain:** Python CLI Testing Infrastructure
**Researched:** 2026-01-20
**Confidence:** HIGH

## Testing Architecture Overview

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Test Execution Layer                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ pytest   │  │  tox     │  │   CI     │  │  Local   │    │
│  │ CLI      │  │  Runner  │  │ Pipeline │  │   Run    │    │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘    │
│       └─────────────┴─────────────┴──────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                    Test Organization Layer                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Unit     │  │ Integration │  │     E2E     │         │
│  │    Tests    │  │    Tests    │  │    Tests    │         │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘         │
│         │                 │                 │                │
├─────────┴─────────────────┴─────────────────┴────────────────┤
│                  Test Support Infrastructure                 │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ Fixtures│  │  Mocks  │  │ Helpers │  │Factories│        │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘        │
└─────────────────────────────────────────────────────────────┘

        Tests mirror application architecture

┌─────────────────────────────────────────────────────────────┐
│                   Application Under Test                     │
├─────────────────────────────────────────────────────────────┤
│  CLI Layer        → Unit tests + CLI invocation tests       │
│  Commands Layer   → Unit tests with mocked controller       │
│  Controller Layer → Unit tests with mocked integrations     │
│  Integrations     → Unit tests with mocked external APIs    │
│  Utilities        → Pure unit tests (no mocks needed)       │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| **Unit Tests** | Test individual functions/classes in isolation | pytest with mocks for dependencies |
| **Integration Tests** | Test component interactions without external services | pytest with real objects, mocked external APIs |
| **E2E Tests** | Test complete workflows through CLI | Bash scripts or subprocess calls to CLI |
| **Fixtures** | Provide reusable test data and setup | pytest fixtures with @pytest.fixture |
| **Mocks** | Simulate external dependencies | pytest-mock, unittest.mock, responses library |
| **Factories** | Generate test data dynamically | Factory pattern or factory_boy |
| **Test Helpers** | Shared assertion and setup utilities | Python modules in tests/helpers/ |

## Recommended Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures and pytest configuration
│
├── unit/                          # Unit tests (mirror src/ structure)
│   ├── __init__.py
│   ├── conftest.py                # Unit-specific fixtures
│   ├── cli/
│   │   ├── __init__.py
│   │   ├── test_main.py           # Tests for CLI entry point
│   │   └── commands/
│   │       ├── __init__.py
│   │       ├── test_case.py       # Tests for case commands
│   │       └── test_other.py      # Tests for other commands
│   ├── controller/
│   │   ├── __init__.py
│   │   └── test_workspace.py      # Tests for WorkspaceManager
│   ├── integrations/
│   │   ├── __init__.py
│   │   ├── test_redhat_api.py     # Tests for RedHatAPIClient
│   │   └── test_ldap.py           # Tests for LDAP functions
│   └── utils/
│       ├── __init__.py
│       ├── test_auth.py           # Tests for authentication
│       ├── test_formatters.py     # Tests for formatters
│       └── test_file_ops.py       # Tests for file operations
│
├── integration/                   # Integration tests
│   ├── __init__.py
│   ├── conftest.py                # Integration-specific fixtures
│   ├── test_workspace_lifecycle.py   # Test workspace creation flow
│   ├── test_case_commands.py         # Test command workflows
│   └── test_api_integration.py       # Test API client integration
│
├── e2e/                           # End-to-end tests
│   ├── __init__.py
│   ├── test_create.sh             # Bash E2E test for create command
│   ├── test_check.sh              # Bash E2E test for check command
│   ├── test_go.sh                 # Bash E2E test for go command
│   └── run_all_tests.sh           # E2E test runner
│
├── fixtures/                      # Test data and fixtures
│   ├── __init__.py
│   ├── api_responses.py           # Mock API response data
│   ├── sample_cases.py            # Sample case data
│   └── sample_accounts.py         # Sample account data
│
└── helpers/                       # Test utilities
    ├── __init__.py
    ├── assertions.py              # Custom assertions
    ├── builders.py                # Test data builders
    └── mock_helpers.py            # Mock setup utilities
```

### Structure Rationale

- **Mirror src/ structure in unit/**: Makes it easy to find tests for specific code. `src/mc/controller/workspace.py` → `tests/unit/controller/test_workspace.py`
- **conftest.py at multiple levels**: Root conftest.py for shared fixtures, subdirectory conftest.py for layer-specific fixtures
- **Separate integration/ from unit/**: Integration tests have different fixture needs and run slower
- **Keep e2e/ for bash scripts**: Existing bash tests are valid E2E tests, maintain separation
- **Centralized fixtures/**: Reusable test data accessible from any test
- **Explicit helpers/**: Avoid scattered utility functions, centralize test helpers

## Architectural Patterns

### Pattern 1: Test Pyramid Structure

**What:** Organize tests in a pyramid - many unit tests, fewer integration tests, minimal E2E tests

**When to use:** All projects (this is the industry standard)

**Trade-offs:**
- **Pros:** Fast feedback, isolated failures, maintainable test suite
- **Cons:** Requires discipline to write good unit tests with mocks

**Recommended distribution for this project:**
```
Unit Tests:        70% (fast, isolated, test single functions)
Integration Tests: 25% (medium speed, test component interactions)
E2E Tests:         5%  (slow, test complete user workflows)
```

### Pattern 2: Dependency Injection for Testability

**What:** Pass dependencies as parameters instead of creating them inside functions

**When to use:** When testing functions that depend on external services (API clients, file systems)

**Trade-offs:**
- **Pros:** Easy to inject mocks, testable without external dependencies
- **Cons:** Requires refactoring existing code that creates dependencies internally

**Example:**
```python
# Before (hard to test)
def attach(case_number, base_dir):
    access_token = get_access_token()  # Hard to mock
    api_client = RedHatAPIClient(access_token)  # Created internally
    case_details = api_client.fetch_case_details(case_number)
    # ...

# After (easy to test)
def attach(case_number, base_dir, api_client=None):
    if api_client is None:
        access_token = get_access_token()
        api_client = RedHatAPIClient(access_token)
    case_details = api_client.fetch_case_details(case_number)
    # ...

# Test
def test_attach():
    mock_client = Mock()
    mock_client.fetch_case_details.return_value = {'accountNumberRef': '123'}
    attach('12345', '/tmp', api_client=mock_client)
    assert mock_client.fetch_case_details.called
```

### Pattern 3: Fixture-Based Mock Setup

**What:** Use pytest fixtures to provide pre-configured mocks and test data

**When to use:** When multiple tests need the same mock setup

**Trade-offs:**
- **Pros:** DRY principle, consistent test setup, easy to maintain
- **Cons:** Can hide test dependencies if overused (fixtures should be obvious)

**Example:**
```python
# In conftest.py
@pytest.fixture
def mock_api_client():
    """Provide a mock RedHat API client with common responses."""
    client = Mock(spec=RedHatAPIClient)
    client.fetch_case_details.return_value = {
        'accountNumberRef': '12345',
        'summary': 'Test case summary',
        'comments': []
    }
    client.fetch_account_details.return_value = {
        'name': 'Test Account'
    }
    return client

# In test file
def test_create_command(mock_api_client, tmp_path):
    create('01234567', str(tmp_path), api_client=mock_api_client)
    assert mock_api_client.fetch_case_details.called
```

### Pattern 4: Response Mocking for HTTP Clients

**What:** Use `responses` library to mock HTTP requests at the requests library level

**When to use:** When testing code that makes HTTP requests directly

**Trade-offs:**
- **Pros:** Tests real HTTP request logic, no need to refactor code
- **Cons:** More brittle than mocking at API client level, tests implementation details

**Example:**
```python
import responses

@responses.activate
def test_fetch_case_details():
    responses.add(
        responses.GET,
        'https://api.access.redhat.com/support/v1/cases/01234567',
        json={'accountNumberRef': '12345', 'summary': 'Test'},
        status=200
    )

    client = RedHatAPIClient('fake-token')
    result = client.fetch_case_details('01234567')
    assert result['summary'] == 'Test'
```

### Pattern 5: Subprocess Mocking for External Commands

**What:** Mock subprocess.run for code that calls external commands (like ldapsearch)

**When to use:** When testing code that uses subprocess to call system commands

**Trade-offs:**
- **Pros:** Test without requiring external tools installed
- **Cons:** Doesn't test actual command integration (need integration test for that)

**Example:**
```python
def test_ldap_search(mocker):
    mock_run = mocker.patch('subprocess.run')
    mock_run.return_value = Mock(
        stdout='cn: John Doe\nuid: jdoe\n',
        stderr='',
        returncode=0
    )

    success, output = ldap_search('jdoe')
    assert success is True
    assert 'John Doe' in output
```

## Data Flow for Testing

### Unit Test Flow

```
Test Function
    ↓
Create Mocks (fixtures or manual)
    ↓
Call Function Under Test
    ↓
Assert Mock Calls
    ↓
Assert Return Values
```

### Integration Test Flow

```
Test Function
    ↓
Setup Real Components (WorkspaceManager, etc.)
    ↓
Mock External Boundaries (HTTP, subprocess)
    ↓
Call High-Level Function
    ↓
Assert File System State
    ↓
Assert Mock Call Counts
```

### E2E Test Flow (Bash)

```
Bash Script
    ↓
Set Environment Variables
    ↓
Create Test Fixtures (files, dirs)
    ↓
Call CLI Binary
    ↓
Capture Output
    ↓
Assert Output Contains Expected
    ↓
Assert File System Changes
    ↓
Cleanup
```

### Key Testing Data Flows

1. **Mock Response Flow:** Test defines mock data → Fixture provides mock → Function calls mock → Test asserts behavior
2. **Fixture Data Flow:** fixtures/ module defines data → conftest.py loads as fixture → Test receives fixture → Test uses data
3. **Assertion Flow:** Test runs code → Test captures result → Helper function validates result → Test passes/fails

## Mock Boundaries and Strategies

### What to Mock at Each Layer

| Application Layer | What to Mock | How to Mock | Why |
|-------------------|--------------|-------------|-----|
| **CLI (main.py)** | Command functions, environment, argparse | `mocker.patch` on command functions | Isolate CLI routing logic |
| **Commands** | Controller classes, API clients | `mocker.patch` or fixture injection | Test command logic without I/O |
| **Controller** | File operations, API clients | `mocker.patch` on utils, inject clients | Test business logic without side effects |
| **Integrations** | HTTP requests, subprocess | `responses` library, `mocker.patch('subprocess.run')` | Test integration logic without external dependencies |
| **Utils** | Usually nothing (pure functions) | Minimal mocking | Utils should be simple and testable as-is |

### External Service Mocking Strategy

#### Red Hat API Mocking

**Approach:** Mock at the `requests` level using `responses` library for integration tests, mock `RedHatAPIClient` for unit tests

```python
# Integration test - mock HTTP
@responses.activate
def test_api_client_integration():
    responses.add(...)
    client = RedHatAPIClient('token')
    result = client.fetch_case_details('01234567')

# Unit test - mock client
def test_command_with_api(mocker):
    mock_client = mocker.Mock(spec=RedHatAPIClient)
    mock_client.fetch_case_details.return_value = {...}
    attach('01234567', '/tmp', api_client=mock_client)
```

#### LDAP Mocking

**Approach:** Mock `subprocess.run` to simulate ldapsearch responses

```python
def test_ldap_search(mocker):
    mock_run = mocker.patch('mc.integrations.ldap.subprocess.run')
    mock_run.return_value = Mock(
        stdout=SAMPLE_LDAP_OUTPUT,
        stderr='',
        returncode=0
    )
    success, output = ldap_search('jdoe')
```

#### File System Mocking

**Approach:** Use `tmp_path` fixture (pytest built-in) for real temp files, or mock `os` functions for unit tests

```python
# Integration test - real files in temp dir
def test_workspace_creation(tmp_path):
    workspace = WorkspaceManager(str(tmp_path), '01234567', 'Acme', 'Summary')
    workspace.create_files()
    assert (tmp_path / 'Acme' / '01234567-Summary').exists()

# Unit test - mock file operations
def test_create_file(mocker):
    mock_open = mocker.patch('builtins.open', mocker.mock_open())
    create_file('/fake/path')
    mock_open.assert_called_once_with('/fake/path', 'w')
```

## Test Infrastructure Build Order

### Phase 1: Foundation (Build First)

**Components:**
1. `tests/conftest.py` - Root pytest configuration
2. `tests/fixtures/api_responses.py` - Mock API data
3. `tests/helpers/mock_helpers.py` - Mock setup utilities
4. `pytest.ini` or `pyproject.toml` - pytest configuration

**Why first:** These are dependencies for all other tests

**Estimated effort:** 2-4 hours

### Phase 2: Utility Tests (Build Second)

**Components:**
1. `tests/unit/utils/test_formatters.py`
2. `tests/unit/utils/test_file_ops.py`
3. `tests/unit/utils/test_auth.py`

**Why second:** Utils have no dependencies, easiest to test, build confidence

**Estimated effort:** 4-6 hours

### Phase 3: Integration Layer Tests (Build Third)

**Components:**
1. `tests/unit/integrations/test_redhat_api.py`
2. `tests/unit/integrations/test_ldap.py`

**Why third:** These have external dependencies that need mocking patterns established

**Estimated effort:** 6-8 hours

### Phase 4: Controller Tests (Build Fourth)

**Components:**
1. `tests/unit/controller/test_workspace.py`

**Why fourth:** Controller depends on utils and integrations, test those first

**Estimated effort:** 4-6 hours

### Phase 5: Command Tests (Build Fifth)

**Components:**
1. `tests/unit/cli/commands/test_case.py`
2. `tests/unit/cli/commands/test_other.py`

**Why fifth:** Commands orchestrate controller and integrations, test dependencies first

**Estimated effort:** 8-10 hours

### Phase 6: CLI Tests (Build Sixth)

**Components:**
1. `tests/unit/cli/test_main.py`

**Why sixth:** CLI depends on all commands being tested

**Estimated effort:** 4-6 hours

### Phase 7: Integration Tests (Build Seventh)

**Components:**
1. `tests/integration/test_workspace_lifecycle.py`
2. `tests/integration/test_case_commands.py`

**Why seventh:** Integration tests require all components working together

**Estimated effort:** 8-12 hours

### Phase 8: E2E Refactoring (Build Last)

**Components:**
1. Move existing bash tests to `tests/e2e/`
2. Ensure they work with mocked external services
3. Add any missing E2E scenarios

**Why last:** E2E tests validate everything works end-to-end after unit/integration tests pass

**Estimated effort:** 4-6 hours

### Dependency Graph

```
Phase 1 (Foundation)
    ↓
Phase 2 (Utils Tests) ← No dependencies on other components
    ↓
Phase 3 (Integration Tests) ← Depends on mock helpers from Phase 1
    ↓
Phase 4 (Controller Tests) ← Depends on utils (Phase 2) and integration mocks (Phase 3)
    ↓
Phase 5 (Command Tests) ← Depends on controller (Phase 4)
    ↓
Phase 6 (CLI Tests) ← Depends on commands (Phase 5)
    ↓
Phase 7 (Integration Tests) ← Depends on all components
    ↓
Phase 8 (E2E) ← Validates everything
```

## Anti-Patterns

### Anti-Pattern 1: Testing Implementation Details

**What people do:** Test internal private methods or implementation details instead of public behavior

```python
# Bad - testing private method
def test_generate_file_dir_list(workspace):
    result = workspace._generate_file_dir_list()
    assert len(result) == 9

# Good - testing public behavior
def test_workspace_creates_expected_structure(workspace, tmp_path):
    workspace.create_files()
    assert (tmp_path / 'Account' / '01234567-Summary' / 'files').exists()
```

**Why it's wrong:** Tests break when refactoring, even if behavior is unchanged

**Do this instead:** Test public APIs and observable behavior (files created, return values, side effects)

### Anti-Pattern 2: Overly Complex Fixtures

**What people do:** Create deeply nested fixtures with lots of dependencies

```python
# Bad - too complex
@pytest.fixture
def fully_configured_system(mock_api, mock_ldap, mock_fs, config, workspace, ...):
    # 50 lines of setup
    ...

# Good - compose simple fixtures
@pytest.fixture
def mock_api():
    return Mock(spec=RedHatAPIClient)

def test_something(mock_api, tmp_path):
    # Test-specific setup is visible
    workspace = WorkspaceManager(str(tmp_path), ...)
```

**Why it's wrong:** Hard to understand what test actually needs, hard to debug failures

**Do this instead:** Keep fixtures simple and focused, compose them in tests where dependencies are visible

### Anti-Pattern 3: Not Isolating Tests

**What people do:** Share state between tests (global variables, persistent files)

```python
# Bad - shared state
shared_workspace = None

def test_create():
    global shared_workspace
    shared_workspace = WorkspaceManager(...)

def test_check():
    # Depends on test_create running first
    status = shared_workspace.check()

# Good - isolated
def test_create(tmp_path):
    workspace = WorkspaceManager(str(tmp_path), ...)
    workspace.create_files()
    # ...

def test_check(tmp_path):
    workspace = WorkspaceManager(str(tmp_path), ...)
    workspace.create_files()
    status = workspace.check()
```

**Why it's wrong:** Tests fail unpredictably, can't run in parallel, hard to debug

**Do this instead:** Each test should set up its own state, use fixtures for common setup

### Anti-Pattern 4: Mocking Too Much

**What people do:** Mock everything, including standard library functions that don't need mocking

```python
# Bad - unnecessary mocking
def test_format_string(mocker):
    mocker.patch('str.lower')
    mocker.patch('str.replace')
    result = shorten_and_format('Test String')

# Good - test real behavior
def test_format_string():
    result = shorten_and_format('Test String')
    assert result == 'test-string'
```

**Why it's wrong:** Tests don't validate real behavior, brittle tests

**Do this instead:** Only mock I/O boundaries (HTTP, file system, subprocess), test real logic

### Anti-Pattern 5: No Assertion Messages

**What people do:** Write assertions without context

```python
# Bad - no context
def test_workspace_check():
    status = workspace.check()
    assert status == "OK"

# Good - helpful message
def test_workspace_check():
    status = workspace.check()
    assert status == "OK", f"Expected workspace to be OK but got {status}"
```

**Why it's wrong:** Test failures are hard to diagnose

**Do this instead:** Add assertion messages, especially for complex conditions

## Integration Points

### External Services

| Service | Integration Pattern | Mock Strategy | Notes |
|---------|---------------------|---------------|-------|
| Red Hat API | HTTP requests via `requests` library | `responses` library for HTTP mocking | Mock at HTTP layer for integration tests, mock client for unit tests |
| LDAP | subprocess call to `ldapsearch` | `mocker.patch('subprocess.run')` | Provide sample LDAP output in fixtures |
| File System | Direct `os` and `pathlib` calls | `tmp_path` fixture for real files, mock for unit tests | Prefer real temp files over mocking when possible |
| Environment | `os.environ` reads | `mocker.patch.dict('os.environ')` | Set test environment variables in fixtures |

### Internal Boundaries

| Boundary | Communication | Testing Strategy |
|----------|---------------|------------------|
| CLI ↔ Commands | Direct function calls | Mock commands, test CLI routing and argument parsing |
| Commands ↔ Controller | Direct instantiation and method calls | Inject mocked controller, test command orchestration |
| Controller ↔ Integrations | Instantiate API clients | Inject mocked clients, test controller logic |
| Integrations ↔ External | HTTP, subprocess | Mock at boundary (responses, subprocess.run) |

## Scaling Considerations

| Test Suite Size | Approach |
|-----------------|----------|
| 0-50 tests | Run all tests locally, simple pytest configuration |
| 50-200 tests | Separate fast unit tests from slow integration tests, use pytest markers |
| 200+ tests | Parallel execution (pytest-xdist), CI optimization, test selection by changed files |

### Test Execution Optimization

**Small suite (current state):**
```bash
pytest  # Run all tests
```

**Medium suite (after adding tests):**
```bash
pytest tests/unit -v              # Fast unit tests only
pytest tests/integration -v       # Slower integration tests
pytest -m "not slow" -v           # Skip slow tests for quick feedback
```

**Large suite (future):**
```bash
pytest -n auto tests/unit         # Parallel execution for unit tests
pytest --lf                        # Run last failed tests
pytest --sw                        # Stop at first failure (stepwise)
```

### CI/CD Considerations

**Test stages for CI pipeline:**
1. **Lint and type check** (fastest feedback)
2. **Unit tests** (fast, run on every commit)
3. **Integration tests** (medium, run on every commit)
4. **E2E tests** (slow, run on PR or scheduled)

**Example GitHub Actions workflow:**
```yaml
test:
  runs-on: ubuntu-latest
  steps:
    - name: Unit Tests
      run: pytest tests/unit -v --cov
    - name: Integration Tests
      run: pytest tests/integration -v
    - name: E2E Tests
      run: bash tests/e2e/run_all_tests.sh
```

## Sources

**High Confidence Sources:**
- pytest official documentation (https://docs.pytest.org/) - Test framework patterns
- Python testing best practices from Real Python and official Python docs
- Established patterns from popular Python CLI projects (click, typer)
- Direct code inspection of existing project structure

**Patterns based on:**
- Industry standard test pyramid (Martin Fowler)
- pytest fixture patterns (pytest documentation)
- Mock strategies from unittest.mock documentation
- File structure conventions from Python Packaging Authority

**Confidence Notes:**
- **HIGH confidence** on pytest patterns, fixture usage, mock strategies (well-established)
- **HIGH confidence** on test structure (mirrors source code structure is proven pattern)
- **HIGH confidence** on build order (dependencies are clear from code inspection)
- **MEDIUM confidence** on specific timing estimates (depends on developer experience)

---
*Testing architecture research for: Python CLI Testing Infrastructure*
*Researched: 2026-01-20*
