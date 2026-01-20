"""Root-level fixtures shared across all tests."""

import pytest
import responses


@pytest.fixture(scope="session")
def sample_case_number():
    """Case number used across test suite."""
    return "12345678"


@pytest.fixture(scope="session")
def mock_api_base_url():
    """API base URL for mocking."""
    return "https://api.access.redhat.com/support/v1"


@pytest.fixture(scope="session")
def mock_sso_url():
    """SSO token endpoint URL for mocking."""
    return "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"


@pytest.fixture
def make_case_response():
    """
    Factory fixture for generating case API responses with variations.

    Returns:
        function: Factory function that creates case response dicts

    Example:
        >>> response = make_case_response("12345678", "Test summary", "Open")
    """
    def _make_response(case_number, summary="Default summary", status="Open"):
        return {
            "case_number": case_number,
            "summary": summary,
            "status": status,
            "account_number": "1234567"
        }
    return _make_response
