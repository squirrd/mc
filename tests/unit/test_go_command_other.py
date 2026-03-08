"""Unit tests for mc.cli.commands.other.go() — browser launch vs URL print behaviour."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock


CASE_NUMBER = "12345678"
EXPECTED_URL = f"https://gss--c.vf.force.com/apex/Case_View?sbstr={CASE_NUMBER}"


@pytest.mark.backwards_compatibility
def test_go_default_launches_browser(capsys: pytest.CaptureFixture[str]) -> None:
    """go(case_number) with no args should launch the browser (subprocess.run called)."""
    from mc.cli.commands.other import go

    with patch("mc.cli.commands.other.subprocess.run") as mock_run:
        go(CASE_NUMBER)
        mock_run.assert_called_once()
        # Verify the URL appears somewhere in the call args
        call_args = mock_run.call_args[0][0]
        assert any(EXPECTED_URL in str(arg) for arg in call_args)

    # Nothing should be printed to stdout when browser is launched
    captured = capsys.readouterr()
    assert EXPECTED_URL not in captured.out


@pytest.mark.backwards_compatibility
def test_go_launch_false_prints_url(capsys: pytest.CaptureFixture[str]) -> None:
    """go(case_number, launch=False) should print the URL and NOT call subprocess.run."""
    from mc.cli.commands.other import go

    with patch("mc.cli.commands.other.subprocess.run") as mock_run:
        go(CASE_NUMBER, launch=False)
        mock_run.assert_not_called()

    captured = capsys.readouterr()
    assert EXPECTED_URL in captured.out
