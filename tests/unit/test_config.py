"""Tests for configuration system."""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from mc.config.manager import ConfigManager
from mc.config.models import get_default_config, validate_config
from mc.config.wizard import run_setup_wizard


class TestConfigManager:
    """Tests for ConfigManager class."""

    def test_get_config_path_returns_path(self):
        """Test that get_config_path returns a Path object with 'mc' in it."""
        manager = ConfigManager()
        config_path = manager.get_config_path()
        assert isinstance(config_path, Path)
        assert "mc" in str(config_path)

    def test_exists_returns_false_when_no_file(self, tmp_path):
        """Test that exists returns False when config file doesn't exist."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "nonexistent" / "config.toml"
        assert not manager.exists()

    def test_save_and_load_round_trip(self, tmp_path):
        """Test that config can be saved and loaded successfully."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        test_config = {
            "base_directory": "/test/path",
            "api": {
                "offline_token": "test_token_123"
            }
        }

        # Save config
        manager.save(test_config)

        # Verify file exists
        assert manager.exists()

        # Load config
        loaded_config = manager.load()

        # Verify contents match
        assert loaded_config == test_config

    def test_save_creates_directory(self, tmp_path):
        """Test that save creates parent directory if it doesn't exist."""
        manager = ConfigManager()
        config_path = tmp_path / "new_dir" / "config.toml"
        manager._config_path = config_path

        test_config = get_default_config()
        manager.save(test_config)

        assert config_path.exists()
        assert config_path.parent.is_dir()

    def test_load_raises_error_when_file_missing(self, tmp_path):
        """Test that load raises FileNotFoundError when config doesn't exist."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "missing.toml"

        with pytest.raises(FileNotFoundError):
            manager.load()


class TestConfigModels:
    """Tests for config models and validation."""

    def test_get_default_config_structure(self):
        """Test that default config has correct structure."""
        config = get_default_config()

        assert "base_directory" in config
        assert "api" in config
        assert "offline_token" in config["api"]

    def test_validate_config_accepts_valid_config(self):
        """Test that validation accepts valid config."""
        valid_config = {
            "base_directory": "~/mc",
            "api": {
                "offline_token": "test_token"
            }
        }

        assert validate_config(valid_config) is True

    def test_validate_config_rejects_missing_base_directory(self):
        """Test that validation rejects config without base_directory."""
        invalid_config = {
            "api": {
                "offline_token": "test_token"
            }
        }

        assert validate_config(invalid_config) is False

    def test_validate_config_rejects_missing_api(self):
        """Test that validation rejects config without api section."""
        invalid_config = {
            "base_directory": "~/mc"
        }

        assert validate_config(invalid_config) is False

    def test_validate_config_rejects_missing_offline_token(self):
        """Test that validation rejects config without offline_token."""
        invalid_config = {
            "base_directory": "~/mc",
            "api": {}
        }

        assert validate_config(invalid_config) is False

    def test_validate_config_rejects_non_dict(self):
        """Test that validation rejects non-dictionary input."""
        assert validate_config("not a dict") is False
        assert validate_config(None) is False
        assert validate_config([]) is False


class TestConfigWizard:
    """Tests for interactive configuration wizard."""

    def test_wizard_with_defaults(self, monkeypatch):
        """Test wizard uses defaults when user input is empty."""
        # Mock input to return empty string for base_dir, token for offline_token
        inputs = iter(["", "test_offline_token_123"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert "base_directory" in config
        assert "mc" in config["base_directory"]
        assert config["api"]["offline_token"] == "test_offline_token_123"

    def test_wizard_with_custom_values(self, monkeypatch):
        """Test wizard uses custom values when provided."""
        inputs = iter(["/custom/path", "custom_token_456"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert config["base_directory"] == "/custom/path"
        assert config["api"]["offline_token"] == "custom_token_456"

    def test_wizard_requires_offline_token(self, monkeypatch):
        """Test wizard loops until offline_token is provided."""
        # First two attempts are empty, third is valid
        inputs = iter(["", "", "", "finally_a_token"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert config["api"]["offline_token"] == "finally_a_token"


class TestLegacyEnvVarDetection:
    """Tests for legacy environment variable detection."""

    def test_no_legacy_vars_passes(self, monkeypatch):
        """Test that check passes when no legacy vars are set."""
        from mc.cli.main import check_legacy_env_vars

        # Ensure no legacy vars
        monkeypatch.delenv("MC_BASE_DIR", raising=False)
        monkeypatch.delenv("RH_API_OFFLINE_TOKEN", raising=False)

        # Should not raise SystemExit
        check_legacy_env_vars()

    def test_legacy_base_dir_detected_bash(self, monkeypatch, capsys):
        """Test detection of MC_BASE_DIR with bash shell."""
        from mc.cli.main import check_legacy_env_vars

        monkeypatch.setenv("MC_BASE_DIR", "/old/path")
        monkeypatch.setenv("SHELL", "/bin/bash")

        with pytest.raises(SystemExit) as exc_info:
            check_legacy_env_vars()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "Legacy environment variables detected" in captured.out
        assert "MC_BASE_DIR" in captured.out
        assert "unset MC_BASE_DIR" in captured.out

    def test_legacy_token_detected_bash(self, monkeypatch, capsys):
        """Test detection of RH_API_OFFLINE_TOKEN with bash shell."""
        from mc.cli.main import check_legacy_env_vars

        monkeypatch.setenv("RH_API_OFFLINE_TOKEN", "old_token")
        monkeypatch.setenv("SHELL", "/bin/bash")

        with pytest.raises(SystemExit) as exc_info:
            check_legacy_env_vars()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "RH_API_OFFLINE_TOKEN" in captured.out
        assert "unset RH_API_OFFLINE_TOKEN" in captured.out

    def test_legacy_vars_detected_fish(self, monkeypatch, capsys):
        """Test detection with fish shell generates correct commands."""
        from mc.cli.main import check_legacy_env_vars

        monkeypatch.setenv("MC_BASE_DIR", "/old/path")
        monkeypatch.setenv("SHELL", "/usr/bin/fish")

        with pytest.raises(SystemExit) as exc_info:
            check_legacy_env_vars()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "set -e MC_BASE_DIR" in captured.out
        assert "unset" not in captured.out

    def test_multiple_legacy_vars_detected(self, monkeypatch, capsys):
        """Test detection of multiple legacy variables."""
        from mc.cli.main import check_legacy_env_vars

        monkeypatch.setenv("MC_BASE_DIR", "/old/path")
        monkeypatch.setenv("RH_API_OFFLINE_TOKEN", "old_token")
        monkeypatch.setenv("SHELL", "/bin/bash")

        with pytest.raises(SystemExit) as exc_info:
            check_legacy_env_vars()

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "MC_BASE_DIR" in captured.out
        assert "RH_API_OFFLINE_TOKEN" in captured.out
        assert "unset MC_BASE_DIR" in captured.out
        assert "unset RH_API_OFFLINE_TOKEN" in captured.out
