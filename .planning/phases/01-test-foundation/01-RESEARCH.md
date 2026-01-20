# Phase 1: Test Foundation - Research

**Researched:** 2026-01-20
**Domain:** Python testing with pytest
**Confidence:** HIGH

## Summary

Pytest is the de facto standard for Python testing with a mature ecosystem of plugins for mocking, coverage, and specialized testing needs. The recommended approach uses pytest (9.0.2+) with pytest-cov (7.0.0) for coverage reporting and pytest-mock (3.15.1) as the general mocking layer. For HTTP request mocking, the responses library (0.25.8) provides a purpose-built solution that's simpler and more feature-rich than generic mocking.

Test organization follows the src layout pattern with tests/ directory separate from application code. Fixtures are organized hierarchically using conftest.py files at appropriate scopes (function for isolation, module/session for expensive setup). The modern approach uses importlib import mode and tmp_path fixtures for file system testing.

Coverage targets should be context-dependent: 60-70% is a reasonable baseline for this phase (foundation + critical path testing), with the option to set higher targets (90%+) for critical modules like auth and API client.

**Primary recommendation:** Use pytest + pytest-cov + pytest-mock + responses library with separate tests/ directory, hierarchical conftest.py fixtures, and tmp_path for file system testing.

## Standard Stack

The established libraries/tools for Python testing:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2+ | Test framework and runner | Industry standard, powerful fixtures, excellent plugin ecosystem |
| pytest-cov | 7.0.0 | Coverage reporting plugin | Official pytest integration, multiple report formats, CI-friendly |
| pytest-mock | 3.15.1 | General mocking via mocker fixture | Thin wrapper over unittest.mock, cleaner syntax, automatic cleanup |
| responses | 0.25.8 | HTTP request mocking | Purpose-built for requests library, simpler than generic mocks |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| requests-mock | Latest | Alternative HTTP mocking | If responses doesn't fit (similar but different API) |
| ldap3 | 2.10.2+ | LDAP mocking (built-in) | Has MockSyncStrategy for offline LDAP testing |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| pytest-mock | unittest.mock directly | pytest-mock provides cleaner syntax and automatic cleanup |
| responses | pytest-mock for HTTP | responses is specialized and simpler for requests library mocking |
| tmp_path | Mock file system | Real temp files provide better isolation, tmp_path is recommended |

**Installation:**
```bash
pip install pytest>=9.0.0 pytest-cov>=7.0.0 pytest-mock>=3.15.0 responses>=0.25.0
```

## Architecture Patterns

### Recommended Project Structure
```
pyproject.toml              # pytest config in [tool.pytest.ini_options]
src/
  mc/                       # Application code
    utils/
    integrations/
    controller/
tests/                      # Separate from source (src layout)
  conftest.py               # Root fixtures (session/module scope)
  unit/
    conftest.py             # Unit test fixtures
    test_auth.py            # Mirror source structure
    test_redhat_api.py
    test_workspace.py
  integration/
    conftest.py             # Integration test fixtures
    test_api_integration.py
  fixtures/                 # Optional: JSON/YAML test data files
    api_responses/
      case_details.json
      attachments.json
```

### Pattern 1: Hierarchical Fixture Organization

**What:** Use conftest.py files at multiple levels with appropriate fixture scopes
**When to use:** Always - enables fixture reuse and proper cleanup

**Example:**
```python
# tests/conftest.py (root level - shared across all tests)
import pytest

@pytest.fixture(scope="session")
def sample_case_number():
    """Case number used across test suite."""
    return "12345678"

@pytest.fixture(scope="session")
def mock_api_base_url():
    """API base URL for mocking."""
    return "https://api.access.redhat.com/support/v1"

# tests/unit/conftest.py (unit test specific)
@pytest.fixture
def mock_case_data():
    """Fresh mock case data per test (function scope)."""
    return {
        "case_number": "12345678",
        "summary": "Test case summary",
        "account_number": "1234567"
    }
```

### Pattern 2: HTTP Mocking with responses

**What:** Use responses library to mock requests HTTP calls
**When to use:** Testing code that uses requests library (auth, API client)

**Example:**
```python
# Source: https://github.com/getsentry/responses
import responses
import requests

@responses.activate
def test_fetch_case_details():
    # Register mock response
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/12345678",
        json={"case_number": "12345678", "summary": "Test"},
        status=200
    )

    # Test code that makes request
    client = RedHatAPIClient(access_token="fake_token")
    result = client.fetch_case_details("12345678")

    assert result["case_number"] == "12345678"
```

