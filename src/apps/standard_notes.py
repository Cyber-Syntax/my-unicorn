#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standard Notes application-specific handler.

This module provides customizations for Standard Notes AppImage handling.
"""

import logging
import os
import re
from typing import Tuple, Optional

from src.app_config import AppConfigManager

# Configure module logger
logger = logging.getLogger(__name__)


class StandardNotesHandler:
    """
    Handler for Standard Notes application-specific functionality.

    Provides customizations for Standard Notes including proper display name
    and desktop file management.
    """

    @staticmethod
    def create_desktop_file(
        app_config: AppConfigManager, appimage_path: str, icon_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create a customized desktop entry file for Standard Notes.

        Overrides the default desktop file creation to use "Standard Notes"
        as the display name instead of the repository name "app".

        Args:
            app_config: The application configuration manager
            appimage_path: Full path to the AppImage file
            icon_path: Path to the icon file, if available

        Returns:
            Tuple[bool, str]: Success status and error message or filepath if successful
        """
        try:
            # Ensure desktop file directory exists
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)

            # Use standardnotes for the desktop filename instead of app_id (which is 'app')
            desktop_file_path = os.path.join(desktop_dir, "standardnotes.desktop")
            desktop_file_temp = f"{desktop_file_path}.tmp"

            # Use "Standard Notes" as the display name
            display_name = "Standard Notes"

            # Determine icon path (using app_config's logic for finding icons)
            final_icon_path = icon_path
            if not final_icon_path:
                # Define icon locations using both standardnotes and repository-based structure
                icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")
                # Try standardnotes directory first
                std_notes_icon_dir = os.path.join(icon_base_dir, "standardnotes")
                app_icon_dir = os.path.join(icon_base_dir, app_config.app_id)

                # Check for icons in standardnotes directory first
                icon_locations = [
                    os.path.join(std_notes_icon_dir, "icon.svg"),
                    os.path.join(std_notes_icon_dir, "icon.png"),
                    # Then check app_id directory
                    os.path.join(app_icon_dir, "icon.svg"),
                    os.path.join(app_icon_dir, "icon.png"),
                ]

                # Check each location for an existing icon
                for location in icon_locations:
                    if os.path.exists(location):
                        final_icon_path = location
                        logger.info(f"Using existing icon at: {final_icon_path}")
                        break

            # Parse existing desktop file if it exists
            existing_entries = {}
            if os.path.exists(desktop_file_path):
                try:
                    with open(desktop_file_path, "r", encoding="utf-8") as f:
                        section = None
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue

                            # Check for section headers [SectionName]
                            if line.startswith("[") and line.endswith("]"):
                                section = line[1:-1]
                                continue

                            # Only process lines with key=value format in Desktop Entry section
                            if section == "Desktop Entry" and "=" in line:
                                key, value = line.split("=", 1)
                                existing_entries[key.strip()] = value.strip()

                    logger.info(f"Found existing desktop file: {desktop_file_path}")
                except Exception as e:
                    logger.warning(f"Error reading existing desktop file: {e}")

            # Create new desktop file content
            new_entries = {
                "Name": display_name,
                "Exec": appimage_path,
                "Terminal": "false",
                "Type": "Application",
                "Comment": "Standard Notes - A free, open-source, and completely encrypted notes app",
                "Categories": "Office;Notes;Utility;",
                "StartupWMClass": "Standard Notes",
            }

            # Add icon if available
            if final_icon_path:
                new_entries["Icon"] = final_icon_path

            # Check if content would actually change to avoid unnecessary writes
            needs_update = False
            for key, value in new_entries.items():
                if key not in existing_entries or existing_entries[key] != value:
                    needs_update = True
                    break

            # If no update needed, return early
            if not needs_update:
                logger.info(f"Desktop file {desktop_file_path} already up to date")
                return True, desktop_file_path

            # Write to temporary file for atomic replacement
            with open(desktop_file_temp, "w", encoding="utf-8") as f:
                f.write("[Desktop Entry]\n")
                for key, value in new_entries.items():
                    f.write(f"{key}={value}\n")

                # Preserve additional entries that we don't explicitly set
                for key, value in existing_entries.items():
                    if key not in new_entries:
                        f.write(f"{key}={value}\n")

            # Ensure proper permissions on the temp file
            os.chmod(desktop_file_temp, 0o755)  # Make executable

            # Atomic replace
            os.replace(desktop_file_temp, desktop_file_path)

            logger.info(f"Updated desktop file at {desktop_file_path}")
            return True, desktop_file_path

        except Exception as e:
            error_msg = f"Failed to create/update Standard Notes desktop file: {e}"
            logger.error(error_msg)
            # Clean up temp file if exists
            if "desktop_file_temp" in locals() and os.path.exists(desktop_file_temp):
                try:
                    os.remove(desktop_file_temp)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
            return False, error_msg
    
    #TODO: Need better way to handle this in api.py
    @staticmethod
    def extract_version(appimage_name: str) -> str:
        """
        Extract the version from the AppImage file name or repository tag.

        Handles both Standard Notes version formats:
        - Standard format: app-3.195.13-x86_64.AppImage
        - Package format: @standardnotes/desktop@3.195.13

        Args:
            appimage_name: The name of the AppImage file or tag string

        Returns:
            The extracted version string or "unknown" if not found
        """
        # Handle the @standardnotes/desktop@3.195.13 format
        std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", appimage_name)
        if std_notes_match:
            return std_notes_match.group(1)

        # Handle standard format: app-3.195.13-x86_64.AppImage
        match = re.search(r"-(\d+\.\d+\.\d+)", appimage_name)
        if match:
            return match.group(1)

        return "unknown"
