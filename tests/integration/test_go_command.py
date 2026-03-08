"""Integration tests for the mc go command."""
from unittest.mock import patch

import pytest


@pytest.mark.integration
def test_go_link_flag_reversed_regression() -> None:
    """Regression test for inverted -l/--launch flag logic in mc go.

    Bug discovered: 2026-03-08
    Platform: Both
    Severity: minor
    Source: ad-hoc

    Problem:
    The mc go command has its flag logic inverted. Running `mc go <case>` (no flag)
    should launch the Salesforce URL in a browser by default, and `mc go -l <case>`
    should print the URL for copy/paste. The implementation had these backwards:
    the -l/--launch flag launched the browser, and the default (no flag) printed the URL.

    Steps to reproduce:
    1. Run `mc go 04392393` — expect browser to open, but URL is printed to stdout
    2. Run `mc go -l 04392393` — expect URL printed to stdout, but browser opens instead

    Expected: go(case_number) launches browser; go(case_number, launch=False) prints URL
    Actual:   go(case_number) prints URL; go(case_number, launch=True) launches browser

    This test ensures the bug does not regress.
    """
    from mc.cli.commands.other import go

    # Without -l flag: default action must be to launch the browser
    with patch("mc.cli.commands.other.subprocess.run") as mock_run:
        go("04392393")

    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "04392393" in call_args[-1]


@pytest.mark.integration
def test_go_link_flag_prints_url_regression(capsys: pytest.CaptureFixture[str]) -> None:
    """Regression test: -l flag on mc go must print URL, not launch browser.

    Bug discovered: 2026-03-08
    Platform: Both
    Severity: minor
    Source: ad-hoc

    Problem:
    When -l is passed to mc go, the URL should be printed to stdout for copy/paste.
    Before the fix, -l launched the browser instead.

    Expected: go(case_number, launch=False) prints URL to stdout (launch=False is what -l maps to)
    Actual:   go(case_number, launch=True) opens browser via subprocess.run

    This test ensures the bug does not regress.
    """
    from mc.cli.commands.other import go

    # -l flag maps to launch=False in the fixed code (main.py: launch=not args.link)
    with patch("mc.cli.commands.other.subprocess.run") as mock_run:
        go("04392393", launch=False)

    mock_run.assert_not_called()

    output = capsys.readouterr().out
    assert "https://gss--c.vf.force.com/apex/Case_View?sbstr=04392393" in output
