"""Configuration file manager for MC CLI."""

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w
from platformdirs import user_config_dir


class ConfigManager:
    """Manage application configuration file."""

    def __init__(self, app_name: str = "mc") -> None:
        """Initialize config manager.

        Args:
            app_name: Application name for config directory
        """
        self.app_name = app_name
        self._config_path: Path | None = None

    def get_config_path(self) -> Path:
        """Get config file path, creating directory if needed.

        Returns:
            Path to config file
        """
        if self._config_path is None:
            config_dir = Path(user_config_dir(self.app_name, appauthor=False))
            config_dir.mkdir(parents=True, exist_ok=True)
            self._config_path = config_dir / "config.toml"
        return self._config_path

    def exists(self) -> bool:
        """Check if config file exists.

        Returns:
            True if config file exists, False otherwise
        """
        return self.get_config_path().exists()

    def load(self) -> dict[str, Any]:
        """Load configuration from file.

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        config_path = self.get_config_path()
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "rb") as f:
            return tomllib.load(f)

    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dotted key path with default fallback.

        Args:
            key: Dotted key path (e.g., 'workspace.base_directory')
            default: Default value if key not found or config doesn't exist

        Returns:
            Config value or default

        Examples:
            >>> config.get('workspace.base_directory', '~/mc')
            '/Users/user/mc'
            >>> config.get('missing.key', 'fallback')
            'fallback'
        """
        try:
            config = self.load()
            keys = key.split('.')
            value = config
            for k in keys:
                value = value[k]
            return value
        except (FileNotFoundError, KeyError, TypeError):
            return default

    def save(self, config: dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save
        """
        config_path = self.get_config_path()
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
