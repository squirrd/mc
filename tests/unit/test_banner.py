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


class TestVersionCheckFailureThrottle:
    """Regression tests for failure throttle in show_update_banner().

    Bug discovered: 2026-03-19
    Platform: Both
    Severity: minor
    Source: ad-hoc / user report

    Problem:
    show_update_banner() has no failure throttle. When _fetch_with_timeout()
    returns None (GitHub 404, network error, or no releases), no failure
    timestamp is stored. The next MC invocation immediately hits GitHub again,
    causing a network call on every single MC run when the check is failing.

    Additionally, stale config keys (last_check, last_status_code) written by
    the now-dead version_check.py VersionChecker were never cleaned up from
    config.toml, leaving misleading entries.

    Expected: when last fetch failed < 1 hour ago, the fetch is skipped entirely.
    Actual:   fetch is called again on every MC invocation regardless.

    This test ensures the regression does not recur.
    """

    def test_skips_fetch_when_last_check_failed_recently(self) -> None:
        """show_update_banner() must NOT fetch when last fetch failed < 1 hour ago."""
        import time

        recent_failure_ts = time.time() - 60  # 1 minute ago — within 1-hour throttle

        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_banner_shown": None,
            "last_failed_fetch": recent_failure_ts,
        }

        with patch("mc.banner._is_version_invocation", return_value=False), \
             patch("sys.stdout") as mock_stdout, \
             patch("mc.banner._fetch_with_timeout", return_value=None) as mock_fetch, \
             patch("mc.config.manager.ConfigManager", return_value=mock_config):
            mock_stdout.isatty.return_value = True
            show_update_banner()

        mock_fetch.assert_not_called()

    def test_does_fetch_when_last_failure_was_over_one_hour_ago(self) -> None:
        """show_update_banner() MUST fetch when last failure was > 1 hour ago."""
        import time

        old_failure_ts = time.time() - 3700  # just over 1 hour ago

        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_banner_shown": None,
            "last_failed_fetch": old_failure_ts,
        }

        with patch("mc.banner._is_version_invocation", return_value=False), \
             patch("sys.stdout") as mock_stdout, \
             patch("mc.banner._fetch_with_timeout", return_value=None) as mock_fetch, \
             patch("mc.config.manager.ConfigManager", return_value=mock_config):
            mock_stdout.isatty.return_value = True
            show_update_banner()

        mock_fetch.assert_called_once()

    def test_does_fetch_when_no_previous_failure_recorded(self) -> None:
        """show_update_banner() must fetch when last_failed_fetch is None (first run)."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_banner_shown": None,
            "last_failed_fetch": None,
        }

        with patch("mc.banner._is_version_invocation", return_value=False), \
             patch("sys.stdout") as mock_stdout, \
             patch("mc.banner._fetch_with_timeout", return_value=None) as mock_fetch, \
             patch("mc.config.manager.ConfigManager", return_value=mock_config):
            mock_stdout.isatty.return_value = True
            show_update_banner()

        mock_fetch.assert_called_once()

    def test_stores_failure_timestamp_when_fetch_returns_none(self) -> None:
        """show_update_banner() must write last_failed_fetch when fetch returns None."""
        mock_config = MagicMock()
        mock_config.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_banner_shown": None,
            "last_failed_fetch": None,
        }

        with patch("mc.banner._is_version_invocation", return_value=False), \
             patch("sys.stdout") as mock_stdout, \
             patch("mc.banner._fetch_with_timeout", return_value=None), \
             patch("mc.config.manager.ConfigManager", return_value=mock_config):
            mock_stdout.isatty.return_value = True
            show_update_banner()

        mock_config.update_version_config.assert_called_once()
        call_kwargs = mock_config.update_version_config.call_args[1]
        assert "last_failed_fetch" in call_kwargs
        assert isinstance(call_kwargs["last_failed_fetch"], float)
