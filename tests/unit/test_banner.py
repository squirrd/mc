"""Unit tests for mc.banner module.

Tests cover:
- _is_version_invocation(): version flag detection
- _already_shown_today(): suppression date comparison
- _fetch_with_timeout(): threaded GitHub fetch with timeout
- _write_suppression_timestamp(): conditional config write
- _render_banner(): Rich Panel output for standard and pinned cases
- show_update_banner(): orchestrator skip conditions and happy path

Patching strategy (all lazy imports must be patched at source):
- mc.update._fetch_latest_version  (imported inside _fetch_with_timeout)
- mc.config.manager.ConfigManager  (imported inside _already_shown_today,
                                    _write_suppression_timestamp, show_update_banner)
- mc.version.get_version           (imported inside show_update_banner)
- rich.console.Console             (imported inside _render_banner)
- rich.panel.Panel                 (imported inside _render_banner)
"""
from __future__ import annotations

import sys
import time
from datetime import date, timedelta
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from mc.banner import (
    _already_shown_today,
    _fetch_with_timeout,
    _is_version_invocation,
    _render_banner,
    _write_suppression_timestamp,
    show_update_banner,
)


class TestIsVersionInvocation:
    """Tests for _is_version_invocation()."""

    def test_returns_true_when_version_flag_first_arg(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns True when --version is the first (and only) argument."""
        monkeypatch.setattr(sys, "argv", ["mc", "--version"])
        assert _is_version_invocation() is True

    def test_returns_false_when_subcommand_before_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test returns False when --version follows a subcommand (e.g. mc case --version)."""
        monkeypatch.setattr(sys, "argv", ["mc", "case", "--version"])
        assert _is_version_invocation() is False

    def test_returns_false_when_no_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test returns False when no arguments are provided (bare mc invocation)."""
        monkeypatch.setattr(sys, "argv", ["mc"])
        assert _is_version_invocation() is False


class TestAlreadyShownToday:
    """Tests for _already_shown_today().

    ConfigManager is lazily imported inside _already_shown_today so must be patched
    at mc.config.manager.ConfigManager (the source module).
    """

    def test_returns_false_when_none(self) -> None:
        """Test returns False when last_banner_shown is None (never shown)."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.config.manager.ConfigManager", return_value=mock_config):
            result = _already_shown_today()
        assert result is False

    def test_returns_true_when_today(self) -> None:
        """Test returns True when stored date matches today's date."""
        today_iso = date.today().isoformat() + "T10:00:00"
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": today_iso,
        }
        with patch("mc.config.manager.ConfigManager", return_value=mock_config):
            result = _already_shown_today()
        assert result is True

    def test_returns_false_when_yesterday(self) -> None:
        """Test returns False when stored date is yesterday."""
        yesterday_iso = (date.today() - timedelta(days=1)).isoformat() + "T10:00:00"
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": yesterday_iso,
        }
        with patch("mc.config.manager.ConfigManager", return_value=mock_config):
            result = _already_shown_today()
        assert result is False


