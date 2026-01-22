# Phase 2: Critical Path Testing - Research

**Researched:** 2026-01-22
**Domain:** pytest unit testing and integration testing for Python HTTP clients, workspace management, and LDAP integration
**Confidence:** HIGH

## Summary

Phase 2 focuses on creating comprehensive unit and integration tests for five core modules in the mc CLI codebase: auth, RedHatAPIClient, WorkspaceManager, utilities (formatters and file_ops), and LDAP integration. The codebase has a simple, well-organized structure with clear dependencies primarily on the `requests` library for HTTP, `subprocess` for LDAP searches, and filesystem operations.

The testing infrastructure from Phase 1 provides pytest 9.0+, responses library for HTTP mocking, pytest-mock, and hierarchical fixtures. The user context specifies a balanced approach: focus on happy path + critical errors, validate error messages thoroughly, use parameterized tests for utilities, and include both mocked tests and real integration tests.

**Primary recommendation:** Write unit tests for each module using responses library for HTTP mocking, tmp_path for filesystem testing, and subprocess mocking for LDAP. Include integration tests that validate critical workflows with real API calls and a Docker-based LDAP server for CI.

## Standard Stack

The established libraries/tools for pytest-based testing of this domain:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0+ | Test framework | Industry standard, excellent fixture system, parametrization support |
| responses | 0.25.0 | HTTP mocking for requests library | Purpose-built for requests, simple decorator pattern, already in Phase 1 |
| pytest-mock | 3.15.0 | Enhanced mocking | Provides mocker fixture, cleaner than unittest.mock directly |
| pytest-cov | 7.0.0 | Coverage reporting | Integrated with pytest, HTML reports, already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| tmp_path | built-in | Filesystem testing | All file/directory operations (WorkspaceManager, file_ops) |
| monkeypatch | built-in | Environment variables | Auth token testing, environment variable isolation |
| subprocess.run | stdlib | Subprocess mocking | LDAP integration tests |
| pytest.mark.parametrize | built-in | Data-driven tests | Utilities with multiple input variations (formatters) |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| responses | requests-mock | responses is simpler, less boilerplate for basic mocking |
| tmp_path | tmpdir | tmp_path uses pathlib (modern), tmpdir uses py.path.local (legacy) |
| Docker LDAP | mockldap library | Docker tests real parsing, library is unmaintained |

**Installation:**
All dependencies already installed in Phase 1. No additional packages needed.

## Architecture Patterns

### Recommended Test Structure
```
tests/
├── unit/                    # Fast, isolated tests
│   ├── test_auth.py        # Token retrieval, caching, error handling
│   ├── test_redhat_api.py  # HTTP client methods with mocked responses
│   ├── test_workspace.py   # Workspace lifecycle without real files (mostly)
│   ├── test_formatters.py  # String formatting with parametrize
│   ├── test_file_ops.py    # File operations with tmp_path
│   └── test_ldap.py        # LDAP search with subprocess mocking
└── integration/             # Slower, realistic tests
    ├── test_auth_integration.py      # Token caching with real files
    ├── test_api_integration.py       # Optional: real API calls (requires token)
    ├── test_workspace_integration.py # Full workspace lifecycle with tmp_path
    └── test_ldap_docker.py           # LDAP with Docker container
```

### Pattern 1: HTTP Mocking with responses
**What:** Use @responses.activate decorator and responses.add() to mock HTTP calls
**When to use:** All RedHatAPIClient tests, auth token retrieval
**Example:**
```python
# Source: https://github.com/getsentry/responses
import responses
import requests
from mc.integrations.redhat_api import RedHatAPIClient

@responses.activate
def test_fetch_case_details_success(api_client, mock_api_base_url):
    case_number = "12345678"
    expected_data = {
        "case_number": case_number,
        "summary": "Test case",
        "status": "Open",
        "accountNumberRef": "1234567"
    }

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/{case_number}",
        json=expected_data,
        status=200
    )

    result = api_client.fetch_case_details(case_number)
    assert result["case_number"] == case_number
    assert result["summary"] == "Test case"
```

### Pattern 2: Parametrized Tests for Utilities
**What:** Use @pytest.mark.parametrize to test multiple input/output pairs
**When to use:** Formatters, file_ops utilities with predictable transformations
**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest
from mc.utils.formatters import shorten_and_format

