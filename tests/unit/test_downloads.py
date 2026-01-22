"""Tests for parallel download manager."""

import os
import pytest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, MagicMock, call
from mc.utils.downloads import download_attachments_parallel, _download_single_file


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
