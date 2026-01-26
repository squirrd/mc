"""Unit tests for SQLite cache and background refresh manager."""

import time
import threading
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock
from mc.utils.cache import CaseMetadataCache, CACHE_TTL_SECONDS
from mc.controller.cache_manager import CacheManager, REFRESH_INTERVAL_SECONDS
from mc.exceptions import SalesforceAPIError


# Test fixtures

@pytest.fixture
def tmp_cache(tmp_path):
    """Create temporary cache for testing."""
    return CaseMetadataCache(cache_dir=tmp_path)


@pytest.fixture
def mock_sf_client():
    """Mock SalesforceAPIClient for testing."""
    client = Mock()
    client.query_case.return_value = {
        "case_number": "12345678",
        "account_name": "Acme Corp",
        "cluster_id": "cluster-abc123",
        "subject": "Cluster down",
        "severity": "High",
        "status": "Open",
        "owner_name": "John Doe",
        "created_date": "2026-01-26T00:00:00Z"
    }
    return client


@pytest.fixture
def cache_manager(tmp_cache, mock_sf_client):
    """Create CacheManager instance for testing."""
    return CacheManager(tmp_cache, mock_sf_client)


# CaseMetadataCache tests

def test_cache_set_and_get(tmp_cache):
    """Test setting and retrieving cache entries."""
    case_number = "12345678"
    case_data = {
        "case_number": case_number,
        "account_name": "Acme Corp",
        "subject": "Test case"
    }
    account_data = {
        "name": "Acme Corp"
    }

    # Set cache entry
    tmp_cache.set(case_number, case_data, account_data)

    # Get cache entry
    retrieved_case, retrieved_account, was_cached = tmp_cache.get(case_number)

    # Verify data matches
    assert was_cached is True
    assert retrieved_case == case_data
    assert retrieved_account == account_data


def test_cache_expiry(tmp_cache):
    """Test cache expiration with short TTL."""
    case_number = "12345678"
    case_data = {"case_number": case_number}
    account_data = {"name": "Acme Corp"}

    # Set cache with 1-second TTL
    tmp_cache.set(case_number, case_data, account_data, ttl_seconds=1)

    # Should be cached immediately
    _, _, was_cached = tmp_cache.get(case_number)
    assert was_cached is True

    # Wait for expiry
    time.sleep(1.1)

    # Should be expired now
    _, _, was_cached = tmp_cache.get(case_number)
    assert was_cached is False


