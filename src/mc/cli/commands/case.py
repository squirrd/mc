"""Case-related commands."""

import os
from mc.utils.auth import get_access_token
from mc.integrations.redhat_api import RedHatAPIClient
from mc.controller.workspace import WorkspaceManager


def attach(case_number, base_dir):
    """
    Download attachments for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
    """
    print(f"Downloading attachments for case number: {case_number}")

    # Get API client
    access_token = get_access_token()
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

    for file_meta in attachments:
        print("----------------------------")
        filename = f"{attach_dir}/{file_meta['fileName']}"
        url = file_meta['link']
        print(f"Filename: {filename}")
        print(f"url: {url}")
        if os.path.exists(filename):
            print(f"File already exists no need to download")
        else:
            print(f"Downloading file...")
            api_client.download_file(url, filename)


def check(case_number, base_dir, fix=False):
    """
    Check workspace status for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        fix: If True, create missing files
    """
    # Get API client
    access_token = get_access_token()
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
            print("Fixing missing files")
            create(case_number, base_dir, download=False, no_check=True)
        elif status == "FATAL":
            print("Fatal errors in check.  Nothing can be fixed")
        else:
            print("Files OK.  Nothing to fix")


def create(case_number, base_dir, download=False, no_check=False):
    """
    Create workspace for a case.

    Args:
        case_number: Case number
        base_dir: Base directory for cases
        download: If True, also download attachments
        no_check: If True, skip initial check
    """
    print("Creating files", end="")
    if download:
        print(f" and downloading attachments for case: {case_number}")
    else:
        print(f" for case: {case_number}")

    # Get API client
    access_token = get_access_token()
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
        print(f"CheckStatus: {status}")
        if status == "FATAL":
            print(f"FATAL: Failed file check")
            exit(1)
    else:
        status = "WARN"

    if status == "WARN":
        print(f"WARN: Some or all files do not exist.  Creating them.")
        workspace.create_files()

    if download:
        attach(case_number, base_dir)


def case_comments(case_number):
    """
    Display case comments.

    Args:
        case_number: Case number
    """
    from pprint import pprint

    # Get API client
    access_token = get_access_token()
    api_client = RedHatAPIClient(access_token)

    # Fetch case details
    case_details = api_client.fetch_case_details(case_number)

    print("Logging into OCM backplane")
    pprint(case_details['comments'])
