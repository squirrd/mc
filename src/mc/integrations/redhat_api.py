"""Red Hat API client for case management."""

import os
import shutil
import logging
from typing import Any, TypedDict, NotRequired
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from mc.exceptions import HTTPAPIError, APITimeoutError, APIConnectionError, APIError

logger = logging.getLogger(__name__)


class CaseDetails(TypedDict):
    """Red Hat Support Case structure."""
    summary: str
    accountNumberRef: str
    status: str
    severity: NotRequired[str]
    product: NotRequired[str]


class AttachmentMetadata(TypedDict):
    """Case attachment metadata."""
    fileName: str
    link: str
    fileSize: NotRequired[int]


def get_ca_bundle() -> str | bool:
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


def check_download_safety(file_size: int, download_path: str, threshold_gb: int = 3) -> tuple[bool, str | None]:
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

    def __init__(
        self,
        access_token: str,
        verify_ssl: str | bool | None = None,
        max_retries: int = 3,
        timeout: tuple[float, float] = (3.05, 27)
    ) -> None:
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

    def fetch_case_details(self, case_number: str) -> CaseDetails:
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

    def fetch_account_details(self, account_number: str) -> dict[str, Any]:
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

    def list_attachments(self, case_number: str) -> list[AttachmentMetadata]:
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=(
            retry_if_exception_type(requests.exceptions.Timeout) |
            retry_if_exception_type(requests.exceptions.ConnectionError) |
            retry_if_exception_type(requests.exceptions.HTTPError)
        ),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def download_file(self, url: str, local_filename: str, force: bool = False) -> None:
        """
        Download file with progress bar, automatic retry, and resume support.

        Shows progress bar with transfer speed and ETA. Automatically retries
        on network errors (timeout, connection) and transient API failures
        (503, 429) with exponential backoff. Resumes interrupted downloads
        from last byte position using HTTP Range requests.

        Args:
            url: URL to download from
            local_filename: Path to save file to
            force: If True, skip large file warnings and proceed with download

        Raises:
            HTTPAPIError: On authentication failure (401, 403)
            APITimeoutError: If download times out
            APIConnectionError: If connection fails
            APIError: For other download failures
            RuntimeError: If insufficient disk space or download failure after retries
        """
        logger.debug("Downloading file from %s to %s", url, local_filename)

        # Check if partial file exists for resume
        downloaded = 0
        mode = 'wb'
        headers = {}

        if os.path.exists(local_filename):
            downloaded = os.path.getsize(local_filename)
            if downloaded > 0:
                headers['Range'] = f'bytes={downloaded}-'
                mode = 'ab'
                logger.debug("Resuming download from byte %d", downloaded)

        # Get file size from HEAD request (unless resuming)
        file_size = 0
        if not downloaded:
            try:
                head_response = self.session.head(url, verify=self.verify_ssl, timeout=self.timeout)
                head_response.raise_for_status()
                file_size = int(head_response.headers.get('content-length', 0))
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

            # Check download safety
            is_safe, warning = check_download_safety(file_size, local_filename)

            if warning and not force:
                logger.warning(warning)
                if not is_safe:
                    raise RuntimeError("Download blocked due to insufficient disk space")

        # Proceed with download
        try:
            # Merge Range header if resuming
            request_headers = self.session.headers.copy()
            if headers:
                request_headers.update(headers)

            response = self.session.get(url, headers=request_headers, verify=self.verify_ssl, stream=True, timeout=self.timeout)

            # Don't retry 401/403 - these are auth failures (fail fast)
            if response.status_code in (401, 403):
                response.raise_for_status()

            # Handle 429 rate limiting - let retry decorator handle it
            if response.status_code == 429:
                logger.warning("Rate limit hit (429), will retry")
                response.raise_for_status()

            # Handle 503 service unavailable - let retry decorator handle it
            if response.status_code == 503:
                logger.warning("Service unavailable (503), will retry")
                response.raise_for_status()

            # Accept both 200 (full content) and 206 (partial content/resume)
            if response.status_code not in (200, 206):
                response.raise_for_status()

            # Get total file size
            if response.status_code == 206:
                # Parse Content-Range header: "bytes 1000-2000/3000" -> total is 3000
                content_range = response.headers.get('Content-Range', '')
                if content_range:
                    total_size = int(content_range.split('/')[-1])
                else:
                    total_size = downloaded + int(response.headers.get('Content-Length', 0))
            else:
                total_size = int(response.headers.get('Content-Length', 0))

            # Download with progress bar
            with open(local_filename, mode) as f, tqdm(
                desc=os.path.basename(local_filename),
                initial=downloaded,
                total=total_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                mininterval=0.1,
            ) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    size = f.write(chunk)
                    pbar.update(size)

            logger.debug("Successfully downloaded file to %s", local_filename)
            logger.info("File downloaded successfully: %s", local_filename)

        except requests.exceptions.HTTPError as e:
            # Check if it's an auth error (already raised above for fail-fast)
            if e.response.status_code in (401, 403):
                raise HTTPAPIError.from_response(e.response)
            # For other HTTP errors (429, 503), let retry decorator handle
            raise
        except requests.exceptions.Timeout:
            logger.warning("Download timed out, will retry if attempts remain")
            raise
        except requests.exceptions.ConnectionError as e:
            logger.warning("Connection error during download, will retry if attempts remain")
            raise
        except requests.exceptions.RequestException as e:
            raise APIError(f"Download failed: {str(e)}")

    def close(self) -> None:
        """Close session and cleanup resources."""
        self.session.close()

    def __enter__(self) -> 'RedHatAPIClient':
        """Context manager entry."""
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> None:
        """Context manager exit."""
        self.close()