### Pattern 3: File System Testing with tmp_path

**What:** Use pytest's built-in tmp_path fixture for file operations
**When to use:** Testing workspace creation, file operations (preferred over mocking)

**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
def test_workspace_creation(tmp_path):
    """Test workspace file creation using real temp directory."""
    workspace = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    workspace.create_files()

    # Verify files exist
    assert (tmp_path / "test_account" / "12345678-test_summary" / "00-caseComments.md").exists()
    # Automatic cleanup after test
```

### Pattern 4: Fixture Factories

**What:** Return a function from fixture that can be called multiple times
**When to use:** When tests need multiple instances with variations

**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/fixtures.html
@pytest.fixture
def make_api_response():
    """Factory for creating varied API responses."""
    def _make_response(case_number, status="Open"):
        return {
            "case_number": case_number,
            "status": status,
            "summary": f"Case {case_number} summary"
        }
    return _make_response

def test_multiple_cases(make_api_response):
    case1 = make_api_response("11111111", "Open")
    case2 = make_api_response("22222222", "Closed")
    # Test with multiple case variations
```

### Pattern 5: Parametrization for Test Variations

**What:** Use @pytest.mark.parametrize to run same test with different inputs
**When to use:** Testing multiple scenarios (success/error, different status codes)

**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
@pytest.mark.parametrize("status_code,expected_exception", [
    (200, None),
    (401, requests.HTTPError),
    (404, requests.HTTPError),
    (500, requests.HTTPError),
])
@responses.activate
def test_api_error_handling(status_code, expected_exception):
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/12345678",
        status=status_code
    )

    client = RedHatAPIClient("token")
    if expected_exception:
        with pytest.raises(expected_exception):
            client.fetch_case_details("12345678")
    else:
        result = client.fetch_case_details("12345678")
        assert result is not None
