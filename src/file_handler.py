#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File handling module for AppImage operations.

This module handles file operations related to AppImages, including moving files,
creating desktop entries, and downloading icons.
"""

# Standard library imports
import logging
import re
import shutil
import stat
import subprocess
import sys
import time
from importlib import import_module
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any

# Third-party imports
import requests

# Local imports
from src.api import GitHubAPI

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
APPIMAGE_EXTENSION = ".AppImage"
DESKTOP_ENTRY_DIR = Path("~/.local/share/applications").expanduser()
DESKTOP_ENTRY_FILE_MODE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
DEFAULT_CATEGORIES = "Utility;"
DESKTOP_FILE_SECTION = "Desktop Entry"


class FileHandler:
    """
    Handles file operations for AppImage management.

    This class provides methods for:
    - Moving AppImage files to installation directories
    - Creating and updating .desktop files
    - Managing backup files
    - Setting proper file permissions
    """

    # Dictionary mapping repo names to app-specific handler modules
    APP_HANDLERS = {
        "app": "standard_notes",  # Standard Notes repo is called "app"
    }

    def __init__(
        self,
        appimage_name: str,
        repo: str,
        owner: Optional[str] = None,
        version: Optional[str] = None,
        sha_name: Optional[str] = None,
        config_file: Optional[str] = None,
        appimage_download_folder_path: Optional[str] = None,
        appimage_download_backup_folder_path: Optional[str] = None,
        config_folder: Optional[str] = None,
        config_file_name: Optional[str] = None,
        batch_mode: bool = False,
        keep_backup: bool = True,
        max_backups: int = 3,
    ):
        """
        Initialize file handler with paths and configuration.

        Args:
            appimage_name: Name of the AppImage file
            repo: Repository name (original case preserved)
            owner: Repository owner/organization name
            version: AppImage version
            sha_name: SHA file name
            config_file: Path to global config file
            appimage_download_folder_path: Directory where AppImages are stored
            appimage_download_backup_folder_path: Directory for backup AppImages
            config_folder: Directory for configuration files
            config_file_name: Name of configuration file
            batch_mode: Whether to run in batch mode (no user prompts)
            keep_backup: Whether to keep backup files
            max_backups: Maximum number of backup files to keep per app
        """
        # Validate required parameters
        if not appimage_name:
            raise ValueError("AppImage name cannot be empty")
        if not repo:
            raise ValueError("Repository name cannot be empty")

        self.appimage_name = appimage_name
        self.repo = repo
        self.owner = owner
        self.version = version
        self.sha_name = sha_name
        self.config_file = config_file
        self.config_folder = config_folder
        self.config_file_name = config_file_name
        self.batch_mode = batch_mode
        self.keep_backup = keep_backup
        self.max_backups = max_backups

        # Convert paths to Path objects
        self.appimage_download_folder_path = (
            Path(appimage_download_folder_path) if appimage_download_folder_path else None
        )
        self.appimage_download_backup_folder_path = (
            Path(appimage_download_backup_folder_path)
            if appimage_download_backup_folder_path
            else None
        )

        # Derived paths
        # Construct the AppImage file path with proper .AppImage extension if missing
        file_name = self.repo
        if not file_name.lower().endswith(APPIMAGE_EXTENSION.lower()):
            file_name += APPIMAGE_EXTENSION

        self.appimage_path = (
            self.appimage_download_folder_path / file_name
            if self.appimage_download_folder_path
            else None
        )

        # Use original appimage_name for backup path so we can properly match downloaded files
        self.backup_path = (
            self.appimage_download_backup_folder_path / self.appimage_name
            if self.appimage_download_backup_folder_path
            else None
        )

    def handle_appimage_operations(self, github_api: Optional[GitHubAPI] = None) -> bool:
        """
        Perform all required file operations for an AppImage.

        Args:
            github_api: Optional GitHubAPI instance for additional operations

        Returns:
            bool: True if all operations succeeded, False otherwise
        """
        try:
            # Create destination folders if they don't exist
            self._ensure_directories_exist()

            # Make backup of existing AppImage if it exists
            if self.appimage_path and self.appimage_path.exists():
                if not self._backup_appimage():
                    return False

            # Move downloaded AppImage to destination folder
            if not self._move_appimage():
                return False

            # Set executable permissions
            if not self._set_executable_permission():
                return False

            # Create or update desktop entry
            if not self._create_desktop_entry():
                logging.warning("Failed to create desktop entry, but continuing")

            return True

        except Exception as e:
            logging.error(f"Error handling AppImage operations: {str(e)}")
            return False

    def _ensure_directories_exist(self) -> None:
        """Create required directories if they don't exist."""
        if self.appimage_download_folder_path:
            self.appimage_download_folder_path.mkdir(parents=True, exist_ok=True)
        if self.appimage_download_backup_folder_path:
            self.appimage_download_backup_folder_path.mkdir(parents=True, exist_ok=True)

    def _backup_appimage(self) -> bool:
        """
        Backup existing AppImage file and maintain backup rotation.

        Keeps only the specified number of backup files per app, removing older backups
        when the limit is reached.

        Returns:
            bool: True if backup succeeded or was skipped, False otherwise
        """
        try:
            # Check if the backup folder exists or create it
            if self.appimage_download_backup_folder_path:
                self.appimage_download_backup_folder_path.mkdir(parents=True, exist_ok=True)

            # If keep_backup is False, skip backup creation
            if not self.keep_backup:
                logging.info("Backups disabled, skipping backup creation")
                return True

            # Get app name for grouping backups by app
            app_base_name = self.repo.lower()

            # Create a unique backup name with timestamp
            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_name = f"{app_base_name}_{timestamp}.AppImage"
            new_backup_path = self.appimage_download_backup_folder_path / backup_name

            # Move current AppImage to timestamped backup
            logging.info(f"Backing up {self.appimage_path} to {new_backup_path}")
            shutil.copy2(self.appimage_path, new_backup_path)

            # Always clean up old backups based on max_backups setting after adding a new backup
            self._cleanup_old_backups(app_base_name)

            return True

        except OSError as e:
            logging.error(f"Failed to backup AppImage: {str(e)}")
            return False

    def _cleanup_old_backups(self, app_base_name: str) -> None:
        """
        Remove old backup files based on max_backups setting.

        Args:
            app_base_name: Base name of the app to clean up backups for
        """
        try:
            # Skip cleanup if backup is disabled
            if not self.keep_backup or not self.appimage_download_backup_folder_path:
                return

            # Ensure backup directory exists
            backup_dir = self.appimage_download_backup_folder_path
            if not backup_dir.exists():
                logging.info(f"Backup directory does not exist: {backup_dir}")
                return

            # Normalize app_base_name for consistent comparison
            app_base_name = app_base_name.lower()

            # Find all backup files for this app
            all_backups = []

            for filepath in backup_dir.iterdir():
                if not filepath.name.lower().endswith(".appimage") or not filepath.is_file():
                    continue

                # Simplified matching - just check if the normalized filename starts with the app name
                filename_lower = filepath.name.lower()
                if (
                    filename_lower.startswith(f"{app_base_name}-")
                    or filename_lower.startswith(f"{app_base_name}_")
                    or filename_lower == f"{app_base_name}.appimage"
                ):
                    # Get file modification time for sorting
                    mod_time = filepath.stat().st_mtime
                    all_backups.append((filepath, mod_time, filepath.name))
                    logging.debug(f"Found backup file: {filepath.name}")

            # Sort backups by modification time (newest first)
            all_backups.sort(key=lambda x: x[1], reverse=True)

            # Log the number of backups found
            backups_count = len(all_backups)
            logging.info(
                f"Found {backups_count} backups for {app_base_name}, max_backups={self.max_backups}"
            )

            # Keep only the newest max_backups files
            if backups_count > self.max_backups:
                files_to_remove = all_backups[self.max_backups :]
                removed_count = 0

                for filepath, _, filename in files_to_remove:
                    try:
                        filepath.unlink()
                        removed_count += 1
                        logging.info(f"Removed old backup: {filename}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old backup {filename}: {e}")

                if removed_count > 0:
                    logging.info(
                        f"✓ Cleaned up {removed_count} old backup{'s' if removed_count > 1 else ''} for {app_base_name}"
                        f" (kept {self.max_backups} newest)"
                    )
            else:
                logging.info(
                    f"No backups to remove for {app_base_name}, current count ({backups_count}) ≤ max_backups ({self.max_backups})"
                )

        except OSError as e:
            # Log but don't fail the whole operation if cleanup fails
            logging.warning(f"Error during backup cleanup: {str(e)}")
        except Exception as e:
            # Catch any other unexpected errors
            logging.warning(f"Unexpected error during backup cleanup: {str(e)}")

    def _move_appimage(self) -> bool:
        """
        Move downloaded AppImage to destination folder.

        Returns:
            bool: True if the move succeeded, False otherwise
        """
        try:
            # Import DownloadManager at runtime to avoid circular imports
            from src.download import DownloadManager

            # Get the downloads directory path using the class method
            downloads_dir = DownloadManager.get_downloads_dir()
            current_path = Path(downloads_dir) / self.appimage_name

            # Check if file exists in downloads directory
            if not current_path.exists():
                logging.error(f"Downloaded AppImage not found at {current_path}")
                return False

            # Move file to destination
            logging.info(f"Moving {current_path} to {self.appimage_path}")
            shutil.move(str(current_path), str(self.appimage_path))
            return True

        except Exception as e:
            logging.error(f"Failed to move AppImage: {str(e)}")
            return False

    def _set_executable_permission(self) -> bool:
        """
        Set executable permissions on the AppImage.

        Returns:
            bool: True if permissions were set successfully, False otherwise
        """
        try:
            # Make the AppImage executable (add +x to current permissions)
            self.appimage_path.chmod(self.appimage_path.stat().st_mode | DESKTOP_ENTRY_FILE_MODE)
            logging.info(f"Set executable permissions on {self.appimage_path}")
            return True

        except Exception as e:
            logging.error(f"Failed to set executable permissions: {str(e)}")
            return False

    def _create_desktop_entry(self) -> bool:
        """
        Create or update .desktop file for easy launching of the AppImage.

        Creates a standard conformant desktop entry file in the user's
        applications directory with proper permissions and icon support.
        Avoids unnecessary writes by comparing content with existing file.

        Returns:
            bool: True if desktop entry was created successfully or unchanged,
                 False otherwise
        """
        try:
            # Check if there's a specialized handler for this application
            if self.repo.lower() in self.APP_HANDLERS:
                try:
                    # Import the appropriate app handler module
                    handler_module_name = self.APP_HANDLERS[self.repo.lower()]
                    module_path = f"src.apps.{handler_module_name}"

                    # Import the module dynamically
                    handler_module = import_module(module_path)

                    # Get the handler class (assuming it follows the pattern: RepoNameHandler)
                    handler_class_name = (
                        "".join(word.capitalize() for word in handler_module_name.split("_"))
                        + "Handler"
                    )
                    handler_class = getattr(handler_module, handler_class_name)

                    # Get the app_config instance
                    from src.app_config import AppConfigManager

                    app_config = AppConfigManager(
                        owner=self.owner,
                        repo=self.repo,
                        version=self.version,
                        sha_name=self.sha_name,
                        appimage_name=self.appimage_name,
                    )

                    # Get icon path if available
                    from src.icon_manager import IconManager

                    icon_manager = IconManager()
                    icon_path = icon_manager.get_icon_path(self.repo)

                    # Use the specialized handler to create the desktop file
                    success, result = handler_class.create_desktop_file(
                        app_config=app_config, appimage_path=self.appimage_path, icon_path=icon_path
                    )

                    if success:
                        logging.info(f"Created desktop entry using {handler_class_name}: {result}")
                        return True
                    else:
                        logging.warning(
                            f"App-specific handler failed: {result}, falling back to default"
                        )
                        # Continue with default implementation if specialized handler failed
                except (ImportError, AttributeError, Exception) as e:
                    logging.warning(f"Failed to use app-specific handler: {str(e)}, using default")

            # Default desktop entry creation implementation
            app_name = self.repo  # Preserve original case for display name
            desktop_file = f"{self.repo.lower()}.desktop"
            desktop_path = DESKTOP_ENTRY_DIR / desktop_file

            logging.info(f"Processing desktop entry at {desktop_path}")

            # Ensure desktop directory exists
            DESKTOP_ENTRY_DIR.mkdir(parents=True, exist_ok=True)

            # Get icon path if available
            from src.icon_manager import IconManager

            icon_manager = IconManager()
            icon_path = icon_manager.get_icon_path(self.repo)

            # Read existing desktop file content if it exists
            existing_entries = {}
            if desktop_path.exists():
                try:
                    with desktop_path.open("r", encoding="utf-8") as f:
                        section = None
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                section = line[1:-1]
                                continue
                            if section == DESKTOP_FILE_SECTION and "=" in line:
                                key, value = line.split("=", 1)
                                existing_entries[key.strip()] = value.strip()
                    logging.info(f"Found existing desktop file: {desktop_path}")
                except Exception as e:
                    logging.warning(f"Error reading existing desktop file: {str(e)}")

            # New desktop entry content
            new_entries = {
                "Type": "Application",
                "Name": app_name,  # Use original case for display name
                "Exec": str(self.appimage_path),  # Use full path to AppImage
                "Terminal": "false",
                "Categories": DEFAULT_CATEGORIES,
                "Comment": f"AppImage for {app_name}",
            }

            # Add icon if available
            if icon_path:
                new_entries["Icon"] = str(icon_path)
                logging.info(f"Using icon from: {icon_path}")
            else:
                logging.info("No icon found for desktop entry")

            # Check if anything would actually change
            needs_update = False

            # Check if essential entries exist and match
            for key, new_value in new_entries.items():
                if key not in existing_entries or existing_entries[key] != new_value:
                    needs_update = True
                    logging.info(f"Desktop entry update needed: {key} changed")
                    break

            # If no update needed, return early
            if not needs_update:
                logging.info(f"Desktop entry {desktop_path} is already up to date")
                return True

            # Write updated desktop file with atomic operation pattern
            temp_path = desktop_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(f"[{DESKTOP_FILE_SECTION}]\n")
                for key, value in new_entries.items():
                    f.write(f"{key}={value}\n")

                # Preserve any additional entries from existing file that we don't explicitly set
                for key, value in existing_entries.items():
                    if key not in new_entries:
                        f.write(f"{key}={value}\n")

            # Set proper executable permissions
            temp_path.chmod(temp_path.stat().st_mode | DESKTOP_ENTRY_FILE_MODE)

            # Replace original file with temp file (atomic operation)
            temp_path.replace(desktop_path)

            logging.info(f"Updated desktop entry at {desktop_path}")
            return True

        except OSError as e:
            logging.error(f"Failed to create desktop entry due to file system error: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error creating desktop entry: {str(e)}")
            return False
