"""Red Hat API client for case management."""

import os
import requests


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


class RedHatAPIClient:
    """Client for interacting with Red Hat Support APIs."""

    BASE_URL = "https://api.access.redhat.com/support/v1"

    def __init__(self, access_token, verify_ssl=None):
        """
        Initialize API client.

        Args:
            access_token: Red Hat API access token
            verify_ssl: SSL verification setting (True/False/path to CA bundle).
                       If None, uses get_ca_bundle() to check environment variables.
        """
        self.access_token = access_token
        self.headers = {'Authorization': f'Bearer {access_token}'}
        self.verify_ssl = verify_ssl if verify_ssl is not None else get_ca_bundle()

    def fetch_case_details(self, case_number):
        """
        Fetch details for a specific case.

        Args:
            case_number: Case number to fetch

        Returns:
            dict: Case details

        Raises:
            requests.HTTPError: If API request fails
            requests.exceptions.SSLError: If SSL verification fails
        """
        url = f"{self.BASE_URL}/cases/{case_number}"
        try:
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise

    def fetch_account_details(self, account_number):
        """
        Fetch details for a specific account.

        Args:
            account_number: Account number to fetch

        Returns:
            dict: Account details

        Raises:
            requests.HTTPError: If API request fails
            requests.exceptions.SSLError: If SSL verification fails
        """
        url = f"{self.BASE_URL}/accounts/{account_number}"
        try:
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise

    def list_attachments(self, case_number):
        """
        List attachments for a case.

        Args:
            case_number: Case number

        Returns:
            list: Attachment metadata

        Raises:
            requests.HTTPError: If API request fails
            requests.exceptions.SSLError: If SSL verification fails
        """
        url = f"{self.BASE_URL}/cases/{case_number}/attachments/"
        try:
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise

    def download_file(self, url, local_filename):
        """
        Download a file from the API.

        Args:
            url: URL to download from
            local_filename: Path to save file to

        Raises:
            requests.HTTPError: If download fails
            requests.exceptions.SSLError: If SSL verification fails
        """
        try:
            with requests.get(url, headers=self.headers, verify=self.verify_ssl, stream=True) as response:
                response.raise_for_status()
                with open(local_filename, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
            print(f"File downloaded successfully: {local_filename}")
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise
