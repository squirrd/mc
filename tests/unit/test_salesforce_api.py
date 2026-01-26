"""Unit tests for SalesforceAPIClient."""

import time
import pytest
from unittest.mock import Mock, MagicMock
from simple_salesforce.exceptions import SalesforceAuthenticationFailed, SalesforceError  # type: ignore
from mc.integrations.salesforce_api import SalesforceAPIClient, TOKEN_LIFETIME_SECONDS, REFRESH_THRESHOLD_SECONDS
from mc.exceptions import SalesforceAPIError


@pytest.fixture
def sf_credentials():
    """Salesforce credentials for testing."""
    return {
        "username": "test@example.com",
        "password": "testpass",
        "security_token": "testtoken123"
    }


@pytest.fixture
def sf_client(sf_credentials):
    """SalesforceAPIClient instance for testing."""
    return SalesforceAPIClient(
        username=sf_credentials["username"],
        password=sf_credentials["password"],
        security_token=sf_credentials["security_token"]
    )


@pytest.fixture
def mock_salesforce_session(mocker):
    """Mock Salesforce session instance."""
    mock_session = MagicMock()
    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )
    return mock_session


def test_query_case_success(sf_client, mock_salesforce_session):
    """Test successful case query with all metadata fields."""
    case_number = "12345678"

    # Mock SOQL query response
    mock_salesforce_session.query.return_value = {
        "records": [{
            "CaseNumber": case_number,
            "Account": {"Name": "Acme Corp"},
            "Cluster_ID__c": "abc123",
            "Subject": "Cluster down",
            "Severity__c": "High",
            "Status": "Open",
            "Owner": {"Name": "John Doe"},
            "CreatedDate": "2026-01-26T00:00:00Z"
        }]
    }

    result = sf_client.query_case(case_number)

    # Verify all fields extracted correctly
    assert result["case_number"] == case_number
    assert result["account_name"] == "Acme Corp"
    assert result["cluster_id"] == "abc123"
    assert result["subject"] == "Cluster down"
    assert result["severity"] == "High"
    assert result["status"] == "Open"
    assert result["owner_name"] == "John Doe"
    assert result["created_date"] == "2026-01-26T00:00:00Z"

    # Verify SOQL query was called
    assert mock_salesforce_session.query.call_count == 1
    query_arg = mock_salesforce_session.query.call_args[0][0]
    assert "CaseNumber" in query_arg
    assert "Account.Name" in query_arg
    assert "Cluster_ID__c" in query_arg
    assert f"WHERE CaseNumber = '{case_number}'" in query_arg


def test_query_case_not_found(sf_client, mock_salesforce_session):
    """Test query when case not found (empty records)."""
    case_number = "99999999"

    # Mock empty result
    mock_salesforce_session.query.return_value = {
        "records": []
    }

    with pytest.raises(SalesforceAPIError) as exc_info:
        sf_client.query_case(case_number)

    assert exc_info.value.status_code == 404
    assert case_number in str(exc_info.value)


def test_query_case_missing_account(sf_client, mock_salesforce_session):
    """Test query handles missing Account relationship gracefully."""
    case_number = "12345678"

    # Mock response with null Account
    mock_salesforce_session.query.return_value = {
        "records": [{
            "CaseNumber": case_number,
            "Account": None,  # Missing account relationship
            "Cluster_ID__c": "abc123",
            "Subject": "Test case",
            "Severity__c": "Medium",
            "Status": "Open",
            "Owner": {"Name": "Jane Smith"},
            "CreatedDate": "2026-01-26T00:00:00Z"
        }]
    }

    result = sf_client.query_case(case_number)

    # Should default to empty string when Account is None
    assert result["account_name"] == ""
    assert result["case_number"] == case_number


def test_query_case_missing_optional_fields(sf_client, mock_salesforce_session):
    """Test query handles missing optional fields (Cluster_ID__c)."""
    case_number = "12345678"

    # Mock response without Cluster_ID__c
    mock_salesforce_session.query.return_value = {
        "records": [{
            "CaseNumber": case_number,
            "Account": {"Name": "Test Account"},
            # Cluster_ID__c missing
            "Subject": "Test case",
            "Severity__c": "Low",
            "Status": "Closed",
            "Owner": {"Name": "Support Team"},
            "CreatedDate": "2026-01-26T00:00:00Z"
        }]
    }

    result = sf_client.query_case(case_number)

    # Should default to empty string for missing fields
    assert result["cluster_id"] == ""
    assert result["account_name"] == "Test Account"


def test_rate_limiting_429_retry(sf_client, mocker):
    """Test retry with exponential backoff on rate limiting."""
    case_number = "12345678"

    mock_session = MagicMock()

    # First two calls raise rate limit error, third succeeds
    rate_limit_error = SalesforceError(
        url="https://test.salesforce.com",
        status=429,
        resource_name="Case",
        content=b"REQUEST_LIMIT_EXCEEDED"
    )

    mock_session.query.side_effect = [
        rate_limit_error,
        rate_limit_error,
        {
            "records": [{
                "CaseNumber": case_number,
                "Account": {"Name": "Test"},
                "Subject": "Test",
                "Severity__c": "High",
                "Status": "Open",
                "Owner": {"Name": "Tester"},
                "CreatedDate": "2026-01-26T00:00:00Z"
            }]
        }
    ]

    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    result = sf_client.query_case(case_number)

    # Should succeed after retries
    assert result["case_number"] == case_number
    assert mock_session.query.call_count == 3  # Verify retries occurred