```

### Anti-Patterns to Avoid

- **Testing private methods:** Test public interfaces only, implementation is internal
- **Using API calls in fixtures:** Load test data from dicts/JSON, not real APIs
- **Static JSON fixtures instead of factories:** Generate test data dynamically for flexibility
- **System clock at collection time:** Use factory.LazyFunction for time-dependent data
- **Overly broad fixture scope:** Use function scope by default, broader only when needed
- **Patching at wrong location:** Patch where object is used, not where it's defined
- **Non-unique test file names with prepend mode:** Use importlib import mode instead

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Mock HTTP requests | Manual mock setup with unittest.mock | responses library | Handles request matching, multiple responses, pass-through, validation |
| Temporary files/directories | Manual temp dir creation/cleanup | tmp_path fixture | Automatic cleanup, isolation, pathlib support, session factory available |
| Mocking with cleanup | Manual patch/unpatch | pytest-mock mocker fixture | Automatic cleanup, scoped to test, cleaner syntax |
| Coverage reporting | Running coverage.py separately | pytest-cov plugin | Integrated workflow, automatic .coverage management, multiple formats |
| Test data variations | Copy-paste test functions | @pytest.mark.parametrize | DRY principle, better reporting, less maintenance |
| Mock LDAP server | Custom fake LDAP | ldap3.MockSyncStrategy | Supports Bind, Search, Modify operations, offline schemas for AD/OpenLDAP |
| Fixture parametrization | Multiple fixture copies | params in @pytest.fixture | Automatic test multiplication, cleaner code |

**Key insight:** The pytest ecosystem is mature with battle-tested plugins. Using them avoids edge cases around cleanup, thread safety, and test isolation that custom solutions miss.

## Common Pitfalls

### Pitfall 1: Incorrect Test Discovery

**What goes wrong:** Tests aren't found or run despite being written
**Why it happens:** Files/functions don't follow naming convention, or import mode issues
**How to avoid:**
- Name test files `test_*.py` or `*_test.py`
- Name test functions starting with `test_`
- Name test classes starting with `Test` (no `__init__` method)
- Use `--import-mode=importlib` to avoid unique name requirement
**Warning signs:** pytest reports 0 tests collected when you have test files

### Pitfall 2: Fixture Scope Confusion

**What goes wrong:** Tests interfere with each other, or expensive setup runs too often
**Why it happens:** Wrong fixture scope for the use case
**How to avoid:**
- Use function scope (default) for test isolation
- Use module scope for expensive setup shared in one file
- Use session scope only for truly global, read-only resources
- Never use session scope for mutable state
**Warning signs:** Tests pass individually but fail when run together, or slow test runs

### Pitfall 3: Patching at Wrong Location

**What goes wrong:** Mock doesn't work, real code still executes
**Why it happens:** Patching where object is defined instead of where it's used
**How to avoid:**
- Patch `module_under_test.dependency` not `dependency.module`
- Example: Patch `auth.requests.post` not `requests.post` when testing auth.py
- Use pytest-mock's `mocker.patch.object()` for clarity
**Warning signs:** Real HTTP calls in tests that should be mocked

### Pitfall 4: Coverage Theater

**What goes wrong:** High coverage but poor test quality
**Why it happens:** Chasing coverage numbers without testing behavior
**How to avoid:**
- Focus on testing behavior, not just executing lines
- 100% coverage doesn't mean bug-free code
- Use coverage to find untested code paths, not as success metric
- Start with baseline target (60-70%), increase for critical modules
**Warning signs:** High coverage but bugs still slip through

### Pitfall 5: Flaky Tests from Shared State

**What goes wrong:** Tests pass/fail inconsistently
**Why it happens:** Tests share mutable state (caches, databases, files)
**How to avoid:**
- Use function-scoped fixtures for fresh state per test
- Clear caches between tests or use separate cache instances
- Use tmp_path for isolated file systems
- Avoid relying on test execution order
**Warning signs:** Tests fail when run with others but pass alone

### Pitfall 6: Missing Test Data Cleanup

**What goes wrong:** Temp files accumulate, disk fills up
**Why it happens:** Manual cleanup code not executed (exceptions, early returns)
**How to avoid:**
- Use `yield` fixtures for guaranteed cleanup
- Use tmp_path which auto-cleans
- Use pytest-mock which auto-unmocks
- Avoid manual try/finally blocks
**Warning signs:** Tests leave artifacts in /tmp or working directory

### Pitfall 7: Overloaded conftest.py

**What goes wrong:** Hard to find fixtures, slow test discovery, unclear dependencies
**Why it happens:** Putting all fixtures in root conftest.py
**How to avoid:**
- Use hierarchical conftest.py (root, unit/, integration/)
- Put fixtures close to where they're used
- Use descriptive fixture names
- Document fixture purpose in docstrings
**Warning signs:** Root conftest.py >200 lines, can't find fixture definitions

### Pitfall 8: Static Test Data Files

**What goes wrong:** Brittle tests, hard to modify, version control bloat
**Why it happens:** Saving JSON/YAML files for every test scenario
**How to avoid:**
- Use fixture factories to generate test data
- Only save test data files for complex/real-world examples
- Keep test data minimal and focused
- Generate variations programmatically
**Warning signs:** fixtures/ directory with dozens of nearly identical JSON files

## Code Examples

Verified patterns from official sources:

### pytest Configuration in pyproject.toml
```toml
# Source: https://docs.pytest.org/en/stable/explanation/goodpractices.html
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "--strict-markers",
    "--import-mode=importlib",
    "--cov=mc",
    "--cov-report=term-missing",
    "--cov-report=html",
    "--cov-fail-under=60",
]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/test_*.py"]

[tool.coverage.report]
exclude_lines = [
    "pragma: no cover",
    "def __repr__",
    "raise AssertionError",
    "raise NotImplementedError",
    "if __name__ == .__main__.:",
]
```

### Testing auth.get_access_token with responses
```python
# Source: https://github.com/getsentry/responses
import responses
import pytest
from mc.utils.auth import get_access_token

@responses.activate
def test_get_access_token_success(monkeypatch):
    """Test successful token fetch."""
    monkeypatch.setenv("RH_API_OFFLINE_TOKEN", "fake_offline_token")

    responses.post(
        "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token",
        json={"access_token": "fake_access_token"},
        status=200
    )

    token = get_access_token()
    assert token == "fake_access_token"

@responses.activate
def test_get_access_token_http_error(monkeypatch):
    """Test HTTP error handling."""
    monkeypatch.setenv("RH_API_OFFLINE_TOKEN", "fake_offline_token")

    responses.post(
        "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token",
        json={"error": "invalid_grant"},
        status=401
    )

    with pytest.raises(requests.HTTPError):
        get_access_token()

