"""Red Hat API client for case management."""

import os
import shutil
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from mc.exceptions import HTTPAPIError, APITimeoutError, APIConnectionError, APIError

logger = logging.getLogger(__name__)


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

    def __init__(self, access_token, verify_ssl=None, max_retries=3, timeout=(3.05, 27)):
        """
        Initialize API client.

        Args:
            access_token: Red Hat API access token
            verify_ssl: SSL verification setting (True/False/path to CA bundle).
                       If None, uses get_ca_bundle() to check environment variables.
            max_retries: Maximum number of retry attempts (default: 3)
            timeout: Request timeout as (connect, read) tuple in seconds (default: (3.05, 27))
        """
        self.access_token = access_token
        self.verify_ssl = verify_ssl if verify_ssl is not None else get_ca_bundle()
        self.timeout = timeout
        self.session = self._create_session(max_retries)

    def _create_session(self, max_retries: int) -> requests.Session:
        """Create session with retry configuration.

        Args:
            max_retries: Maximum number of retry attempts

        Returns:
            requests.Session: Configured session with retry strategy
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=max_retries,
            connect=max_retries,
            read=max_retries,
            status=max_retries,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS"],
            backoff_factor=0.3,
            respect_retry_after_header=True
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            'Authorization': f'Bearer {self.access_token}',
            'User-Agent': 'mc-cli/0.1.0'
        })

        return session

    def fetch_case_details(self, case_number):
        """
        Fetch details for a specific case.

        Args:
            case_number: Case number to fetch

        Returns:
            dict: Case details

        Raises:
            HTTPAPIError: If API request returns HTTP error
            APITimeoutError: If request times out
            APIConnectionError: If connection fails
            APIError: For other request failures
        """
        url = f"{self.BASE_URL}/cases/{case_number}"
        logger.debug("Fetching case details for %s from %s", case_number, url)

        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("Successfully fetched case %s", case_number)
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out while fetching case {case_number}",
                "Check: Network connectivity and try again"
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to API for case {case_number}",
                "Check: VPN connection and network access"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"API request failed for case {case_number}: {str(e)}")

    def fetch_account_details(self, account_number):
        """
        Fetch details for a specific account.

        Args:
            account_number: Account number to fetch

        Returns:
            dict: Account details

        Raises:
            HTTPAPIError: If API request returns HTTP error
            APITimeoutError: If request times out
            APIConnectionError: If connection fails
            APIError: For other request failures
        """
        url = f"{self.BASE_URL}/accounts/{account_number}"
        logger.debug("Fetching account details for %s from %s", account_number, url)

        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("Successfully fetched account %s", account_number)
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out while fetching account {account_number}",
                "Check: Network connectivity and try again"
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to API for account {account_number}",
                "Check: VPN connection and network access"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"API request failed for account {account_number}: {str(e)}")

    def list_attachments(self, case_number):
        """
        List attachments for a case.

        Args:
            case_number: Case number

        Returns:
            list: Attachment metadata

        Raises:
            HTTPAPIError: If API request returns HTTP error
            APITimeoutError: If request times out
            APIConnectionError: If connection fails
            APIError: For other request failures
        """
        url = f"{self.BASE_URL}/cases/{case_number}/attachments/"
        logger.debug("Listing attachments for case %s from %s", case_number, url)

        try:
            response = self.session.get(url, verify=self.verify_ssl, timeout=self.timeout)
            response.raise_for_status()
            logger.debug("Successfully listed attachments for case %s", case_number)
            return response.json()
        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out while listing attachments for case {case_number}",
                "Check: Network connectivity and try again"
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to API for case {case_number} attachments",
                "Check: VPN connection and network access"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"API request failed for case {case_number} attachments: {str(e)}")

    def download_file(self, url, local_filename, force=False):
        """
        Download a file from the API.

        Args:
            url: URL to download from
            local_filename: Path to save file to
            force: If True, skip large file warnings and proceed with download

        Raises:
            HTTPAPIError: If download fails with HTTP error
            APITimeoutError: If download times out
            APIConnectionError: If connection fails
            APIError: For other download failures
            RuntimeError: If insufficient disk space for download
        """
        logger.debug("Downloading file from %s to %s", url, local_filename)

        # Get file size from HEAD request
        try:
            head_response = self.session.head(url, verify=self.verify_ssl, timeout=self.timeout)
            head_response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out while checking file size for {url}",
                "Check: Network connectivity and try again"
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to API for file download",
                "Check: VPN connection and network access"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"API request failed for file download: {str(e)}")

        file_size = int(head_response.headers.get('content-length', 0))

        # Check download safety
        is_safe, warning = check_download_safety(file_size, local_filename)

        if warning and not force:
            logger.warning(warning)
            if not is_safe:
                raise RuntimeError("Download blocked due to insufficient disk space")
            # For large files with sufficient space, just warn and continue

        # Proceed with download
        try:
            with self.session.get(url, verify=self.verify_ssl, stream=True, timeout=self.timeout) as response:
                response.raise_for_status()
                with open(local_filename, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=8192):
                        file.write(chunk)
            logger.debug("Successfully downloaded file to %s", local_filename)
            logger.info("File downloaded successfully: %s", local_filename)
        except requests.exceptions.HTTPError as e:
            raise HTTPAPIError.from_response(e.response)
        except requests.exceptions.Timeout:
            raise APITimeoutError(
                f"Request timed out while downloading file from {url}",
                "Check: Network connectivity and try again"
            )
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                f"Failed to connect to API during file download",
                "Check: VPN connection and network access"
            )
        except requests.exceptions.RequestException as e:
            raise APIError(f"Download failed: {str(e)}")

    def close(self):
        """Close session and cleanup resources."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
