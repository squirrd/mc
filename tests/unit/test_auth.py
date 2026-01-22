"""Unit tests for auth module."""

import io
import sys
import pytest
import responses
import requests
from mc.utils.auth import get_access_token


@responses.activate
def test_get_access_token_success(mock_env_vars, mock_sso_url):
    """Test successful token retrieval."""
    expected_token = "test_token_123"

    responses.add(
        responses.POST,
        mock_sso_url,
        json={"access_token": expected_token, "expires_in": 3600},
        status=200
    )

    token = get_access_token()

    assert token == expected_token
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == mock_sso_url


def test_get_access_token_missing_env_var(monkeypatch):
    """Test error when RH_API_OFFLINE_TOKEN is not set."""
    # Remove environment variable
    monkeypatch.delenv("RH_API_OFFLINE_TOKEN", raising=False)

    # Capture printed output since auth.py uses print()
    captured_output = io.StringIO()
    sys.stdout = captured_output

    # Verify SystemExit is raised
    with pytest.raises(SystemExit) as exc_info:
        get_access_token()

    # Restore stdout
    sys.stdout = sys.__stdout__
    output = captured_output.getvalue()

    # Verify exit code
    assert exc_info.value.code == 1

    # Verify error message is clear and actionable
    assert "RH_API_OFFLINE_TOKEN" in output
    assert "must be set" in output


@responses.activate
def test_get_access_token_http_401_unauthorized(mock_env_vars, mock_sso_url):
    """Test HTTP 401 Unauthorized error from SSO endpoint."""
    responses.add(
        responses.POST,
        mock_sso_url,
        json={"error": "invalid_grant"},
        status=401
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        get_access_token()

    # Verify status code
    assert exc_info.value.response.status_code == 401


@responses.activate
def test_get_access_token_http_500_server_error(mock_env_vars, mock_sso_url):
    """Test HTTP 500 Internal Server Error from SSO endpoint."""
    responses.add(
        responses.POST,
        mock_sso_url,
        json={"error": "server_error"},
        status=500
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        get_access_token()

    # Verify status code
    assert exc_info.value.response.status_code == 500
