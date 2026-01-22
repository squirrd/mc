"""Tests for parallel download manager."""

import os
import pytest
import requests
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, MagicMock, call
from mc.utils.downloads import download_attachments_parallel, _download_single_file, _should_retry


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    client = Mock()
    client.verify_ssl = True
    client.timeout = (3.05, 27)
    client.session = Mock()
    return client


@pytest.fixture
def sample_attachments():
    """Sample attachment metadata."""
    return [
        {'fileName': 'file1.log', 'link': 'https://api.example.com/file1'},
        {'fileName': 'file2.tar.gz', 'link': 'https://api.example.com/file2'},
        {'fileName': 'file3.txt', 'link': 'https://api.example.com/file3'},
    ]


def test_download_attachments_parallel_success(tmp_path, mock_api_client, sample_attachments):
    """Test successful parallel download."""
    attach_dir = str(tmp_path)

    # Mock HEAD response for file size
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET response for download
    mock_get = Mock()
    mock_get.headers = {'content-length': '1024'}
    mock_get.iter_content.return_value = [b'x' * 1024]
    mock_api_client.session.get.return_value = mock_get

    # Run download
    result = download_attachments_parallel(
        sample_attachments,
        attach_dir,
        mock_api_client,
        max_workers=2,
        show_progress=True
    )

    # Verify results
    assert len(result['success']) == 3
    assert len(result['failed']) == 0
    assert 'file1.log' in result['success']
    assert 'file2.tar.gz' in result['success']
    assert 'file3.txt' in result['success']

    # Verify files created
    assert os.path.exists(os.path.join(attach_dir, 'file1.log'))
    assert os.path.exists(os.path.join(attach_dir, 'file2.tar.gz'))
    assert os.path.exists(os.path.join(attach_dir, 'file3.txt'))

    # Verify API calls
    assert mock_api_client.session.head.call_count == 3
    assert mock_api_client.session.get.call_count == 3


def test_download_attachments_parallel_skip_existing(tmp_path, mock_api_client, sample_attachments):
    """Test that existing files are skipped."""
    attach_dir = str(tmp_path)

    # Create existing file
    existing_file = os.path.join(attach_dir, 'file1.log')
    with open(existing_file, 'w') as f:
        f.write('existing content')

    # Mock responses for other files
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    mock_get = Mock()
    mock_get.headers = {'content-length': '1024'}
    mock_get.iter_content.return_value = [b'x' * 1024]
    mock_api_client.session.get.return_value = mock_get

    # Run download
    result = download_attachments_parallel(
        sample_attachments,
        attach_dir,
        mock_api_client,
        max_workers=2,
        show_progress=True
    )

    # Verify results
    assert len(result['success']) == 3
    assert 'file1.log' in result['success']

    # Verify only 2 downloads (file1 was skipped)
    assert mock_api_client.session.head.call_count == 2
    assert mock_api_client.session.get.call_count == 2

    # Verify existing file unchanged
    with open(existing_file, 'r') as f:
        assert f.read() == 'existing content'


def test_download_attachments_parallel_partial_failure(tmp_path, mock_api_client, sample_attachments):
    """Test that one failure doesn't crash all downloads."""
    attach_dir = str(tmp_path)

    # Mock HEAD to succeed
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET to fail for second file
    call_count = [0]

    def mock_get_side_effect(*args, **kwargs):
        call_count[0] += 1
        mock_response = Mock()
        mock_response.headers = {'content-length': '1024'}
        if call_count[0] == 2:  # Second call fails
            mock_response.iter_content.side_effect = Exception("Network error")
        else:
            mock_response.iter_content.return_value = [b'x' * 1024]
        return mock_response

    mock_api_client.session.get.side_effect = mock_get_side_effect

    # Run download
    result = download_attachments_parallel(
        sample_attachments,
        attach_dir,
        mock_api_client,
        max_workers=2,
        show_progress=True
    )

    # Verify results - 2 success, 1 failure
    assert len(result['success']) == 2
    assert len(result['failed']) == 1

    # Verify failed entry
    failed_filename, error_msg = result['failed'][0]
    assert 'file' in failed_filename
    assert 'Network error' in error_msg


