"""Configuration file manager for MC CLI."""

import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

import tomli_w


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

        Uses consolidated ~/mc/config/ location. Auto-migrates from old
        platformdirs location on first access if needed.

        When MC_ENV is set, uses ~/mc-{MC_ENV}/config/ instead to isolate
        UAT and other environments from production state.

        Returns:
            Path to config file
        """
        if self._config_path is None:
            mc_env = os.environ.get("MC_ENV")
            dir_name = f"{self.app_name}-{mc_env}" if mc_env else self.app_name
            config_dir = Path.home() / dir_name / "config"
            self._config_path = config_dir / "config.toml"

            # Auto-migration: Move from old platformdirs location if needed
            if not self._config_path.exists():
                old_path = self._get_old_config_path()
                if old_path and old_path.exists():
                    config_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(old_path, self._config_path)
                    print(f"Migrated config from {old_path} to {self._config_path}")
                else:
                    # No old config, just ensure new directory exists
                    config_dir.mkdir(parents=True, exist_ok=True)

        return self._config_path

    def _get_old_config_path(self) -> Path | None:
        """Get old platformdirs config path for migration.

        Returns:
            Path to old config file, or None if not using old location
        """
        try:
            from platformdirs import user_config_dir
            old_dir = Path(user_config_dir(self.app_name, appauthor=False))
            return old_dir / "config.toml"
        except ImportError:
            return None

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

    def save_atomic(self, config: dict[str, Any]) -> None:
        """Save configuration to file atomically using temp file + rename pattern.

        This method ensures that the config file is never left in a partially written
        state, even if the process crashes or is interrupted during the write.

        Args:
            config: Configuration dictionary to save
        """
        config_path = self.get_config_path()
        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Create temp file in same directory (ensures same filesystem for atomic replace)
        temp = tempfile.NamedTemporaryFile(
            mode='wb',
            dir=config_path.parent,  # CRITICAL: same directory as target
            prefix='.config_',       # hidden temp file
            suffix='.tmp',
            delete=False             # manual cleanup for atomic rename
        )

        try:
            # Write config to temp file
            tomli_w.dump(config, temp)
            temp.flush()
            os.fsync(temp.fileno())  # Force write to disk (durability)
            temp.close()

            # Atomic replace: either complete success or complete failure
            os.replace(temp.name, config_path)
        except Exception:
            # Cleanup temp file on failure
            temp.close()
            try:
                os.unlink(temp.name)
            except OSError:
                pass  # Temp file already gone, ignore
            raise

    def get_version_config(self) -> dict[str, Any]:
        """Get version configuration with backward-compatible defaults.

        Returns dict with keys:
        - pinned_mc: Version string (default: "latest" if not set)
        - last_banner_shown: ISO 8601 datetime string or None if never shown
        - last_failed_fetch: Unix epoch timestamp (float) of last failed GitHub
          fetch, or None if no failure recorded

        Returns:
            Version configuration dictionary
        """
        return {
            'pinned_mc': self.get('version.pinned_mc', 'latest'),
            'last_banner_shown': self.get('version.last_banner_shown', None),
            'last_failed_fetch': self.get('version.last_failed_fetch', None),
        }

    def update_version_config(
        self,
        pinned_mc: str | None = None,
        last_banner_shown: str | None = None,
        last_failed_fetch: float | None = None,
    ) -> None:
        """Update version configuration fields atomically.

        Only updates fields that are specified (not None). Preserves other fields.
        Automatically removes stale keys (last_check, last_status_code) written
        by the now-dead version_check.py VersionChecker.

        Args:
            pinned_mc: Version string to pin to, or None to keep current
            last_banner_shown: ISO 8601 datetime string, or None to keep current
            last_failed_fetch: Unix epoch timestamp of last failed GitHub fetch,
                or None to keep current
        """
        # Load current config (or get defaults if missing)
        try:
            config = self.load()
        except FileNotFoundError:
            from mc.config.models import get_default_config
            config = get_default_config()

        # Ensure [version] section exists
        if 'version' not in config:
            config['version'] = {}

        # Remove stale keys written by the now-dead version_check.py VersionChecker
        config['version'].pop('last_check', None)
        config['version'].pop('last_status_code', None)

        # Update only specified fields
        if pinned_mc is not None:
            config['version']['pinned_mc'] = pinned_mc
        if last_banner_shown is not None:
            config['version']['last_banner_shown'] = last_banner_shown
        if last_failed_fetch is not None:
            config['version']['last_failed_fetch'] = last_failed_fetch

        # Save using atomic write for safety
        self.save_atomic(config)
