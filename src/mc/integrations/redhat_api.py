"""Red Hat API client for case management."""

import os
import shutil
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


def check_download_safety(file_size, download_path, threshold_gb=3):
    """
    Check if download is safe (enough disk space, reasonable size).

    Args:
        file_size: Size of file in bytes
        download_path: Path where file will be saved
        threshold_gb: Warning threshold in GB (default 3)

    Returns:
        tuple: (is_safe: bool, warning_msg: str or None)
    """
    threshold_bytes = threshold_gb * 1024 * 1024 * 1024

    # Check file size threshold
    if file_size > threshold_bytes:
        # Get disk usage
        stat = shutil.disk_usage(os.path.dirname(download_path))
        free_gb = stat.free / (1024 ** 3)
        file_gb = file_size / (1024 ** 3)

        # Estimate download time (assume 10 MB/s average connection)
        estimated_seconds = file_size / (10 * 1024 * 1024)
        estimated_minutes = estimated_seconds / 60

        warning = (
            f"\n⚠️  Large file download warning:\n"
            f"  File: {os.path.basename(download_path)}\n"
            f"  Size: {file_gb:.2f} GB\n"
            f"  Free disk space: {free_gb:.2f} GB\n"
            f"  Estimated download time: {estimated_minutes:.1f} minutes\n"
        )

        # Check if enough space (need file size + 10% buffer)
        if stat.free < (file_size * 1.1):
            return False, warning + "  ❌ Insufficient disk space!\n"

        return True, warning

    return True, None


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
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
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
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
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
            response = requests.get(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise

    def download_file(self, url, local_filename, force=False):
        """
        Download a file from the API.

        Args:
            url: URL to download from
            local_filename: Path to save file to
            force: If True, skip large file warnings and proceed with download

        Raises:
            requests.HTTPError: If download fails
            requests.exceptions.SSLError: If SSL verification fails
            RuntimeError: If insufficient disk space for download
        """
        # Get file size from HEAD request
        try:
            head_response = requests.head(url, headers=self.headers, verify=self.verify_ssl, timeout=30)
            head_response.raise_for_status()
        except requests.exceptions.SSLError as e:
            print(f"SSL certificate verification failed for {url}")
            print(f"Reason: {str(e)}")
            print(f"To bypass verification (not recommended): Set REQUESTS_CA_BUNDLE environment variable")
            raise

        file_size = int(head_response.headers.get('content-length', 0))

        # Check download safety
        is_safe, warning = check_download_safety(file_size, local_filename)

        if warning and not force:
            print(warning)
            if not is_safe:
                raise RuntimeError("Download blocked due to insufficient disk space")
            # For large files with sufficient space, just warn and continue

        # Proceed with download
        try:
            with requests.get(url, headers=self.headers, verify=self.verify_ssl, stream=True, timeout=30) as response:
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