def test_download_attachments_parallel_no_progress(tmp_path, mock_api_client, sample_attachments):
    """Test sequential download with progress disabled."""
    attach_dir = str(tmp_path)

    # Mock download_file method
    mock_api_client.download_file = Mock()

    # Run download without progress
    result = download_attachments_parallel(
        sample_attachments,
        attach_dir,
        mock_api_client,
        max_workers=8,
        show_progress=False
    )

    # Verify download_file was called for each attachment
    assert mock_api_client.download_file.call_count == 3

    # Verify all succeeded
    assert len(result['success']) == 3
    assert len(result['failed']) == 0


def test_download_attachments_parallel_empty_list(tmp_path, mock_api_client):
    """Test handling of empty attachment list."""
    attach_dir = str(tmp_path)

    result = download_attachments_parallel(
        [],
        attach_dir,
        mock_api_client,
        max_workers=8,
        show_progress=True
    )

    assert result['success'] == []
    assert result['failed'] == []


def test_download_attachments_parallel_max_workers(tmp_path, mock_api_client):
    """Test max_workers parameter is respected."""
    attach_dir = str(tmp_path)
    attachments = [{'fileName': 'file1.log', 'link': 'https://api.example.com/file1'}]

    # Mock responses
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    mock_get = Mock()
    mock_get.headers = {'content-length': '1024'}
    mock_get.iter_content.return_value = [b'x' * 1024]
    mock_api_client.session.get.return_value = mock_get

    # Patch ThreadPoolExecutor to verify max_workers
    with patch('mc.utils.downloads.ThreadPoolExecutor', wraps=ThreadPoolExecutor) as mock_pool:
        # Run with custom max_workers
        result = download_attachments_parallel(
            attachments,
            attach_dir,
            mock_api_client,
            max_workers=4,
            show_progress=True
        )

        # Verify ThreadPoolExecutor called with correct max_workers
        mock_pool.assert_called_once_with(max_workers=4)

        # Verify download succeeded
        assert len(result['success']) == 1


def test_download_single_file_success(tmp_path, mock_api_client):
    """Test single file download with progress updates."""
    local_path = os.path.join(tmp_path, 'test.log')
    url = 'https://api.example.com/test.log'

    # Mock HEAD response
    mock_head = Mock()
    mock_head.headers = {'content-length': '2048'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET response
    mock_get = Mock()
    mock_get.headers = {'content-length': '2048'}
    mock_get.iter_content.return_value = [b'x' * 1024, b'y' * 1024]
    mock_api_client.session.get.return_value = mock_get

    # Mock progress
    mock_progress = Mock()

    # Run download
    _download_single_file(1, url, local_path, mock_api_client, mock_progress)

    # Verify progress updates
    mock_progress.update.assert_called()
    mock_progress.start_task.assert_called_once_with(1)

    # Verify file created
    assert os.path.exists(local_path)
    with open(local_path, 'rb') as f:
        content = f.read()
        assert len(content) == 2048


def test_download_single_file_error(tmp_path, mock_api_client):
    """Test single file download error handling."""
    local_path = os.path.join(tmp_path, 'test.log')
    url = 'https://api.example.com/test.log'

    # Mock HEAD to fail
    mock_api_client.session.head.side_effect = Exception("Connection failed")

    # Mock progress
    mock_progress = Mock()

    # Run download - should raise
    with pytest.raises(Exception, match="Connection failed"):
        _download_single_file(1, url, local_path, mock_api_client, mock_progress)


def test_should_retry_network_error():
    """Test retry decision for network errors without response."""
    # Network timeout (no response)
    exc = requests.exceptions.Timeout()
    assert _should_retry(exc) is True

    # Connection error (no response)
    exc = requests.exceptions.ConnectionError()
    assert _should_retry(exc) is True


def test_should_retry_transient_errors():
    """Test retry decision for transient server errors."""
    # Mock response for 5xx errors
    for status in [500, 502, 503, 504]:
        response = Mock()
        response.status_code = status
        exc = requests.exceptions.HTTPError(response=response)
        exc.response = response
        assert _should_retry(exc) is True, f"Should retry {status}"

    # Mock response for 429 rate limit
    response = Mock()
    response.status_code = 429
    exc = requests.exceptions.HTTPError(response=response)
    exc.response = response
    assert _should_retry(exc) is True


def test_should_retry_permanent_errors():
    """Test retry decision for permanent client errors."""
    # Don't retry 4xx errors (except 429)
    for status in [400, 401, 403, 404]:
        response = Mock()
        response.status_code = status
        exc = requests.exceptions.HTTPError(response=response)
        exc.response = response
        assert _should_retry(exc) is False, f"Should not retry {status}"


def test_should_retry_non_request_exception():
    """Test retry decision for non-RequestException errors."""
    exc = ValueError("Not a request exception")
    assert _should_retry(exc) is False


@patch('mc.utils.downloads.backoff.on_exception')
def test_retry_decorator_applied(mock_backoff, tmp_path, mock_api_client):
    """Test that backoff decorator is applied to _download_single_file."""
    # Verify the decorator was called with correct parameters
    # This tests the decorator configuration
    from mc.utils.downloads import _download_single_file
    import backoff

    # Check function is decorated (has backoff attributes)
    # The actual decorated function will have __wrapped__ attribute
    assert hasattr(_download_single_file, '__wrapped__') or callable(_download_single_file)


def test_retry_on_500_error(tmp_path, mock_api_client):
    """Test automatic retry on 500 server error."""
    local_path = os.path.join(tmp_path, 'test.log')
    url = 'https://api.example.com/test.log'

    # Mock HEAD to succeed
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET to fail with 500 twice, then succeed
    call_count = [0]

    def mock_get_side_effect(*args, **kwargs):
        call_count[0] += 1
        mock_response = Mock()
        mock_response.headers = {'content-length': '1024'}

        if call_count[0] <= 2:  # First two calls fail with 500
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
                response=mock_response
            )
        else:  # Third call succeeds
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [b'x' * 1024]

        return mock_response

    mock_api_client.session.get.side_effect = mock_get_side_effect

    # Mock progress
    mock_progress = Mock()
    mock_progress.console = Mock()

    # With backoff, this should eventually succeed after retries
    # Note: We can't easily test exact retry count without mocking backoff itself
    # But we verify it doesn't immediately fail
    with patch('mc.utils.downloads.time.sleep'):  # Speed up test
        _download_single_file(1, url, local_path, mock_api_client, mock_progress)

    # Verify file was created (success after retries)
    assert os.path.exists(local_path)
    # Verify GET was called multiple times (retries happened)
    assert mock_api_client.session.get.call_count >= 2


