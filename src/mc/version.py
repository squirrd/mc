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
    1. importlib.metadata for 'mc' (works when mc is installed in the active venv)
    2. `uv tool list` output (works when mc is installed as a uv tool but not in the venv)
    3. pyproject.toml (development mode fallback)
    """
    try:
        # Works when mc package metadata is available in the active venv
        return version("mc")
    except PackageNotFoundError:
        pass

    # mc is installed as a uv tool (separate isolated env) — query the tool list
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

    # Development mode: parse pyproject.toml
    if sys.version_info >= (3, 11):
        import tomllib
    else:
        import tomli as tomllib

    pyproject_path = Path(__file__).parent.parent.parent / "pyproject.toml"
    with open(pyproject_path, "rb") as f:
        pyproject = tomllib.load(f)
    return cast(str, pyproject["project"]["version"])
