"""Version information for mc CLI."""

from importlib.metadata import version, PackageNotFoundError
import sys
from pathlib import Path


def get_version() -> str:
    """Get package version from metadata or pyproject.toml.

    Returns version from installed package metadata when available.
    Falls back to parsing pyproject.toml in development mode.
    """
    try:
        # Works for installed package
        return version("mc-cli")
    except PackageNotFoundError:
        # Development mode: parse pyproject.toml
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            import tomli as tomllib

        pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
        with open(pyproject_path, "rb") as f:
            pyproject = tomllib.load(f)
        return pyproject["project"]["version"]
