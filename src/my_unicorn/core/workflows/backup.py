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

from my_unicorn.constants import (
    APP_CONFIG_VERSION,
    BACKUP_METADATA_CORRUPTED_SUFFIX,
    BACKUP_METADATA_FILENAME,
    BACKUP_METADATA_TMP_PREFIX,
    BACKUP_METADATA_TMP_SUFFIX,
    BACKUP_TEMP_SUFFIX,
)
from my_unicorn.logger import get_logger

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
            return sorted(versions, key=Version, reverse=reverse)
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


# Helper functions for backup operations


def _validate_backup_exists(
    backup_path: Path, version: str, app_name: str
) -> None:
    """Validate that backup file exists.

    Args:
        backup_path: Path to backup file
        version: Version string
        app_name: Application name

    Raises:
        FileNotFoundError: If backup file doesn't exist
    """
    if not backup_path.exists():
        msg = f"Backup file not found: {backup_path}"
        logger.error(msg)
        raise FileNotFoundError(msg)


def _validate_backup_integrity(
    metadata: "BackupMetadata", version: str, backup_path: Path, app_name: str
) -> None:
    """Validate backup file integrity using checksum.

    Args:
        metadata: BackupMetadata instance
        version: Version string
        backup_path: Path to backup file
        app_name: Application name

    Raises:
        ValueError: If integrity check fails
    """
    if not metadata.verify_backup_integrity(version, backup_path):
        msg = f"Backup integrity check failed for {app_name} v{version}"
        logger.error(msg)
        raise ValueError(msg)


def _group_backups_by_version(backups: list[Path]) -> dict[str, list[Path]]:
    """Group backup files by version number.

    Args:
        backups: List of backup file paths

    Returns:
        Dictionary mapping version strings to lists of backup paths
    """
    version_groups: dict[str, list[Path]] = {}
    for backup in backups:
        # Extract version from backup filename (format: app-version.AppImage)
        parts = backup.stem.split("-")
        if len(parts) >= 2:
            version = parts[-1]
            version_groups.setdefault(version, []).append(backup)
    return version_groups


def _delete_old_backups(
    versions_to_remove: list[str],
    metadata: "BackupMetadata",
    app_backup_dir: Path,
) -> None:
    """Delete old backup files and update metadata.

    Args:
        versions_to_remove: List of version strings to remove
        metadata: BackupMetadata instance
        app_backup_dir: Backup directory for the app
    """
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


