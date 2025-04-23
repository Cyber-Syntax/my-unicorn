#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
File handling module for AppImage operations.

This module handles file operations related to AppImages, including moving files,
creating desktop entries, and downloading icons.
"""

import logging
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from importlib import import_module

import requests
from tqdm import tqdm

from src.api import GitHubAPI

# Configure module logger
logger = logging.getLogger(__name__)


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
        owner: str = None,
        version: str = None,
        sha_name: str = None,
        config_file: str = None,
        appimage_download_folder_path: str = None,
        appimage_download_backup_folder_path: str = None,
        config_folder: str = None,
        config_file_name: str = None,
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
        self.appimage_name = appimage_name
        self.repo = repo
        self.owner = owner
        self.version = version
        self.sha_name = sha_name
        self.config_file = config_file
        self.appimage_download_folder_path = appimage_download_folder_path
        self.appimage_download_backup_folder_path = appimage_download_backup_folder_path
        self.config_folder = config_folder
        self.config_file_name = config_file_name
        self.batch_mode = batch_mode
        self.keep_backup = keep_backup
        self.max_backups = max_backups

        # Derived paths
        # Construct the AppImage file path with proper .AppImage extension if missing
        file_name = self.repo
        if not file_name.lower().endswith(".appimage"):
            file_name += ".AppImage"
        self.appimage_path = os.path.join(self.appimage_download_folder_path, file_name)

        # Use original appimage_name for backup path so we can properly match downloaded files
        self.backup_path = os.path.join(
            self.appimage_download_backup_folder_path, self.appimage_name
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
            if os.path.exists(self.appimage_path):
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
        os.makedirs(self.appimage_download_folder_path, exist_ok=True)
        os.makedirs(self.appimage_download_backup_folder_path, exist_ok=True)

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
            os.makedirs(self.appimage_download_backup_folder_path, exist_ok=True)

            # If keep_backup is False, skip backup creation
            if not self.keep_backup:
                logging.info("Backups disabled, skipping backup creation")
                return True

            # Get app name for grouping backups by app
            app_base_name = os.path.splitext(self.repo)[0].lower()

            # Create a unique backup name with timestamp
            import time

            timestamp = time.strftime("%Y%m%d-%H%M%S")
            backup_name = f"{app_base_name}_{timestamp}.AppImage"
            new_backup_path = os.path.join(self.appimage_download_backup_folder_path, backup_name)

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
            if not self.keep_backup:
                return

            # Ensure backup directory exists
            backup_dir = self.appimage_download_backup_folder_path
            if not os.path.exists(backup_dir):
                logging.info(f"Backup directory does not exist: {backup_dir}")
                return

            # Normalize app_base_name for consistent comparison
            app_base_name = app_base_name.lower()

            # Find all backup files for this app
            all_backups = []

            for filename in os.listdir(backup_dir):
                filepath = os.path.join(backup_dir, filename)
                if not filename.lower().endswith(".appimage") or not os.path.isfile(filepath):
                    continue

                # Simplified matching - just check if the normalized filename starts with the app name
                filename_lower = filename.lower()
                if (
                    filename_lower.startswith(f"{app_base_name}-")
                    or filename_lower.startswith(f"{app_base_name}_")
                    or filename_lower == f"{app_base_name}.appimage"
                ):
                    # Get file modification time for sorting
                    mod_time = os.path.getmtime(filepath)
                    all_backups.append((filepath, mod_time, filename))
                    logging.debug(f"Found backup file: {filename}")

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
                        os.remove(filepath)
                        removed_count += 1
                        logging.info(f"Removed old backup: {filename}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old backup {filename}: {e}")

                if removed_count > 0:
                    print(
                        f"✓ Cleaned up {removed_count} old backup{'s' if removed_count > 1 else ''}"
                    )
                    logging.info(f"Cleaned up {removed_count} old backups for {app_base_name}")
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
            # Assume file was downloaded to current directory
            current_path = os.path.join(os.getcwd(), self.appimage_name)

            # Check if file exists
            if not os.path.exists(current_path):
                logging.error(f"Downloaded AppImage not found at {current_path}")
                return False

            # Move file to destination
            logging.info(f"Moving {current_path} to {self.appimage_path}")
            shutil.move(current_path, self.appimage_path)
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
            os.chmod(
                self.appimage_path,
                os.stat(self.appimage_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
            )
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
                    icon_path = self._get_icon_path(self.repo)

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
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            desktop_file = f"{self.repo.lower()}.desktop"
            desktop_path = os.path.join(desktop_dir, desktop_file)

            logging.info(f"Processing desktop entry at {desktop_path}")

            # Ensure desktop directory exists
            os.makedirs(desktop_dir, exist_ok=True)

            # Get icon path if available
            icon_path = self._get_icon_path(self.repo)

            # Read existing desktop file content if it exists
            existing_entries = {}
            if os.path.exists(desktop_path):
                try:
                    with open(desktop_path, "r", encoding="utf-8") as f:
                        section = None
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            if line.startswith("[") and line.endswith("]"):
                                section = line[1:-1]
                                continue
                            if section == "Desktop Entry" and "=" in line:
                                key, value = line.split("=", 1)
                                existing_entries[key.strip()] = value.strip()
                    logging.info(f"Found existing desktop file: {desktop_path}")
                except Exception as e:
                    logging.warning(f"Error reading existing desktop file: {str(e)}")

            # New desktop entry content
            new_entries = {
                "Type": "Application",
                "Name": app_name,  # Use original case for display name
                "Exec": self.appimage_path,  # Use full path to AppImage
                "Terminal": "false",
                "Categories": "Utility;",
                "Comment": f"AppImage for {app_name}",
            }

            # Add icon if available
            if icon_path:
                new_entries["Icon"] = icon_path
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
            temp_path = f"{desktop_path}.tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\n")
                for key, value in new_entries.items():
                    f.write(f"{key}={value}\n")

                # Preserve any additional entries from existing file that we don't explicitly set
                for key, value in existing_entries.items():
                    if key not in new_entries:
                        f.write(f"{key}={value}\n")

            # Set proper executable permissions
            os.chmod(temp_path, os.stat(temp_path).st_mode | stat.S_IXUSR)

            # Replace original file with temp file (atomic operation)
            os.replace(temp_path, desktop_path)

            logging.info(f"Updated desktop entry at {desktop_path}")
            return True

        except OSError as e:
            logging.error(f"Failed to create desktop entry due to file system error: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error creating desktop entry: {str(e)}")
            return False

    def _get_icon_path(self, app_name: str) -> Optional[str]:
        """
        Get path to application icon if it exists.

        Searches for icons in the repository-specific directory structure:
        - Then in the repository name directory (for backward compatibility)
        - Finally in legacy icon locations

        Args:
            app_name: Name of the application (original case preserved)

        Returns:
            str or None: Path to icon file or None if not found
        """
        # Base icon directory for myunicorn
        icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")

        app_id_icon_dir = os.path.join(icon_base_dir, self.repo)
        repo_icon_dir = os.path.join(icon_base_dir, app_name)

        # List of directories to search in priority order
        icon_dirs = []

        if self.repo != app_name:
            icon_dirs.append(app_id_icon_dir)

        # Always check the repo directory
        icon_dirs.append(repo_icon_dir)

        # Build list of potential icon paths
        search_paths = []

        # Check standard icon filenames in each directory
        for icon_dir in icon_dirs:
            if os.path.exists(icon_dir) and os.path.isdir(icon_dir):
                # Add standard filenames
                search_paths.extend(
                    [
                        os.path.join(icon_dir, "icon.svg"),
                        os.path.join(icon_dir, "icon.png"),
                        os.path.join(icon_dir, "icon.jpg"),
                        os.path.join(icon_dir, "logo.svg"),
                        os.path.join(icon_dir, "logo.png"),
                        # Also add any image files in the directory
                        *[
                            os.path.join(icon_dir, f)
                            for f in os.listdir(icon_dir)
                            if os.path.isfile(os.path.join(icon_dir, f))
                            and any(
                                f.lower().endswith(ext) for ext in [".svg", ".png", ".jpg", ".jpeg"]
                            )
                        ],
                    ]
                )

        # Also check the fallback legacy locations (for backward compatibility)
        search_paths.extend(
            [
                os.path.join(icon_base_dir, "scalable/apps", f"{app_name}.svg"),
                os.path.join(icon_base_dir, "256x256/apps", f"{app_name}.png"),
                os.path.join(icon_base_dir, "scalable/apps", f"{self.repo}.svg"),
                os.path.join(icon_base_dir, "256x256/apps", f"{self.repo}.png"),
                # Fall back to generic icon locations
                os.path.expanduser(f"~/.local/share/icons/{app_name}.png"),
                os.path.expanduser(f"~/.local/share/icons/{app_name}.svg"),
                os.path.expanduser(f"~/.local/share/icons/{self.repo}.png"),
                os.path.expanduser(f"~/.local/share/icons/{self.repo}.svg"),
            ]
        )

        # Check each location for a valid icon file
        for icon_path in search_paths:
            try:
                if os.path.exists(icon_path) and os.path.isfile(icon_path):
                    logging.debug(f"Found icon at: {icon_path}")
                    return icon_path
            except Exception:
                # Skip any paths that cause errors (e.g., permission issues)
                continue

        logging.debug(f"No icon found for {app_name} or {self.repo}")
        return None

    def download_app_icon(self, owner: str, repo: str) -> Tuple[bool, str]:
        """
        Download application icon from GitHub repository if it doesn't exist locally.

        Uses the IconManager to find and download the best icon for the repository.
        Icons are stored in ~/.local/share/icons/myunicorn/<repo>/ directory.

        Args:
            owner: Repository owner
            repo: Repository name (original case preserved)

        Returns:
            tuple: (success, message) where success is a boolean and message is
                  a descriptive string
        """
        try:
            # Generate app identifier for icon directory naming
            from src.app_config import AppConfigManager

            app_config = AppConfigManager(owner=owner, repo=repo)
            app_id = app_config.repo

            # This ensures consistency with other file naming throughout the application
            icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")

            app_id_icon_dir = os.path.join(icon_base_dir, app_id)

            # Also check the repo directory (for backward compatibility)
            repo_icon_dir = os.path.join(icon_base_dir, repo)

            # Ensure primary icon directory exists
            os.makedirs(app_id_icon_dir, exist_ok=True)

            target_icon_dir = app_id_icon_dir

            # Check if icon already exists in either directory
            for check_dir in [app_id_icon_dir, repo_icon_dir]:
                if os.path.exists(check_dir):
                    for ext in [".svg", ".png", ".jpg", ".jpeg"]:
                        icon_path = os.path.join(check_dir, f"icon{ext}")
                        if os.path.exists(icon_path):
                            logging.info(f"Icon already exists at {icon_path}")
                            return True, icon_path

            # Initialize GitHub API for authentication headers
            from src.api import GitHubAPI

            github_api = GitHubAPI(owner=owner, repo=repo)

            # Import and use IconManager with our enhanced search logic
            from src.icon_manager import IconManager

            icon_manager = IconManager()

            # Find icon using the improved manager
            icon_info = icon_manager.find_icon(owner, repo, headers=github_api._headers)

            if not icon_info:
                # This is a valid use case - some apps work with system theme icons
                message = (
                    f"No icon configuration found for {owner}/{repo}. "
                    f"Desktop entry will use the app name ('{repo}') which may work with "
                    f"system icon themes like Papirus or Adwaita."
                )
                logging.info(message)
                return True, message

            # Download the icon to the target directory
            success, result_path = icon_manager.download_icon(icon_info, target_icon_dir)

            if success:
                logging.info(f"Successfully downloaded icon to {result_path}")
                return True, result_path
            else:
                logging.error(f"Failed to download icon: {result_path}")
                return False, result_path

        except Exception as e:
            logging.error(f"Failed to download icon: {str(e)}")
            # Provide a more descriptive message when the fallback is "default"
            if str(e) == "'default'":
                return False, (
                    f"Icon path not defined for {repo}. Desktop entry will use the app name, "
                    f"which may work with system icon themes like Papirus or Adwaita."
                )
            return False, f"Error: {str(e)}"
