"""Test case metadata caching functionality."""

import json
import os
import time
import pytest
from unittest.mock import Mock, patch
from mc.utils.cache import (
    get_cache_path,
    is_cache_expired,
    load_cache,
    cache_case_metadata,
    get_cached_age_minutes,
    get_case_metadata,
    CACHE_TTL_SECONDS
)


@pytest.fixture
def cache_dir(tmp_path):
    """Override cache directory to use tmp_path for test isolation."""
    test_cache_dir = tmp_path / "cache"
    with patch("mc.utils.cache.CACHE_DIR", str(test_cache_dir)):
        yield test_cache_dir


@pytest.fixture
def mock_api_client():
    """Create mock API client."""
    client = Mock()
    client.fetch_case_details.return_value = {
        'caseNumber': '12345678',
        'summary': 'Test case',
        'accountNumberRef': 'ACC123'
    }
    client.fetch_account_details.return_value = {
        'number': 'ACC123',
        'name': 'Test Account'
    }
    return client


def test_get_cache_path(cache_dir):
    """Test cache path generation."""
    path = get_cache_path("12345678")
    assert path == os.path.join(str(cache_dir), "case_12345678.json")


def test_is_cache_expired():
    """Test cache expiration logic."""
    # Fresh cache (1 minute old)
    cached_at = time.time() - 60
    assert not is_cache_expired(cached_at)

    # Expired cache (31 minutes old)
    cached_at = time.time() - (CACHE_TTL_SECONDS + 60)
    assert is_cache_expired(cached_at)

    # Cache at exact TTL boundary
    cached_at = time.time() - CACHE_TTL_SECONDS
    assert is_cache_expired(cached_at)


def test_cache_miss_no_file(cache_dir):
    """Test cache miss when file doesn't exist."""
    result = load_cache("12345678")
    assert result is None


def test_cache_hit_within_ttl(cache_dir):
    """Test cache hit when data is within TTL."""
    # Create cache file
    case_data = {
        'data': {
            'case_details': {'caseNumber': '12345678'},
            'account_details': {'name': 'Test'}
        },
        'cached_at': time.time()
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        json.dump(case_data, f)

    # Load cache
    result = load_cache("12345678")
    assert result is not None
    assert result['data']['case_details']['caseNumber'] == '12345678'
    assert result['data']['account_details']['name'] == 'Test'


def test_cache_corrupted_json(cache_dir):
    """Test handling of corrupted cache file."""
    # Create corrupted cache file
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        f.write("{ invalid json }")

    # Should return None and delete corrupted file
    result = load_cache("12345678")
    assert result is None
    assert not cache_path.exists()


def test_cache_case_metadata(cache_dir):
    """Test caching case metadata."""
    case_details = {'caseNumber': '12345678', 'summary': 'Test'}
    account_details = {'name': 'Test Account'}

    cache_case_metadata("12345678", case_details, account_details)

    # Verify cache file was created
    cache_path = cache_dir / "case_12345678.json"
    assert cache_path.exists()

    # Verify cache structure
    with open(cache_path, 'r') as f:
        cache = json.load(f)
    assert 'data' in cache
    assert 'cached_at' in cache
    assert cache['data']['case_details'] == case_details
    assert cache['data']['account_details'] == account_details

    # Verify permissions (0600)
    stat_info = os.stat(cache_path)
    perms = oct(stat_info.st_mode)[-3:]
    assert perms == '600'


def test_get_cached_age_minutes(cache_dir):
    """Test cache age calculation."""
    # No cache
    age = get_cached_age_minutes("12345678")
    assert age is None

    # Create cache 5 minutes ago
    cache_data = {
        'data': {
            'case_details': {'caseNumber': '12345678'},
            'account_details': {'name': 'Test'}
        },
        'cached_at': time.time() - 300  # 5 minutes ago
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

    age = get_cached_age_minutes("12345678")
    assert age == 5


def test_get_case_metadata_cache_hit(cache_dir, mock_api_client):
    """Test get_case_metadata returns cached data within TTL."""
    # Create fresh cache
    cache_data = {
        'data': {
            'case_details': {'caseNumber': '12345678', 'summary': 'Cached'},
            'account_details': {'name': 'Cached Account'}
        },
        'cached_at': time.time()
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

    # Get metadata
    case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client)

    # Should return cached data without calling API
    assert was_cached is True
    assert case_details['summary'] == 'Cached'
    assert account_details['name'] == 'Cached Account'
    mock_api_client.fetch_case_details.assert_not_called()
    mock_api_client.fetch_account_details.assert_not_called()


def test_get_case_metadata_cache_miss(cache_dir, mock_api_client):
    """Test get_case_metadata fetches from API when cache missing."""
    # Get metadata (no cache exists)
    case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client)

    # Should fetch from API
    assert was_cached is False
    assert case_details['summary'] == 'Test case'
    assert account_details['name'] == 'Test Account'
    mock_api_client.fetch_case_details.assert_called_once_with("12345678")
    mock_api_client.fetch_account_details.assert_called_once_with('ACC123')

    # Should have created cache
    cache_path = cache_dir / "case_12345678.json"
    assert cache_path.exists()


def test_get_case_metadata_cache_expired(cache_dir, mock_api_client):
    """Test get_case_metadata fetches from API when cache expired."""
    # Create expired cache (31 minutes old)
    cache_data = {
        'data': {
            'case_details': {'caseNumber': '12345678', 'summary': 'Expired'},
            'account_details': {'name': 'Expired Account'}
        },
        'cached_at': time.time() - (CACHE_TTL_SECONDS + 60)
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

    # Get metadata
    case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client)

    # Should fetch from API (cache expired)
    assert was_cached is False
    assert case_details['summary'] == 'Test case'
    assert account_details['name'] == 'Test Account'
    mock_api_client.fetch_case_details.assert_called_once_with("12345678")
    mock_api_client.fetch_account_details.assert_called_once_with('ACC123')


def test_get_case_metadata_force_refresh(cache_dir, mock_api_client):
    """Test force_refresh bypasses cache."""
    # Create fresh cache
    cache_data = {
        'data': {
            'case_details': {'caseNumber': '12345678', 'summary': 'Cached'},
            'account_details': {'name': 'Cached Account'}
        },
        'cached_at': time.time()
    }
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / "case_12345678.json"
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

    # Get metadata with force_refresh
    case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client, force_refresh=True)

    # Should fetch from API despite valid cache
    assert was_cached is False
    assert case_details['summary'] == 'Test case'
    assert account_details['name'] == 'Test Account'
    mock_api_client.fetch_case_details.assert_called_once_with("12345678")
    mock_api_client.fetch_account_details.assert_called_once_with('ACC123')
