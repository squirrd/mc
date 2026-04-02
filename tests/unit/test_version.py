"""Unit tests for mc.version module."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from unittest import mock

import pytest


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

    _, kwargs = mock_run.call_args
    assert mock_run.call_args[0][0] == ["uv", "tool", "list"]
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert kwargs.get("check") is False
    assert result == "2.0.11", (
        f"get_version() returned {result!r} when using uv tool list fallback. "
        f"Expected '2.0.11' (mc version from uv tool list)."
    )


class TestGetVersionUvEnv:
    """Tests that get_version() passes the correct UV_TOOL_DIR env to subprocess.run."""

    def test_uv_tool_dir_set_when_mc_env_is_dev(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MC_ENV=dev, subprocess.run must receive UV_TOOL_DIR=~/mc-dev/tools."""
        from mc.version import get_version

        monkeypatch.setenv("MC_ENV", "dev")

        fake_completed = mock.MagicMock()
        fake_completed.stdout = "mc v2.0.11\n- mc\n"
        fake_completed.returncode = 0

        with (
            mock.patch("mc.version.version", side_effect=PackageNotFoundError("mc")),
            mock.patch("mc.version.subprocess.run", return_value=fake_completed) as mock_run,
        ):
            get_version()

        _, kwargs = mock_run.call_args
        passed_env = kwargs.get("env")
        assert passed_env is not None, "subprocess.run was not called with an env= kwarg"
        expected_tool_dir = str(Path.home() / "mc-dev" / "tools")
        assert "UV_TOOL_DIR" in passed_env, (
            f"UV_TOOL_DIR not set in env passed to subprocess.run. env keys: {list(passed_env.keys())}"
        )
        assert passed_env["UV_TOOL_DIR"] == expected_tool_dir, (
            f"UV_TOOL_DIR={passed_env['UV_TOOL_DIR']!r}, expected {expected_tool_dir!r}"
        )

    def test_uv_tool_dir_not_set_when_mc_env_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """When MC_ENV is unset, UV_TOOL_DIR must NOT appear in the env passed to subprocess.run."""
        from mc.version import get_version

        monkeypatch.delenv("MC_ENV", raising=False)

        fake_completed = mock.MagicMock()
        fake_completed.stdout = "mc v2.0.11\n- mc\n"
        fake_completed.returncode = 0

        with (
            mock.patch("mc.version.version", side_effect=PackageNotFoundError("mc")),
            mock.patch("mc.version.subprocess.run", return_value=fake_completed) as mock_run,
        ):
            get_version()

        _, kwargs = mock_run.call_args
        passed_env = kwargs.get("env")
        # env kwarg may be passed (copy of os.environ), but UV_TOOL_DIR must not be in it
        if passed_env is not None:
            assert "UV_TOOL_DIR" not in passed_env, (
                f"UV_TOOL_DIR should not be set when MC_ENV is absent, "
                f"but found UV_TOOL_DIR={passed_env['UV_TOOL_DIR']!r}"
            )
