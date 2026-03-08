"""Unit tests for mc CLI main.py argument parser wiring."""
from __future__ import annotations

import argparse
import sys
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers: build the 'go' subparser in isolation (avoids full main() setup)
# ---------------------------------------------------------------------------

def build_go_parser() -> argparse.ArgumentParser:
    """Reproduce the 'go' subparser logic from main.py for isolated testing."""
    parser = argparse.ArgumentParser(prog='mc')
    subparsers = parser.add_subparsers(dest='command')
    parser_go = subparsers.add_parser('go')
    parser_go.add_argument('case_number', type=str)
    parser_go.add_argument('-l', '--link', action='store_true',
                           help='Print URL instead of launching browser')
    return parser


# ---------------------------------------------------------------------------
# Argparse wiring tests
# ---------------------------------------------------------------------------

class TestGoArgparseFlagWiring:
    """Verify that -l sets args.link=True and absence leaves args.link=False."""

    def test_go_no_flag_link_is_false(self) -> None:
        """Without -l, args.link should be False (browser should launch)."""
        parser = build_go_parser()
        args = parser.parse_args(['go', '12345678'])
        assert args.link is False

    def test_go_with_l_flag_link_is_true(self) -> None:
        """With -l, args.link should be True (URL printed, no browser)."""
        parser = build_go_parser()
        args = parser.parse_args(['go', '12345678', '-l'])
        assert args.link is True

    def test_go_with_link_long_flag_link_is_true(self) -> None:
        """With --link, args.link should be True."""
        parser = build_go_parser()
        args = parser.parse_args(['go', '12345678', '--link'])
        assert args.link is True


# ---------------------------------------------------------------------------
# Integration tests: verify the call to other.go with correct launch value
# ---------------------------------------------------------------------------

def _run_main_go(argv: list[str]) -> None:
    """
    Drive main() with a controlled argv and mocked dependencies so we can
    assert on the call to other.go.
    """
    import mc.cli.main as main_module

    with patch.object(sys, 'argv', argv), \
         patch('mc.cli.main.check_legacy_env_vars'), \
         patch('mc.cli.main.ConfigManager') as MockCfgMgr, \
         patch('mc.cli.main.does_path_exist', return_value=True), \
         patch('mc.cli.main.get_runtime_mode', return_value='host'), \
         patch('mc.cli.main.VersionChecker'), \
         patch('mc.cli.main.setup_logging', return_value=MagicMock()):
        # Configure fake config manager so it looks like config exists
        instance = MockCfgMgr.return_value
        instance.exists.return_value = True
        instance.load.return_value = {
            'base_directory': '/tmp/mc',
            'api': {'rh_api_offline_token': 'fake-token'},
        }
        main_module.main()


class TestGoCommandCallsOtherGo:
    """Verify that main() routes 'go' to other.go with the correct launch value."""

    def test_go_no_flag_calls_other_go_with_launch_true(self) -> None:
        """
        Without -l, main() must call other.go(..., launch=True).

        This is the bug case: currently the flag is wired as --launch
        (store_true) and passed directly, so no flag means launch=False.
        After the fix, no flag means args.link=False → launch=not False=True.
        """
        with patch('mc.cli.commands.other.go') as mock_go:
            _run_main_go(['mc', 'go', '12345678'])
            mock_go.assert_called_once_with('12345678', launch=True)

    def test_go_with_l_flag_calls_other_go_with_launch_false(self) -> None:
        """
        With -l, main() must call other.go(..., launch=False).

        After the fix, -l sets args.link=True → launch=not True=False.
        """
        with patch('mc.cli.commands.other.go') as mock_go:
            _run_main_go(['mc', 'go', '12345678', '-l'])
            mock_go.assert_called_once_with('12345678', launch=False)
