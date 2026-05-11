"""Version information for mc CLI."""

from importlib.metadata import version, PackageNotFoundError
import os
import subprocess
import sys
from pathlib import Path
from typing import cast


def get_version() -> str:
    """Get the installed mc version.

    Resolution order:
    1. `uv tool list` output (authoritative when mc is installed as a uv tool)
    2. importlib.metadata for 'mc' (works when mc is installed in the active venv)
    3. pyproject.toml (development mode fallback)

    uv tool list is checked first because importlib.metadata can reflect a dev
    checkout's pyproject.toml version rather than the actually-installed tool version
    when both are on the Python path.
    """
    # mc is installed as a uv tool — query the tool list (authoritative source)
    try:
        mc_env = os.environ.get("MC_ENV")
        uv_env = dict(os.environ)
        if mc_env:
            uv_env["UV_TOOL_DIR"] = str(Path.home() / f"mc-{mc_env}" / "tools")
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
            check=False,
            env=uv_env,
        )
        for line in result.stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("mc "):
                parts = stripped.split()
                if len(parts) >= 2:
                    return parts[1].lstrip("v")
    except FileNotFoundError:
        pass

    # Fallback: importlib.metadata (works when mc is installed in the active venv)
    try:
        return version("mc")
    except PackageNotFoundError:
        pass

    # Development mode: parse pyproject.toml
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return cast(str, pyproject["project"]["version"])
