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
    """Test that version matches pyproject.toml value."""
    import sys
    from pathlib import Path

    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    expected_version = pyproject["project"]["version"]

    version = get_version()
    assert version == expected_version


def test_get_version_fallback_to_pyproject(monkeypatch):
    """Test fallback to pyproject.toml when package not installed."""
    import importlib.metadata

    def mock_version(name):
        raise PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, 'version', mock_version)

    # Should fall back to parsing pyproject.toml
    version = get_version()
    assert version == "0.1.0"
    assert isinstance(version, str)


def test_get_version_from_installed_package():
    """Test that get_version tries importlib.metadata first."""
    with patch('mc.version.version') as mock_version:
        mock_version.return_value = "1.2.3"

        version = get_version()

        assert version == "1.2.3"
        mock_version.assert_called_once_with("mc-cli")
