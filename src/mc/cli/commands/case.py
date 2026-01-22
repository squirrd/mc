"""Case-related commands."""

import os
import logging
from mc.utils.auth import get_access_token
from mc.utils.validation import validate_case_number
from mc.utils.cache import get_case_metadata, get_cached_age_minutes
from mc.utils.downloads import download_attachments_parallel
from mc.integrations.redhat_api import RedHatAPIClient
from mc.controller.workspace import WorkspaceManager
from mc.exceptions import HTTPAPIError, APIError, ValidationError

logger = logging.getLogger(__name__)


def attach(case_number: str, base_dir: str, offline_token: str, serial: bool = False, quiet: bool = False) -> None:
    """
    Download attachments for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        offline_token: Red Hat API offline token
        serial: If True, download one at a time (default: False)
        quiet: If True, suppress progress output (default: False)
    """
    # Validate case number format
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        logger.error("Error: %s", e)
        exit(1)

    logger.info("Downloading attachments for case number: %s", case_number)

    try:
        # Get API client
        access_token = get_access_token(offline_token)
        api_client = RedHatAPIClient(access_token)

        # Fetch case and account details from cache or API
        case_details, account_details, was_cached = get_case_metadata(case_number, api_client)
        if was_cached:
            age_minutes = get_cached_age_minutes(case_number)
            # print OK - user-facing cache indicator
            print(f"Using cached data (cached {age_minutes}m ago)")  # print OK

        # Create workspace manager
        workspace = WorkspaceManager(
            base_dir,
            case_number,
            account_details['name'],
            case_details['summary']
        )

        # List attachments
        attachments = api_client.list_attachments(case_number)
        attach_dir = workspace.get_attachment_dir()

        if not attachments:
            # print OK - user-facing message
            print("No attachments found for this case")
            return

        logger.info("Starting download of %d attachments for case %s", len(attachments), case_number)

        # Download in parallel or serial mode
        if serial:
            # Serial mode: download one at a time with simple output
            logger.info("Serial mode: downloading attachments one at a time")
            downloaded = 0
            skipped = 0
            failed_files = []

            for file_meta in attachments:
                filename = f"{attach_dir}/{file_meta['fileName']}"
                url = file_meta['link']
                logger.debug("Processing attachment: %s (URL: %s)", filename, url)

                if os.path.exists(filename):
                    # print OK - user-facing message
                    print(f"Skipping {file_meta['fileName']} (already exists)")
                    logger.info("File already exists, skipping: %s", file_meta['fileName'])
                    skipped += 1
                else:
                    # print OK - user-facing message
                    print(f"Downloading {file_meta['fileName']}...")
                    try:
                        api_client.download_file(url, filename)
                        downloaded += 1
                    except (RuntimeError, HTTPAPIError, APIError) as e:
                        # print OK - user-facing error
                        print(f"Download failed: {e}")
                        logger.error("Download failed for %s: %s", file_meta['fileName'], e)
                        failed_files.append(file_meta['fileName'])
                        # Continue to next attachment instead of crashing
                        continue

            # Print summary
            logger.info("Download summary: %d downloaded, %d skipped, %d failed", downloaded, skipped, len(failed_files))

            if failed_files:
                logger.error("Failed files: %s", ', '.join(failed_files))
                raise APIError(f"Failed to download {len(failed_files)} file(s)")

        else:
            # Parallel mode: download concurrently with rich progress
            logger.info("Parallel mode: downloading up to 8 attachments concurrently")
            show_progress = not quiet
            # Cast attachments from TypedDict list to dict list for downloads module
            attachment_dicts = [dict(a) for a in attachments]
            result = download_attachments_parallel(
                attachment_dicts,
                attach_dir,
                api_client,
                max_workers=8,
                show_progress=show_progress
            )

            # Print summary
            if result['success']:
                # print OK - user-facing summary
                print(f"\n✓ Successfully downloaded {len(result['success'])} file(s)")
                logger.info("Successfully downloaded %d files", len(result['success']))

            if result['failed']:
                # print OK - user-facing error summary
                print(f"\n✗ Failed to download {len(result['failed'])} file(s):")
                for filename, error in result['failed']:
                    print(f"  - {filename}: {error}")
                logger.error("Failed to download %d files", len(result['failed']))
                raise APIError(f"Failed to download {len(result['failed'])} file(s)")

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in attach command: %s", e)
        raise


