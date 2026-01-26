"""Unit tests for case number to workspace path resolution."""

import pytest
from pathlib import Path
from unittest.mock import Mock
from mc.controller.case_resolver import CaseResolver
from mc.controller.workspace import WorkspaceManager
from mc.controller.cache_manager import CacheManager
from mc.exceptions import WorkspaceError
from mc.utils.formatters import shorten_and_format


# Test fixtures

@pytest.fixture
def tmp_base_dir(tmp_path):
    """Create temporary base directory for workspaces."""
    base_dir = tmp_path / "workspaces"
    base_dir.mkdir()
    return base_dir


@pytest.fixture
def mock_cache_manager():
    """Mock CacheManager with typical Salesforce response."""
    manager = Mock(spec=CacheManager)
    manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Acme Corporation",
            "case_summary": "OpenShift cluster nodes failing health checks",
            "severity": "High",
            "status": "Open"
        },
        {"name": "Acme Corporation"},
        True  # was_cached
    )
    return manager


@pytest.fixture
def case_resolver(tmp_base_dir, mock_cache_manager):
    """Create CaseResolver instance for testing."""
    return CaseResolver(mock_cache_manager, tmp_base_dir)


# CaseResolver.resolve() tests

def test_resolve_case_to_path(tmp_base_dir, mock_cache_manager):
    """Test resolving case number to workspace path with valid metadata."""
    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    workspace_path = resolver.resolve("12345678")

    # Verify path structure: {base_dir}/{account_formatted}/{case_number}-{summary_formatted}
    assert workspace_path.parent.name == shorten_and_format("Acme Corporation")
    assert workspace_path.name.startswith("12345678-")
    assert "openshi" in workspace_path.name.lower()  # Summary formatted and shortened

    # Verify cache_manager called
    mock_cache_manager.get_or_fetch.assert_called_once_with("12345678")


def test_resolve_uses_cache(tmp_base_dir, mock_cache_manager):
    """Test that resolve uses cached data (no Salesforce call)."""
    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    # Mock returns was_cached=True
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Test Corp",
            "case_summary": "Test issue"
        },
        {"name": "Test Corp"},
        True  # was_cached
    )

    workspace_path = resolver.resolve("12345678")

    # Verify path constructed
    assert workspace_path.parent.name == shorten_and_format("Test Corp")
    assert workspace_path.name.startswith("12345678-")

    # Verify get_or_fetch was called (cache manager handles cache hit internally)
    mock_cache_manager.get_or_fetch.assert_called_once_with("12345678")


def test_resolve_fetches_on_cache_miss(tmp_base_dir, mock_cache_manager):
    """Test that resolve works when cache manager fetches from Salesforce."""
    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    # Mock returns was_cached=False (cache miss, API called)
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "87654321",
            "account_name": "New Customer",
            "case_summary": "Database connectivity issue"
        },
        {"name": "New Customer"},
        False  # was_cached (cache miss)
    )

    workspace_path = resolver.resolve("87654321")

    # Verify path constructed correctly
    assert workspace_path.parent.name == shorten_and_format("New Customer")
    assert workspace_path.name.startswith("87654321-")
    assert "databas" in workspace_path.name.lower()

    # Verify get_or_fetch was called
    mock_cache_manager.get_or_fetch.assert_called_once_with("87654321")


def test_missing_case_summary_fails(tmp_base_dir, mock_cache_manager):
    """Test that missing case_summary raises WorkspaceError."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Acme Corp"
            # Missing case_summary
        },
        {"name": "Acme Corp"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    with pytest.raises(WorkspaceError) as exc_info:
        resolver.resolve("12345678")

    assert "case_summary" in str(exc_info.value).lower()
    assert "missing" in str(exc_info.value).lower()


def test_empty_case_summary_fails(tmp_base_dir, mock_cache_manager):
    """Test that empty case_summary raises WorkspaceError."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Acme Corp",
            "case_summary": ""  # Empty
        },
        {"name": "Acme Corp"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    with pytest.raises(WorkspaceError) as exc_info:
        resolver.resolve("12345678")

    assert "case_summary" in str(exc_info.value).lower()


def test_path_formatting(tmp_base_dir, mock_cache_manager):
    """Test that shorten_and_format is applied to account and summary."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Very Long Company Name That Should Be Shortened",
            "case_summary": "Extremely long case summary that exceeds the character limit"
        },
        {"name": "Very Long Company Name That Should Be Shortened"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)
    workspace_path = resolver.resolve("12345678")

    # Verify formatting applied (max 22 chars per component)
    account_part = workspace_path.parent.name
    summary_part = workspace_path.name.split("-", 1)[1]  # After case number

    assert len(account_part) <= 22
    assert len(summary_part) <= 22


# CaseResolver.get_workspace_manager() tests

def test_get_workspace_manager(tmp_base_dir, mock_cache_manager):
    """Test getting WorkspaceManager instance from case number."""
    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    workspace_mgr = resolver.get_workspace_manager("12345678")

    # Verify WorkspaceManager created
    assert isinstance(workspace_mgr, WorkspaceManager)
    assert workspace_mgr.case_number == "12345678"
    assert workspace_mgr.account_name_formatted == shorten_and_format("Acme Corporation")
    assert workspace_mgr.case_summary_formatted == shorten_and_format(
        "OpenShift cluster nodes failing health checks"
    )

    # Verify cache_manager called
    mock_cache_manager.get_or_fetch.assert_called_once_with("12345678")


def test_get_workspace_manager_missing_account_name(tmp_base_dir, mock_cache_manager):
    """Test that get_workspace_manager fails if account_name missing."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "case_summary": "Test summary"
            # Missing account_name
        },
        {},  # No account data either
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    with pytest.raises(WorkspaceError) as exc_info:
        resolver.get_workspace_manager("12345678")

    assert "account_name" in str(exc_info.value).lower()


