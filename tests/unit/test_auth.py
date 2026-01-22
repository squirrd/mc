"""Unit tests for auth module."""

import os
import pytest
import responses
import requests
from mc.utils.auth import get_access_token, TOKEN_CACHE_PATH


@pytest.fixture(autouse=True)
def clear_token_cache():
    """Clear token cache before and after each test."""
    # Clear before test
    if os.path.exists(TOKEN_CACHE_PATH):
        os.remove(TOKEN_CACHE_PATH)
    yield
    # Clear after test
    if os.path.exists(TOKEN_CACHE_PATH):
        os.remove(TOKEN_CACHE_PATH)


@responses.activate
def test_get_access_token_success(mock_sso_url):
    """Test successful token retrieval."""
    expected_token = "test_token_123"
    offline_token = "fake_offline_token"

    responses.add(
        responses.POST,
        mock_sso_url,
        json={"access_token": expected_token, "expires_in": 3600},
        status=200
    )

    token = get_access_token(offline_token)

    assert token == expected_token
    assert len(responses.calls) == 1
    assert responses.calls[0].request.url == mock_sso_url


@responses.activate
def test_get_access_token_http_401_unauthorized(mock_sso_url):
    """Test HTTP 401 Unauthorized error from SSO endpoint."""
    offline_token = "fake_offline_token"

    responses.add(
        responses.POST,
        mock_sso_url,
        json={"error": "invalid_grant"},
        status=401
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        get_access_token(offline_token)

    # Verify status code
    assert exc_info.value.response.status_code == 401


@responses.activate
def test_get_access_token_http_500_server_error(mock_sso_url):
    """Test HTTP 500 Internal Server Error from SSO endpoint."""
    offline_token = "fake_offline_token"

    responses.add(
        responses.POST,
        mock_sso_url,
        json={"error": "server_error"},
        status=500
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        get_access_token(offline_token)

    # Verify status code
    assert exc_info.value.response.status_code == 500