def check(case_number: str, base_dir: str, offline_token: str, fix: bool = False) -> None:
    """
    Check workspace status for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        offline_token: Red Hat API offline token
        fix: If True, create missing files
    """
    # Validate case number format
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        logger.error("Error: %s", e)
        exit(1)

    try:
        # Get API client
        access_token = get_access_token(offline_token)
        api_client = RedHatAPIClient(access_token)

        # Fetch case and account details from cache or API
        case_details, account_details, was_cached = get_case_metadata(case_number, api_client)
        if was_cached:
            age_minutes = get_cached_age_minutes(case_number)
            # print OK - user-facing cache indicator
            print(f"Using cached data (cached {age_minutes}m ago)")  # print OK

        # Create workspace manager
        workspace = WorkspaceManager(
            base_dir,
            case_number,
            account_details['name'],
            case_details['summary']
        )

        # Check status
        status = workspace.check()

        if fix:
            if status == "WARN":
                logger.info("Fixing missing files")
                create(case_number, base_dir, offline_token, download=False, no_check=True)
            elif status == "FATAL":
                logger.error("Fatal errors in check. Nothing can be fixed")
            else:
                logger.info("Files OK. Nothing to fix")

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in check command: %s", e)
        raise


def create(case_number: str, base_dir: str, offline_token: str, download: bool = False, no_check: bool = False) -> None:
    """
    Create workspace for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        offline_token: Red Hat API offline token
        download: If True, also download attachments
        no_check: If True, skip initial check
    """
    # Validate case number format
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        logger.error("Error: %s", e)
        exit(1)

    if download:
        logger.info("Creating files and downloading attachments for case: %s", case_number)
    else:
        logger.info("Creating files for case: %s", case_number)

    try:
        # Get API client
        access_token = get_access_token(offline_token)
        api_client = RedHatAPIClient(access_token)

        # Fetch case and account details from cache or API
        case_details, account_details, was_cached = get_case_metadata(case_number, api_client)
        if was_cached:
            age_minutes = get_cached_age_minutes(case_number)
            # print OK - user-facing cache indicator
            print(f"Using cached data (cached {age_minutes}m ago)")  # print OK

        # Create workspace manager
        workspace = WorkspaceManager(
            base_dir,
            case_number,
            account_details['name'],
            case_details['summary']
        )

        # Check first unless told not to
        if not no_check:
            status = workspace.check()
            logger.info("CheckStatus: %s", status)
            if status == "FATAL":
                logger.error("FATAL: Failed file check")
                exit(1)
        else:
            status = "WARN"

        if status == "WARN":
            logger.warning("WARN: Some or all files do not exist. Creating them.")
            workspace.create_files()

        if download:
            attach(case_number, base_dir, offline_token)

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in create command: %s", e)
        raise


def case_comments(case_number: str, offline_token: str) -> None:
    """
    Display case comments.

    Args:
        case_number: Case number
        offline_token: Red Hat API offline token
    """
    import json

    # Validate case number format
    try:
        case_number = validate_case_number(case_number)
    except ValueError as e:
        logger.error("Error: %s", e)
        exit(1)

    try:
        # Get API client
        access_token = get_access_token(offline_token)
        api_client = RedHatAPIClient(access_token)

        # Fetch case details from cache or API (ignore account_details)
        case_details, _, was_cached = get_case_metadata(case_number, api_client)
        if was_cached:
            age_minutes = get_cached_age_minutes(case_number)
            # print OK - user-facing cache indicator
            print(f"Using cached data (cached {age_minutes}m ago)")  # print OK

        logger.debug("Fetching case comments for case %s", case_number)
        logger.info("Case comments:\n%s", json.dumps(case_details['comments'], indent=2))

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in case_comments command: %s", e)
        raise
