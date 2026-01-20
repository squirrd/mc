"""Authentication utilities."""

import os
import requests


def get_access_token():
    """
    Get Red Hat API access token using offline token from environment.

    Returns:
        str: Access token

    Raises:
        SystemExit: If RH_API_OFFLINE_TOKEN environment variable is not set
        requests.HTTPError: If token refresh fails
    """
    offline_token = os.environ.get('RH_API_OFFLINE_TOKEN', None)
    if offline_token is None:
        print("The env variable 'RH_API_OFFLINE_TOKEN' must be set")
        exit(1)

    url = "https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"
    payload = {
        'grant_type': 'refresh_token',
        'client_id': 'rhsm-api',
        'refresh_token': offline_token
    }
    response = requests.post(url, data=payload)
    response.raise_for_status()
    return response.json()['access_token']
