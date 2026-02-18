"""BackupService for creating and managing AppImage backups.

This module provides the main service for:
- Creating versioned backups of AppImage files
- Querying backup information
- Cleaning up old backups
- Delegating restore operations to restore module
"""

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from my_unicorn.constants import BACKUP_TEMP_SUFFIX
from my_unicorn.core.backup.helpers import delete_old_backups
from my_unicorn.core.backup.metadata import BackupMetadata
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from my_unicorn.config.config import ConfigManager
    from my_unicorn.types import GlobalConfig

logger = get_logger(__name__)


class BackupService:
    """Enhanced service for creating and managing AppImage backups.

    Provides versioning, metadata tracking, and restore capabilities.
    """

    def __init__(
        self,
        config_manager: "ConfigManager",
        global_config: "GlobalConfig",
    ) -> None:
        """Initialize backup service with dependencies.

        Args:
            config_manager: Configuration manager for app configs
            global_config: Global configuration dictionary

        """
        self.config_manager = config_manager
        self.global_config = global_config

    @classmethod
    def create_default(
        cls, config_manager: "ConfigManager | None" = None
    ) -> "BackupService":
        """Create BackupService with default dependencies.

        Factory method for simplified instantiation with defaults.

        Args:
            config_manager: Optional configuration manager
                (creates new if None)

        Returns:
            Configured BackupService instance

        """
        if config_manager is None:
            # Import here to avoid circular dependency
            from my_unicorn.config.config import ConfigManager  # noqa: PLC0415

            config_manager = ConfigManager()

        global_config = config_manager.load_global_config()

        return cls(
            config_manager=config_manager,
            global_config=global_config,
        )

    def create_backup(
        self,
        file_path: Path,
        app_name: str,
        version: str | None = None,
        *,
        skip_cleanup: bool = False,
    ) -> Path | None:
        """Create versioned backup of existing file.

        Args:
            file_path: Path to file to backup
            app_name: Name of the application
            version: Version string to include in backup name
            skip_cleanup: If True, skip cleanup of old backups (default: False)

        Returns:
            Path to backup file or None if no existing file

        """
        if not file_path.exists():
            return None

        # Create app-specific backup directory
        backup_base_dir = Path(self.global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name
        app_backup_dir.mkdir(parents=True, exist_ok=True)

        # Determine version
        if not version:
            app_config = self.config_manager.load_app_config(app_name)
            if app_config:
                # Check config version to determine structure
                config_version = app_config.get("config_version", "1.0.0")
                if config_version == "2.0.0":
                    # v2 config: version is in state section
                    state_dict = cast(
                        "dict[str, Any]", app_config.get("state", {})
                    )
                    version = state_dict.get("version", "unknown")
                else:
                    # v1 config: version is in appimage section
                    version = app_config.get("appimage", {}).get(
                        "version", "unknown"
                    )
            else:
                version = "unknown"

        # Create backup filename
        stem = file_path.stem
        suffix = file_path.suffix
        backup_filename = f"{stem}-{version}{suffix}"
        backup_path = app_backup_dir / backup_filename

        # Copy file to backup location atomically
        with tempfile.NamedTemporaryFile(
            dir=app_backup_dir,
            prefix=f".{backup_filename}_",
            suffix=BACKUP_TEMP_SUFFIX,
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)

        try:
            shutil.copy2(file_path, temp_path)
            temp_path.replace(backup_path)

            # Update metadata
            metadata = BackupMetadata(app_backup_dir)
            # Version should not be None at this point
            if version is None:
                msg = f"Version is None when creating backup for {app_name}"
                logger.error(msg)
                raise ValueError(msg)
            metadata.add_version(version, backup_filename, backup_path)

        except OSError:
            # Cleanup temp file on error
            if temp_path.exists():
                temp_path.unlink()
            logger.exception("Failed to create backup for %s", app_name)
            raise
        else:
            logger.info("Backup created: %s (v%s)", backup_path, version)

            # Cleanup old backups after successful backup (unless skipped)
            if not skip_cleanup:
                self._cleanup_old_backups_for_app(app_backup_dir)

            return backup_path

    def restore_latest_backup(
        self, app_name: str, destination_dir: Path
    ) -> Path | None:
        """Restore the latest backup version for an app.

        Args:
            app_name: Name of the application
            destination_dir: Directory to restore the backup to

        Returns:
            Path to restored file or None if no backup exists

        """
        # Import here to avoid circular dependency
        from my_unicorn.core.backup.restore import (  # noqa: PLC0415
            restore_latest_backup,
        )

        return restore_latest_backup(
            app_name, destination_dir, self.config_manager, self.global_config
        )

    def restore_specific_version(
        self, app_name: str, version: str, destination_dir: Path
    ) -> Path | None:
        """Restore a specific version backup for an app.

        Args:
            app_name: Name of the application
            version: Specific version to restore
            destination_dir: Directory to restore the backup to

        Returns:
            Path to restored file or None if backup doesn't exist

        """
        # Import here to avoid circular dependency
        from my_unicorn.core.backup.restore import (  # noqa: PLC0415
            restore_specific_version,
        )

        return restore_specific_version(
            app_name,
            version,
            destination_dir,
            self.config_manager,
            self.global_config,
        )

    def get_backup_info(self, app_name: str) -> list[dict[str, Any]]:
        """Get information about available backups for an app.

        Args:
            app_name: Name of the app

        Returns:
            List of backup information dictionaries sorted by version
            (newest first)

        """
        backup_base_dir = Path(self.global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name

        if not app_backup_dir.exists():
            return []

        metadata = BackupMetadata(app_backup_dir)
        versions = metadata.list_versions()

        backups = []
        for version in versions:
            version_info = metadata.get_version_info(version)
            if version_info:
                backup_path = app_backup_dir / version_info["filename"]
                backups.append(
                    {
                        "version": version,
                        "path": backup_path,
                        "filename": version_info["filename"],
                        "size": version_info.get("size", 0),
                        "created": datetime.fromisoformat(
                            version_info["created"]
                        )
                        if version_info.get("created")
                        else None,
                        "sha256": version_info.get("sha256"),
                        "exists": backup_path.exists(),
                    }
                )

        return backups

    def cleanup_old_backups(self, app_name: str | None = None) -> None:
        """Clean up old backup files according to max_backup setting.

        Args:
            app_name: Specific app to clean up, or None for all apps

        """
        backup_base_dir = Path(self.global_config["directory"]["backup"])

        if not backup_base_dir.exists():
            return

        if app_name:
            app_backup_dir = backup_base_dir / app_name
            if app_backup_dir.exists():
                self._cleanup_old_backups_for_app(app_backup_dir)
        else:
            # Clean up all apps
            for app_dir in backup_base_dir.iterdir():
                if app_dir.is_dir():
                    self._cleanup_old_backups_for_app(app_dir)

    def _cleanup_old_backups_for_app(self, app_backup_dir: Path) -> None:
        """Clean up old backups for a specific app.

        Args:
            app_backup_dir: Backup directory for the app

        """
        metadata = BackupMetadata(app_backup_dir)
        max_backups = self.global_config["max_backup"]

        if max_backups == 0:
            # Delete all backups
            versions = metadata.list_versions()
            delete_old_backups(versions, metadata, app_backup_dir)

            # Remove metadata file and directory if empty
            if metadata.metadata_file.exists():
                metadata.metadata_file.unlink()
            if not any(app_backup_dir.iterdir()):
                app_backup_dir.rmdir()
            return

        # Keep only the most recent max_backups versions
        versions = metadata.list_versions()  # Already sorted newest to oldest
        versions_to_remove = versions[max_backups:]
        delete_old_backups(versions_to_remove, metadata, app_backup_dir)

    def list_apps_with_backups(self) -> list[str]:
        """List all apps that have backups.

        Returns:
            List of app names that have backup directories

        """
        backup_base_dir = Path(self.global_config["directory"]["backup"])

        if not backup_base_dir.exists():
            return []

        apps = []
        for item in backup_base_dir.iterdir():
            if item.is_dir():
                # Check if directory has any backups
                metadata = BackupMetadata(item)
                if metadata.list_versions():
                    apps.append(item.name)

        return sorted(apps)