def test_get_access_token_missing_env_var(monkeypatch):
    """Test missing environment variable."""
    monkeypatch.delenv("RH_API_OFFLINE_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        get_access_token()
    assert exc_info.value.code == 1
```

### Testing RedHatAPIClient with responses
```python
# Source: https://github.com/getsentry/responses
import responses
import pytest
from mc.integrations.redhat_api import RedHatAPIClient

@pytest.fixture
def api_client():
    """Create API client with fake token."""
    return RedHatAPIClient(access_token="fake_token")

@responses.activate
def test_fetch_case_details(api_client):
    """Test fetching case details."""
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/12345678",
        json={
            "case_number": "12345678",
            "summary": "Test case",
            "status": "Open"
        },
        status=200
    )

    result = api_client.fetch_case_details("12345678")
    assert result["case_number"] == "12345678"
    assert result["status"] == "Open"

@pytest.mark.parametrize("status_code", [401, 404, 500])
@responses.activate
def test_fetch_case_details_errors(api_client, status_code):
    """Test error handling for various HTTP errors."""
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/12345678",
        status=status_code
    )

    with pytest.raises(requests.HTTPError):
        api_client.fetch_case_details("12345678")
```

### Testing WorkspaceManager with tmp_path
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
import pytest
from mc.controller.workspace import WorkspaceManager

def test_workspace_creation(tmp_path):
    """Test workspace file structure creation."""
    workspace = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    workspace.create_files()

    # Check directories exist
    case_dir = tmp_path / "test_account" / "12345678-test_summary"
    assert (case_dir / "files" / "attach").is_dir()
    assert (case_dir / "files" / "dp").is_dir()

    # Check files exist
    assert (case_dir / "00-caseComments.md").is_file()
    assert (case_dir / "10-notes.md").is_file()

def test_workspace_check_ok(tmp_path):
    """Test workspace check with all files present."""
    workspace = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    workspace.create_files()
    status = workspace.check()

    assert status == "OK"

def test_workspace_check_missing(tmp_path):
    """Test workspace check with missing files."""
    workspace = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    # Don't create files
    status = workspace.check()

    assert status == "WARN"
```

### Fixture Factory Pattern
```python
# Source: https://docs.pytest.org/en/stable/how-to/fixtures.html
@pytest.fixture
def make_case_response():
    """Factory for creating case API responses."""
    def _make_response(case_number, summary="Default summary", status="Open"):
        return {
            "case_number": case_number,
            "summary": summary,
            "status": status,
            "account_number": "1234567"
        }
    return _make_response

@responses.activate
def test_multiple_cases(api_client, make_case_response):
    """Test handling multiple cases."""
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/11111111",
        json=make_case_response("11111111", "First case")
    )
    responses.get(
        "https://api.access.redhat.com/support/v1/cases/22222222",
        json=make_case_response("22222222", "Second case")
    )

    case1 = api_client.fetch_case_details("11111111")
    case2 = api_client.fetch_case_details("22222222")

    assert case1["summary"] == "First case"
    assert case2["summary"] == "Second case"
```

### Using pytest-mock for Non-HTTP Mocking
```python
# Source: https://pypi.org/project/pytest-mock/
def test_workspace_with_mocked_utilities(mocker):
    """Example of mocking utility functions."""
    # Mock the utility functions
    mock_create_file = mocker.patch('mc.controller.workspace.create_file')
    mock_create_dir = mocker.patch('mc.controller.workspace.create_directory')

    workspace = WorkspaceManager(
        base_dir="/tmp/test",
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    workspace.create_files()

    # Verify utility functions were called
    assert mock_create_file.call_count == 5  # 5 markdown files
    assert mock_create_dir.call_count == 4   # 4 directories
```

