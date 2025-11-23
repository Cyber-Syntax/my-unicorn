"""Enhanced backup service for managing AppImage backups with folder structure and versioning.

This module implements a robust backup system that:
- Uses folder-based structure for each app
- Maintains metadata.json files with version information and checksums
- Supports version comparison and restore functionality
- Provides migration from old flat backup structure
- Implements atomic operations and error handling
"""

import hashlib
import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from packaging.version import InvalidVersion, Version

from .constants import (
    APPIMAGE_SUFFIX,
    BACKUP_METADATA_CORRUPTED_SUFFIX,
    BACKUP_METADATA_FILENAME,
    BACKUP_METADATA_TMP_PREFIX,
    BACKUP_METADATA_TMP_SUFFIX,
    BACKUP_TEMP_SUFFIX,
    CONFIG_BACKUP_EXTENSION,
    OLD_FLAT_BACKUP_GLOB,
)
from .logger import get_logger

logger = get_logger(__name__)


class BackupMetadata:
    """Manages backup metadata for version tracking and integrity."""

    def __init__(self, backup_dir: Path):
        """Initialize metadata manager.

        Args:
            backup_dir: Directory containing app backups

        """
        self.backup_dir = backup_dir
        self.metadata_file = backup_dir / BACKUP_METADATA_FILENAME

    def load(self) -> dict[str, Any]:
        """Load metadata from file.

        Returns:
            Metadata dictionary with versions and file info

        """
        if not self.metadata_file.exists():
            return {"versions": {}}

        try:
            with open(self.metadata_file, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Corrupted metadata file %s: %s", self.metadata_file, e
            )
            # Create backup of corrupted file
            corrupted_backup = self.metadata_file.with_suffix(
                BACKUP_METADATA_CORRUPTED_SUFFIX
            )
            if self.metadata_file.exists():
                shutil.copy2(self.metadata_file, corrupted_backup)
                logger.info(
                    "Backed up corrupted metadata to %s", corrupted_backup
                )
            return {"versions": {}}

    def save(self, metadata: dict[str, Any]) -> None:
        """Save metadata to file atomically.

        Args:
            metadata: Metadata dictionary to save

        """
        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first for atomic operation
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=self.backup_dir,
            prefix=BACKUP_METADATA_TMP_PREFIX,
            suffix=BACKUP_METADATA_TMP_SUFFIX,
            delete=False,
            encoding="utf-8",
        ) as tmp_file:
            json.dump(metadata, tmp_file, indent=2, sort_keys=True)
            tmp_file.flush()
            temp_path = Path(tmp_file.name)

        # Atomic move
        temp_path.replace(self.metadata_file)
        logger.debug("Saved metadata to %s", self.metadata_file)

    def add_version(
        self, version: str, filename: str, file_path: Path
    ) -> None:
        """Add a version entry to metadata with checksum.

        Args:
            version: Version string
            filename: Name of the backup file
            file_path: Path to the backup file for checksum calculation

        """
        metadata = self.load()

        # Calculate checksum
        sha256_hash = self._calculate_sha256(file_path)

        # Add version entry
        metadata["versions"][version] = {
            "filename": filename,
            "sha256": sha256_hash,
            "created": datetime.now().isoformat(),
            "size": file_path.stat().st_size,
        }

        self.save(metadata)
        logger.debug("Added version %s to metadata", version)

    def _sort_versions(
        self, versions: list[str], reverse: bool = True
    ) -> list[str]:
        """Sort versions using semantic versioning with fallback.

        Args:
            versions: List of version strings to sort
            reverse: Sort in descending order (newest first) if True

        Returns:
            Sorted list of version strings

        """
        if not versions:
            return []

        try:
            return sorted(
                versions, key=lambda x: Version(x), reverse=reverse
            )
        except InvalidVersion:
            logger.warning(
                "Invalid version format detected, using lexicographic sorting"
            )
            return sorted(versions, reverse=reverse)

    def get_latest_version(self) -> str | None:
        """Get the latest version from metadata.

        Returns:
            Latest version string or None if no versions exist

        """
        metadata = self.load()
        versions = list(metadata["versions"].keys())

        if not versions:
            return None

        sorted_versions = self._sort_versions(versions, reverse=True)
        return sorted_versions[0]

    def get_version_info(self, version: str) -> dict[str, Any] | None:
        """Get information for a specific version.

        Args:
            version: Version string to look up

        Returns:
            Version information dictionary or None if not found

        """
        metadata = self.load()
        return metadata["versions"].get(version)

    def list_versions(self) -> list[str]:
        """List all available versions sorted by version number.

        Returns:
            List of version strings sorted newest to oldest

        """
        metadata = self.load()
        versions = list(metadata["versions"].keys())
        return self._sort_versions(versions, reverse=True)

    def remove_version(self, version: str) -> bool:
        """Remove a version from metadata.

        Args:
            version: Version to remove

        Returns:
            True if version was removed, False if not found

        """
        metadata = self.load()
        if version in metadata["versions"]:
            del metadata["versions"][version]
            self.save(metadata)
            logger.debug("Removed version %s from metadata", version)
            return True
        return False

    def verify_backup_integrity(self, version: str, file_path: Path) -> bool:
        """Verify backup file integrity using stored checksum.

        Args:
            version: Version to verify
            file_path: Path to backup file

        Returns:
            True if integrity check passes, False otherwise

        """
        version_info = self.get_version_info(version)
        if not version_info or not file_path.exists():
            return False

        stored_hash = version_info.get("sha256")
        if not stored_hash:
            logger.warning("No checksum stored for version %s", version)
            return False

        actual_hash = self._calculate_sha256(file_path)
        is_valid = actual_hash == stored_hash

        if not is_valid:
            logger.error(
                "Integrity check failed for %s: expected %s, got %s",
                file_path,
                stored_hash,
                actual_hash,
            )

        return is_valid

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file.

        Args:
            file_path: Path to file

        Returns:
            SHA256 checksum as hex string

        """
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()


class BackupService:
    """Enhanced service for creating and managing AppImage backups with versioning."""

    def __init__(self, config_manager, global_config):
        """Initialize backup service with dependencies.

        Args:
            config_manager: Configuration manager for app configs
            global_config: Global configuration dictionary

        """
        self.config_manager = config_manager
        self.global_config = global_config

        # Migration flag to handle old backup format
        self._migration_checked = False

    def create_backup(
        self, file_path: Path, app_name: str, version: str | None = None
    ) -> Path | None:
        """Create versioned backup of existing file.

        Args:
            file_path: Path to file to backup
            app_name: Name of the application
            version: Version string to include in backup name

        Returns:
            Path to backup file or None if no existing file

        """
        if not file_path.exists():
            return None

        # Ensure migration is checked
        self._ensure_migration()

        # Create app-specific backup directory
        backup_base_dir = Path(self.global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name
        app_backup_dir.mkdir(parents=True, exist_ok=True)

        # Determine version
        if not version:
            app_config = self.config_manager.load_app_config(app_name)
            version = (
                app_config.get("appimage", {}).get("version", "unknown")
                if app_config
                else "unknown"
            )

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
            metadata.add_version(version, backup_filename, backup_path)

            logger.info("💾 Backup created: %s (v%s)", backup_path, version)

            # Cleanup old backups after successful backup
            self._cleanup_old_backups_for_app(app_name, app_backup_dir)

            return backup_path

        except Exception as e:
            # Cleanup temp file on error
            if temp_path.exists():
                temp_path.unlink()
            logger.error("Failed to create backup for %s: %s", app_name, e)
            raise

    def restore_latest_backup(
        self, app_name: str, destination_dir: Path
    ) -> Path | None:
        """Restore the latest backup version for an app.

        This method performs the following operations:
        1. Backs up the current version (if different from restore version)
        2. Restores the specified backup version to the proper location
        3. Updates the app configuration with the restored version info
        4. Makes the restored file executable

        Args:
            app_name: Name of the application
            destination_dir: Directory to restore the backup to

        Returns:
            Path to restored file or None if no backup exists

        """
        # Ensure migration is checked
        self._ensure_migration()

        backup_base_dir = Path(self.global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name

        if not app_backup_dir.exists():
            logger.warning("No backup directory found for %s", app_name)
            return None

        # Get latest version from metadata
        metadata = BackupMetadata(app_backup_dir)
        latest_version = metadata.get_latest_version()

        if not latest_version:
            logger.warning("No backup versions found for %s", app_name)
            return None

        return self._restore_specific_version(
            app_name, latest_version, destination_dir
        )

    def restore_specific_version(
        self, app_name: str, version: str, destination_dir: Path
    ) -> Path | None:
        """Restore a specific version backup for an app.

        This method performs the same workflow as restore_latest_backup
        but for a specific version rather than the latest available.

        Args:
            app_name: Name of the application
            version: Specific version to restore
            destination_dir: Directory to restore the backup to

        Returns:
            Path to restored file or None if backup doesn't exist

        """
        return self._restore_specific_version(
            app_name, version, destination_dir
        )

    def _backup_current_version(
        self, destination_path: Path, app_name: str, current_version: str
    ) -> None:
        """Backup current version before restore if it exists.

        Args:
            destination_path: Path to current AppImage
            app_name: Name of the application
            current_version: Current version to backup

        """
        if not destination_path.exists():
            return

        logger.info(
            "Backing up current version %s before restore...", current_version
        )
        try:
            current_backup_path = self.create_backup(
                destination_path, app_name, current_version
            )
            if current_backup_path:
                logger.info(
                    "Current version backed up to: %s", current_backup_path
                )
            else:
                logger.warning(
                    "Failed to backup current version, "
                    "continuing with restore..."
                )
        except Exception as e:
            logger.warning(
                "Failed to backup current version: %s, "
                "continuing with restore...",
                e,
            )

    def _perform_atomic_restore(
        self,
        backup_path: Path,
        destination_path: Path,
        destination_dir: Path,
        appimage_name: str,
    ) -> None:
        """Restore file atomically using temporary file.

        Args:
            backup_path: Path to backup file
            destination_path: Final destination path
            destination_dir: Destination directory
            appimage_name: Name of the AppImage

        Raises:
            Exception: If restore fails

        """
        with tempfile.NamedTemporaryFile(
            dir=destination_dir,
            prefix=f".{appimage_name}_",
            suffix=BACKUP_TEMP_SUFFIX,
            delete=False,
        ) as tmp_file:
            temp_path = Path(tmp_file.name)

        try:
            shutil.copy2(backup_path, temp_path)
            temp_path.replace(destination_path)
            destination_path.chmod(0o755)
        except Exception:
            if temp_path.exists():
                temp_path.unlink()
            raise

    def _update_config_after_restore(
        self,
        app_name: str,
        version: str,
        version_info: dict[str, Any],
        app_config: dict[str, Any],
        appimage_name: str,
    ) -> None:
        """Update app config with restored version info.

        Args:
            app_name: Name of the application
            version: Restored version
            version_info: Version metadata from backup
            app_config: App configuration dictionary
            appimage_name: Name of the AppImage

        """
        app_config["appimage"]["version"] = version
        app_config["appimage"]["installed_date"] = datetime.now().isoformat()

        if version_info.get("sha256"):
            app_config["appimage"]["digest"] = (
                f"sha256:{version_info['sha256']}"
            )

        if "name" not in app_config["appimage"]:
            app_config["appimage"]["name"] = appimage_name

        try:
            self.config_manager.save_app_config(app_name, app_config)
            logger.debug(
                "Updated app config for %s with version %s", app_name, version
            )
        except Exception as e:
            logger.error(
                "Failed to update app config for %s: %s", app_name, e
            )

    def _restore_specific_version(
        self, app_name: str, version: str, destination_dir: Path
    ) -> Path | None:
        """Internal method to restore a specific version.

        Args:
            app_name: Name of the application
            version: Version to restore
            destination_dir: Directory to restore to

        Returns:
            Path to restored file or None if restore failed

        """
        backup_base_dir = Path(self.global_config["directory"]["backup"])
        app_backup_dir = backup_base_dir / app_name

        if not app_backup_dir.exists():
            logger.error("No backup directory found for %s", app_name)
            return None

        # Get version info from metadata
        metadata = BackupMetadata(app_backup_dir)
        version_info = metadata.get_version_info(version)

        if not version_info:
            logger.error("Version %s not found for %s", version, app_name)
            return None

        backup_filename = version_info["filename"]
        backup_path = app_backup_dir / backup_filename

        if not backup_path.exists():
            logger.error("Backup file not found: %s", backup_path)
            return None

        # Verify backup integrity
        if not metadata.verify_backup_integrity(version, backup_path):
            logger.error(
                "Backup integrity check failed for %s v%s", app_name, version
            )
            return None

        # Get app config to determine proper filename and current version
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("App configuration not found for %s", app_name)
            return None

        # Validate app config structure
        if "appimage" not in app_config:
            logger.error(
                "Invalid app configuration for %s: missing 'appimage' section",
                app_name,
            )
            return None

        appimage_config = app_config["appimage"]

        # Use the rename field for the actual AppImage name
        app_rename = appimage_config.get("rename", app_name)
        if not app_rename:
            app_rename = app_name
        appimage_name = f"{app_rename}.AppImage"
        destination_path = destination_dir / appimage_name
        destination_dir.mkdir(parents=True, exist_ok=True)

        # Backup current version if different from restore version
        current_version = appimage_config.get("version", "unknown")
        if current_version != version:
            self._backup_current_version(
                destination_path, app_name, current_version
            )

        # Restore file atomically
        try:
            self._perform_atomic_restore(
                backup_path, destination_path, destination_dir, appimage_name
            )

            # Update app config with restored version info
            self._update_config_after_restore(
                app_name, version, version_info, app_config, appimage_name
            )

            logger.info(
                "🔄 Restored %s v%s to %s", app_name, version, destination_path
            )
            logger.info("📝 Updated app configuration with restored version")
            return destination_path

        except Exception as e:
            logger.error("Failed to restore %s v%s: %s", app_name, version, e)
            raise

    def get_backup_info(self, app_name: str) -> list[dict[str, Any]]:
        """Get information about available backups for an app.

        Args:
            app_name: Name of the app

        Returns:
            List of backup information dictionaries sorted by version (newest first)

        """
        # Ensure migration is checked
        self._ensure_migration()

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
        # Ensure migration is checked
        self._ensure_migration()

        backup_base_dir = Path(self.global_config["directory"]["backup"])
        max_backups = self.global_config["max_backup"]

        if not backup_base_dir.exists():
            return

        if app_name:
            app_backup_dir = backup_base_dir / app_name
            if app_backup_dir.exists():
                self._cleanup_old_backups_for_app(app_name, app_backup_dir)
        else:
            # Clean up all apps
            for app_dir in backup_base_dir.iterdir():
                if app_dir.is_dir():
                    self._cleanup_old_backups_for_app(app_dir.name, app_dir)

    def _cleanup_old_backups_for_app(
        self, app_name: str, app_backup_dir: Path
    ) -> None:
        """Clean up old backups for a specific app.

        Args:
            app_name: Name of the app
            app_backup_dir: Backup directory for the app

        """
        max_backups = self.global_config["max_backup"]

        if max_backups == 0:
            # Delete all backups
            metadata = BackupMetadata(app_backup_dir)
            versions = metadata.list_versions()
            for version in versions:
                version_info = metadata.get_version_info(version)
                if version_info:
                    backup_path = app_backup_dir / version_info["filename"]
                    if backup_path.exists():
                        backup_path.unlink()
                        logger.info("Removed backup: %s", backup_path)
                    metadata.remove_version(version)

            # Remove metadata file and directory if empty
            if metadata.metadata_file.exists():
                metadata.metadata_file.unlink()
            if not any(app_backup_dir.iterdir()):
                app_backup_dir.rmdir()
            return

        # Keep only the most recent max_backups versions
        metadata = BackupMetadata(app_backup_dir)
        versions = metadata.list_versions()  # Already sorted newest to oldest

        versions_to_remove = versions[max_backups:]

        for version in versions_to_remove:
            version_info = metadata.get_version_info(version)
            if version_info:
                backup_path = app_backup_dir / version_info["filename"]
                if backup_path.exists():
                    try:
                        backup_path.unlink()
                        metadata.remove_version(version)
                        logger.info(
                            "Removed old backup: %s (v%s)",
                            backup_path,
                            version,
                        )
                    except Exception as e:
                        logger.error(
                            "Failed to remove backup %s: %s", backup_path, e
                        )

    def migrate_old_backups(self) -> int:
        """Migrate old flat backup structure to new folder-based structure.

        Returns:
            Number of backups migrated

        """
        backup_dir = Path(self.global_config["directory"]["backup"])

        if not backup_dir.exists():
            return 0

        # Find old backup files (*.backup.AppImage)
        old_backups = list(backup_dir.glob(OLD_FLAT_BACKUP_GLOB))

        if not old_backups:
            logger.debug("No old backups found to migrate")
            return 0

        logger.info(
            "🔄 Migrating %d old backups to new format...", len(old_backups)
        )

        migrated_count = 0

        for old_backup in old_backups:
            try:
                # Parse filename to extract app name and version
                # Format: appname-version.backup.AppImage
                filename = old_backup.stem  # Remove .AppImage
                if filename.endswith(CONFIG_BACKUP_EXTENSION):
                    filename = filename[: -len(CONFIG_BACKUP_EXTENSION)]
                    # Remove backup extension (e.g. '.backup')

                # Try to parse app name and version
                # Strategy: Look for installed apps first, then fallback to parsing
                app_name = None
                version = "unknown"

                if "-" in filename:
                    # Try to match against installed apps first
                    installed_apps = self.config_manager.list_installed_apps()
                    for installed_app in installed_apps:
                        if filename.startswith(installed_app + "-"):
                            app_name = installed_app
                            version_part = filename[len(installed_app) + 1 :]
                            if version_part:
                                version = version_part
                            break

                    # If no match found, use the first part as app name
                    if app_name is None:
                        parts = filename.split("-", 1)
                        app_name = parts[0]
                        if len(parts) > 1:
                            version = parts[1]
                else:
                    app_name = filename
                    version = "unknown"

                # Validate app_name and version
                if not app_name.strip():
                    app_name = filename
                    version = "unknown"

                # Sanitize app_name
                app_name = app_name.strip()

                # Create new directory structure
                app_backup_dir = backup_dir / app_name
                app_backup_dir.mkdir(exist_ok=True)

                # New filename format: appname-version.AppImage
                new_filename = f"{app_name}-{version}{APPIMAGE_SUFFIX}"
                new_path = app_backup_dir / new_filename

                # Move file to new location
                if not new_path.exists():
                    old_backup.rename(new_path)

                    # Create metadata entry
                    metadata = BackupMetadata(app_backup_dir)
                    metadata.add_version(version, new_filename, new_path)

                    migrated_count += 1
                    logger.debug("Migrated %s -> %s", old_backup, new_path)
                else:
                    # File already exists, remove old backup
                    old_backup.unlink()
                    logger.debug(
                        "Removed duplicate old backup: %s", old_backup
                    )

            except Exception as e:
                logger.error("Failed to migrate %s: %s", old_backup, e)

        if migrated_count > 0:
            logger.info(
                "✅ Successfully migrated %d backups to new format",
                migrated_count,
            )

        return migrated_count

    def _ensure_migration(self) -> None:
        """Ensure migration from old backup format is checked and performed if needed."""
        if not self._migration_checked:
            self.migrate_old_backups()
            self._migration_checked = True

    def list_apps_with_backups(self) -> list[str]:
        """List all apps that have backups.

        Returns:
            List of app names that have backup directories

        """
        self._ensure_migration()

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