def test_authentication_failure_401(sf_client, mocker):
    """Test authentication failure raises error without retry."""
    case_number = "12345678"

    mock_session = MagicMock()
    auth_error = SalesforceError(
        url="https://test.salesforce.com",
        status=401,
        resource_name="Case",
        content=b"INVALID_SESSION_ID: Session expired or invalid"
    )
    mock_session.query.side_effect = auth_error

    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    with pytest.raises(SalesforceAPIError) as exc_info:
        sf_client.query_case(case_number)

    assert exc_info.value.status_code == 401


def test_permission_denied_403(sf_client, mocker):
    """Test permission denied error."""
    case_number = "12345678"

    mock_session = MagicMock()
    permission_error = SalesforceError(
        url="https://test.salesforce.com",
        status=403,
        resource_name="Case",
        content=b"INSUFFICIENT_ACCESS: User lacks permissions"
    )
    mock_session.query.side_effect = permission_error

    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    with pytest.raises(SalesforceAPIError) as exc_info:
        sf_client.query_case(case_number)

    assert exc_info.value.status_code == 403


def test_token_refresh_proactive(sf_client, mocker):
    """Test proactive token refresh when within 5 minutes of expiry."""
    case_number = "12345678"

    # Mock time to simulate near expiry
    current_time = time.time()
    near_expiry_time = current_time + (REFRESH_THRESHOLD_SECONDS - 60)  # 4 minutes until expiry

    # Set token to expire soon
    sf_client._token_expires_at = near_expiry_time

    mock_session = MagicMock()
    mock_session.query.return_value = {
        "records": [{
            "CaseNumber": case_number,
            "Account": {"Name": "Test"},
            "Subject": "Test",
            "Severity__c": "High",
            "Status": "Open",
            "Owner": {"Name": "Tester"},
            "CreatedDate": "2026-01-26T00:00:00Z"
        }]
    }

    mock_salesforce_class = mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    result = sf_client.query_case(case_number)

    # Should have refreshed session (created new Salesforce instance)
    assert mock_salesforce_class.call_count >= 1
    assert result["case_number"] == case_number


def test_token_refresh_not_needed(sf_client, mocker):
    """Test no refresh when token is still fresh."""
    case_number = "12345678"

    # Set token to expire far in future
    sf_client._token_expires_at = time.time() + TOKEN_LIFETIME_SECONDS - 60  # Fresh token

    mock_session = MagicMock()
    sf_client._session = mock_session  # Use existing session

    mock_session.query.return_value = {
        "records": [{
            "CaseNumber": case_number,
            "Account": {"Name": "Test"},
            "Subject": "Test",
            "Severity__c": "High",
            "Status": "Open",
            "Owner": {"Name": "Tester"},
            "CreatedDate": "2026-01-26T00:00:00Z"
        }]
    }

    mock_salesforce_class = mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    result = sf_client.query_case(case_number)

    # Should NOT have created new session (used existing)
    assert mock_salesforce_class.call_count == 0
    assert result["case_number"] == case_number


def test_session_creation_authentication_failed(sf_credentials, mocker):
    """Test session creation handles authentication failure."""
    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        side_effect=SalesforceAuthenticationFailed("INVALID_LOGIN", "Invalid credentials")
    )

    client = SalesforceAPIClient(
        username=sf_credentials["username"],
        password=sf_credentials["password"],
        security_token=sf_credentials["security_token"]
    )

    with pytest.raises(SalesforceAPIError) as exc_info:
        client._create_session()

    assert exc_info.value.status_code == 401
    assert "Authentication failed" in str(exc_info.value)


def test_session_creation_generic_error(sf_credentials, mocker):
    """Test session creation handles generic Salesforce errors."""
    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        side_effect=SalesforceError(
            url="https://test.salesforce.com",
            status=500,
            resource_name="Session",
            content=b"Generic error"
        )
    )

    client = SalesforceAPIClient(
        username=sf_credentials["username"],
        password=sf_credentials["password"],
        security_token=sf_credentials["security_token"]
    )

    with pytest.raises(SalesforceAPIError) as exc_info:
        client._create_session()

    assert "Failed to create session" in str(exc_info.value)


def test_needs_refresh_no_session(sf_client):
    """Test _needs_refresh returns True when no session exists."""
    sf_client._session = None
    assert sf_client._needs_refresh() is True


def test_needs_refresh_within_threshold(sf_client):
    """Test _needs_refresh returns True within 5-minute threshold."""
    sf_client._session = MagicMock()
    # Set expiry to 4 minutes from now (within 5-minute threshold)
    sf_client._token_expires_at = time.time() + 240
    assert sf_client._needs_refresh() is True


def test_needs_refresh_outside_threshold(sf_client):
    """Test _needs_refresh returns False when well before expiry."""
    sf_client._session = MagicMock()
    # Set expiry to 30 minutes from now (outside threshold)
    sf_client._token_expires_at = time.time() + 1800
    assert sf_client._needs_refresh() is False


def test_context_manager(sf_credentials, mocker):
    """Test client works as context manager."""
    mock_session = MagicMock()
    mocker.patch(
        "mc.integrations.salesforce_api.Salesforce",
        return_value=mock_session
    )

    with SalesforceAPIClient(
        username=sf_credentials["username"],
        password=sf_credentials["password"],
        security_token=sf_credentials["security_token"]
    ) as client:
        assert client is not None
        # Session should be None initially (lazy creation)
        assert client._session is None

    # After exit, session should be closed (set to None)
    assert client._session is None


def test_close_method(sf_client):
    """Test close method cleans up session."""
    sf_client._session = MagicMock()

    sf_client.close()

    assert sf_client._session is None
