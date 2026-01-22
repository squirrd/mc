"""Parallel download manager with rich progress tracking."""

import os
import logging
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


def download_attachments_parallel(
    attachments,
    attach_dir,
    api_client,
    max_workers=8,
    show_progress=True
):
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

    return {'success': success, 'failed': failed}


def _download_single_file(task_id, url, local_path, api_client, progress):
    """Download single file with progress updates.

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
    try:
        # Get file size from HEAD request
        head_response = api_client.session.head(
            url, verify=api_client.verify_ssl, timeout=api_client.timeout
        )
        head_response.raise_for_status()
        total = int(head_response.headers.get('content-length', 0))

        # Update progress with total size and start
        progress.update(task_id, total=total)
        progress.start_task(task_id)

        # Download with streaming
        response = api_client.session.get(
            url, verify=api_client.verify_ssl, stream=True, timeout=api_client.timeout
        )
        response.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # Filter out keep-alive chunks
                    f.write(chunk)
                    progress.update(task_id, advance=len(chunk))

        logger.debug("Successfully downloaded %s", local_path)

    except Exception as exc:
        logger.error("Download failed for %s: %s", local_path, exc)
        raise  # Re-raise to be caught in as_completed loop
