"""Tests for configuration system."""

import os
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
        assert version_config['last_failed_fetch'] is None

    def test_get_version_config_returns_stored_values(self, tmp_path):
        """Test get_version_config returns stored values from file."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Save config with version section using ISO datetime string
        config = get_default_config()
        config['version']['pinned_mc'] = "2.0.4"
        config['version']['last_failed_fetch'] = "2024-05-20T14:30:00"
        manager.save(config)

        # Load version config
        version_config = manager.get_version_config()

        assert version_config['pinned_mc'] == "2.0.4"
        assert version_config['last_failed_fetch'] == "2024-05-20T14:30:00"

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
        iso_ts = "2026-05-20T14:30:00"
        manager.update_version_config(pinned_mc="2.0.4", last_failed_fetch=iso_ts)

        # Verify [version] section exists with correct values
        loaded_config = manager.load()
        assert 'version' in loaded_config
        assert loaded_config['version']['pinned_mc'] == "2.0.4"
        assert loaded_config['version']['last_failed_fetch'] == iso_ts

    def test_update_version_config_partial_update_preserves_fields(self, tmp_path):
        """Test update_version_config partial update preserves other fields."""
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Create config with version fields set
        config = get_default_config()
        config['version']['pinned_mc'] = "2.0.3"
        config['version']['last_failed_fetch'] = "2024-05-20T14:30:00"
        manager.save(config)

        # Update only pinned_mc
        manager.update_version_config(pinned_mc="2.0.5")

        # Verify pinned_mc changed but last_failed_fetch preserved
        loaded_config = manager.load()
        assert loaded_config['version']['pinned_mc'] == "2.0.5"
        assert loaded_config['version']['last_failed_fetch'] == "2024-05-20T14:30:00"

    def test_update_version_config_strips_stale_version_check_keys(self, tmp_path):
        """Test update_version_config removes stale last_check/last_status_code from config.

        These keys were written by the now-dead version_check.py VersionChecker.
        update_version_config() must clean them up when it next writes the config.
        """
        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Simulate old config with stale keys from version_check.py
        config = get_default_config()
        config['version']['last_check'] = 1773291771.0
        config['version']['last_status_code'] = 404
        manager.save(config)

        # Trigger any update — stale keys should be removed
        manager.update_version_config(pinned_mc="latest")

        loaded_config = manager.load()
        assert 'last_check' not in loaded_config['version']
        assert 'last_status_code' not in loaded_config['version']

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


class TestConfigManagerAgentBaseDir:
    """Tests for agent-mode base_directory override in ConfigManager.load()."""

    @pytest.mark.backwards_compatibility
    def test_load_overrides_base_directory_in_agent_mode(self, tmp_path, monkeypatch):
        """When MC_RUNTIME_MODE=agent, load() must override base_directory to ~/mc.

        Bug: config.toml is mounted from the host into the container with
        base_directory set to the host path (e.g. /Users/dsquirre/mc). Agent-mode
        code that reads base_directory gets a path that does not exist inside the
        container.

        Expected: In agent mode, base_directory in the returned config dict is
                  os.path.expanduser('~/mc'), regardless of the TOML value.
        Actual (before fix): base_directory is the verbatim host path from config.toml.
        """
        monkeypatch.setenv("MC_RUNTIME_MODE", "agent")
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        # Write config with a host-specific base_directory that won't exist in container
        host_path = "/Users/hostuser/mc"
        test_config = {
            "base_directory": host_path,
            "api": {
                "rh_api_offline_token": "test_token"
            },
        }
        manager.save(test_config)

        loaded_config = manager.load()

        # In agent mode, base_directory must be overridden to ~/mc (container path)
        expected_base_dir = os.path.expanduser("~/mc")
        assert loaded_config["base_directory"] == expected_base_dir, (
            f"In agent mode, base_directory should be '{expected_base_dir}' "
            f"but got '{loaded_config['base_directory']}'. "
            f"The host path leaked through config.toml without override."
        )

    @pytest.mark.backwards_compatibility
    def test_load_preserves_base_directory_in_controller_mode(self, tmp_path, monkeypatch):
        """When MC_RUNTIME_MODE=controller, load() must NOT override base_directory.

        This ensures the agent-mode override does not affect normal host operation.
        """
        monkeypatch.setenv("MC_RUNTIME_MODE", "controller")
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        custom_path = "/custom/host/path"
        test_config = {
            "base_directory": custom_path,
            "api": {
                "rh_api_offline_token": "test_token"
            },
        }
        manager.save(test_config)

        loaded_config = manager.load()

        assert loaded_config["base_directory"] == custom_path, (
            f"In controller mode, base_directory should be preserved as '{custom_path}' "
            f"but got '{loaded_config['base_directory']}'"
        )

    @pytest.mark.backwards_compatibility
    def test_load_preserves_base_directory_when_runtime_mode_unset(
        self, tmp_path, monkeypatch
    ):
        """When MC_RUNTIME_MODE is not set, load() must NOT override base_directory.

        Default mode is controller — base_directory should be preserved.
        """
        monkeypatch.delenv("MC_RUNTIME_MODE", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        manager._config_path = tmp_path / "config.toml"

        custom_path = "/custom/host/path"
        test_config = {
            "base_directory": custom_path,
            "api": {
                "rh_api_offline_token": "test_token"
            },
        }
        manager.save(test_config)

        loaded_config = manager.load()

        assert loaded_config["base_directory"] == custom_path, (
            f"When MC_RUNTIME_MODE is unset, base_directory should be preserved "
            f"as '{custom_path}' but got '{loaded_config['base_directory']}'"
        )


class TestConfigManagerEnvIsolation:
    """Tests for MC_ENV-based path isolation in ConfigManager."""

    @pytest.mark.backwards_compatibility
    def test_get_config_path_mc_env_set_returns_env_specific_path(self, tmp_path, monkeypatch):
        """When MC_ENV is set, get_config_path() must NOT return the production path.

        Bug: ConfigManager.get_config_path() always resolved to ~/mc/config/config.toml
        regardless of MC_ENV, causing UAT and production runs to share the same config.

        Expected: MC_ENV=uat → ~/mc-uat/config/config.toml (not ~/mc/config/config.toml)
        """
        monkeypatch.setenv("MC_ENV", "uat")
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        config_path = manager.get_config_path()

        production_path = tmp_path / "mc" / "config" / "config.toml"
        assert str(config_path) != str(production_path), (
            f"Config path still resolves to production path {production_path} even when "
            f"MC_ENV=uat — environment-based path isolation is not implemented."
        )

    @pytest.mark.backwards_compatibility
    def test_get_config_path_mc_env_uat_uses_suffixed_dir(self, tmp_path, monkeypatch):
        """When MC_ENV=uat, get_config_path() must resolve to ~/mc-uat/config/config.toml."""
        monkeypatch.setenv("MC_ENV", "uat")
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        config_path = manager.get_config_path()

        expected_path = tmp_path / "mc-uat" / "config" / "config.toml"
        assert str(config_path) == str(expected_path), (
            f"Expected env-specific path {expected_path}, got {config_path}"
        )

    @pytest.mark.backwards_compatibility
    def test_get_config_path_no_mc_env_uses_production_path(self, tmp_path, monkeypatch):
        """When MC_ENV is not set, get_config_path() must still use ~/mc/config/config.toml."""
        monkeypatch.delenv("MC_ENV", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        manager = ConfigManager()
        config_path = manager.get_config_path()

        expected_path = tmp_path / "mc" / "config" / "config.toml"
        assert str(config_path) == str(expected_path), (
            f"Expected production path {expected_path}, got {config_path}"
        )
