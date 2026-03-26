"""Unit tests for mc.version module."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from unittest import mock


def test_get_version_resolves_mc_cli_package_not_mc() -> None:
    """get_version() must look up the 'mc-cli' package, not the dev-repo 'mc' package.

    Bug: version.py called importlib.metadata.version("mc"), which resolves to the
    dev-repo tool (v2.0.9) instead of the prod uv tool 'mc-cli' (v2.0.4).
    """
    from mc.version import get_version

    calls: list[str] = []

    def fake_version(pkg: str) -> str:
        calls.append(pkg)
        if pkg == "mc-cli":
            return "2.0.4"
        raise PackageNotFoundError(pkg)

    with mock.patch("mc.version.version", side_effect=fake_version):
        result = get_version()

    assert "mc-cli" in calls, (
        f"get_version() never called importlib.metadata.version('mc-cli'). "
        f"Calls observed: {calls}. "
        f"Bug: version('mc') resolves dev-repo, not the prod mc-cli uv tool."
    )
    assert result == "2.0.4", (
        f"get_version() returned {result!r}, expected '2.0.4' (mc-cli version). "
        f"Bug: version('mc') resolves dev-repo package instead of prod mc-cli."
    )


def test_get_version_falls_back_to_uv_tool_list_when_metadata_absent() -> None:
    """get_version() falls back to 'uv tool list' when mc-cli is not in the active venv.

    When mc-cli is installed as a uv tool (separate isolated env), importlib.metadata
    cannot see it. The fallback reads 'uv tool list' output to find the mc-cli version.
    """
    from importlib.metadata import PackageNotFoundError
    from mc.version import get_version

    fake_uv_output = "mc v2.0.9\n- mc\n- mc-update\nmc-cli v2.0.4\n- mc\n"

    fake_completed = mock.MagicMock()
    fake_completed.stdout = fake_uv_output
    fake_completed.returncode = 0

    with (
        mock.patch("mc.version.version", side_effect=PackageNotFoundError("mc-cli")),
        mock.patch("mc.version.subprocess.run", return_value=fake_completed) as mock_run,
    ):
        result = get_version()

    mock_run.assert_called_once_with(
        ["uv", "tool", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result == "2.0.4", (
        f"get_version() returned {result!r} when using uv tool list fallback. "
        f"Expected '2.0.4' (mc-cli version from uv tool list)."
    )
