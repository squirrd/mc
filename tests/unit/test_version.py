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
