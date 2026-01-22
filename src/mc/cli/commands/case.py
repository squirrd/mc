"""Case-related commands."""

import os
import logging
from mc.utils.auth import get_access_token
from mc.utils.validation import validate_case_number
from mc.integrations.redhat_api import RedHatAPIClient
from mc.controller.workspace import WorkspaceManager
from mc.exceptions import HTTPAPIError, APIError, ValidationError

logger = logging.getLogger(__name__)


def attach(case_number, base_dir, offline_token):
    """
    Download attachments for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        offline_token: Red Hat API offline token
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

        # Fetch case and account details
        case_details = api_client.fetch_case_details(case_number)
        account_details = api_client.fetch_account_details(case_details['accountNumberRef'])

        # Create workspace manager
        workspace = WorkspaceManager(
            base_dir,
            case_number,
            account_details['name'],
            case_details['summary']
        )

        # List and download attachments
        attachments = api_client.list_attachments(case_number)
        attach_dir = workspace.get_attachment_dir()

        # Track download results
        total_files = len(attachments)
        downloaded = 0
        skipped = 0
        failed_files = []

        for file_meta in attachments:
            logger.info("----------------------------")
            filename = f"{attach_dir}/{file_meta['fileName']}"
            url = file_meta['link']
            logger.debug("Filename: %s", filename)
            logger.debug("URL: %s", url)

            if os.path.exists(filename):
                logger.info("File already exists, skipping: %s", file_meta['fileName'])
                skipped += 1
            else:
                logger.info("Downloading file: %s", file_meta['fileName'])
                try:
                    api_client.download_file(url, filename)
                    downloaded += 1
                except (RuntimeError, HTTPAPIError, APIError) as e:
                    logger.error("Download failed for %s: %s", file_meta['fileName'], e)
                    failed_files.append(file_meta['fileName'])
                    # Continue to next attachment instead of crashing
                    continue

        # Print summary
        logger.info("----------------------------")
        logger.info("Download summary: %d downloaded, %d skipped, %d failed", downloaded, skipped, len(failed_files))

        if failed_files:
            logger.error("Failed files: %s", ', '.join(failed_files))
            raise APIError(f"Failed to download {len(failed_files)} file(s)")

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in attach command: %s", e)
        raise


def check(case_number, base_dir, offline_token, fix=False):
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

        # Fetch case and account details
        case_details = api_client.fetch_case_details(case_number)
        account_details = api_client.fetch_account_details(case_details['accountNumberRef'])

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


def create(case_number, base_dir, offline_token, download=False, no_check=False):
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

        # Fetch case and account details
        case_details = api_client.fetch_case_details(case_number)
        account_details = api_client.fetch_account_details(case_details['accountNumberRef'])

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


def case_comments(case_number, offline_token):
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

        # Fetch case details
        case_details = api_client.fetch_case_details(case_number)

        logger.debug("Fetching case comments for case %s", case_number)
        logger.info("Case comments:\n%s", json.dumps(case_details['comments'], indent=2))

    except HTTPAPIError as e:
        logger.error("Failed to fetch case %s: %s", case_number, e)
        raise
    except APIError as e:
        logger.error("API error in case_comments command: %s", e)
        raise
