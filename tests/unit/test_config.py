"""Tests for configuration system."""

import pytest
import sys
import time
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
        assert "rh_api_offline_token" in config["api"]

    def test_validate_config_accepts_valid_config(self):
        """Test that validation accepts valid config with new key."""
        valid_config = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            }
        }

        assert validate_config(valid_config) is True

    def test_validate_config_accepts_old_offline_token_key(self):
        """Test that validation accepts old offline_token key for backwards compatibility."""
        valid_config = {
            "base_directory": "~/mc",
            "api": {
                "offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
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
        """Test that validation rejects config without rh_api_offline_token or offline_token."""
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
        # Mock input to return empty string for base_dir, token for rh_api_offline_token
        inputs = iter(["", "test_offline_token_123"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert "base_directory" in config
        assert "mc" in config["base_directory"]
        assert config["api"]["rh_api_offline_token"] == "test_offline_token_123"

    def test_wizard_with_custom_values(self, monkeypatch):
        """Test wizard uses custom values when provided."""
        inputs = iter(["/custom/path", "custom_token_456"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert config["base_directory"] == "/custom/path"
        assert config["api"]["rh_api_offline_token"] == "custom_token_456"

    def test_wizard_requires_offline_token(self, monkeypatch):
        """Test wizard loops until rh_api_offline_token is provided."""
        # First two attempts are empty, third is valid
        inputs = iter(["", "", "", "finally_a_token"])
        monkeypatch.setattr('builtins.input', lambda _: next(inputs))

        config = run_setup_wizard()

        assert config["api"]["rh_api_offline_token"] == "finally_a_token"


class TestVersionConfig:
    """Tests for version config functionality."""

    def test_default_config_includes_version_section(self):
        """Test that default config includes version section with correct defaults."""
        config = get_default_config()

        assert 'version' in config
        assert config['version']['pinned_mc'] == 'latest'
        # last_check is omitted from default config (TOML doesn't support None)
        # The get_version_config() method provides None as default when missing
        assert 'last_check' not in config['version']

    def test_validate_config_accepts_version_section(self):
        """Test that validation accepts config with version section."""
        valid_config = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            },
            "version": {
                "pinned_mc": "2.0.4",
                "last_check": 1234567890.0
            }
        }

        assert validate_config(valid_config) is True

    def test_validate_config_accepts_missing_version_section(self):
        """Test that validation accepts config without version section (backward compatibility)."""
        valid_config = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            }
        }

        assert validate_config(valid_config) is True

    def test_validate_config_rejects_invalid_version_types(self):
        """Test that validation rejects invalid types for version fields."""
        # Test invalid pinned_mc type (should be string)
        invalid_config_pinned = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            },
            "version": {
                "pinned_mc": 123,  # Invalid: should be string
                "last_check": None
            }
        }

        assert validate_config(invalid_config_pinned) is False

        # Test invalid last_check type (should be float/int/None)
        invalid_config_check = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            },
            "version": {
                "pinned_mc": "latest",
                "last_check": "not_a_timestamp"  # Invalid: should be float/None
            }
        }

        assert validate_config(invalid_config_check) is False

    def test_get_version_config_returns_defaults_when_missing(self, tmp_path):
        """Test get_version_config returns defaults when config doesn't exist."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        version_config = manager.get_version_config()

        assert version_config['pinned_mc'] == 'latest'
        assert version_config['last_check'] is None

    def test_get_version_config_returns_stored_values(self, tmp_path):
        """Test get_version_config returns stored values from file."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Save config with version section
        config = get_default_config()
        config['version']['pinned_mc'] = "2.0.4"
        config['version']['last_check'] = 1234567890.0
        manager.save(config)

        # Load version config
        version_config = manager.get_version_config()

        assert version_config['pinned_mc'] == "2.0.4"
        assert version_config['last_check'] == 1234567890.0

    def test_update_version_config_creates_section_if_missing(self, tmp_path):
        """Test update_version_config creates [version] section if missing."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Create config without version section
        config = {
            "base_directory": "~/mc",
            "api": {
                "rh_api_offline_token": "test_token"
            },
            "salesforce": {
                "username": "",
                "password": "",
                "security_token": ""
            }
        }
        manager.save(config)

        # Update version config
        timestamp = time.time()
        manager.update_version_config(pinned_mc="2.0.4", last_check=timestamp)

        # Verify [version] section exists with correct values
        loaded_config = manager.load()
        assert 'version' in loaded_config
        assert loaded_config['version']['pinned_mc'] == "2.0.4"
        assert loaded_config['version']['last_check'] == timestamp

    def test_update_version_config_partial_update_preserves_fields(self, tmp_path):
        """Test update_version_config partial update preserves other fields."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Create config with both version fields set
        config = get_default_config()
        config['version']['pinned_mc'] = "2.0.3"
        config['version']['last_check'] = 1234567890.0
        manager.save(config)

        # Update only pinned_mc
        manager.update_version_config(pinned_mc="2.0.5")

        # Verify pinned_mc changed but last_check unchanged
        loaded_config = manager.load()
        assert loaded_config['version']['pinned_mc'] == "2.0.5"
        assert loaded_config['version']['last_check'] == 1234567890.0

    def test_save_atomic_creates_file(self, tmp_path):
        """Test save_atomic creates file with correct content."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        test_config = {'test': 'value'}
        manager.save_atomic(test_config)

        assert manager.exists()
        loaded_config = manager.load()
        assert loaded_config == test_config

    def test_save_atomic_no_temp_file_left_on_success(self, tmp_path):
        """Test save_atomic cleans up temp files after successful write."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        test_config = {'test': 'value'}
        manager.save_atomic(test_config)

        # List all files in directory
        files = list(tmp_path.iterdir())

        # Check no .config_*.tmp files exist
        temp_files = [f for f in files if f.name.startswith('.config_') and f.name.endswith('.tmp')]
        assert len(temp_files) == 0

    def test_save_atomic_overwrites_existing_file(self, tmp_path):
        """Test save_atomic atomically overwrites existing file."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Save initial config
        initial_config = {'initial': 'data'}
        manager.save_atomic(initial_config)

        # Overwrite with new config
        new_config = {'new': 'data'}
        manager.save_atomic(new_config)

        # Verify file content reflects new config
        loaded_config = manager.load()
        assert loaded_config == new_config
        assert 'initial' not in loaded_config
