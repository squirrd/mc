"""Authentication utilities."""

import requests


def get_access_token(offline_token: str) -> str:
    """
    Get Red Hat API access token using offline token.

    Args:
        offline_token: Red Hat API offline token

    Returns:
        str: Access token

    Raises:
        requests.HTTPError: If token refresh fails
    """
    url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': 'rhsm-api',
        'refresh_token': offline_token
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()['access_token']