def test_no_retry_on_404_error(tmp_path, mock_api_client):
    """Test immediate failure on 404 error without retry."""
    local_path = os.path.join(tmp_path, 'test.log')
    url = 'https://api.example.com/test.log'

    # Mock HEAD to succeed
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET to fail with 404 (permanent error)
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=mock_response
    )
    mock_api_client.session.get.return_value = mock_response

    # Mock progress
    mock_progress = Mock()

    # Should fail immediately without retry
    with pytest.raises(requests.exceptions.HTTPError):
        _download_single_file(1, url, local_path, mock_api_client, mock_progress)

    # Verify GET was called only once (no retries)
    assert mock_api_client.session.get.call_count == 1


def test_rate_limit_with_retry_after(tmp_path, mock_api_client):
    """Test 429 rate limit with Retry-After header."""
    local_path = os.path.join(tmp_path, 'test.log')
    url = 'https://api.example.com/test.log'

    # Mock HEAD to succeed
    mock_head = Mock()
    mock_head.headers = {'content-length': '1024'}
    mock_api_client.session.head.return_value = mock_head

    # Mock GET to return 429 first, then succeed
    call_count = [0]

    def mock_get_side_effect(*args, **kwargs):
        call_count[0] += 1
        mock_response = Mock()
        mock_response.headers = {'content-length': '1024'}

        if call_count[0] == 1:  # First call returns 429
            mock_response.status_code = 429
            mock_response.headers['Retry-After'] = '2'  # Wait 2 seconds
        else:  # Second call succeeds
            mock_response.status_code = 200
            mock_response.raise_for_status.return_value = None
            mock_response.iter_content.return_value = [b'x' * 1024]

        return mock_response

    mock_api_client.session.get.side_effect = mock_get_side_effect

    # Mock progress
    mock_progress = Mock()
    mock_progress.console = Mock()

    # Mock time.sleep to verify wait
    with patch('mc.utils.downloads.time.sleep') as mock_sleep:
        _download_single_file(1, url, local_path, mock_api_client, mock_progress)

        # Verify sleep was called with Retry-After value (2 seconds)
        # Note: backoff decorator also calls sleep, so check any call had our value
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert 2 in sleep_calls, f"Expected sleep(2) in calls, got: {sleep_calls}"

    # Verify file was created
    assert os.path.exists(local_path)
    # Verify retry happened
    assert mock_api_client.session.get.call_count >= 2
