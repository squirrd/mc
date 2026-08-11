"""Integration test specific fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def skip_image_pull_for_local_builds(monkeypatch):
    """Skip registry image pull when testing against a locally-built container image.

    Set MC_TEST_LOCAL_IMAGE=1 to prevent ContainerManager._ensure_image() from
    pulling from the registry.  This is required during development iteration on
    Containerfile changes: the local image has the changes, but the registry
    image does not yet.

    Without this, _ensure_image() detects a digest mismatch and overwrites the
    local image with the (stale) registry version, causing the test to fail even
    though the Containerfile change is correct.
    """
    if os.environ.get("MC_TEST_LOCAL_IMAGE"):
        from mc.container.manager import ContainerManager

        monkeypatch.setattr(
            ContainerManager,
            "_ensure_image",
            lambda self, image_name, registry_image: None,
        )


def pytest_configure(config):
    """Register custom markers for integration tests."""
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require external services)"
    )


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
