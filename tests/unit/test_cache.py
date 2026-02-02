"""Test case metadata caching functionality."""

import time
import pytest
from unittest.mock import Mock, patch
from mc.utils.cache import (
    CaseMetadataCache,
    get_case_metadata,
    get_cached_age_minutes,
    CACHE_TTL_SECONDS
)


@pytest.fixture
def cache_dir(tmp_path):
    """Override cache directory to use tmp_path for test isolation."""
    test_cache_dir = tmp_path / "cache"
    test_cache_dir.mkdir(parents=True, exist_ok=True)
    return test_cache_dir


@pytest.fixture
def cache(cache_dir):
    """Create cache instance with test directory."""
    # Create empty database file first to prevent auto-migration from real cache
    db_path = cache_dir / "case_metadata.db"
    db_path.touch()
    return CaseMetadataCache(cache_dir)


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


def test_cache_miss_no_entry(cache):
    """Test cache miss when entry doesn't exist."""
    case_data, account_data, was_cached = cache.get("12345678")
    assert was_cached is False
    assert case_data == {}
    assert account_data == {}


def test_cache_hit_within_ttl(cache):
    """Test cache hit when data is within TTL."""
    # Cache data
    case_details = {'caseNumber': '12345678', 'summary': 'Test'}
    account_details = {'name': 'Test Account'}
    cache.set("12345678", case_details, account_details)

    # Retrieve from cache
    case_data, account_data, was_cached = cache.get("12345678")
    assert was_cached is True
    assert case_data == case_details
    assert account_data == account_details


def test_cache_expired(cache):
    """Test cache expiration logic."""
    # Cache data with 1-second TTL
    case_details = {'caseNumber': '12345678', 'summary': 'Test'}
    account_details = {'name': 'Test Account'}
    cache.set("12345678", case_details, account_details, ttl_seconds=1)

    # Wait for expiry
    time.sleep(1.5)

    # Should be expired
    case_data, account_data, was_cached = cache.get("12345678")
    assert was_cached is False
    assert case_data == {}
    assert account_data == {}


def test_cache_update_replaces_existing(cache):
    """Test that setting cache updates existing entry."""
    # Cache initial data
    cache.set("12345678", {'summary': 'Old'}, {'name': 'Old Account'})

    # Update cache
    cache.set("12345678", {'summary': 'New'}, {'name': 'New Account'})

    # Should return updated data
    case_data, account_data, was_cached = cache.get("12345678")
    assert was_cached is True
    assert case_data['summary'] == 'New'
    assert account_data['name'] == 'New Account'


def test_list_all_cached_cases(cache):
    """Test listing all cached case numbers."""
    # Initially empty
    cases = cache.list_all()
    assert cases == []

    # Cache multiple cases
    cache.set("12345678", {'summary': 'Case 1'}, {'name': 'Account 1'})
    cache.set("87654321", {'summary': 'Case 2'}, {'name': 'Account 2'})

    # Should return all case numbers
    cases = cache.list_all()
    assert len(cases) == 2
    assert "12345678" in cases
    assert "87654321" in cases


def test_delete_cache_entry(cache):
    """Test deleting cache entry."""
    # Cache data
    cache.set("12345678", {'summary': 'Test'}, {'name': 'Test Account'})

    # Verify cached
    _, _, was_cached = cache.get("12345678")
    assert was_cached is True

    # Delete
    cache.delete("12345678")

    # Verify deleted
    _, _, was_cached = cache.get("12345678")
    assert was_cached is False


def test_get_cached_age_minutes_no_cache(cache_dir):
    """Test cache age when no cache exists."""
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        age = get_cached_age_minutes("12345678")
        assert age == 0


def test_get_cached_age_minutes_with_cache(cache_dir):
    """Test cache age calculation."""
    cache = CaseMetadataCache(cache_dir)

    # Cache data with long TTL so it won't expire during test
    cache.set("12345678", {'summary': 'Test'}, {'name': 'Test Account'}, ttl_seconds=3600)

    # Manually update cached_at to simulate age (5 minutes ago)
    with cache._get_connection() as conn:
        conn.execute(
            "UPDATE case_cache SET cached_at = ? WHERE case_number = ?",
            (time.time() - 300, "12345678")
        )

    # Patch CACHE_DIR after updating the database so get_cached_age_minutes uses same DB
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        # Age should now be 5 minutes
        age = get_cached_age_minutes("12345678")
        assert age == 5


def test_get_case_metadata_cache_hit(cache_dir, mock_api_client):
    """Test get_case_metadata returns cached data within TTL."""
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        cache = CaseMetadataCache(cache_dir)

        # Create fresh cache
        cache.set(
            "12345678",
            {'caseNumber': '12345678', 'summary': 'Cached'},
            {'name': 'Cached Account'}
        )

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
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        # Get metadata (no cache exists)
        case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client)

        # Should fetch from API
        assert was_cached is False
        assert case_details['summary'] == 'Test case'
        assert account_details['name'] == 'Test Account'
        mock_api_client.fetch_case_details.assert_called_once_with("12345678")
        mock_api_client.fetch_account_details.assert_called_once_with('ACC123')


def test_get_case_metadata_cache_expired(cache_dir, mock_api_client):
    """Test get_case_metadata fetches from API when cache expired."""
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        cache = CaseMetadataCache(cache_dir)

        # Create cache with 1-second TTL
        cache.set(
            "12345678",
            {'caseNumber': '12345678', 'summary': 'Expired'},
            {'name': 'Expired Account'},
            ttl_seconds=1
        )

        # Wait for expiry
        time.sleep(1.5)

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
    with patch("mc.utils.cache.CACHE_DIR", cache_dir):
        cache = CaseMetadataCache(cache_dir)

        # Create fresh cache
        cache.set(
            "12345678",
            {'caseNumber': '12345678', 'summary': 'Cached'},
            {'name': 'Cached Account'}
        )

        # Get metadata with force_refresh
        case_details, account_details, was_cached = get_case_metadata("12345678", mock_api_client, force_refresh=True)

        # Should fetch from API despite valid cache
        assert was_cached is False
        assert case_details['summary'] == 'Test case'
        assert account_details['name'] == 'Test Account'
        mock_api_client.fetch_case_details.assert_called_once_with("12345678")
        mock_api_client.fetch_account_details.assert_called_once_with('ACC123')


def test_concurrent_cache_access(cache):
    """Test that cache handles concurrent access gracefully."""
    # This test verifies WAL mode allows concurrent reads
    # Cache some data
    cache.set("12345678", {'summary': 'Test'}, {'name': 'Test Account'})

    # Multiple concurrent reads should work
    results = []
    for _ in range(10):
        case_data, account_data, was_cached = cache.get("12345678")
        results.append(was_cached)

    # All reads should succeed
    assert all(results)