def test_get_workspace_manager_missing_case_summary(tmp_base_dir, mock_cache_manager):
    """Test that get_workspace_manager fails if case_summary missing."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Acme Corp"
            # Missing case_summary
        },
        {"name": "Acme Corp"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)

    with pytest.raises(WorkspaceError) as exc_info:
        resolver.get_workspace_manager("12345678")

    assert "case_summary" in str(exc_info.value).lower()


# WorkspaceManager.from_case_number() tests

def test_workspace_manager_from_case_number(tmp_base_dir, mock_cache_manager):
    """Test WorkspaceManager.from_case_number() classmethod."""
    workspace_mgr = WorkspaceManager.from_case_number(
        "12345678",
        mock_cache_manager,
        tmp_base_dir
    )

    # Verify WorkspaceManager created with correct metadata
    assert isinstance(workspace_mgr, WorkspaceManager)
    assert workspace_mgr.case_number == "12345678"
    assert workspace_mgr.account_name_formatted == shorten_and_format("Acme Corporation")
    assert workspace_mgr.case_summary_formatted == shorten_and_format(
        "OpenShift cluster nodes failing health checks"
    )

    # Verify cache_manager called
    mock_cache_manager.get_or_fetch.assert_called_once_with("12345678")


def test_workspace_manager_from_case_number_missing_metadata(tmp_base_dir, mock_cache_manager):
    """Test WorkspaceManager.from_case_number() fails with missing metadata."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Acme Corp"
            # Missing case_summary
        },
        {"name": "Acme Corp"},
        True
    )

    with pytest.raises(WorkspaceError) as exc_info:
        WorkspaceManager.from_case_number(
            "12345678",
            mock_cache_manager,
            tmp_base_dir
        )

    assert "case_summary" in str(exc_info.value).lower()


# Edge case tests

def test_account_name_from_account_data_fallback(tmp_base_dir, mock_cache_manager):
    """Test that account_name falls back to account_data if not in case_data."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "case_summary": "Test issue"
            # No account_name in case_data
        },
        {"name": "Fallback Company"},  # Should use this
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)
    workspace_path = resolver.resolve("12345678")

    # Verify account_name from account_data used
    assert workspace_path.parent.name == shorten_and_format("Fallback Company")


def test_subject_field_fallback(tmp_base_dir, mock_cache_manager):
    """Test that Subject field is used as fallback for case_summary."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Test Corp",
            "Subject": "Subject field value"  # Using Subject instead of case_summary
        },
        {"name": "Test Corp"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)
    workspace_path = resolver.resolve("12345678")

    # Verify Subject used as summary
    summary_part = workspace_path.name.split("-", 1)[1]
    assert "subject" in summary_part.lower()


def test_both_account_name_sources_present(tmp_base_dir, mock_cache_manager):
    """Test that case_data account_name takes precedence over account_data."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Primary Company",  # Should use this
            "case_summary": "Test issue"
        },
        {"name": "Secondary Company"},  # Should be ignored
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)
    workspace_path = resolver.resolve("12345678")

    # Verify case_data account_name used (takes precedence)
    assert workspace_path.parent.name == shorten_and_format("Primary Company")


def test_case_summary_precedence(tmp_base_dir, mock_cache_manager):
    """Test that case_summary takes precedence over Subject."""
    mock_cache_manager.get_or_fetch.return_value = (
        {
            "case_number": "12345678",
            "account_name": "Test Corp",
            "case_summary": "Primary summary",  # Should use this
            "Subject": "Secondary subject"  # Should be ignored
        },
        {"name": "Test Corp"},
        True
    )

    resolver = CaseResolver(mock_cache_manager, tmp_base_dir)
    workspace_path = resolver.resolve("12345678")

    # Verify case_summary used (takes precedence)
    summary_part = workspace_path.name.split("-", 1)[1]
    assert "primary" in summary_part.lower()
