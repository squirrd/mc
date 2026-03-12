"""Unit tests for the iterm2 Python API path in MacOSLauncher."""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Generator
from unittest.mock import MagicMock, Mock

import pytest

from mc.terminal.launcher import LaunchOptions
from mc.terminal.macos import (
    MacOSLauncher,
    _record_iterm2_fallback_notice,
    _should_show_iterm2_fallback_notice,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_options(
    title: str = "12345678 - Test - Case",
    command: str = "podman exec -it mc-12345678 bash",
) -> LaunchOptions:
    return LaunchOptions(title=title, command=command, auto_focus=True)


# ---------------------------------------------------------------------------
# _try_iterm2_api
# ---------------------------------------------------------------------------


class TestTryIterm2Api:
    """Tests for MacOSLauncher._try_iterm2_api()."""

    def test_try_iterm2_api_lib_available_returns_window_id(self, mocker: Mock) -> None:
        """_try_iterm2_api returns window_id when library is available and API succeeds."""
        mocker.patch("mc.terminal.macos._ITERM2_LIB_AVAILABLE", True)
        mocker.patch.object(
            MacOSLauncher,
            "_launch_via_iterm2_api",
            return_value="w1234-uuid",
        )
        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        result = launcher._try_iterm2_api(options)

        assert result == "w1234-uuid"

    def test_try_iterm2_api_lib_not_available_returns_none(self, mocker: Mock) -> None:
        """_try_iterm2_api returns None immediately when library is not available."""
        mocker.patch("mc.terminal.macos._ITERM2_LIB_AVAILABLE", False)
        mock_launch = mocker.patch.object(MacOSLauncher, "_launch_via_iterm2_api")
        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        result = launcher._try_iterm2_api(options)

        assert result is None
        mock_launch.assert_not_called()

    def test_try_iterm2_api_exception_returns_none(self, mocker: Mock) -> None:
        """_try_iterm2_api returns None when API raises an exception (connection refused)."""
        mocker.patch("mc.terminal.macos._ITERM2_LIB_AVAILABLE", True)
        mocker.patch.object(
            MacOSLauncher,
            "_launch_via_iterm2_api",
            side_effect=OSError("connection refused"),
        )
        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        result = launcher._try_iterm2_api(options)

        assert result is None

    def test_try_iterm2_api_exception_does_not_reraise(self, mocker: Mock) -> None:
        """_try_iterm2_api never re-raises exceptions — caller always gets None or a window_id."""
        mocker.patch("mc.terminal.macos._ITERM2_LIB_AVAILABLE", True)
        mocker.patch.object(
            MacOSLauncher,
            "_launch_via_iterm2_api",
            side_effect=RuntimeError("API disabled in iTerm2 settings"),
        )
        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        # Must not raise
        result = launcher._try_iterm2_api(options)

        assert result is None


# ---------------------------------------------------------------------------
# launch() — API path vs. fallback path
# ---------------------------------------------------------------------------


class TestLaunchApiPath:
    """Tests for MacOSLauncher.launch() focusing on the API vs. fallback decision."""

    def test_launch_api_succeeds_popen_not_called(self, mocker: Mock) -> None:
        """When _try_iterm2_api returns a window_id, launch() must not call subprocess.Popen."""
        mocker.patch.object(MacOSLauncher, "_try_iterm2_api", return_value="w0ABC123")
        mock_popen = mocker.patch("subprocess.Popen")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        launcher.launch(options)

        mock_popen.assert_not_called()
        assert launcher._last_api_window_id == "w0ABC123"

    def test_launch_api_succeeds_window_id_stored(self, mocker: Mock) -> None:
        """After API-success launch, _last_api_window_id is set and consumed by _capture_window_id."""  # noqa: E501
        mocker.patch.object(MacOSLauncher, "_try_iterm2_api", return_value="w0ABC123")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        launcher.launch(options)

        assert launcher._last_api_window_id == "w0ABC123"
        captured = launcher._capture_window_id()
        assert captured == "w0ABC123"
        assert launcher._last_api_window_id is None  # consumed

    def test_launch_api_fails_falls_back_to_terminal_app(self, mocker: Mock) -> None:
        """When _try_iterm2_api returns None, launch() falls back to Terminal.app AppleScript."""
        mocker.patch.object(MacOSLauncher, "_try_iterm2_api", return_value=None)
        mocker.patch("mc.terminal.macos._should_show_iterm2_fallback_notice", return_value=False)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_process = MagicMock()
        mock_popen.return_value = mock_process
        mocker.patch("threading.Thread")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        launcher.launch(options)

        mock_popen.assert_called_once()
        call_args = mock_popen.call_args
        script = call_args[0][0][2]
        assert "Terminal" in script

    def test_launch_api_fails_shows_fallback_notice_on_first_occurrence(
        self, mocker: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When API fails and notice not yet shown today, prints warning to stderr."""
        mocker.patch.object(MacOSLauncher, "_try_iterm2_api", return_value=None)
        mocker.patch("mc.terminal.macos._should_show_iterm2_fallback_notice", return_value=True)
        mock_record = mocker.patch("mc.terminal.macos._record_iterm2_fallback_notice")
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = MagicMock()
        mocker.patch("threading.Thread")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        launcher.launch(options)

        captured = capsys.readouterr()
        assert "iTerm2 API unavailable" in captured.err
        assert "Enable via iTerm2 > Settings > General > Magic" in captured.err
        mock_record.assert_called_once()

    def test_launch_api_fails_fallback_notice_suppressed_same_day(
        self, mocker: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """When API fails but notice already shown today, stderr stays clean."""
        mocker.patch.object(MacOSLauncher, "_try_iterm2_api", return_value=None)
        mocker.patch("mc.terminal.macos._should_show_iterm2_fallback_notice", return_value=False)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")
        mock_popen = mocker.patch("subprocess.Popen")
        mock_popen.return_value = MagicMock()
        mocker.patch("threading.Thread")

        launcher = MacOSLauncher(terminal="iTerm2")
        options = _make_options()

        launcher.launch(options)

        captured = capsys.readouterr()
        assert "iTerm2 API unavailable" not in captured.err


# ---------------------------------------------------------------------------
# _capture_window_id() — API window_id path
# ---------------------------------------------------------------------------


class TestCaptureWindowId:
    """Tests for MacOSLauncher._capture_window_id()."""

    def test_capture_window_id_returns_api_id_when_set(self) -> None:
        """_capture_window_id returns the stored API window_id when set."""
        launcher = MacOSLauncher(terminal="iTerm2")
        launcher._last_api_window_id = "w1234-uuid"

        result = launcher._capture_window_id()

        assert result == "w1234-uuid"

    def test_capture_window_id_clears_stored_id_after_return(self) -> None:
        """_capture_window_id consumes the stored API window_id (sets it to None)."""
        launcher = MacOSLauncher(terminal="iTerm2")
        launcher._last_api_window_id = "w1234-uuid"

        launcher._capture_window_id()

        assert launcher._last_api_window_id is None

    def test_capture_window_id_falls_back_to_applescript_when_no_api_id(
        self, mocker: Mock
    ) -> None:
        """_capture_window_id calls osascript fallback when _last_api_window_id is None."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(returncode=0, stdout="12345\n")
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")

        launcher = MacOSLauncher(terminal="iTerm2")
        # _last_api_window_id is None by default

        result = launcher._capture_window_id()

        assert result == "12345"
        mock_run.assert_called_once()


# ---------------------------------------------------------------------------
# _window_exists_by_id() — API dispatch vs. AppleScript fallback
# ---------------------------------------------------------------------------


class TestWindowExistsById:
    """Tests for MacOSLauncher._window_exists_by_id()."""

    def test_window_exists_by_id_uses_api_when_available(self, mocker: Mock) -> None:
        """_window_exists_by_id uses the Python API path when API returns a result."""
        mocker.patch.object(
            MacOSLauncher, "_window_exists_by_id_api", return_value=True
        )
        mock_run = mocker.patch("subprocess.run")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher._window_exists_by_id("w1234-uuid")

        assert result is True
        mock_run.assert_not_called()

    def test_window_exists_by_id_api_returns_false_when_window_missing(
        self, mocker: Mock
    ) -> None:
        """_window_exists_by_id returns False when API says window doesn't exist."""
        mocker.patch.object(
            MacOSLauncher, "_window_exists_by_id_api", return_value=False
        )
        mock_run = mocker.patch("subprocess.run")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher._window_exists_by_id("w-nonexistent")

        assert result is False
        mock_run.assert_not_called()

    def test_window_exists_by_id_falls_back_to_applescript_when_api_returns_none(
        self, mocker: Mock
    ) -> None:
        """_window_exists_by_id falls back to AppleScript when API returns None (unavailable)."""
        mocker.patch.object(
            MacOSLauncher, "_window_exists_by_id_api", return_value=None
        )
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(stdout="true\n", returncode=0)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher._window_exists_by_id("12345")

        assert result is True
        mock_run.assert_called_once()

    def test_window_exists_by_id_terminal_app_uses_applescript_only(
        self, mocker: Mock
    ) -> None:
        """_window_exists_by_id does not call the Python API for Terminal.app."""
        mock_api = mocker.patch.object(MacOSLauncher, "_window_exists_by_id_api")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(stdout="false\n", returncode=0)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")

        launcher = MacOSLauncher(terminal="Terminal.app")

        result = launcher._window_exists_by_id("12345")

        assert result is False
        mock_api.assert_not_called()


# ---------------------------------------------------------------------------
# focus_window_by_id() — API dispatch vs. AppleScript fallback
# ---------------------------------------------------------------------------


class TestFocusWindowById:
    """Tests for MacOSLauncher.focus_window_by_id()."""

    def test_focus_window_by_id_uses_api_when_available(self, mocker: Mock) -> None:
        """focus_window_by_id returns True using Python API when window found via API."""
        mocker.patch.object(
            MacOSLauncher, "_focus_window_by_id_api", return_value=True
        )
        mock_run = mocker.patch("subprocess.run")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher.focus_window_by_id("w1234-uuid")

        assert result is True
        mock_run.assert_not_called()

    def test_focus_window_by_id_api_returns_false_when_not_found(
        self, mocker: Mock
    ) -> None:
        """focus_window_by_id returns False without osascript when API says window missing."""
        mocker.patch.object(
            MacOSLauncher, "_focus_window_by_id_api", return_value=False
        )
        mock_run = mocker.patch("subprocess.run")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher.focus_window_by_id("w-nonexistent")

        assert result is False
        mock_run.assert_not_called()

    def test_focus_window_by_id_falls_back_to_applescript_when_api_returns_none(
        self, mocker: Mock
    ) -> None:
        """focus_window_by_id falls back to AppleScript when API returns None."""
        mocker.patch.object(
            MacOSLauncher, "_focus_window_by_id_api", return_value=None
        )
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(stdout="true\n", returncode=0)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")

        launcher = MacOSLauncher(terminal="iTerm2")

        result = launcher.focus_window_by_id("12345")

        assert result is True
        mock_run.assert_called_once()

    def test_focus_window_by_id_terminal_app_uses_applescript_only(
        self, mocker: Mock
    ) -> None:
        """focus_window_by_id does not call the Python API for Terminal.app."""
        mock_api = mocker.patch.object(MacOSLauncher, "_focus_window_by_id_api")
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = Mock(stdout="false\n", returncode=0)
        mocker.patch("shutil.which", return_value="/usr/bin/osascript")

        launcher = MacOSLauncher(terminal="Terminal.app")

        result = launcher.focus_window_by_id("12345")

        assert result is False
        mock_api.assert_not_called()


# ---------------------------------------------------------------------------
# _should_show_iterm2_fallback_notice / _record_iterm2_fallback_notice
# ---------------------------------------------------------------------------


class TestFallbackNoticeSentinel:
    """Tests for fallback notice sentinel file logic."""

    @pytest.fixture(autouse=True)
    def patch_sentinel(  # noqa: E501
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> Generator[Path, None, None]:
        """Redirect _ITERM2_FALLBACK_SENTINEL to a tmp_path file for isolation."""
        sentinel = tmp_path / "iterm2_fallback_notice_date"
        monkeypatch.setattr("mc.terminal.macos._ITERM2_FALLBACK_SENTINEL", sentinel)
        yield sentinel

    def test_should_show_returns_true_when_sentinel_missing(
        self, patch_sentinel: Path
    ) -> None:
        """_should_show_iterm2_fallback_notice returns True when sentinel file does not exist."""
        assert not patch_sentinel.exists()

        result = _should_show_iterm2_fallback_notice()

        assert result is True

    def test_should_show_returns_false_after_record_same_day(
        self, patch_sentinel: Path
    ) -> None:
        """After _record_iterm2_fallback_notice, _should_show returns False on same calendar day."""
        _record_iterm2_fallback_notice()

        result = _should_show_iterm2_fallback_notice()

        assert result is False

    def test_should_show_returns_true_when_sentinel_has_old_date(
        self, patch_sentinel: Path
    ) -> None:
        """_should_show_iterm2_fallback_notice returns True when sentinel contains a past date."""
        patch_sentinel.parent.mkdir(parents=True, exist_ok=True)
        patch_sentinel.write_text("2020-01-01")

        result = _should_show_iterm2_fallback_notice()

        assert result is True

    def test_record_writes_todays_date(self, patch_sentinel: Path) -> None:
        """_record_iterm2_fallback_notice writes today's ISO date to the sentinel file."""
        _record_iterm2_fallback_notice()

        content = patch_sentinel.read_text().strip()
        assert content == datetime.date.today().isoformat()