@pytest.mark.parametrize("input_str,expected", [
    ("Simple Test", "Simple_Test"),
    ("Very Long Account Name Here", "Very_Lo_Accoun_Name_H"),
    ("Test-With-Hyphens", "Test_With_Hyphens"),
    ("Special@Characters#Here", "Special_Charact_Here"),
    ("", ""),
])
def test_shorten_and_format(input_str, expected):
    result = shorten_and_format(input_str)
    assert result == expected
```

### Pattern 3: Filesystem Testing with tmp_path
**What:** Use tmp_path fixture to create real temporary files/directories
**When to use:** WorkspaceManager, file_ops, token caching tests
**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
from mc.controller.workspace import WorkspaceManager

def test_workspace_creation(tmp_path):
    base_dir = str(tmp_path)
    workspace = WorkspaceManager(
        base_dir=base_dir,
        case_number="12345678",
        account_name="Test Account",
        case_summary="Test Summary"
    )

    workspace.create_files()

    # Verify directories created
    attach_dir = workspace.get_attachment_dir()
    assert (tmp_path / "Test_Ac" / "12345678-Test_Su" / "files" / "attach").exists()
```

### Pattern 4: Error Testing with pytest.raises
**What:** Verify exceptions are raised with correct types and messages
**When to use:** All error scenarios (missing env vars, HTTP errors, invalid input)
**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/assert.html
import pytest
from mc.utils.auth import get_access_token

def test_get_access_token_missing_env_var(monkeypatch):
    monkeypatch.delenv("RH_API_OFFLINE_TOKEN", raising=False)

    with pytest.raises(SystemExit) as exc_info:
        get_access_token()

    assert exc_info.value.code == 1
```

### Pattern 5: Subprocess Mocking for LDAP
**What:** Mock subprocess.run to simulate LDAP command output
**When to use:** LDAP integration unit tests (Docker for integration tests)
**Example:**
```python
# Source: https://testfixtures.readthedocs.io/en/latest/popen.html
from unittest.mock import Mock
from mc.integrations.ldap import ldap_search

def test_ldap_search_success(mocker):
    mock_result = Mock()
    mock_result.stdout = "dn: uid=testuser,dc=redhat,dc=com\nuid: testuser\ncn: Test User"
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("testuser")
    assert success is True
    assert "testuser" in output
```

### Anti-Patterns to Avoid
- **Don't use real HTTP calls in unit tests:** Always mock with responses library. Save real calls for explicit integration tests.
- **Don't share state between tests:** Each test should be independent. Use function-scoped fixtures, not module/session scope for mutable state.
- **Don't mock too deeply:** Mock at the boundary (HTTP, filesystem, subprocess), not internal functions.
- **Don't ignore error message validation:** User context requires validating error messages, not just exception types.

## Don't Hand-Roll

Problems that look simple but have existing solutions:

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP mocking | Custom request interceptor | responses library | Handles edge cases (redirects, streaming), already installed |
| Temp file cleanup | Manual teardown logic | tmp_path fixture | Automatic cleanup, path isolation, pytest handles edge cases |
| Test parametrization | Loop in test function | @pytest.mark.parametrize | Better test isolation, clearer failure reporting, test IDs |
| Subprocess mocking | Custom process mock | mocker.patch("subprocess.run") | Handles return codes, stdout/stderr, exceptions properly |
| Environment variables | os.environ manipulation | monkeypatch fixture | Automatic cleanup, no test pollution |
| Token caching | Custom cache mock | Real temp files with tmp_path | Tests actual caching behavior, catches serialization bugs |

**Key insight:** pytest's built-in fixtures and the responses library solve 90% of testing needs. Custom mocking logic often misses edge cases that libraries already handle.

## Common Pitfalls

### Pitfall 1: Incomplete HTTP Error Testing
**What goes wrong:** Tests only verify exception is raised, not HTTP status code or error message
**Why it happens:** requests.HTTPError doesn't automatically include status code in exception message
**How to avoid:** Use responses to mock specific HTTP errors (401, 403, 404, 500) and verify both exception and status code
**Warning signs:** Tests pass but production errors are unclear to users
**Example:**
```python
@responses.activate
def test_fetch_case_not_found(api_client, mock_api_base_url):
    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/99999999",
        json={"error": "Case not found"},
        status=404
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        api_client.fetch_case_details("99999999")

    # Verify status code, not just exception
    assert exc_info.value.response.status_code == 404
