"""Unit tests for mc.update module (mc-update entry point).

Tests cover:
- _run_upgrade(): happy path, non-zero exit, uv not found
- _verify_mc_version(): success, non-zero exit, mc not found
- upgrade(): agent mode guard, happy path, uv failure recovery, verify failure recovery
- main(): no-args prints help, upgrade subcommand dispatches to upgrade()
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

from mc.update import _print_recovery_instructions, _run_upgrade, _verify_mc_version, main, upgrade


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
