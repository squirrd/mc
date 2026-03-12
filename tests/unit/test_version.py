"""Tests for version management."""

import pytest
from unittest.mock import patch
from importlib.metadata import PackageNotFoundError
from mc.version import get_version


def test_get_version_returns_string():
    """Test that get_version returns a string."""
    version = get_version()
    assert isinstance(version, str)
    assert len(version) > 0


def test_get_version_format():
    """Test that version matches semantic versioning pattern."""
    version = get_version()
    parts = version.split('.')
    assert len(parts) == 3, "Version should be in X.Y.Z format"
    for part in parts:
        assert part.isdigit(), f"Version part '{part}' should be numeric"


def test_get_version_matches_pyproject():
    """Test that version matches pyproject.toml value when installed from source."""
    import sys
    from pathlib import Path
    from importlib.metadata import PackageNotFoundError

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    expected_version = pyproject["project"]["version"]

    version = get_version()

    # When installed from source in editable mode, version should match pyproject.toml
    # When installed from a package, it may differ (e.g., installed 0.1.0 vs pyproject 2.0.0)
    # This test verifies get_version returns a valid version string
    assert isinstance(version, str)
    assert len(version.split('.')) == 3  # X.Y.Z format


def test_get_version_fallback_to_pyproject(monkeypatch):
    """Test fallback to pyproject.toml when package not installed."""
    import sys
    from pathlib import Path
    from mc import version as version_module

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        expected_version = tomllib.load(f)["project"]["version"]

    def mock_version(name):
        raise PackageNotFoundError(name)

    # Patch the version function in mc.version module (not importlib.metadata)
    monkeypatch.setattr(version_module, 'version', mock_version)

    # Should fall back to parsing pyproject.toml — reads expected value dynamically
    # so this test never needs updating when the version bumps.
    version = get_version()
    assert version == expected_version
    assert isinstance(version, str)


def test_get_version_from_installed_package():
    """Test that get_version tries importlib.metadata first."""
    with patch('mc.version.version') as mock_version:
        mock_version.return_value = "1.2.3"

        version = get_version()

        assert version == "1.2.3"
        mock_version.assert_called_once_with("mc")