```

### Pitfall 2: Forgetting to Activate responses Decorator
**What goes wrong:** Test makes real HTTP calls instead of using mocked responses
**Why it happens:** Forgot @responses.activate decorator or used it on wrong function
**How to avoid:** Always use @responses.activate on test functions using responses.add()
**Warning signs:** Tests are slow or fail with network errors

### Pitfall 3: Hardcoded Paths in Tests
**What goes wrong:** Tests create files in source tree or rely on absolute paths
**Why it happens:** Not using tmp_path fixture properly
**How to avoid:** Always use tmp_path for file operations, convert to str() when needed
**Warning signs:** Test artifacts left in repo, tests fail on CI with different paths

### Pitfall 4: LDAP Output Parsing Not Tested
**What goes wrong:** Tests mock LDAP but don't verify parsing logic handles real formats
**Why it happens:** Mock data is too clean, doesn't match real LDAP output structure
**How to avoid:** Use realistic LDAP output samples, test multi-line entries, edge cases (missing fields)
**Warning signs:** Unit tests pass but integration tests fail with real LDAP
**Example:**
```python
def test_ldap_parsing_multiline_entry(mocker):
    # Realistic multi-line LDAP output
    ldap_output = """dn: uid=jsmith,ou=people,dc=redhat,dc=com
uid: jsmith
cn: John Smith
manager: uid=bjones,ou=people,dc=redhat,dc=com
rhatJobTitle: Senior Engineer

dn: uid=alee,ou=people,dc=redhat,dc=com
uid: alee
cn: Alice Lee
"""
    mock_result = Mock()
    mock_result.stdout = ldap_output
    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("smith")
    assert success is True
    # Verify parsing handles multi-line and multiple entries
```

### Pitfall 5: Not Testing Error Messages
**What goes wrong:** Tests verify exception type but not that message helps users
**Why it happens:** Easy to forget user context requirement for error message validation
**How to avoid:** Every error test should assert on message content, not just exception type
**Warning signs:** User context explicitly requires message validation
**Example:**
```python
def test_auth_missing_token_clear_message(monkeypatch):
    monkeypatch.delenv("RH_API_OFFLINE_TOKEN", raising=False)

    # Capture printed output since auth.py uses print()
    import io
    import sys
    captured = io.StringIO()
    sys.stdout = captured

    with pytest.raises(SystemExit):
        get_access_token()

    sys.stdout = sys.__stdout__
    output = captured.getvalue()

    # Verify error message is clear and actionable
    assert "RH_API_OFFLINE_TOKEN" in output
    assert "must be set" in output
```

### Pitfall 6: Mixing Real and Mock in Same Test
**What goes wrong:** Test uses real filesystem but mocked HTTP, causing confusion
**Why it happens:** User context allows mixing mocks with real tests, but per-test not per-operation
**How to avoid:** Each test should be consistently mocked OR consistently real, not mixed
**Warning signs:** Test failures are hard to diagnose, unclear what's being tested

## Code Examples

Verified patterns from official sources:

### Testing Auth Module with Environment Variables
```python
# Source: https://docs.pytest.org/en/stable/how-to/monkeypatch.html
import pytest
import responses
from mc.utils.auth import get_access_token

@responses.activate
def test_get_access_token_success(mock_env_vars, mock_sso_url):
    """Test successful token retrieval."""
    expected_token = "test_access_token_123"
    responses.add(
        responses.POST,
        mock_sso_url,
        json={"access_token": expected_token, "expires_in": 3600},
        status=200
    )

    token = get_access_token()
    assert token == expected_token
    assert len(responses.calls) == 1
```

### Testing RedHatAPIClient with Multiple HTTP Methods
```python
# Source: https://github.com/getsentry/responses
import responses
from mc.integrations.redhat_api import RedHatAPIClient

@responses.activate
def test_list_attachments(api_client, mock_api_base_url):
    case_number = "12345678"
    expected_attachments = [
        {"fileName": "sosreport.tar.gz", "link": "https://api.example.com/file1"},
        {"fileName": "logs.txt", "link": "https://api.example.com/file2"}
    ]

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/{case_number}/attachments/",
        json=expected_attachments,
        status=200
    )

    attachments = api_client.list_attachments(case_number)
    assert len(attachments) == 2
    assert attachments[0]["fileName"] == "sosreport.tar.gz"
