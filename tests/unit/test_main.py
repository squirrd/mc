"""Unit tests for mc CLI main.py argument parser wiring."""
from __future__ import annotations

import argparse
import sys
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers: build the 'launch' subparser in isolation (avoids full main() setup)
# ---------------------------------------------------------------------------

def build_launch_parser() -> argparse.ArgumentParser:
    """Reproduce the 'launch' subparser logic from main.py for isolated testing."""
    parser = argparse.ArgumentParser(prog='mc')
    subparsers = parser.add_subparsers(dest='command')
    parser_launch = subparsers.add_parser('launch', aliases=['url'])
    parser_launch.set_defaults(command='launch')
    parser_launch.add_argument('case_number', type=str)
    parser_launch.add_argument('-l', '--link', action='store_true',
                               help='Print URL instead of launching browser')
    return parser


# ---------------------------------------------------------------------------
# Argparse wiring tests
# ---------------------------------------------------------------------------

class TestLaunchArgparseFlagWiring:
    """Verify that -l sets args.link=True and absence leaves args.link=False."""

    def test_launch_no_flag_link_is_false(self) -> None:
        """Without -l, args.link should be False (browser should launch)."""
        parser = build_launch_parser()
        args = parser.parse_args(['launch', '12345678'])
        assert args.link is False

    def test_launch_with_l_flag_link_is_true(self) -> None:
        """With -l, args.link should be True (URL printed, no browser)."""
        parser = build_launch_parser()
        args = parser.parse_args(['launch', '12345678', '-l'])
        assert args.link is True

    def test_launch_with_link_long_flag_link_is_true(self) -> None:
        """With --link, args.link should be True."""
        parser = build_launch_parser()
        args = parser.parse_args(['launch', '12345678', '--link'])
        assert args.link is True

    def test_url_alias_no_flag_link_is_false(self) -> None:
        """Via 'url' alias, args.link should be False without -l."""
        parser = build_launch_parser()
        args = parser.parse_args(['url', '12345678'])
        assert args.link is False

    def test_url_alias_with_l_flag_link_is_true(self) -> None:
        """Via 'url' alias, -l should set args.link=True."""
        parser = build_launch_parser()
        args = parser.parse_args(['url', '12345678', '-l'])
        assert args.link is True


# ---------------------------------------------------------------------------
# Integration tests: verify the call to other.go with correct launch value
# ---------------------------------------------------------------------------

def _run_main_launch(argv: list[str]) -> None:
    """
    Drive main() with a controlled argv and mocked dependencies so we can
    assert on the call to other.go.
    """
    import mc.cli.main as main_module

    with patch.object(sys, 'argv', argv), \
         patch('mc.cli.main.ConfigManager') as MockCfgMgr, \
         patch('mc.cli.main.does_path_exist', return_value=True), \
         patch('mc.cli.main.get_runtime_mode', return_value='host'), \
         patch('mc.cli.main.show_update_banner'), \
         patch('mc.cli.main.setup_logging', return_value=MagicMock()):
        # Configure fake config manager so it looks like config exists
        instance = MockCfgMgr.return_value
        instance.exists.return_value = True
        instance.load.return_value = {
            'base_directory': '/tmp/mc',
            'api': {'rh_api_offline_token': 'fake-token'},
        }
        main_module.main()


class TestLaunchCommandCallsOtherGo:
    """Verify that main() routes 'launch' to other.go with the correct launch value."""

    def test_launch_no_flag_calls_other_go_with_launch_true(self) -> None:
        """Without -l, main() must call other.go(..., launch=True)."""
        with patch('mc.cli.commands.other.go') as mock_go:
            _run_main_launch(['mc', 'launch', '12345678'])
            mock_go.assert_called_once_with('12345678', launch=True)

    def test_launch_with_l_flag_calls_other_go_with_launch_false(self) -> None:
        """With -l, main() must call other.go(..., launch=False)."""
        with patch('mc.cli.commands.other.go') as mock_go:
            _run_main_launch(['mc', 'launch', '12345678', '-l'])
            mock_go.assert_called_once_with('12345678', launch=False)

    def test_url_alias_calls_other_go_with_launch_true(self) -> None:
        """Via 'url' alias, main() must call other.go(..., launch=True)."""
        with patch('mc.cli.commands.other.go') as mock_go:
            _run_main_launch(['mc', 'url', '12345678'])
            mock_go.assert_called_once_with('12345678', launch=True)


# ---------------------------------------------------------------------------
# Banner agent-mode guard tests
# ---------------------------------------------------------------------------

class TestBannerAgentModeGuard:
    """Verify the banner is shown in host mode and suppressed in agent mode."""

    def _run_main_with_mode(self, runtime_mode: str) -> MagicMock:
        """Run main() with a controlled runtime mode; return the show_update_banner mock."""
        import mc.cli.main as main_module

        is_agent = runtime_mode == 'agent'
        mock_banner = MagicMock()
        with patch.object(sys, 'argv', ['mc', 'ldap', 'someuid']), \
             patch('mc.cli.main.ConfigManager') as MockCfgMgr, \
             patch('mc.cli.main.does_path_exist', return_value=True), \
             patch('mc.cli.main.get_runtime_mode', return_value=runtime_mode), \
             patch('mc.cli.main.should_check_for_updates', return_value=not is_agent), \
             patch('mc.cli.main.show_update_banner', mock_banner), \
             patch('mc.cli.commands.other.ls'), \
             patch('mc.cli.main.setup_logging', return_value=MagicMock()):
            instance = MockCfgMgr.return_value
            instance.exists.return_value = True
            instance.load.return_value = {
                'base_directory': '/tmp/mc',
                'api': {'rh_api_offline_token': 'fake-token'},
            }
            main_module.main()
        return mock_banner

    def test_show_update_banner_called_in_host_mode(self) -> None:
        """When runtime mode is 'host', show_update_banner must be called."""
        mock_banner = self._run_main_with_mode('host')
        mock_banner.assert_called_once()

    def test_show_update_banner_not_called_in_agent_mode(self) -> None:
        """When runtime mode is 'agent', show_update_banner must NOT be called."""
        mock_banner = self._run_main_with_mode('agent')
        mock_banner.assert_not_called()
