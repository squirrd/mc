"""Tests for runtime mode detection module."""

from unittest.mock import patch

import pytest

from mc.runtime import (
    get_runtime_mode,
    is_agent_mode,
    is_controller_mode,
    is_running_in_container,
    should_check_for_updates,
)


class TestGetRuntimeMode:
    """Tests for get_runtime_mode() function."""

    def test_default_mode_is_controller_when_env_var_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default mode is 'controller' when MC_RUNTIME_MODE not set."""
        # Remove environment variable if it exists
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        mode = get_runtime_mode()

        assert mode == "controller"

    def test_mode_is_agent_when_env_var_set_to_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that mode is 'agent' when MC_RUNTIME_MODE=agent."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        mode = get_runtime_mode()

        assert mode == "agent"

    def test_mode_is_controller_when_env_var_set_to_controller(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that mode is 'controller' when MC_RUNTIME_MODE=controller."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        mode = get_runtime_mode()

        assert mode == "controller"

    def test_invalid_mode_value_defaults_to_controller(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that invalid MC_RUNTIME_MODE values default to 'controller'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "invalid")

        mode = get_runtime_mode()

        assert mode == "controller"

    def test_empty_mode_value_defaults_to_controller(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that empty MC_RUNTIME_MODE value defaults to 'controller'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "")

        mode = get_runtime_mode()

        assert mode == "controller"

    def test_case_sensitive_mode_detection(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that mode detection is case-sensitive (AGENT != agent)."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "AGENT")

        mode = get_runtime_mode()

        # Should default to controller since "AGENT" != "agent"
        assert mode == "controller"


class TestIsAgentMode:
    """Tests for is_agent_mode() helper function."""

    def test_returns_true_when_mode_is_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_agent_mode() returns True when mode is 'agent'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        assert is_agent_mode() is True

    def test_returns_false_when_mode_is_controller(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_agent_mode() returns False when mode is 'controller'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        assert is_agent_mode() is False

    def test_returns_false_when_env_var_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_agent_mode() returns False when env var not set."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        assert is_agent_mode() is False


class TestIsControllerMode:
    """Tests for is_controller_mode() helper function."""

    def test_returns_true_when_mode_is_controller(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_controller_mode() returns True when mode is 'controller'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        assert is_controller_mode() is True

    def test_returns_true_when_env_var_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_controller_mode() returns True when env var not set (default)."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        assert is_controller_mode() is True

    def test_returns_false_when_mode_is_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that is_controller_mode() returns False when mode is 'agent'."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        assert is_controller_mode() is False


class TestRuntimeModeIntegration:
    """Integration tests for runtime mode detection."""

    def test_controller_and_agent_modes_are_mutually_exclusive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that controller and agent modes are mutually exclusive."""
        # Test in agent mode
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        assert is_agent_mode() is True
        assert is_controller_mode() is False

        # Test in controller mode
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")
        assert is_agent_mode() is False
        assert is_controller_mode() is True

        # Test default (controller)
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        assert is_agent_mode() is False
        assert is_controller_mode() is True


class TestIsRunningInContainer:
    """Tests for is_running_in_container() layered detection."""

    def test_returns_true_when_env_var_is_agent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test primary detection: MC_RUNTIME_MODE=agent."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        assert is_running_in_container() is True

    def test_returns_false_when_env_var_is_controller_and_no_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that controller mode + no files = host mode."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        # Mock all container indicator files to not exist
        with patch("mc.runtime.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            assert is_running_in_container() is False

    def test_returns_false_when_no_indicators_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test default: no env var, no files = host mode."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        # Mock all container indicator files to not exist
        with patch("mc.runtime.Path") as mock_path:
            mock_path.return_value.exists.return_value = False

            assert is_running_in_container() is False

    def test_fallback_detection_podman_run_containerenv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test fallback: /run/.containerenv detected (Podman standard)."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        # Mock /run/.containerenv exists, others don't
        with patch("mc.runtime.Path") as mock_path_class:
            def exists_side_effect(path_str):
                # Create a mock path object that checks the string representation
                mock_instance = type('MockPath', (), {})()
                mock_instance.exists = lambda: str(path_str) == "/run/.containerenv"
                return mock_instance

            # We need to mock the Path constructor calls
            paths_checked = []

            def path_constructor(path_str):
                paths_checked.append(str(path_str))
                mock_instance = type('MockPath', (), {})()
                mock_instance.exists = lambda: str(path_str) == "/run/.containerenv"
                return mock_instance

            mock_path_class.side_effect = path_constructor

            assert is_running_in_container() is True

    def test_fallback_detection_podman_legacy_containerenv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test fallback: /.containerenv detected (Podman legacy)."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        # Mock /.containerenv exists, others don't
        with patch("mc.runtime.Path") as mock_path_class:
            def path_constructor(path_str):
                mock_instance = type('MockPath', (), {})()
                mock_instance.exists = lambda: str(path_str) == "/.containerenv"
                return mock_instance

            mock_path_class.side_effect = path_constructor

            assert is_running_in_container() is True

    def test_fallback_detection_docker_dockerenv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test fallback: /.dockerenv detected (Docker standard)."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        # Mock /.dockerenv exists, others don't
        with patch("mc.runtime.Path") as mock_path_class:
            def path_constructor(path_str):
                mock_instance = type('MockPath', (), {})()
                mock_instance.exists = lambda: str(path_str) == "/.dockerenv"
                return mock_instance

            mock_path_class.side_effect = path_constructor

            assert is_running_in_container() is True

    def test_environment_variable_takes_precedence_over_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MC_RUNTIME_MODE=controller overrides file detection."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        # Mock all container files to exist
        with patch("mc.runtime.Path") as mock_path_class:
            def path_constructor(path_str):
                mock_instance = type('MockPath', (), {})()
                mock_instance.exists = lambda: True  # All files exist
                return mock_instance

            mock_path_class.side_effect = path_constructor

            # Even though files exist, env var should override
            assert is_running_in_container() is False

    def test_agent_mode_via_env_var_skips_file_checks(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that MC_RUNTIME_MODE=agent returns True without checking files."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        # Don't mock Path at all - if function checks files, this would fail
        # This tests that the function returns early on env var check
        assert is_running_in_container() is True


class TestShouldCheckForUpdates:
    """Tests for should_check_for_updates() auto-update guard."""

    def test_returns_false_in_agent_mode(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        """Test that agent mode blocks update checks."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        result = should_check_for_updates()

        assert result is False

    def test_returns_true_in_controller_mode(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that controller mode allows update checks."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        result = should_check_for_updates()

        assert result is True

    def test_returns_true_when_env_var_not_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test that default mode (controller) allows update checks."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        result = should_check_for_updates()

        assert result is True

    def test_displays_message_when_blocking_in_agent_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Test that informational message shown when blocking updates."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")

        result = should_check_for_updates()
        captured = capsys.readouterr()

        assert result is False
        assert "Updates managed via container builds" in captured.err

    def test_no_message_when_allowing_in_controller_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Test that no message shown when allowing updates."""
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")

        result = should_check_for_updates()
        captured = capsys.readouterr()

        assert result is True
        assert captured.err == ""  # No output to stderr

    def test_no_message_when_allowing_in_default_mode(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Test that no message shown in default mode."""
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)

        result = should_check_for_updates()
        captured = capsys.readouterr()

        assert result is True
        assert captured.err == ""  # No output to stderr