```

### Testing WorkspaceManager with tmp_path
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
from pathlib import Path
from mc.controller.workspace import WorkspaceManager

def test_workspace_check_status_ok(tmp_path):
    """Test workspace check returns OK when all files exist."""
    workspace = WorkspaceManager(
        base_dir=str(tmp_path),
        case_number="12345678",
        account_name="Red Hat Inc",
        case_summary="Authentication Issue"
    )

    # Create all expected files
    workspace.create_files()

    status = workspace.check()
    assert status == "OK"

def test_workspace_check_status_warn(tmp_path):
    """Test workspace check returns WARN when files missing."""
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

### Testing Formatters with Parametrize
```python
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest
from mc.utils.formatters import shorten_and_format

@pytest.mark.parametrize("input_str,expected", [
    # Basic alphanumeric
    ("Simple Test", "Simple_Test"),
    # Long strings get truncated
    ("Very Long Account Name That Exceeds Limit", "Very_Lo_Accoun_Name_T"),
    # Hyphens converted to underscores
    ("Test-With-Hyphens", "Test_With_Hyphens"),
    # Special characters removed
    ("Special@Chars#Here!", "Special_Chars_Here"),
    # Empty string
    ("", ""),
    # Single word
    ("OneWord", "OneWord"),
    # Multiple spaces collapsed
    ("Multiple    Spaces", "Multipl_Spaces"),
])
def test_shorten_and_format_variations(input_str, expected):
    """Test string formatting with various inputs."""
    result = shorten_and_format(input_str)
    assert result == expected
```

### Testing LDAP with Subprocess Mock
```python
# Source: https://testfixtures.readthedocs.io/en/latest/popen.html
from unittest.mock import Mock
import pytest
from mc.integrations.ldap import ldap_search

def test_ldap_search_successful(mocker):
    """Test successful LDAP search returns formatted output."""
    mock_output = """dn: uid=testuser,dc=redhat,dc=com
uid: testuser
cn: Test User
rhatJobTitle: Engineer
"""
    mock_result = Mock()
    mock_result.stdout = mock_output
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("testuser")
    assert success is True
    assert "testuser" in output

def test_ldap_search_not_found(mocker):
    """Test LDAP search with no results returns error."""
    mock_result = Mock()
    mock_result.stdout = ""
    mock_result.returncode = 0

    mocker.patch("subprocess.run", return_value=mock_result)

    success, output = ldap_search("nonexistent")
    assert success is False
    assert "No results found" in output
```

### Testing HTTP Error Scenarios
```python
# Source: https://pytest-test-categories.readthedocs.io/en/stable/examples/http-mocking.html
import pytest
import requests
import responses
from mc.integrations.redhat_api import RedHatAPIClient

@pytest.mark.parametrize("status_code,error_msg", [
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (500, "Internal Server Error"),
])
@responses.activate
def test_api_error_handling(api_client, mock_api_base_url, status_code, error_msg):
    """Test API client handles various HTTP errors."""
    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/12345678",
        json={"error": error_msg},
        status=status_code
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        api_client.fetch_case_details("12345678")

    assert exc_info.value.response.status_code == status_code
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tmpdir fixture | tmp_path fixture | pytest 5.0+ (2019) | pathlib support, cleaner API |
| unittest.mock | pytest-mock mocker fixture | pytest-mock 1.0+ (2015) | Better integration, automatic cleanup |
| Manual response mocking | responses library | 2014+ | Simpler HTTP mocking, less boilerplate |
| Parametrize with tuples | Parametrize with pytest.param | pytest 3.0+ (2016) | Named parameters, test IDs, skip/xfail |
| requests-mock | responses | 2020+ community shift | Simpler API for basic use cases |

**Deprecated/outdated:**
- tmpdir fixture: Use tmp_path instead (pathlib vs py.path.local)
- Direct unittest.mock in tests: Use pytest-mock's mocker fixture
- mockldap library: Unmaintained, use Docker LDAP for integration tests
- pytest-responsemock: Less mature than responses library

## Integration Test Strategy

Based on user context decision for "mix of mocks + real integration tests":