def test_cache_concurrent_access(tmp_cache):
    """Test concurrent read/write access without database locked errors."""
    case_number = "12345678"
    case_data = {"case_number": case_number}
    account_data = {"name": "Acme Corp"}

    # Pre-populate cache
    tmp_cache.set(case_number, case_data, account_data)

    # Track errors from threads
    errors = []

    def reader():
        """Read from cache repeatedly."""
        try:
            for _ in range(10):
                tmp_cache.get(case_number)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)

    def writer():
        """Write to cache repeatedly."""
        try:
            for i in range(10):
                updated_data = case_data.copy()
                updated_data["iteration"] = i
                tmp_cache.set(case_number, updated_data, account_data)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)

    # Start multiple readers and one writer
    threads = [
        threading.Thread(target=reader),
        threading.Thread(target=reader),
        threading.Thread(target=reader),
        threading.Thread(target=writer)
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Verify no database locked errors
    assert len(errors) == 0, f"Concurrent access errors: {errors}"


def test_cache_list_all(tmp_cache):
    """Test listing all cached case numbers."""
    case_numbers = ["12345678", "87654321", "11111111"]

    # Cache multiple cases
    for case_number in case_numbers:
        tmp_cache.set(
            case_number,
            {"case_number": case_number},
            {"name": "Test"}
        )

    # List all cached cases
    cached = tmp_cache.list_all()

    # Verify all cases present
    assert sorted(cached) == sorted(case_numbers)


def test_cache_delete(tmp_cache):
    """Test deleting cache entry."""
    case_number = "12345678"

    # Cache a case
    tmp_cache.set(
        case_number,
        {"case_number": case_number},
        {"name": "Test"}
    )

    # Verify cached
    _, _, was_cached = tmp_cache.get(case_number)
    assert was_cached is True

    # Delete cache entry
    tmp_cache.delete(case_number)

    # Verify no longer cached
    _, _, was_cached = tmp_cache.get(case_number)
    assert was_cached is False


def test_cache_wal_mode_enabled(tmp_cache):
    """Test that WAL mode is enabled for concurrent access."""
    import sqlite3

    # Check journal mode directly
    conn = sqlite3.connect(str(tmp_cache.db_path))
    cursor = conn.execute("PRAGMA journal_mode")
    mode = cursor.fetchone()[0]
    conn.close()

    assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"


# CacheManager tests

def test_get_or_fetch_cache_hit(cache_manager, mock_sf_client):
    """Test get_or_fetch with cache hit (no API call)."""
    case_number = "12345678"

    # Pre-populate cache
    cache_manager.cache.set(
        case_number,
        {"case_number": case_number, "account_name": "Acme Corp"},
        {"name": "Acme Corp"}
    )

    # Get from cache (should not call API)
    case_data, account_data, was_cached = cache_manager.get_or_fetch(case_number)

    # Verify cache hit
    assert was_cached is True
    assert case_data["case_number"] == case_number
    assert account_data["name"] == "Acme Corp"

    # Verify no API call
    mock_sf_client.query_case.assert_not_called()


def test_get_or_fetch_cache_miss(cache_manager, mock_sf_client):
    """Test get_or_fetch with cache miss (API call)."""
    case_number = "12345678"

    # Get from empty cache (should call API)
    case_data, account_data, was_cached = cache_manager.get_or_fetch(case_number)

    # Verify cache miss
    assert was_cached is False
    assert case_data["case_number"] == case_number
    assert account_data["name"] == "Acme Corp"

    # Verify API was called
    mock_sf_client.query_case.assert_called_once_with(case_number)

    # Verify cache was updated
    cached_case, cached_account, now_cached = cache_manager.cache.get(case_number)
    assert now_cached is True
    assert cached_case["case_number"] == case_number


def test_background_refresh_updates_cache(cache_manager, mock_sf_client):
    """Test background refresh worker updates cache."""
    case_number = "12345678"

    # Pre-populate cache with old data
    cache_manager.cache.set(
        case_number,
        {"case_number": case_number, "old": "data"},
        {"name": "Old Account"},
        ttl_seconds=1  # Short TTL to force refresh
    )

    # Configure mock to return updated data
    mock_sf_client.query_case.return_value = {
        "case_number": case_number,
        "account_name": "Updated Corp",
        "subject": "Updated subject",
        "severity": "High",
        "status": "Open"
    }

    # Start background refresh with short interval for testing
    original_interval = REFRESH_INTERVAL_SECONDS
    import mc.controller.cache_manager as cm_module
    cm_module.REFRESH_INTERVAL_SECONDS = 1  # 1 second for testing

    try:
        cache_manager.start_background_refresh([case_number])

        # Wait for refresh (interval + processing time)
        time.sleep(2.0)

        # Stop worker
        cache_manager.stop_background_refresh()

        # Verify cache was updated
        cached_case, cached_account, was_cached = cache_manager.cache.get(case_number)
        assert was_cached is True
        assert cached_case["account_name"] == "Updated Corp"
        assert cached_account["name"] == "Updated Corp"

        # Verify API was called
        assert mock_sf_client.query_case.called

    finally:
        # Restore original interval
        cm_module.REFRESH_INTERVAL_SECONDS = original_interval


def test_start_stop_worker(cache_manager):
    """Test background worker lifecycle (start/stop)."""
    case_number = "12345678"

    # Start worker
    cache_manager.start_background_refresh([case_number])

    # Verify worker thread is running
    assert cache_manager._worker_thread is not None
    assert cache_manager._worker_thread.is_alive()

    # Save reference to thread before stopping
    worker_thread = cache_manager._worker_thread

    # Stop worker
    cache_manager.stop_background_refresh()

    # Wait a bit for thread to exit
    time.sleep(0.5)

    # Verify worker stopped (thread should not be alive)
    assert not worker_thread.is_alive()

    # Verify internal state cleared
    assert cache_manager._worker_thread is None


def test_refresh_failure_doesnt_stop_worker(cache_manager, mock_sf_client):
    """Test worker continues after one case refresh fails."""
    case_numbers = ["12345678", "87654321"]

    # Configure mock to fail for first case, succeed for second
    def query_side_effect(case_number):
        if case_number == "12345678":
            raise SalesforceAPIError("API error")
        return {
            "case_number": case_number,
            "account_name": "Acme Corp",
            "subject": "Test",
            "severity": "High",
            "status": "Open"
        }

    mock_sf_client.query_case.side_effect = query_side_effect

    # Start background refresh with short interval
    original_interval = REFRESH_INTERVAL_SECONDS
    import mc.controller.cache_manager as cm_module
    cm_module.REFRESH_INTERVAL_SECONDS = 1

    try:
        cache_manager.start_background_refresh(case_numbers)

        # Wait for refresh cycle
        time.sleep(2.0)

        # Stop worker
        cache_manager.stop_background_refresh()

        # Verify second case was refreshed despite first failing
        cached_case, cached_account, was_cached = cache_manager.cache.get("87654321")
        assert was_cached is True
        assert cached_case["case_number"] == "87654321"

        # Verify first case has no cache (failed to refresh)
        _, _, was_cached_failed = cache_manager.cache.get("12345678")
        assert was_cached_failed is False

    finally:
        cm_module.REFRESH_INTERVAL_SECONDS = original_interval


def test_cache_manager_thread_safety(cache_manager, mock_sf_client):
    """Test CacheManager handles concurrent operations safely."""
    case_numbers = ["12345678", "87654321", "11111111"]

    # Pre-populate cache
    for case_number in case_numbers:
        cache_manager.cache.set(
            case_number,
            {"case_number": case_number},
            {"name": "Test"}
        )

    errors = []

    def concurrent_get_or_fetch():
        """Fetch cases concurrently."""
        try:
            for case_number in case_numbers:
                cache_manager.get_or_fetch(case_number)
                time.sleep(0.01)
        except Exception as e:
            errors.append(e)

    # Start multiple threads
    threads = [threading.Thread(target=concurrent_get_or_fetch) for _ in range(5)]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    # Verify no errors
    assert len(errors) == 0, f"Concurrent errors: {errors}"
