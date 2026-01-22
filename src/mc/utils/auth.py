"""Authentication utilities."""

import json
import os
import time
import requests


# Token cache configuration
TOKEN_CACHE_PATH = os.path.expanduser("~/.mc/token")
EXPIRY_BUFFER_SECONDS = 300  # 5-minute buffer
DEFAULT_TTL_SECONDS = 3600  # 1 hour default


def get_ca_bundle():
    """
    Get CA bundle path from environment variables.

    Checks REQUESTS_CA_BUNDLE and CURL_CA_BUNDLE environment variables.
    Falls back to True (use certifi default bundle).

    Returns:
        str or bool: Path to CA bundle or True for default
    """
    ca_bundle = os.environ.get('REQUESTS_CA_BUNDLE')
    if not ca_bundle:
        ca_bundle = os.environ.get('CURL_CA_BUNDLE')
    return ca_bundle if ca_bundle else True


def is_token_expired(expires_at, buffer_seconds=300):
    """
    Check if token is expired or will expire within buffer period.

    Args:
        expires_at: Unix timestamp when token expires
        buffer_seconds: Safety buffer in seconds (default 300)

    Returns:
        bool: True if token is expired or expiring soon
    """
    current_time = time.time()
    return current_time >= (expires_at - buffer_seconds)


def load_token_cache():
    """
    Load token from cache file if it exists.

    Returns:
        dict or None: Cache dict with access_token, expires_at, token_type if valid,
                     None if cache doesn't exist or is corrupted
    """
    if not os.path.exists(TOKEN_CACHE_PATH):
        return None

    try:
        with open(TOKEN_CACHE_PATH, 'r') as f:
            cache = json.load(f)
        return cache
    except (json.JSONDecodeError, IOError):
        # Corrupted cache, ignore it
        return None


def save_token_cache(access_token, expires_in=None):
    """
    Save token to cache file with secure permissions.

    Args:
        access_token: The access token to cache
        expires_in: Token lifetime in seconds (default: DEFAULT_TTL_SECONDS)
    """
    # Calculate expiration timestamp
    expires_at = time.time() + (expires_in or DEFAULT_TTL_SECONDS)

    # Create cache structure
    cache = {
        'access_token': access_token,
        'expires_at': expires_at,
        'token_type': 'Bearer'
    }

    # Ensure cache directory exists with secure permissions
    cache_dir = os.path.dirname(TOKEN_CACHE_PATH)
    os.makedirs(cache_dir, mode=0o700, exist_ok=True)

    # Write file atomically with secure permissions
    fd = os.open(TOKEN_CACHE_PATH, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(cache, f, indent=2)

    # Verify permissions were set correctly
    stat_info = os.stat(TOKEN_CACHE_PATH)
    actual_perms = oct(stat_info.st_mode)[-3:]
    if actual_perms != '600':
        raise RuntimeError(f"Failed to set secure permissions on {TOKEN_CACHE_PATH}")


def get_access_token(offline_token: str) -> str:
    """
    Get Red Hat API access token, using cache if valid.

    Args:
        offline_token: Red Hat API offline token

    Returns:
        str: Access token

    Raises:
        requests.HTTPError: If token refresh fails
        requests.exceptions.SSLError: If SSL verification fails
    """
    # Try to load cached token
    cache = load_token_cache()
    if cache and not is_token_expired(cache['expires_at'], EXPIRY_BUFFER_SECONDS):
        return cache['access_token']

    # Cache doesn't exist or is expired - fetch new token
    url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': 'rhsm-api',
        'refresh_token': offline_token
    }

    ca_bundle = get_ca_bundle()
    try:
        response = requests.post(url, data=payload, verify=ca_bundle)
        response.raise_for_status()
    except requests.exceptions.SSLError as e:
        print(f"SSL certificate verification failed for {url}")
        print(f"Reason: {str(e)}")
        print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
        raise

    # Extract token data
    token_data = response.json()
    access_token = token_data['access_token']
    expires_in = token_data.get('expires_in')

    # Save to cache
    save_token_cache(access_token, expires_in)

    return access_token