### Unit Tests (Mocked)
- **auth.py:** Mock HTTP response from SSO endpoint
- **redhat_api.py:** Mock all API endpoints with responses
- **workspace.py:** Use tmp_path for real files (fast enough)
- **formatters.py:** Pure functions, no mocking needed
- **file_ops.py:** Use tmp_path for real filesystem
- **ldap.py:** Mock subprocess.run

### Integration Tests (Real/Docker)
- **auth integration:** Test token caching with real temp files
- **API integration (optional):** Real API calls if RH_API_OFFLINE_TOKEN available
- **workspace integration:** Full lifecycle with tmp_path (already real)
- **LDAP Docker:** Spin up rroemhild/docker-test-openldap for real LDAP parsing

### Docker LDAP Setup for CI
Use docker-compose.yml or pytest-docker plugin:
```yaml
# Source: https://github.com/rroemhild/docker-test-openldap
version: '3'
services:
  openldap:
    image: rroemhild/test-openldap:latest
    ports:
      - "10389:10389"
      - "10636:10636"
```

## Open Questions

Things that couldn't be fully resolved:

1. **Token Caching Implementation**
   - What we know: auth.py doesn't currently cache tokens
   - What's unclear: Whether Phase 2 should test non-existent caching or Phase 4 implements it
   - Recommendation: Test current behavior (no caching), note gap for Phase 4. Per requirements, SEC-01 and PERF-03 cover caching.

2. **Real API Integration Tests**
   - What we know: User wants mix of mocks and real API calls
   - What's unclear: How to handle CI without RH_API_OFFLINE_TOKEN
   - Recommendation: Mark real API tests with @pytest.mark.integration, skip if token unavailable

3. **Coverage Target Per Module**
   - What we know: Overall target 60%, tiered by risk is Claude's discretion
   - What's unclear: Exact percentages per module
   - Recommendation:
     - auth.py: 80%+ (critical, security-sensitive)
     - redhat_api.py: 80%+ (critical, user-facing)
     - workspace.py: 70%+ (important, complex logic)
     - formatters.py: 90%+ (easy to test, pure functions)
     - file_ops.py: 70%+ (simple but important)
     - ldap.py: 60%+ (lower risk, nice-to-have feature)

## Sources

### Primary (HIGH confidence)
- [pytest official documentation - Good Integration Practices](https://docs.pytest.org/en/stable/explanation/goodpractices.html)
- [pytest official documentation - Parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html)
- [pytest official documentation - tmp_path](https://docs.pytest.org/en/stable/how-to/tmp_path.html)
- [pytest official documentation - monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)
- [responses library GitHub](https://github.com/getsentry/responses)

### Secondary (MEDIUM confidence)
- [Pytest With Eric - Python Unit Testing Best Practices](https://pytest-with-eric.com/introduction/python-unit-testing-best-practices/)
- [Pytest With Eric - Pytest tmp_path Guide](https://pytest-with-eric.com/pytest-best-practices/pytest-tmp-path/)
- [Real Python - Effective Python Testing With pytest](https://realpython.com/pytest-python-testing/)
- [Docker Test OpenLDAP - GitHub rroemhild](https://github.com/rroemhild/docker-test-openldap)
- [pytest-docker GitHub](https://github.com/avast/pytest-docker)
- [CodiLime - Testing APIs with PyTest Mocks](https://codilime.com/blog/testing-apis-with-pytest-mocks-in-python/)

### Tertiary (LOW confidence)
- WebSearch: pytest best practices 2026 (multiple blog sources)
- WebSearch: LDAP testing patterns (community recommendations)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Official pytest documentation and established libraries
- Architecture patterns: HIGH - Direct from pytest docs and responses library
- Pitfalls: MEDIUM - Mix of documented patterns and experience-based
- Integration strategy: MEDIUM - Docker LDAP verified, API integration is recommended approach
- Module analysis: HIGH - Direct code inspection of mc codebase

**Research date:** 2026-01-22
**Valid until:** 2026-02-22 (30 days - pytest/responses are stable, slow-moving)

**Codebase specifics validated:**
- 5 core modules identified and analyzed
- Dependencies mapped (requests, subprocess, os/filesystem)
- Existing Phase 1 fixtures reviewed and incorporated
- User context decisions integrated into recommendations
