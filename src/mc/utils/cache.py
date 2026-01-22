"""Case metadata caching utilities."""

import json
import os
import time
import logging
from typing import Any

logger = logging.getLogger(__name__)


# Cache configuration
CACHE_DIR = os.path.expanduser("~/.mc/cache")
CACHE_TTL_SECONDS = 1800  # 30 minutes


def get_cache_path(case_number: str) -> str:
    """
    Get cache file path for a case number.

    Args:
        case_number: Case number

    Returns:
        str: Path to cache file
    """
    return os.path.join(CACHE_DIR, f"case_{case_number}.json")


def is_cache_expired(cached_at: float, ttl_seconds: int = CACHE_TTL_SECONDS) -> bool:
    """
    Check if cache is expired.

    Args:
        cached_at: Unix timestamp when data was cached
        ttl_seconds: Cache TTL in seconds (default: CACHE_TTL_SECONDS)

    Returns:
        bool: True if cache is expired
    """
    current_time = time.time()
    return current_time >= (cached_at + ttl_seconds)


def load_cache(case_number: str) -> dict[str, Any] | None:
    """
    Load cached case metadata if it exists.

    Args:
        case_number: Case number

    Returns:
        dict or None: Cache dict with data and cached_at if valid,
                     None if cache doesn't exist or is corrupted
    """
    cache_path = get_cache_path(case_number)
    if not os.path.exists(cache_path):
        return None

    try:
        with open(cache_path, 'r') as f:
            cache = json.load(f)
        return cache
    except (json.JSONDecodeError, IOError) as e:
        # Corrupted cache, delete it
        logger.debug("Corrupted cache file, deleting: %s", e)
        try:
            os.remove(cache_path)
        except OSError:
            pass
        return None


def cache_case_metadata(case_number: str, case_details: dict[str, Any], account_details: dict[str, Any]) -> None:
    """
    Save case metadata to cache with timestamp.

    Args:
        case_number: Case number
        case_details: Case details dict from API
        account_details: Account details dict from API
    """
    # Create cache structure
    cache = {
        'data': {
            'case_details': case_details,
            'account_details': account_details
        },
        'cached_at': time.time()
    }

    # Ensure cache directory exists with secure permissions
    os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)

    # Write file atomically with secure permissions
    cache_path = get_cache_path(case_number)
    fd = os.open(cache_path, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(cache, f, indent=2)

    logger.debug("Cached metadata for case %s", case_number)


def get_cached_age_minutes(case_number: str) -> int | None:
    """
    Get age of cached data in minutes.

    Args:
        case_number: Case number

    Returns:
        int or None: Age in minutes if cache exists, None otherwise
    """
    cache = load_cache(case_number)
    if not cache or 'cached_at' not in cache:
        return None

    age_seconds = time.time() - cache['cached_at']
    return int(age_seconds / 60)


def get_case_metadata(case_number: str, api_client: Any, force_refresh: bool = False) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """
    Get case metadata from cache or API.

    Checks cache first and returns cached data if within TTL window.
    Otherwise fetches fresh data from API and updates cache.

    Args:
        case_number: Case number
        api_client: RedHatAPIClient instance
        force_refresh: If True, bypass cache and fetch from API

    Returns:
        tuple: (case_details, account_details, was_cached)
            - case_details: Case details dict
            - account_details: Account details dict
            - was_cached: True if data came from cache
    """
    # Check cache unless force refresh
    if not force_refresh:
        cache = load_cache(case_number)
        if cache and not is_cache_expired(cache['cached_at']):
            logger.debug("Cache hit for case %s (age: %dm)", case_number, get_cached_age_minutes(case_number))
            data = cache['data']
            return data['case_details'], data['account_details'], True

    # Cache miss or expired - fetch from API
    logger.debug("Cache miss for case %s, fetching from API", case_number)
    case_details = api_client.fetch_case_details(case_number)
    account_details = api_client.fetch_account_details(case_details['accountNumberRef'])

    # Update cache
    cache_case_metadata(case_number, case_details, account_details)

    return case_details, account_details, False
