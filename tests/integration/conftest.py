"""Integration test specific fixtures."""

import pytest


@pytest.fixture
def workspace_base_dir(tmp_path):
    """
    Returns temporary directory for workspace testing.

    Args:
        tmp_path: pytest's built-in tmp_path fixture

    Returns:
        Path: Temporary directory path
    """
    return tmp_path


@pytest.fixture
def sample_workspace_params(workspace_base_dir):
    """
    Returns dict with workspace parameters for testing.

    Args:
        workspace_base_dir: Fixture providing temporary directory

    Returns:
        dict: Parameters for WorkspaceManager initialization
    """
    return {
        "base_dir": str(workspace_base_dir),
        "case_number": "12345678",
        "account_name": "Test Account",
        "case_summary": "Test Summary"
    }
