"""Red Hat API client for case management."""

import requests


class RedHatAPIClient:
    """Client for interacting with Red Hat Support APIs."""

    BASE_URL = "https://api.access.redhat.com/support/v1"

    def __init__(self, access_token):
        """
        Initialize API client.

        Args:
            access_token: Red Hat API access token
        """
        self.access_token = access_token
        self.headers = {'Authorization': f'Bearer {access_token}'}

    def fetch_case_details(self, case_number):
        """
        Fetch details for a specific case.

        Args:
            case_number: Case number to fetch

        Returns:
            dict: Case details

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/cases/{case_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def fetch_account_details(self, account_number):
        """
        Fetch details for a specific account.

        Args:
            account_number: Account number to fetch

        Returns:
            dict: Account details

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/accounts/{account_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def list_attachments(self, case_number):
        """
        List attachments for a case.

        Args:
            case_number: Case number

        Returns:
            list: Attachment metadata

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.BASE_URL}/cases/{case_number}/attachments/"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def download_file(self, url, local_filename):
        """
        Download a file from the API.

        Args:
            url: URL to download from
            local_filename: Path to save file to

        Raises:
            requests.HTTPError: If download fails
        """
        with requests.get(url, headers=self.headers, stream=True) as response:
            response.raise_for_status()
            with open(local_filename, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
        print(f"File downloaded successfully: {local_filename}")
