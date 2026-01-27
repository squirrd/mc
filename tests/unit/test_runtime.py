"""Tests for runtime mode detection module."""

import pytest

from mc.runtime import get_runtime_mode, is_agent_mode, is_controller_mode


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
