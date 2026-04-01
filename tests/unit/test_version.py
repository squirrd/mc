"""Unit tests for mc.version module."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from unittest import mock


def test_get_version_resolves_mc_package() -> None:
    """get_version() must look up the 'mc' package via importlib.metadata.

    The package name in pyproject.toml is 'mc' (since fix/rename-package-to-mc).
    """
    from mc.version import get_version

    calls: list[str] = []

    def fake_version(pkg: str) -> str:
        calls.append(pkg)
        if pkg == "mc":
            return "2.0.11"
        raise PackageNotFoundError(pkg)

    with mock.patch("mc.version.version", side_effect=fake_version):
        result = get_version()

    assert "mc" in calls, (
        f"get_version() never called importlib.metadata.version('mc'). "
        f"Calls observed: {calls}."
    )
    assert result == "2.0.11", (
        f"get_version() returned {result!r}, expected '2.0.11'."
    )


def test_get_version_falls_back_to_uv_tool_list_when_metadata_absent() -> None:
    """get_version() falls back to 'uv tool list' when 'mc' is not in the active venv.

    When mc is installed as a uv tool (separate isolated env), importlib.metadata
    cannot see it. The fallback reads 'uv tool list' output to find the mc version.
    """
    from mc.version import get_version

    fake_uv_output = "mc v2.0.11\n- mc\n- mc-update\n"

    fake_completed = mock.MagicMock()
    fake_completed.stdout = fake_uv_output
    fake_completed.returncode = 0

    with (
        mock.patch("mc.version.version", side_effect=PackageNotFoundError("mc")),
        mock.patch("mc.version.subprocess.run", return_value=fake_completed) as mock_run,
    ):
        result = get_version()

    mock_run.assert_called_once_with(
        ["uv", "tool", "list"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result == "2.0.11", (
        f"get_version() returned {result!r} when using uv tool list fallback. "
        f"Expected '2.0.11' (mc version from uv tool list)."
    )
