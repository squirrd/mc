"""Case metadata caching utilities with SQLite backend."""

import json
import sqlite3
import time
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Any, Iterator

logger = logging.getLogger(__name__)


# Cache configuration
CACHE_DIR = Path.home() / ".mc" / "cache"
CACHE_TTL_SECONDS = 300  # 5 minutes (per REQUIREMENTS.md SF-02)


class CaseMetadataCache:
    """SQLite-based cache with concurrent access support.

    Uses Write-Ahead Logging (WAL) mode for concurrent reads during
    background refresh operations. Provides atomic upserts and thread-safe
    connection management.

    Attributes:
        db_path: Path to SQLite database file
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize SQLite cache.

        Args:
            cache_dir: Directory for cache database (default: ~/.mc/cache)
        """
        if cache_dir is None:
            cache_dir = CACHE_DIR

        self.cache_dir = Path(cache_dir)
        self.db_path = self.cache_dir / "case_metadata.db"

        # Ensure cache directory exists with secure permissions
        self.cache_dir.mkdir(parents=True, mode=0o700, exist_ok=True)

        # Initialize database schema
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database with WAL mode for concurrent access."""
        with self._get_connection() as conn:
            # Enable WAL mode for concurrent readers + single writer
            conn.execute("PRAGMA journal_mode=WAL")

            # Create schema
            conn.execute("""
                CREATE TABLE IF NOT EXISTS case_cache (
                    case_number TEXT PRIMARY KEY,
                    case_data TEXT NOT NULL,
                    account_data TEXT NOT NULL,
                    cached_at REAL NOT NULL,
                    ttl_seconds INTEGER NOT NULL
                )
            """)

            logger.debug("Initialized cache database at %s", self.db_path)

    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """Thread-safe connection context manager.

        Yields:
            sqlite3.Connection: Database connection

        Raises:
            sqlite3.OperationalError: If connection fails after retry
        """
        conn = sqlite3.connect(str(self.db_path), timeout=5.0)
        try:
            yield conn
            conn.commit()
        except sqlite3.OperationalError as e:
            # Retry once on lock timeout
            logger.warning("Database operation failed, retrying: %s", e)
            conn.rollback()
            time.sleep(0.1)
            try:
                yield conn
                conn.commit()
            except sqlite3.OperationalError:
                logger.error("Database operation failed after retry")
                conn.rollback()
                raise
        finally:
            conn.close()

    def get(self, case_number: str) -> tuple[dict[str, Any], dict[str, Any], bool]:
        """Get case metadata from cache.

        Args:
            case_number: Case number

        Returns:
            tuple: (case_data, account_data, was_cached)
                - case_data: Case metadata dict (empty if not cached)
                - account_data: Account metadata dict (empty if not cached)
                - was_cached: True if data came from cache and wasn't expired
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT case_data, account_data, cached_at, ttl_seconds "
                "FROM case_cache WHERE case_number = ?",
                (case_number,)
            )
            row = cursor.fetchone()

            if row:
                case_data_json, account_data_json, cached_at, ttl_seconds = row

                # Check expiry
                if not self._is_expired(cached_at, ttl_seconds):
                    logger.debug("Cache hit for case %s", case_number)
                    return (
                        json.loads(case_data_json),
                        json.loads(account_data_json),
                        True
                    )
                else:
                    logger.debug("Cache expired for case %s", case_number)

        # Cache miss or expired
        return {}, {}, False

    def set(
        self,
        case_number: str,
        case_data: dict[str, Any],
        account_data: dict[str, Any],
        ttl_seconds: int = CACHE_TTL_SECONDS
    ) -> None:
        """Cache case metadata with TTL.

        Uses INSERT OR REPLACE for atomic upserts.

        Args:
            case_number: Case number
            case_data: Case metadata dict
            account_data: Account metadata dict
            ttl_seconds: Cache TTL in seconds (default: 300 = 5 minutes)
        """
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO case_cache
                (case_number, case_data, account_data, cached_at, ttl_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    case_number,
                    json.dumps(case_data),
                    json.dumps(account_data),
                    time.time(),
                    ttl_seconds
                )
            )

            logger.debug("Cached metadata for case %s", case_number)

    def _is_expired(self, cached_at: float, ttl_seconds: int) -> bool:
        """Check if cache entry is expired.

        Args:
            cached_at: Unix timestamp when data was cached
            ttl_seconds: Cache TTL in seconds

        Returns:
            bool: True if cache is expired
        """
        current_time = time.time()
        return current_time >= (cached_at + ttl_seconds)

    def list_all(self) -> list[str]:
        """List all cached case numbers.

        Returns:
            list: List of cached case numbers
        """
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT case_number FROM case_cache")
            return [row[0] for row in cursor.fetchall()]

    def delete(self, case_number: str) -> None:
        """Delete cache entry for case.

        Args:
            case_number: Case number
        """
        with self._get_connection() as conn:
            conn.execute(
                "DELETE FROM case_cache WHERE case_number = ?",
                (case_number,)
            )
            logger.debug("Deleted cache for case %s", case_number)


# Backward compatibility: v1.0 function signature
def get_case_metadata(
    case_number: str,
    api_client: Any,
    force_refresh: bool = False
) -> tuple[dict[str, Any], dict[str, Any], bool]:
    """Get case metadata from cache or API (v1.0 compatibility function).

    This function maintains backward compatibility with v1.0 code that
    expects JSON file-based caching. In v2.0, use CaseMetadataCache directly
    for better control over cache lifecycle.

    Args:
        case_number: Case number
        api_client: API client with fetch_case_details() and fetch_account_details()
        force_refresh: If True, bypass cache and fetch from API

    Returns:
        tuple: (case_details, account_details, was_cached)
    """
    cache = CaseMetadataCache()

    # Check cache unless force refresh
    if not force_refresh:
        case_data, account_data, was_cached = cache.get(case_number)
        if was_cached:
            return case_data, account_data, True

    # Cache miss or expired - fetch from API
    logger.debug("Cache miss for case %s, fetching from API", case_number)
    case_details = api_client.fetch_case_details(case_number)
    account_details = api_client.fetch_account_details(
        case_details['accountNumberRef']
    )

    # Update cache
    cache.set(case_number, case_details, account_details)

    return case_details, account_details, False