### LDAP Mocking with ldap3
```python
# Source: https://ldap3.readthedocs.io/en/latest/mocking.html
from ldap3 import Server, Connection, MOCK_SYNC

def test_ldap_search():
    """Test LDAP search with mock strategy."""
    server = Server('fake_server')
    connection = Connection(
        server,
        user='cn=user,dc=example,dc=com',
        password='password',
        client_strategy=MOCK_SYNC
    )

    # Add mock entries
    connection.strategy.add_entry(
        'uid=testuser,ou=people,dc=example,dc=com',
        {
            'uid': 'testuser',
            'cn': 'Test User',
            'mail': 'test@example.com'
        }
    )

    # Perform search
    connection.search('ou=people,dc=example,dc=com', '(uid=testuser)')

    assert len(connection.entries) == 1
    assert connection.entries[0].cn.value == 'Test User'
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| unittest framework | pytest framework | ~2015 | Simpler syntax, better fixtures, rich plugin ecosystem |
| prepend import mode | importlib import mode | pytest 6.0 (2020) | No unique filename requirement, better namespace handling |
| tmpdir fixture | tmp_path fixture | pytest 3.9 (2018) | pathlib.Path instead of py.path, modern Python |
| coverage.py separately | pytest-cov plugin | ~2013 | Integrated workflow, automatic management |
| Manual mocking | pytest-mock plugin | ~2014 | Cleaner syntax, automatic cleanup |
| unittest.mock for HTTP | responses/requests-mock | ~2015 | Purpose-built, simpler, more features |
| setup.py test | pytest directly | pytest 7.0 (2021) | Avoid deprecated setuptools integration |

**Deprecated/outdated:**
- `tmpdir` fixture: Use `tmp_path` instead (pathlib support)
- `python setup.py test`: Use `pytest` command directly
- `prepend` import mode: Use `importlib` for new projects
- `request.addfinalizer()`: Prefer `yield` fixtures for cleanup
- `pytest.config`: Use `pytest.Config` API instead

## Open Questions

Things that couldn't be fully resolved:

1. **Exact coverage threshold for Phase 1**
   - What we know: 60-70% is reasonable baseline, 90%+ for critical modules
   - What's unclear: Should we enforce different thresholds per module or global?
   - Recommendation: Use global 60% minimum for Phase 1, increase to 80%+ in Phase 2 with critical path tests

2. **Fixture data file organization**
   - What we know: Can use tests/fixtures/ directory or dynamic factories
   - What's unclear: Best approach for this specific codebase
   - Recommendation: Start with dynamic factories in conftest.py, only add JSON files if needed for complex API responses

3. **LDAP testing approach**
   - What we know: ldap3 has built-in MockSyncStrategy
   - What's unclear: Current codebase LDAP implementation details not reviewed
   - Recommendation: Defer LDAP testing to Phase 2 when LDAP code is reviewed

## Sources

### Primary (HIGH confidence)
- pytest documentation (9.0.2) - https://docs.pytest.org/en/stable/
  - Good practices: https://docs.pytest.org/en/stable/explanation/goodpractices.html
  - Fixtures: https://docs.pytest.org/en/stable/how-to/fixtures.html
  - Parametrization: https://docs.pytest.org/en/stable/how-to/parametrize.html
  - tmp_path: https://docs.pytest.org/en/stable/how-to/tmp_path.html
- pytest-cov documentation (7.0.0) - https://pytest-cov.readthedocs.io/en/latest/
  - Configuration: https://pytest-cov.readthedocs.io/en/latest/config.html
  - PyPI: https://pypi.org/project/pytest-cov/
- pytest-mock PyPI (3.15.1) - https://pypi.org/project/pytest-mock/
- responses GitHub (0.25.8) - https://github.com/getsentry/responses
- ldap3 documentation (2.10.2) - https://ldap3.readthedocs.io/en/latest/mocking.html

### Secondary (MEDIUM confidence)
- Real Python pytest tutorial - https://realpython.com/pytest-python-testing/
- NerdWallet pytest best practices - https://www.nerdwallet.com/blog/engineering/5-pytest-best-practices/
- Pytest with Eric (comprehensive tutorials) - https://pytest-with-eric.com/
- Emiliano Martin pytest practices - https://emimartin.me/pytest_best_practices
- DataCamp pytest-mock tutorial - https://www.datacamp.com/tutorial/pytest-mock
- Enodeas pytest coverage guide - https://enodeas.com/pytest-code-coverage-explained/

### Tertiary (LOW confidence)
- WebSearch results for anti-patterns and pitfalls (cross-verified with official docs)
- Medium articles on pytest fixtures (examples only, verified against official docs)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All versions verified from official PyPI/GitHub
- Architecture: HIGH - Patterns from official pytest documentation
- Pitfalls: MEDIUM - Mix of official docs and community experience

**Research date:** 2026-01-20
**Valid until:** 2026-03-20 (60 days - pytest is stable, infrequent major changes)
