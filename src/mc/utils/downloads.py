"""Parallel download manager with rich progress tracking."""

import os
import time
import logging
from typing import Any
import backoff
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
)

logger = logging.getLogger(__name__)


def _should_retry(exc: Exception) -> bool:
    """Determine if exception should trigger retry.

    Retry transient failures (5xx, 429, timeouts, connection errors).
    Fail fast on permanent errors (404, 401, 403).
    """
    if not isinstance(exc, requests.exceptions.RequestException):
        return False

    if not hasattr(exc, 'response') or exc.response is None:
        # Network error (timeout, connection reset) - retry
        return True

    status = exc.response.status_code

    # Retry these status codes
    if status in [429, 500, 502, 503, 504]:
        return True

    # Don't retry 4xx client errors (except 429 handled above)
    if 400 <= status < 500:
        return False

    return True


def download_attachments_parallel(
    attachments: list[dict[str, Any]],
    attach_dir: Any,
    api_client: Any,
    max_workers: int = 8,
    show_progress: bool = True
) -> dict[str, list[Any]]:
    """Download attachments in parallel with progress tracking.

    Args:
        attachments: List of dicts with 'fileName', 'link' keys
        attach_dir: Directory to save files
        api_client: RedHatAPIClient instance
        max_workers: Concurrent download threads (default: 8)
        show_progress: If False, suppress progress display (default: True)

    Returns:
        dict: {
            'success': [filenames],
            'failed': [(filename, error_message)]
        }
    """
    if not attachments:
        return {'success': [], 'failed': []}

    success = []
    failed = []

    # If progress disabled, download sequentially with simple output
    if not show_progress:
        for file_meta in attachments:
            filename = file_meta['fileName']
            url = file_meta['link']
            local_path = os.path.join(attach_dir, filename)

            # Skip if exists
            if os.path.exists(local_path):
                logger.info("Skipping %s (already exists)", filename)
                success.append(filename)
                continue

            try:
                logger.debug("Downloading %s from %s", filename, url)
                api_client.download_file(url, local_path)
                success.append(filename)
            except Exception as exc:
                logger.error("Download failed for %s: %s", filename, exc)
                failed.append((filename, str(exc)))

        return {'success': success, 'failed': failed}

    # Parallel download with rich progress
    progress = Progress(
        TextColumn("[bold blue]{task.fields[filename]}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.1f}%",
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {}

                for file_meta in attachments:
                    filename = file_meta['fileName']
                    url = file_meta['link']
                    local_path = os.path.join(attach_dir, filename)

                    # Skip if exists
                    if os.path.exists(local_path):
                        # print OK - user-facing status
                        print(f"Skipping {filename} (already exists)")
                        success.append(filename)
                        continue

                    # Add progress task
                    task_id = progress.add_task("download", filename=filename, start=False)

                    # Submit download
                    future = pool.submit(
                        _download_single_file,
                        task_id,
                        url,
                        local_path,
                        api_client,
                        progress
                    )
                    futures[future] = filename

                # Collect results
                for future in as_completed(futures):
                    filename = futures[future]
                    try:
                        future.result()  # Raises if download failed
                        success.append(filename)
                    except Exception as exc:
                        failed.append((filename, str(exc)))
                        progress.console.print(f"[red]Failed: {filename} - {exc}[/red]")

        except KeyboardInterrupt:
            progress.console.print("\n[yellow]Download interrupted by user[/yellow]")
            # ThreadPoolExecutor context manager will wait for running tasks to finish
            # Individual tasks handle cleanup in their own KeyboardInterrupt handlers
            raise

    return {'success': success, 'failed': failed}


@backoff.on_exception(
    backoff.expo,
    requests.exceptions.RequestException,
    max_tries=5,
    giveup=lambda e: not _should_retry(e),
    jitter=backoff.full_jitter,
    on_backoff=lambda details: logger.debug(
        "Retry %s/%s, waiting %.1fs",
        details['tries'],
        details.get('max_tries', 5),
        details['wait']
    )
)
def _download_single_file(task_id: Any, url: str, local_path: str, api_client: Any, progress: Progress) -> None:
    """Download single file with progress updates and resume support.

    This function runs in ThreadPoolExecutor worker thread.

    Args:
        task_id: Rich progress task ID
        url: URL to download from
        local_path: Path to save file to
        api_client: RedHatAPIClient instance
        progress: Rich Progress instance

    Raises:
        Exception: Any download error
    """
    # Check for partial download
    downloaded_bytes = 0
    if os.path.exists(local_path):
        downloaded_bytes = os.path.getsize(local_path)
        logger.debug("Found partial download: %s bytes", downloaded_bytes)

    try:
        # Get file size from HEAD request
        head_response = api_client.session.head(
            url, verify=api_client.verify_ssl, timeout=api_client.timeout
        )
        head_response.raise_for_status()
        total_size = int(head_response.headers.get('content-length', 0))

        # If partial download exists and is smaller than total, resume
        if downloaded_bytes > 0 and downloaded_bytes < total_size:
            logger.debug("Resuming download from byte %s", downloaded_bytes)
            headers = {'Range': f'bytes={downloaded_bytes}-'}
            mode = 'ab'  # Append mode
            progress.update(task_id, total=total_size, completed=downloaded_bytes)
        elif downloaded_bytes >= total_size:
            # File already complete or corrupted (larger than expected)
            logger.debug("Restarting download (existing file size: %s, expected: %s)",
                        downloaded_bytes, total_size)
            headers = {}
            mode = 'wb'  # Write new file
            downloaded_bytes = 0
            progress.update(task_id, total=total_size)
        else:
            headers = {}
            mode = 'wb'  # Write new file
            downloaded_bytes = 0
            progress.update(task_id, total=total_size)

        progress.start_task(task_id)

        # Download with streaming (with Range header if resuming)
        response = api_client.session.get(
            url,
            headers=headers,
            verify=api_client.verify_ssl,
            stream=True,
            timeout=api_client.timeout
        )

        # Check for rate limiting
        if response.status_code == 429:
            retry_after = response.headers.get('Retry-After')
            if retry_after:
                try:
                    wait_seconds = int(retry_after)
                    logger.debug("Rate limited, server says retry after %ss", wait_seconds)
                    progress.console.print(
                        f"[yellow]Rate limited on {os.path.basename(local_path)}, "
                        f"waiting {wait_seconds}s[/yellow]"
                    )
                    time.sleep(wait_seconds)
                except ValueError:
                    pass  # Retry-After might be HTTP date format - ignore for now
            # Raise to trigger backoff retry
            raise requests.exceptions.RequestException(response=response)

        # Accept both 200 (full download) and 206 (partial content/resume)
        if response.status_code not in [200, 206]:
            response.raise_for_status()

        # Write file
        with open(local_path, mode) as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

        logger.debug("Successfully downloaded %s", local_path)

    except KeyboardInterrupt:
        # Clean up partial file on Ctrl+C
        if os.path.exists(local_path):
            logger.debug("Removing partial file after interrupt: %s", local_path)
            os.remove(local_path)
        raise  # Re-raise to propagate to main thread

    except Exception as exc:
        # For other errors, leave partial file for resume on retry
        logger.error("Download failed for %s: %s", local_path, exc)
        raise  # Re-raise to be caught in as_completed loop