class BackupService:
    """Enhanced service for creating and managing AppImage backups with versioning."""

    def __init__(self, config_manager, global_config) -> None:
        """Initialize backup service with dependencies.

        Args:
            config_manager: Configuration manager for app configs
            global_config: Global configuration dictionary

        """
        self.config_manager = config_manager
        self.global_config = global_config

    @classmethod
    def create_default(cls, config_manager=None) -> "BackupService":
        """Create BackupService with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            config_manager: Optional configuration manager (creates new if None)

        Returns:
            Configured BackupService instance

        """
        from my_unicorn.config import ConfigManager

        config_mgr = config_manager or ConfigManager()
        global_config = config_mgr.load_global_config()

        return cls(
            config_manager=config_mgr,
            global_config=global_config,
        )

    def create_backup(
        self,
        file_path: Path,
        app_name: str,
        version: str | None = None,
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
                    version = app_config.get("state", {}).get(
                        "version", "unknown"
                    )
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
            metadata.add_version(version, backup_filename, backup_path)

            logger.info("Backup created: %s (v%s)", backup_path, version)

            # Cleanup old backups after successful backup (unless skipped)
            if not skip_cleanup:
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
            # Skip cleanup during restore - will cleanup after restore succeeds
            current_backup_path = self.create_backup(
                destination_path, app_name, current_version, skip_cleanup=True
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
            app_config: App configuration dictionary (v2 format)
            appimage_name: Name of the AppImage

        """
        # v2 config: update state section
        state = app_config.get("state", {})
        state["version"] = version
        state["installed_date"] = datetime.now().isoformat()

        # Update verification if we have sha256
        if version_info.get("sha256"):
            verification = state.get("verification", {})
            methods = verification.get("methods", [])

            # Update or add digest verification method
            digest_method_found = False
            for method in methods:
                if method.get("type") == "digest":
                    method["expected"] = version_info["sha256"]
                    method["computed"] = version_info["sha256"]
                    method["status"] = "passed"
                    digest_method_found = True
                    break

            if not digest_method_found:
                methods.append(
                    {
                        "type": "digest",
                        "status": "passed",
                        "algorithm": "sha256",
                        "expected": version_info["sha256"],
                        "computed": version_info["sha256"],
                        "source": "backup_restore",
                    }
                )

            verification["methods"] = methods
            verification["passed"] = True
            state["verification"] = verification

        app_config["state"] = state

        try:
            self.config_manager.save_app_config(app_name, app_config)
            logger.debug(
                "Updated app config for %s with version %s", app_name, version
            )
        except Exception as e:
            logger.error("Failed to update app config for %s: %s", app_name, e)

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

        # Validate backup exists and integrity
        try:
            _validate_backup_exists(backup_path, version, app_name)
            _validate_backup_integrity(
                metadata, version, backup_path, app_name
            )
        except (FileNotFoundError, ValueError):
            return None

        # Get app config to determine proper filename and current version
        app_config = self.config_manager.load_app_config(app_name)
        if not app_config:
            logger.error("App configuration not found for %s", app_name)
            return None

        # Check config version to detect v1 vs v2
        config_version = app_config.get("config_version", "1.0.0")
        if config_version != APP_CONFIG_VERSION:
            logger.error(
                "App configuration for %s uses old v%s format",
                app_name,
                config_version,
            )
            logger.info("")
            logger.info("⚠️  Old Configuration Format Detected")
            logger.info("")
            logger.info(
                "The app '%s' uses config version %s (current: %s).",
                app_name,
                config_version,
                APP_CONFIG_VERSION,
            )
            logger.info("Please run the migration command to upgrade to v2:")
            logger.info("")
            logger.info("  my-unicorn migrate")
            logger.info("")
            return None

        # v2 config structure: extract necessary fields from state and overrides
        state = app_config.get("state", {})
        catalog_ref = app_config.get("catalog_ref")

        # Get rename from catalog or overrides
        if catalog_ref:
            # Catalog-based install: need to load catalog for rename field
            # For now, use app_name as fallback
            app_rename = app_name
        else:
            # URL-based install: get from overrides
            overrides = app_config.get("overrides", {})
            appimage_config = overrides.get("appimage", {})
            app_rename = appimage_config.get("rename", app_name)

        # Use the rename field for the actual AppImage name
        if not app_rename:
            app_rename = app_name
        appimage_name = f"{app_rename}.AppImage"
        destination_path = destination_dir / appimage_name
        destination_dir.mkdir(parents=True, exist_ok=True)

        # Backup current version if different from restore version
        current_version = state.get("version", "unknown")
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

            # Cleanup old backups after successful restore
            backup_base_dir = Path(self.global_config["directory"]["backup"])
            app_backup_dir = backup_base_dir / app_name
            self._cleanup_old_backups_for_app(app_name, app_backup_dir)

            logger.info(
                "Restored %s v%s to %s", app_name, version, destination_path
            )
            logger.info("Updated app configuration with restored version")
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
        metadata = BackupMetadata(app_backup_dir)

        if max_backups == 0:
            # Delete all backups
            versions = metadata.list_versions()
            _delete_old_backups(versions, metadata, app_backup_dir)

            # Remove metadata file and directory if empty
            if metadata.metadata_file.exists():
                metadata.metadata_file.unlink()
            if not any(app_backup_dir.iterdir()):
                app_backup_dir.rmdir()
            return

        # Keep only the most recent max_backups versions
        versions = metadata.list_versions()  # Already sorted newest to oldest
        versions_to_remove = versions[max_backups:]
        _delete_old_backups(versions_to_remove, metadata, app_backup_dir)

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
