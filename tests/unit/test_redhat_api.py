"""Unit tests for RedHatAPIClient."""

import pytest
import requests
import responses
from unittest.mock import Mock, patch
from mc.integrations.redhat_api import RedHatAPIClient, check_download_safety


@responses.activate
def test_fetch_case_details_success(api_client, mock_api_base_url):
    """Test successful case details retrieval."""
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
    assert result["status"] == "Open"
    assert result["accountNumberRef"] == "1234567"

    # Verify Authorization header sent correctly
    assert len(responses.calls) == 1
    assert "Authorization" in responses.calls[0].request.headers
    assert responses.calls[0].request.headers["Authorization"] == "Bearer fake_access_token"


@responses.activate
def test_fetch_account_details_success(api_client, mock_api_base_url):
    """Test successful account details retrieval."""
    account_number = "1234567"
    expected_data = {
        "number": account_number,
        "name": "Test Account"
    }

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/accounts/{account_number}",
        json=expected_data,
        status=200
    )

    result = api_client.fetch_account_details(account_number)

    assert result["number"] == account_number
    assert result["name"] == "Test Account"


@responses.activate
def test_list_attachments_success(api_client, mock_api_base_url):
    """Test successful attachment listing."""
    case_number = "12345678"
    expected_attachments = [
        {"fileName": "sosreport.tar.gz", "link": "https://example.com/file1"},
        {"fileName": "logs.txt", "link": "https://example.com/file2"}
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
    assert attachments[1]["fileName"] == "logs.txt"


@responses.activate
def test_download_file_success(api_client, tmp_path):
    """Test successful file download with streaming."""
    file_url = "https://api.example.com/download/file123"
    local_file = tmp_path / "downloaded_file.txt"
    test_content = b"This is test file content\nLine 2\nLine 3"

    # Mock HEAD request for file size check
    responses.add(
        responses.HEAD,
        file_url,
        headers={'content-length': str(len(test_content))},
        status=200
    )

    # Mock streaming download
    responses.add(
        responses.GET,
        file_url,
        body=test_content,
        status=200,
        stream=True
    )

    api_client.download_file(file_url, str(local_file))

    # Verify file exists
    assert local_file.exists()

    # Verify content
    assert local_file.read_bytes() == test_content


@pytest.mark.parametrize("status_code,error_msg", [
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (500, "Internal Server Error"),
])
@responses.activate
def test_fetch_case_details_http_errors(api_client, mock_api_base_url, status_code, error_msg):
    """Test fetch_case_details handles various HTTP errors."""
    case_number = "12345678"

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/{case_number}",
        json={"error": error_msg},
        status=status_code
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        api_client.fetch_case_details(case_number)

    # Verify status code matches expected
    assert exc_info.value.response.status_code == status_code


@pytest.mark.parametrize("status_code,error_msg", [
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (500, "Internal Server Error"),
])
@responses.activate
def test_fetch_account_details_http_errors(api_client, mock_api_base_url, status_code, error_msg):
    """Test fetch_account_details handles various HTTP errors."""
    account_number = "1234567"

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/accounts/{account_number}",
        json={"error": error_msg},
        status=status_code
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        api_client.fetch_account_details(account_number)

    # Verify status code matches expected
    assert exc_info.value.response.status_code == status_code


@pytest.mark.parametrize("status_code,error_msg", [
    (401, "Unauthorized"),
    (403, "Forbidden"),
    (404, "Not Found"),
    (500, "Internal Server Error"),
])
@responses.activate
def test_list_attachments_http_errors(api_client, mock_api_base_url, status_code, error_msg):
    """Test list_attachments handles various HTTP errors."""
    case_number = "12345678"

    responses.add(
        responses.GET,
        f"{mock_api_base_url}/cases/{case_number}/attachments/",
        json={"error": error_msg},
        status=status_code
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        api_client.list_attachments(case_number)

    # Verify status code matches expected
    assert exc_info.value.response.status_code == status_code


def test_check_download_safety_small_file():
    """Small files should not trigger warnings."""
    file_size = 1 * 1024 * 1024 * 1024  # 1 GB
    is_safe, warning = check_download_safety(file_size, "/tmp/test.bin")
    assert is_safe is True
    assert warning is None


@patch('shutil.disk_usage')
def test_check_download_safety_large_file_sufficient_space(mock_disk_usage):
    """Large files with sufficient space should warn but allow download."""
    mock_disk_usage.return_value = Mock(free=100 * 1024**3)  # 100 GB free
    file_size = 5 * 1024 * 1024 * 1024  # 5 GB file
    is_safe, warning = check_download_safety(file_size, "/tmp/test.bin")
    assert is_safe is True
    assert warning is not None
    assert "5.00 GB" in warning
    assert "100.00 GB" in warning


@patch('shutil.disk_usage')
def test_check_download_safety_insufficient_space(mock_disk_usage):
    """Large files without sufficient space should block download."""
    mock_disk_usage.return_value = Mock(free=2 * 1024**3)  # 2 GB free
    file_size = 5 * 1024 * 1024 * 1024  # 5 GB file
    is_safe, warning = check_download_safety(file_size, "/tmp/test.bin")
    assert is_safe is False
    assert warning is not None
    assert "Insufficient disk space" in warning