class TestFetchWithTimeout:
    """Tests for _fetch_with_timeout().

    _fetch_latest_version is lazily imported inside _fetch_with_timeout from mc.update,
    so must be patched at mc.update._fetch_latest_version.
    """

    def test_returns_version_on_success(self) -> None:
        """Test returns version string when _fetch_latest_version succeeds."""
        with patch("mc.update._fetch_latest_version", return_value="2.0.5"):
            result = _fetch_with_timeout()
        assert result == "2.0.5"

    def test_returns_none_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test returns None and prints timeout message when fetch takes too long."""
        monkeypatch.setattr("mc.banner._TIMEOUT_SECONDS", 0.01)

        def slow_fetch() -> Optional[str]:
            time.sleep(5)
            return "2.0.5"

        with patch("mc.update._fetch_latest_version", side_effect=slow_fetch):
            result = _fetch_with_timeout()
        assert result is None
        captured = capsys.readouterr()
        assert "timed out" in captured.err

    def test_returns_none_on_network_failure(self) -> None:
        """Test returns None when _fetch_latest_version returns None (network failure)."""
        with patch("mc.update._fetch_latest_version", return_value=None):
            result = _fetch_with_timeout()
        assert result is None


class TestWriteSuppressionTimestamp:
    """Tests for _write_suppression_timestamp().

    ConfigManager is lazily imported, so patched at mc.config.manager.ConfigManager.
    """

    def test_writes_timestamp_when_tty(self) -> None:
        """Test calls update_version_config with last_banner_shown when stdout is a TTY."""
        mock_config = MagicMock()
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = True
            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                _write_suppression_timestamp()
        mock_config.update_version_config.assert_called_once()
        call_kwargs = mock_config.update_version_config.call_args[1]
        assert "last_banner_shown" in call_kwargs
        # Verify it's an ISO format string containing today's date
        stored = call_kwargs["last_banner_shown"]
        assert date.today().isoformat() in stored

    def test_skips_when_not_tty(self) -> None:
        """Test does NOT call ConfigManager when stdout is not a TTY (piped run)."""
        mock_config = MagicMock()
        with patch("sys.stdout") as mock_stdout:
            mock_stdout.isatty.return_value = False
            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                _write_suppression_timestamp()
        mock_config.update_version_config.assert_not_called()


class TestRenderBanner:
    """Tests for _render_banner().

    Console and Panel are lazily imported inside _render_banner.
    Patch at rich.console.Console and rich.panel.Panel.
    """

    def test_renders_standard_banner(self) -> None:
        """Test standard (non-pinned) banner calls Console with upgrade arrow content."""
        mock_console = MagicMock()
        mock_panel_cls = MagicMock()
        with patch("rich.console.Console", return_value=mock_console):
            with patch("rich.panel.Panel", side_effect=mock_panel_cls):
                _render_banner(current="2.0.4", latest="2.0.5", pinned=None)
        # Panel constructor called with the right content
        panel_call_args = mock_panel_cls.call_args
        content_arg = panel_call_args[0][0]
        assert "2.0.4" in content_arg
        assert "2.0.5" in content_arg
        assert "mc-update upgrade" in content_arg
        # Console.print called 3 times (blank, panel, blank)
        assert mock_console.print.call_count == 3

    def test_renders_pinned_banner(self) -> None:
        """Test pinned banner shows 'pinned at' message and mc-update unpin instruction."""
        mock_console = MagicMock()
        mock_panel_cls = MagicMock()
        with patch("rich.console.Console", return_value=mock_console):
            with patch("rich.panel.Panel", side_effect=mock_panel_cls):
                _render_banner(current="2.0.4", latest="2.0.5", pinned="2.0.4")
        panel_call_args = mock_panel_cls.call_args
        content_arg = panel_call_args[0][0]
        assert "pinned at" in content_arg
        assert "mc-update unpin" in content_arg


class TestShowUpdateBanner:
    """Tests for show_update_banner() orchestrator function.

    Lazy imports inside show_update_banner:
    - mc.version.get_version
    - mc.config.manager.ConfigManager
    Internal helpers patched at mc.banner.<helper_name>.
    """

    def test_skips_on_version_flag(self) -> None:
        """Test returns early without fetching when invocation is 'mc --version'."""
        with patch("mc.banner._is_version_invocation", return_value=True):
            with patch("mc.banner._fetch_with_timeout") as mock_fetch:
                show_update_banner()
        mock_fetch.assert_not_called()

    def test_skips_when_not_tty(self) -> None:
        """Test returns early without checking banner suppression when stdout is not a TTY."""
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = False
                with patch("mc.banner._already_shown_today") as mock_shown:
                    show_update_banner()
        mock_shown.assert_not_called()

    def test_skips_when_shown_today(self) -> None:
        """Test returns early without fetching when banner was already shown today."""
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=True):
                    with patch("mc.banner._fetch_with_timeout") as mock_fetch:
                        show_update_banner()
        mock_fetch.assert_not_called()

    def test_skips_when_no_newer_version(self) -> None:
        """Test does not render banner when installed version equals latest."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=False):
                    with patch("mc.banner._fetch_with_timeout", return_value="2.0.4"):
                        with patch("mc.version.get_version", return_value="2.0.4"):
                            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                                with patch("mc.banner._render_banner") as mock_render:
                                    show_update_banner()
        mock_render.assert_not_called()

    def test_shows_banner_when_newer_available(self) -> None:
        """Test renders banner exactly once when a newer version is available."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=False):
                    with patch("mc.banner._fetch_with_timeout", return_value="2.0.5"):
                        with patch("mc.version.get_version", return_value="2.0.4"):
                            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                                with patch("mc.banner._render_banner") as mock_render:
                                    with patch("mc.banner._write_suppression_timestamp"):
                                        show_update_banner()
        mock_render.assert_called_once_with("2.0.4", "2.0.5", None)

    def test_writes_suppression_after_banner(self) -> None:
        """Test calls _write_suppression_timestamp after rendering banner."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=False):
                    with patch("mc.banner._fetch_with_timeout", return_value="2.0.5"):
                        with patch("mc.version.get_version", return_value="2.0.4"):
                            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                                with patch("mc.banner._render_banner"):
                                    with patch(
                                        "mc.banner._write_suppression_timestamp"
                                    ) as mock_write:
                                        show_update_banner()
        mock_write.assert_called_once()

    def test_skips_when_fetch_returns_none(self) -> None:
        """Test does not render banner when fetch returns None (timeout or network failure)."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=False):
                    with patch("mc.banner._fetch_with_timeout", return_value=None):
                        with patch("mc.version.get_version", return_value="2.0.4"):
                            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                                with patch("mc.banner._render_banner") as mock_render:
                                    show_update_banner()
        mock_render.assert_not_called()

    def test_shows_pinned_banner_when_pin_active(self) -> None:
        """Test renders banner with pinned argument when a version pin is active."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "2.0.3",
            "last_check": None,
            "last_banner_shown": None,
        }
        with patch("mc.banner._is_version_invocation", return_value=False):
            with patch("sys.stdout") as mock_stdout:
                mock_stdout.isatty.return_value = True
                with patch("mc.banner._already_shown_today", return_value=False):
                    with patch("mc.banner._fetch_with_timeout", return_value="2.0.5"):
                        with patch("mc.version.get_version", return_value="2.0.4"):
                            with patch("mc.config.manager.ConfigManager", return_value=mock_config):
                                with patch("mc.banner._render_banner") as mock_render:
                                    with patch("mc.banner._write_suppression_timestamp"):
                                        show_update_banner()
        mock_render.assert_called_once_with("2.0.4", "2.0.5", "2.0.3")
