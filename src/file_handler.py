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

import requests

from src.api import GitHubAPI


class FileHandler:
    """
    Handles file operations for AppImage management.

    This class provides methods for:
    - Moving AppImage files to installation directories
    - Creating and updating .desktop files
    - Managing backup files
    - Setting proper file permissions
    """

    def __init__(
        self,
        appimage_name: str,
        repo: str,
        version: str,
        sha_name: str,
        config_file: str,
        appimage_download_folder_path: str,
        appimage_download_backup_folder_path: str,
        config_folder: str,
        config_file_name: str,
        batch_mode: bool = False,
        keep_backup: bool = True,
    ):
        """
        Initialize file handler with paths and configuration.

        Args:
            appimage_name: Name of the AppImage file
            repo: Repository name (original case preserved)
            version: AppImage version
            sha_name: SHA file name
            config_file: Path to global config file
            appimage_download_folder_path: Directory where AppImages are stored
            appimage_download_backup_folder_path: Directory for backup AppImages
            config_folder: Directory for configuration files
            config_file_name: Name of configuration file
            batch_mode: Whether to run in batch mode (no user prompts)
            keep_backup: Whether to keep backup files
        """
        self.appimage_name = appimage_name
        self.repo = repo
        self.version = version
        self.sha_name = sha_name
        self.config_file = config_file
        self.appimage_download_folder_path = appimage_download_folder_path
        self.appimage_download_backup_folder_path = appimage_download_backup_folder_path
        self.config_folder = config_folder
        self.config_file_name = config_file_name
        self.batch_mode = batch_mode
        self.keep_backup = keep_backup

        # Derived paths
        # Construct the AppImage file path with proper .AppImage extension if missing.
        file_name = self.repo
        if not file_name.lower().endswith(".appimage"):
            file_name += ".AppImage"
        self.appimage_path = os.path.join(self.appimage_download_folder_path, file_name)
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
        Backup existing AppImage file.

        Returns:
            bool: True if backup succeeded or was skipped, False otherwise
        """
        try:
            # Check if the backup folder exists or create it
            os.makedirs(self.appimage_download_backup_folder_path, exist_ok=True)

            # Check if a current backup exists
            if os.path.exists(self.backup_path):
                if self.keep_backup:
                    # Create a unique backup name with timestamp
                    import time

                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    backup_name = f"{os.path.splitext(self.appimage_name)[0]}_{timestamp}.AppImage"
                    new_backup_path = os.path.join(
                        self.appimage_download_backup_folder_path, backup_name
                    )
                    # Copy existing backup to timestamped backup
                    shutil.move(self.backup_path, new_backup_path)
                    logging.info(f"Created historical backup: {backup_name}")
                else:
                    # Remove old backup
                    os.remove(self.backup_path)
                    logging.info(f"Removed old backup: {self.backup_path}")

            # Move current AppImage to backup
            logging.info(f"Backing up {self.appimage_path} to {self.backup_path}")
            shutil.move(self.appimage_path, self.backup_path)
            return True

        except Exception as e:
            logging.error(f"Failed to backup AppImage: {str(e)}")
            return False

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
            # Define paths
            app_name = self.repo  # Preserve original case for display name
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            desktop_file = f"{app_name.lower()}.desktop"  # Lowercase for filename
            desktop_path = os.path.join(desktop_dir, desktop_file)

            logging.info(f"Processing desktop entry at {desktop_path}")

            # Ensure desktop directory exists
            os.makedirs(desktop_dir, exist_ok=True)

            # Get icon path if available
            icon_path = self._get_icon_path(app_name)

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
        ~/.local/share/icons/myunicorn/<repo>/icon.(svg|png|jpg)

        Args:
            app_name: Name of the application (original case preserved)

        Returns:
            str or None: Path to icon file or None if not found
        """
        # Base icon directory for myunicorn
        icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")

        # Primary search location: repo-specific directory
        repo_icon_dir = os.path.join(icon_base_dir, app_name)

        # Search paths in priority order (SVG is highest priority)
        search_paths = [
            # First check repo-specific directory with standard filenames
            os.path.join(repo_icon_dir, "icon.svg"),
            os.path.join(repo_icon_dir, "icon.png"),
            os.path.join(repo_icon_dir, "icon.jpg"),
            os.path.join(repo_icon_dir, "logo.svg"),
            os.path.join(repo_icon_dir, "logo.png"),
            # Also check for any files in the repo directory
            *[
                os.path.join(repo_icon_dir, f)
                for f in os.listdir(repo_icon_dir)
                if os.path.exists(repo_icon_dir) and os.path.isdir(repo_icon_dir)
            ],
            # Check the fallback legacy locations (for backward compatibility)
            os.path.join(icon_base_dir, "scalable/apps", f"{app_name}.svg"),
            os.path.join(icon_base_dir, "256x256/apps", f"{app_name}.png"),
            # Fall back to generic icon locations
            os.path.expanduser(f"~/.local/share/icons/{app_name}.png"),
            os.path.expanduser(f"~/.local/share/icons/{app_name}.svg"),
        ]

        # Check each location
        for icon_path in search_paths:
            if os.path.exists(icon_path):
                logging.debug(f"Found icon at: {icon_path}")
                return icon_path

        logging.debug(f"No icon found for {app_name}")
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
            # Set up proper icon directory structure using the repo name directly
            icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")
            repo_icon_dir = os.path.join(icon_base_dir, repo)

            # Ensure icon directories exist
            os.makedirs(repo_icon_dir, exist_ok=True)

            # Check if icon already exists in repository directory
            for ext in [".svg", ".png", ".jpg", ".jpeg"]:
                icon_path = os.path.join(repo_icon_dir, f"icon{ext}")
                if os.path.exists(icon_path):
                    logging.info(f"Icon already exists at {icon_path}")
                    return True, f"Icon already exists at {icon_path}"

            # Initialize GitHub API for authentication headers
            from src.api import GitHubAPI

            github_api = GitHubAPI(owner=owner, repo=repo)

            # Import and use IconManager with our enhanced search logic
            from src.icon_manager import IconManager

            icon_manager = IconManager()

            # Find icon using the improved manager
            icon_info = icon_manager.find_icon(owner, repo, headers=github_api._headers)

            if not icon_info:
                return False, "No suitable icon found in repository"

            # Download the icon to repo-specific directory
            success, result_path = icon_manager.download_icon(icon_info, repo_icon_dir)

            if success:
                logging.info(f"Successfully downloaded icon to {result_path}")
                return True, result_path
            else:
                logging.error(f"Failed to download icon: {result_path}")
                return False, result_path

        except Exception as e:
            logging.error(f"Failed to download icon: {str(e)}")
            return False, f"Error: {str(e)}"
