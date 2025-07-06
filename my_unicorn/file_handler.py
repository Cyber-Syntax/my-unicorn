#!/usr/bin/env python3
"""File handling module for AppImage operations.

This module handles file operations related to AppImages, including moving files,
creating desktop entries, and downloading icons.
"""

# Standard library imports
import logging
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path

# Local imports
from my_unicorn.icon_manager import IconManager
from my_unicorn.utils.desktop_entry import DesktopEntryManager

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
APPIMAGE_EXTENSION = ".AppImage"
DESKTOP_ENTRY_DIR = Path("~/.local/share/applications").expanduser()
DESKTOP_ENTRY_FILE_MODE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
DEFAULT_CATEGORIES = "Utility;"
DESKTOP_FILE_SECTION = "Desktop Entry"


@dataclass
class FileHandler:
    """Handles file operations for AppImage management.

    This class provides methods for:
    - Moving AppImage files to installation directories
    - Creating and updating .desktop files
    - Managing backup files
    - Setting proper file permissions

    The file lifecycle is tracked explicitly:
    1. Download - Original file downloaded from GitHub to downloads directory
    2. Verification - Verify the downloaded file's integrity
    3. Installation - Move to final installation location in app_storage_path
    4. Backup - Store previous versions in app_backup_storage_path
    """

    appimage_name: str  # Original downloaded filename from GitHub
    repo: str
    owner: str | None = None
    version: str | None = None
    checksum_file_name: str | None = None
    config_file: str | None = None
    app_storage_path: Path | None = None  # Final installation directory
    app_backup_storage_path: Path | None = None  # Backup directory
    config_folder: str | None = None
    config_file_name: str | None = None
    batch_mode: bool = False
    keep_backup: bool = True
    max_backups: int = 3
    app_rename: str = ""

    def __post_init__(self) -> None:
        """Post-initialization processing.

        Validates required fields and converts string paths to Path objects.

        Raises:
            ValueError: If required parameters are missing

        """
        # Validate required parameters
        if not self.appimage_name:
            raise ValueError("AppImage name cannot be empty")
        if not self.repo:
            raise ValueError("Repository name cannot be empty")

        # Use app_rename if provided, otherwise fallback to repo
        if not self.app_rename:
            self.app_rename = self.repo

        # Ensure app_rename is never None after initialization
        if self.app_rename is None:
            self.app_rename = self.repo

        # Convert paths to Path objects
        if self.app_storage_path and isinstance(self.app_storage_path, str):
            self.app_storage_path = Path(self.app_storage_path)

        if self.app_backup_storage_path and isinstance(self.app_backup_storage_path, str):
            self.app_backup_storage_path = Path(self.app_backup_storage_path)

    @property
    def download_path(self) -> Path:
        """Path to the downloaded AppImage file in downloads directory.

        Returns:
            Path: Full path to the downloaded AppImage

        """
        from my_unicorn.global_config import GlobalConfigManager

        downloads_dir = Path(GlobalConfigManager().expanded_app_download_path)
        return downloads_dir / self.appimage_name

    @property
    def installed_filename(self) -> str:
        """Filename for the installed AppImage based on app_rename.

        Returns:
            str: Filename with .AppImage extension

        """
        if not self.app_rename.lower().endswith(APPIMAGE_EXTENSION.lower()):
            return f"{self.app_rename}{APPIMAGE_EXTENSION}"
        return self.app_rename

    @property
    def installed_path(self) -> Path | None:
        """Path where the AppImage is/will be installed.

        Returns:
            Path or None: Full path to installed AppImage or None if app_storage_path not set

        """
        if not self.app_storage_path:
            return None
        return self.app_storage_path / self.installed_filename

    def handle_appimage_operations(self, icon_path: str | None = None) -> bool:
        """Perform all required file operations for an AppImage.

        Args:
            icon_path: Optional path to icon file (to avoid duplicate checks)

        Returns:
            bool: True if all operations succeeded, False otherwise

        """
        try:
            # Create destination folders if they don't exist
            self._ensure_directories_exist()

            # Make backup of existing AppImage if it exists and backup is needed
            if self.installed_path and self.installed_path.exists() and not self._backup_appimage():
                return False

            # Move downloaded AppImage to destination folder
            if not self._move_appimage():
                return False

            # set executable permissions
            if not self._set_executable_permission():
                return False

            # Create or update desktop entry, passing the provided icon_path
            if not self._create_desktop_entry(icon_path=icon_path):
                logger.warning("Failed to create desktop entry, but continuing")

            return True

        except (OSError, ValueError) as e:
            logger.error("Error handling AppImage operations: %s", e)
            return False

    def _ensure_directories_exist(self) -> None:
        """Create required directories if they don't exist."""
        if self.app_storage_path:
            self.app_storage_path.mkdir(parents=True, exist_ok=True)
        if self.app_backup_storage_path:
            self.app_backup_storage_path.mkdir(parents=True, exist_ok=True)

    def _backup_appimage(self) -> bool:
        """Backup existing AppImage file and maintain backup rotation.

        Keeps only the specified number of backup files per app, removing older backups
        when the limit is reached.

        Returns:
            bool: True if backup succeeded or was skipped, False otherwise

        """
        try:
            # Check if the backup folder exists or create it
            if not self.app_backup_storage_path:
                logger.warning("Backup storage path not set, skipping backup")
                return True

            self.app_backup_storage_path.mkdir(parents=True, exist_ok=True)

            # If keep_backup is False, skip backup creation
            if not self.keep_backup:
                logger.info("Backups disabled, skipping backup creation")
                return True

            # Get app name for grouping backups by app
            app_base_name = self.app_rename.lower()

            # Create a unique backup name with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_name = f"{app_base_name}_{timestamp}.AppImage"
            new_backup_path = self.app_backup_storage_path / backup_name

            # Make backup of current AppImage
            if not self.installed_path:
                logger.error("Installation path not set for backup")
                return False

            logger.info("Backing up %s to %s", self.installed_path, new_backup_path)
            shutil.copy2(self.installed_path, new_backup_path)

            # Clean up old backups based on max_backups setting
            self._cleanup_old_backups(app_base_name)

            return True

        except OSError as e:
            logger.error("Failed to backup AppImage: %s", e)
            return False

    def _cleanup_old_backups(self, app_base_name: str) -> None:
        """Remove old backup files based on max_backups setting.

        Args:
            app_base_name: Base name of the app to clean up backups for

        """
        try:
            # Skip cleanup if backup is disabled
            if not self.keep_backup or not self.app_backup_storage_path:
                return

            # Ensure backup directory exists
            backup_dir = self.app_backup_storage_path
            if not backup_dir.exists():
                logger.info("Backup directory does not exist: %s", backup_dir)
                return

            # Normalize app_base_name for consistent comparison
            app_base_name = app_base_name.lower()

            # Find all backup files for this app
            all_backups = []

            for filepath in backup_dir.iterdir():
                if not filepath.name.lower().endswith(".appimage") or not filepath.is_file():
                    continue

                # Simplified matching - just check if filename starts with the app name
                filename_lower = filepath.name.lower()
                if (
                    filename_lower.startswith((f"{app_base_name}-", f"{app_base_name}_"))
                    or filename_lower == f"{app_base_name}.appimage"
                ):
                    # Get file modification time for sorting
                    mod_time = filepath.stat().st_mtime
                    all_backups.append((filepath, mod_time, filepath.name))
                    logger.debug("Found backup file: %s", filepath.name)

            # Sort backups by modification time (newest first)
            all_backups.sort(key=lambda x: x[1], reverse=True)

            # Log the number of backups found
            backups_count = len(all_backups)
            logger.info(
                "Found %d backups for %s, max_backups=%d",
                backups_count,
                app_base_name,
                self.max_backups,
            )

            # Keep only the newest max_backups files
            if backups_count > self.max_backups:
                files_to_remove = all_backups[self.max_backups :]
                removed_count = 0

                for filepath, _, filename in files_to_remove:
                    try:
                        filepath.unlink()
                        removed_count += 1
                        logger.info("Removed old backup: %s", filename)
                    except OSError as e:
                        logger.warning("Failed to remove old backup %s: %s", filename, e)

                if removed_count > 0:
                    plural_s = "s" if removed_count > 1 else ""
                    logger.info(
                        "✓ Cleaned up %d old backup%s for %s (kept %d newest)",
                        removed_count,
                        plural_s,
                        app_base_name,
                        self.max_backups,
                    )
            else:
                logger.info(
                    "No backups to remove for %s, current count (%d) ≤ max_backups (%d)",
                    app_base_name,
                    backups_count,
                    self.max_backups,
                )

        except OSError as e:
            # Log but don't fail the whole operation if cleanup fails
            logger.warning("Error during backup cleanup: %s", e)
        except ValueError as e:
            # Catch any other unexpected errors
            logger.warning("Unexpected error during backup cleanup: %s", e)

    def _move_appimage(self) -> bool:
        """Move downloaded AppImage to destination folder.

        Returns:
            bool: True if the move succeeded, False otherwise

        """
        try:
            # Check if source file exists
            if not self.download_path.exists():
                logger.error("Downloaded AppImage not found at %s", self.download_path)
                return False

            # Check if destination path is set
            if not self.installed_path:
                logger.error("Installation path not set, app_storage_path may be missing")
                return False

            # Move file to destination
            logger.info("Moving %s to %s", self.download_path, self.installed_path)
            shutil.move(str(self.download_path), str(self.installed_path))
            return True

        except OSError as e:
            logger.error("Failed to move AppImage: %s", e)
            return False

    def _set_executable_permission(self) -> bool:
        """Set executable permissions on the AppImage.

        Returns:
            bool: True if permissions were set successfully, False otherwise

        """
        try:
            if not self.installed_path:
                logger.error("Installation path not set")
                return False

            # Make the AppImage executable (add +x to current permissions)
            self.installed_path.chmod(self.installed_path.stat().st_mode | DESKTOP_ENTRY_FILE_MODE)
            logger.info("Set executable permissions on %s", self.installed_path)
            return True

        except OSError as e:
            logger.error("Failed to set executable permissions: %s", e)
            return False

    def _create_desktop_entry(self, icon_path: str | None = None) -> bool:
        """Create or update .desktop file for easy launching of the AppImage.

        Creates a standard conformant desktop entry file in the user's
        applications directory with proper permissions and icon support.
        Avoids unnecessary writes by comparing content with existing file.

        Args:
            icon_path: Optional path to icon file

        Returns:
            bool: True if desktop entry was created successfully or unchanged,
                 False otherwise

        """
        try:
            if not self.installed_path:
                logger.error("Installation path not set")
                return False

            # Get icon path if not provided
            if not icon_path:
                icon_manager = IconManager()
                icon_path = icon_manager.get_icon_path(self.app_rename, self.repo)

            # Use the DesktopEntryManager to handle desktop entry operations
            desktop_manager = DesktopEntryManager()
            success, message = desktop_manager.create_or_update_desktop_entry(
                app_rename=self.app_rename,
                appimage_path=self.installed_path,
                icon_path=icon_path,
            )

            if not success:
                logger.error("Desktop entry creation failed: %s", message)

            return success

        except OSError as e:
            logger.error("Failed to create desktop entry due to file system error: %s", e)
            return False
        except (ValueError, TypeError) as e:
            logger.error("Unexpected error creating desktop entry: %s", e)
            return False
