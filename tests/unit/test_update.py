"""Unit tests for mc.update module (mc-update entry point).

Tests cover:
- _run_upgrade(): happy path, non-zero exit, uv not found
- _verify_mc_version(): success, non-zero exit, mc not found
- upgrade(): agent mode guard, happy path, uv failure recovery, verify failure recovery
- pin(): valid pin success, invalid version format, version not found, GitHub unreachable, agent mode
- unpin(): no active pin (no-op), active pin removed, agent mode block
- check(): all fields present, pin active display, up-to-date, GitHub unreachable, agent mode
- main(): no-args prints help, upgrade/pin/unpin/check subcommand dispatch
"""

import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

from mc.update import (
    _print_recovery_instructions,
    _run_upgrade,
    _verify_mc_version,
    check,
    main,
    pin,
    unpin,
    upgrade,
)


class TestRunUpgrade:
    """Tests for _run_upgrade()."""

    def test_run_upgrade_success(self) -> None:
        """Test that _run_upgrade returns 0 when uv tool upgrade mc exits 0."""
        with patch("mc.update.subprocess.run", return_value=MagicMock(returncode=0)):
            assert _run_upgrade() == 0

    def test_run_upgrade_nonzero_exit(self) -> None:
        """Test that _run_upgrade returns 1 when uv tool upgrade mc exits non-zero."""
        with patch("mc.update.subprocess.run", return_value=MagicMock(returncode=1)):
            assert _run_upgrade() == 1

    def test_run_upgrade_uv_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that _run_upgrade returns 1 and prints error when uv is not on PATH."""
        with patch("mc.update.subprocess.run", side_effect=FileNotFoundError):
            result = _run_upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "uv not found" in captured.err

    def test_run_upgrade_uses_list_form_not_shell(self) -> None:
        """Test that _run_upgrade invokes subprocess with list form and never shell=True.

        Security requirement: subprocess must never use shell=True to prevent shell injection.
        The exact command list must be ['uv', 'tool', 'upgrade', 'mc'].
        """
        with patch("mc.update.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run:
            _run_upgrade()
        assert mock_run.call_args[0][0] == ["uv", "tool", "upgrade", "mc"]
        assert mock_run.call_args.kwargs.get("shell", False) is False


class TestVerifyMcVersion:
    """Tests for _verify_mc_version()."""

    def test_verify_success_prints_version(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that _verify_mc_version returns True and prints version on success."""
        with patch(
            "mc.update.subprocess.run",
            return_value=MagicMock(returncode=0, stdout="mc 2.0.5\n"),
        ):
            result = _verify_mc_version()
        assert result is True
        captured = capsys.readouterr()
        assert "mc 2.0.5" in captured.out

    def test_verify_nonzero_returns_false(self) -> None:
        """Test that _verify_mc_version returns False when mc --version exits non-zero."""
        with patch("mc.update.subprocess.run", return_value=MagicMock(returncode=1, stdout="")):
            result = _verify_mc_version()
        assert result is False

    def test_verify_mc_not_found(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that _verify_mc_version returns False and prints error when mc is not on PATH."""
        with patch("mc.update.subprocess.run", side_effect=FileNotFoundError):
            result = _verify_mc_version()
        assert result is False
        captured = capsys.readouterr()
        assert "mc not found on PATH" in captured.err

    def test_verify_mc_not_found_stderr_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test the exact user-facing error message when mc is absent from PATH post-upgrade.

        RESEARCH Pitfall 2: mc disappears from PATH after uv tool upgrade. The error message
        must be actionable — telling the user exactly what to check.
        """
        with patch("mc.update.subprocess.run", side_effect=FileNotFoundError):
            result = _verify_mc_version()
        assert result is False
        captured = capsys.readouterr()
        assert "mc not found on PATH" in captured.err


class TestUpgrade:
    """Tests for upgrade()."""

    def test_upgrade_blocked_in_agent_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that upgrade() returns 1 immediately when running in agent mode."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "agent mode" in captured.err

    def test_upgrade_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that upgrade() returns 0 and prints 'Upgrade complete' on happy path."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # uv tool upgrade mc
                MagicMock(returncode=0, stdout="mc 2.0.5\n"),  # mc --version
            ]
            result = upgrade()
        assert result == 0
        captured = capsys.readouterr()
        assert "Upgrade complete" in captured.out

    def test_upgrade_uv_fails_shows_recovery(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that upgrade() returns 1 and prints recovery instructions when uv fails."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update.subprocess.run", return_value=MagicMock(returncode=1)):
            result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "uv tool install --force mc" in captured.err

    def test_upgrade_verify_fails_shows_recovery(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test upgrade() returns 1 with recovery instructions when mc --version fails."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # uv tool upgrade mc succeeds
                MagicMock(returncode=1, stdout=""),  # mc --version fails
            ]
            result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "uv tool install --force mc" in captured.err

    def test_upgrade_verify_step_fails_after_success(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test RESEARCH Pitfall 3: upgrade reports success but mc is broken post-upgrade.

        uv tool upgrade exits 0 (reported success) but mc --version then exits non-zero.
        The upgrade() function must return 1, print recovery instructions, and must NOT
        print 'Upgrade complete' — that message is only for true end-to-end success.
        """
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=0),  # uv tool upgrade mc succeeds
                MagicMock(returncode=1, stdout="error: something went wrong\n"),  # mc --version fails  # noqa: E501
            ]
            result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "uv tool install --force mc" in captured.err
        assert "Upgrade complete" not in captured.out

    def test_upgrade_agent_mode_does_not_call_uv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that agent mode guard fires before any subprocess call.

        No uv subprocess must be invoked when running in agent mode. The guard
        must short-circuit the entire upgrade flow.
        """
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        with patch("mc.update.subprocess.run") as mock_run:
            result = upgrade()
        assert result == 1
        assert mock_run.call_count == 0

    def test_upgrade_blocked_when_pinned(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that upgrade() returns 1 and prints pin message when a version pin is active.

        No subprocess (uv) must be called when a pin is active — the pin guard must
        short-circuit before any upgrade attempt.
        """
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "2.0.3",
            "last_check": None,
        }
        with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
            with patch("mc.update.subprocess.run") as mock_subprocess:
                result = upgrade()
        assert result == 1
        captured = capsys.readouterr()
        assert "Version pinned to 2.0.3" in captured.err
        assert "mc-update unpin" in captured.err
        assert mock_subprocess.call_count == 0


class TestPrintRecoveryInstructions:
    """Tests for _print_recovery_instructions()."""

    def test_recovery_instructions_content(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that recovery instructions contain the exact actionable command.

        UPDATE-03 requirement: failure output must include 'uv tool install --force mc'
        so the user has a clear, copy-pasteable recovery path.
        """
        _print_recovery_instructions()
        captured = capsys.readouterr()
        assert "uv tool install --force mc" in captured.err
        assert "To recover" in captured.err


class TestMain:
    """Tests for main() entry point."""

    def test_main_no_args_prints_help(self) -> None:
        """Test that main() with no args exits 0 (prints help)."""
        with patch.object(sys, "argv", ["mc-update"]):
            with pytest.raises(SystemExit) as exc_info:
                main()
        assert exc_info.value.code == 0

    def test_main_upgrade_calls_upgrade(self) -> None:
        """Test that 'mc-update upgrade' dispatches to upgrade() and exits with its return code."""
        with patch("mc.update.upgrade", return_value=0) as mock_upgrade:
            with patch.object(sys, "argv", ["mc-update", "upgrade"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        mock_upgrade.assert_called_once()

    def test_main_pin_calls_pin(self) -> None:
        """Test that 'mc-update pin 2.0.3' dispatches to pin() with the version argument."""
        with patch("mc.update.pin", return_value=0) as mock_pin:
            with patch.object(sys, "argv", ["mc-update", "pin", "2.0.3"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        mock_pin.assert_called_once_with("2.0.3")

    def test_main_unpin_calls_unpin(self) -> None:
        """Test that 'mc-update unpin' dispatches to unpin() and exits with its return code."""
        with patch("mc.update.unpin", return_value=0) as mock_unpin:
            with patch.object(sys, "argv", ["mc-update", "unpin"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        mock_unpin.assert_called_once()

    def test_main_check_calls_check(self) -> None:
        """Test that 'mc-update check' dispatches to check() and exits with its return code."""
        with patch("mc.update.check", return_value=0) as mock_check:
            with patch.object(sys, "argv", ["mc-update", "check"]):
                with pytest.raises(SystemExit) as exc_info:
                    main()
        assert exc_info.value.code == 0
        mock_check.assert_called_once()


class TestPin:
    """Tests for pin()."""

    def test_pin_blocked_in_agent_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() returns 1 immediately when running in agent mode."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        result = pin("2.0.3")
        assert result == 1
        captured = capsys.readouterr()
        assert "agent mode" in captured.err or "container image" in captured.err

    def test_pin_invalid_version_format_rejected(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() returns 1 and prints error for non-semver version strings."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update._validate_version_exists") as mock_validate:
            result = pin("not-a-version")
        assert result == 1
        captured = capsys.readouterr()
        assert "Invalid version format" in captured.err
        mock_validate.assert_not_called()

    def test_pin_invalid_version_with_v_prefix_stripped(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() strips leading 'v' before validation and writes bare semver to config."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.update_version_config = MagicMock()
        with patch("mc.update._validate_version_exists", return_value=True):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                result = pin("v2.0.3")
        assert result == 0
        mock_config_instance.update_version_config.assert_called_once_with(pinned_mc="2.0.3")
        captured = capsys.readouterr()
        assert "2.0.3" in captured.out

    def test_pin_version_not_found_on_github(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() returns 1 and prints error when version tag does not exist on GitHub."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch("mc.update._validate_version_exists", return_value=False):
            result = pin("9.9.9")
        assert result == 1
        captured = capsys.readouterr()
        assert "not found on GitHub" in captured.err

    def test_pin_github_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() returns 1 and prints error when GitHub API is unreachable."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        with patch(
            "mc.update._validate_version_exists",
            side_effect=requests.RequestException("timeout"),
        ):
            result = pin("2.0.3")
        assert result == 1
        captured = capsys.readouterr()
        assert "network unreachable" in captured.err

    def test_pin_success_writes_config(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that pin() writes pinned_mc to config and prints confirmation on success."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.update_version_config = MagicMock()
        with patch("mc.update._validate_version_exists", return_value=True):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                result = pin("2.0.3")
        assert result == 0
        mock_config_instance.update_version_config.assert_called_once_with(pinned_mc="2.0.3")
        captured = capsys.readouterr()
        assert "Pinned to 2.0.3" in captured.out
        assert "mc-update unpin" in captured.out


class TestUnpin:
    """Tests for unpin()."""

    def test_unpin_blocked_in_agent_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that unpin() returns 1 immediately when running in agent mode."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        result = unpin()
        assert result == 1
        captured = capsys.readouterr()
        assert "agent mode" in captured.err or "container image" in captured.err

    def test_unpin_no_active_pin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that unpin() returns 0 and prints 'No pin active.' when no pin is set.

        Does NOT call update_version_config — no write when there's nothing to remove.
        """
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
        }
        mock_config_instance.update_version_config = MagicMock()
        with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
            result = unpin()
        assert result == 0
        captured = capsys.readouterr()
        assert "No pin active." in captured.out
        mock_config_instance.update_version_config.assert_not_called()

    def test_unpin_removes_active_pin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that unpin() writes pinned_mc='latest' and prints 'Pin removed.' when pin active."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "2.0.3",
            "last_check": None,
        }
        mock_config_instance.update_version_config = MagicMock()
        with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
            result = unpin()
        assert result == 0
        mock_config_instance.update_version_config.assert_called_once_with(pinned_mc="latest")
        captured = capsys.readouterr()
        assert "Pin removed." in captured.out


class TestCheck:
    """Tests for check()."""

    def test_check_blocked_in_agent_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that check() returns 1 immediately when running in agent mode."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        result = check()
        assert result == 1
        captured = capsys.readouterr()
        assert "agent mode" in captured.err or "container image" in captured.err

    def test_check_all_fields_no_pin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that check() prints all four fields when GitHub reachable and no pin active."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
        }
        with patch("mc.update._fetch_latest_version", return_value="2.0.5"):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                with patch("mc.version.get_version", return_value="2.0.4"):
                    result = check()
        assert result == 0
        captured = capsys.readouterr()
        assert "Installed : 2.0.4" in captured.out
        assert "Latest    : 2.0.5" in captured.out
        assert "Pin       : none" in captured.out
        assert "Update    : available" in captured.out

    def test_check_with_active_pin(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that check() shows pin version and 'pinned' update status when pin is active."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "2.0.3",
            "last_check": None,
        }
        with patch("mc.update._fetch_latest_version", return_value="2.0.5"):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                with patch("mc.version.get_version", return_value="2.0.4"):
                    result = check()
        assert result == 0
        captured = capsys.readouterr()
        assert "Pin       : 2.0.3" in captured.out
        assert "Update    : pinned" in captured.out

    def test_check_up_to_date(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that check() shows 'up to date' when installed version equals latest."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
        }
        with patch("mc.update._fetch_latest_version", return_value="2.0.4"):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                with patch("mc.version.get_version", return_value="2.0.4"):
                    result = check()
        assert result == 0
        captured = capsys.readouterr()
        assert "Update    : up to date" in captured.out

    def test_check_github_unreachable(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that check() shows 'unavailable (network error)' and omits Update line on failure.

        When GitHub is unreachable (_fetch_latest_version returns None), the Update line
        must be omitted entirely — showing 'up to date' would be misleading.
        """
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        mock_config_instance = MagicMock()
        mock_config_instance.get_version_config.return_value = {
            "pinned_mc": "latest",
            "last_check": None,
        }
        with patch("mc.update._fetch_latest_version", return_value=None):
            with patch("mc.config.manager.ConfigManager", return_value=mock_config_instance):
                with patch("mc.version.get_version", return_value="2.0.4"):
                    result = check()
        assert result == 0
        captured = capsys.readouterr()
        assert "unavailable (network error)" in captured.out
        assert "Update" not in captured.out
