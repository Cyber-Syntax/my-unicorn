"""Backup service for managing AppImage backups following Single Responsibility Principle."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .logger import get_logger

logger = get_logger(__name__)


class BackupService:
    """Service responsible for creating and managing AppImage backups."""

    def __init__(self, config_manager, global_config):
        """Initialize backup service with dependencies.

        Args:
            config_manager: Configuration manager for app configs
            global_config: Global configuration dictionary

        """
        self.config_manager = config_manager
        self.global_config = global_config

    def create_backup(
        self, file_path: Path, backup_dir: Path, version: str | None = None
    ) -> Path | None:
        """Create backup of existing file.

        Args:
            file_path: Path to file to backup
            backup_dir: Directory to store backup
            version: Version string to include in backup name

        Returns:
            Path to backup file or None if no existing file

        """
        if not file_path.exists():
            return None

        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename
        stem = file_path.stem
        suffix = file_path.suffix
        version_str = f"-{version}" if version else ""
        backup_name = f"{stem}{version_str}.backup{suffix}"
        backup_path = backup_dir / backup_name

        # Copy file to backup location
        shutil.copy2(file_path, backup_path)

        logger.debug(f"💾 Backup created: {backup_path}")
        return backup_path

    def cleanup_old_backups(self, app_name: str | None = None) -> None:
        """Clean up old backup files.

        Args:
            app_name: Specific app to clean up, or None for all apps

        """
        backup_dir = self.global_config["directory"]["backup"]
        max_backups = self.global_config["max_backup"]

        if not backup_dir.exists():
            return

        if app_name:
            app_configs = [self.config_manager.load_app_config(app_name)]
        else:
            installed_apps = self.config_manager.list_installed_apps()
            app_configs = [self.config_manager.load_app_config(app) for app in installed_apps]

        for app_config in app_configs:
            if not app_config:
                continue

            # Use the actual AppImage name (without extension) instead of repo name
            appimage_name = app_config["appimage"]["name"]
            # Remove .AppImage extension to get the base name for backup matching
            if appimage_name.lower().endswith(".appimage"):
                base_name = appimage_name[:-9]  # Remove .AppImage
            else:
                base_name = Path(appimage_name).stem

            app_backups = []

            # Find all backup files for this app using the actual AppImage base name
            for backup_file in backup_dir.glob(f"{base_name}*.backup.AppImage"):
                app_backups.append(backup_file)

            # Sort by modification time (newest first)
            app_backups.sort(key=lambda x: x.stat().st_mtime, reverse=True)

            # Handle max_backup=0 case: delete all backups
            if max_backups == 0:
                backups_to_remove = app_backups
            else:
                # Keep only the most recent max_backups files
                backups_to_remove = app_backups[max_backups:]

            # Remove excess backups
            for backup_file in backups_to_remove:
                try:
                    backup_file.unlink()
                    logger.info(f"Removed old backup: {backup_file}")
                except Exception as e:
                    logger.error(f"Failed to remove backup {backup_file}: {e}")

    def get_backup_info(self, app_name: str) -> list[dict[str, Any]]:
        """Get information about available backups for an app.

        Args:
            app_name: Name of the app

        Returns:
            List of backup information dictionaries

        """
        backup_dir = self.global_config["directory"]["backup"]
        backups = []

        if not backup_dir.exists():
            return backups

        # Load app config to get the actual AppImage name
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            return backups

        # Use the actual AppImage name (without extension) instead of repo name
        appimage_name = app_config["appimage"]["name"]
        # Remove .AppImage extension to get the base name for backup matching
        if appimage_name.lower().endswith(".appimage"):
            base_name = appimage_name[:-9]  # Remove .AppImage
        else:
            base_name = Path(appimage_name).stem

        for backup_file in backup_dir.glob(f"{base_name}*.backup.AppImage"):
            stat = backup_file.stat()
            backups.append(
                {
                    "path": backup_file,
                    "size": stat.st_size,
                    "created": datetime.fromtimestamp(stat.st_mtime),
                    "name": backup_file.name,
                }
            )

        # Sort by creation time (newest first)
        backups.sort(key=lambda x: x["created"], reverse=True)
        return backups
