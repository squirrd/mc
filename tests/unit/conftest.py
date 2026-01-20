"""Unit test specific fixtures."""

import pytest
from mc.integrations.redhat_api import RedHatAPIClient


@pytest.fixture
def mock_case_data():
    """
    Fresh mock case data per test (function scope).

    Returns:
        dict: Case data with case_number, summary, account_number, status
    """
    return {
        "case_number": "12345678",
        "summary": "Test case summary",
        "account_number": "1234567",
        "status": "Open"
    }


@pytest.fixture
def mock_access_token():
    """
    Mock access token for API authentication.

    Returns:
        str: Fake access token
    """
    return "fake_access_token"


@pytest.fixture
def api_client(mock_access_token):
    """
    RedHatAPIClient instance with fake token.

    Args:
        mock_access_token: Fixture providing fake token

    Returns:
        RedHatAPIClient: Client instance for testing
    """
    return RedHatAPIClient(access_token=mock_access_token)


@pytest.fixture
def mock_env_vars(monkeypatch):
    """
    Set RH_API_OFFLINE_TOKEN environment variable for auth tests.

    Args:
        monkeypatch: pytest's monkeypatch fixture for environment variables
    """
    monkeypatch.setenv("RH_API_OFFLINE_TOKEN", "fake_offline_token")
