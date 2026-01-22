"""Configuration file manager for MC CLI."""

import sys
from pathlib import Path
from typing import Dict, Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w
from platformdirs import user_config_dir


class ConfigManager:
    """Manage application configuration file."""

    def __init__(self, app_name: str = "mc"):
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

    def load(self) -> Dict[str, Any]:
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

    def save(self, config: Dict[str, Any]) -> None:
        """Save configuration to file.

        Args:
            config: Configuration dictionary to save
        """
        config_path = self.get_config_path()
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)
