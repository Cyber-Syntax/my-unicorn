#!/usr/bin/env python3
"""Desktop entry management module.

This module provides functionality for creating and managing desktop entries
for AppImage applications following the freedesktop.org specifications.
"""

from __future__ import annotations

import logging
import stat
from pathlib import Path

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DESKTOP_ENTRY_DIR = Path("~/.local/share/applications").expanduser()
DESKTOP_ENTRY_FILE_MODE = stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
DESKTOP_FILE_SECTION = "Desktop Entry"
DEFAULT_CATEGORIES = "Utility;"
BROWSER_CATEGORIES = "Network;WebBrowser;"

# Known browser names (case-insensitive patterns)
BROWSER_KEYWORDS = {
    "firefox",
    "chrome",
    "chromium",
    "brave",
    "opera",
    "edge",
    "safari",
    "zen-browser",
    "zen",
    "vivaldi",
    "waterfox",
    "librewolf",
    "tor-browser",
    "tor",
    "epiphany",
    "konqueror",
    "falkon",
    "qutebrowser",
    "midori",
    "seamonkey",
    "palemoon",
    "basilisk",
    "icecat",
    "iceweasel",
}

# MIME types for web browsers
BROWSER_MIME_TYPES = [
    "text/html",
    "text/xml",
    "application/xhtml+xml",
    "application/xml",
    "application/rss+xml",
    "application/rdf+xml",
    "image/gif",
    "image/jpeg",
    "image/png",
    "x-scheme-handler/http",
    "x-scheme-handler/https",
    "x-scheme-handler/ftp",
    "x-scheme-handler/chrome",
    "video/webm",
    "application/x-xpinstall",
]


class DesktopEntryManager:
    """Manages desktop entry file operations.

    This class provides methods for reading, writing, and managing desktop entry files
    according to the freedesktop.org Desktop Entry Specification.

    Example:
        # Create a desktop entry for an AppImage
        desktop_manager = DesktopEntryManager()
        result = desktop_manager.create_or_update_desktop_entry(
            app_rename="MyApp",
            appimage_path="/path/to/MyApp.AppImage",
            icon_path="/path/to/MyApp/icon.png"
        )

    """

    def __init__(self, desktop_dir: Path = DESKTOP_ENTRY_DIR) -> None:
        """Initialize the desktop entry manager.

        Args:
            desktop_dir: Path to the desktop entry directory.
                Defaults to ~/.local/share/applications.

        """
        self.desktop_dir = desktop_dir

        # Ensure desktop directory exists
        self.desktop_dir.mkdir(parents=True, exist_ok=True)

    def is_browser_app(self, app_name: str) -> bool:
        """Determine if an application is a web browser based on its name.

        Args:
            app_name: The application name to check

        Returns:
            True if the application appears to be a browser, False otherwise

        """
        app_name_lower = app_name.lower()

        # Check if any browser keyword is contained in the app name
        return any(keyword in app_name_lower for keyword in BROWSER_KEYWORDS)

    def read_desktop_file(self, desktop_path: Path) -> dict[str, str]:
        """Read an existing desktop entry file and parse its contents.

        Args:
            desktop_path: Path to the desktop entry file

        Returns:
            Dictionary of key-value pairs from the desktop file

        """
        entries = {}
        if not desktop_path.exists():
            return entries

        try:
            with desktop_path.open("r", encoding="utf-8") as f:
                section = None
                for content_line in f:
                    stripped_line = content_line.strip()
                    if not stripped_line:
                        continue
                    if stripped_line.startswith("[") and stripped_line.endswith("]"):
                        section = stripped_line[1:-1]  # Extract section name without brackets
                        continue
                    if section == DESKTOP_FILE_SECTION and "=" in stripped_line:
                        key, value = stripped_line.split("=", 1)
                        entries[key.strip()] = value.strip()
            logger.info("Found existing desktop file: %s", desktop_path)
        except OSError as e:
            logger.warning("Error reading existing desktop file (OS error): %s", e)
        except Exception as e:
            logger.warning("Unexpected error reading desktop file: %s", e)

        return entries

    def needs_update(self, existing_entries: dict[str, str], new_entries: dict[str, str]) -> bool:
        """Check if desktop entry needs an update.

        Args:
            existing_entries: Existing desktop entry key-value pairs
            new_entries: New desktop entry key-value pairs

        Returns:
            True if update is needed, False otherwise

        """
        for key, new_value in new_entries.items():
            if key not in existing_entries or existing_entries[key] != new_value:
                logger.info("Desktop entry update needed: %s changed", key)
                return True
        return False

    def write_desktop_file(
        self, desktop_path: Path, new_entries: dict[str, str], existing_entries: dict[str, str]
    ) -> bool:
        """Write desktop entry file with atomic operation pattern.

        Args:
            desktop_path: Path to the desktop entry file
            new_entries: New entries to write
            existing_entries: Existing entries to preserve if not overwritten

        Returns:
            True if file was written successfully

        """
        try:
            temp_path = desktop_path.with_suffix(".tmp")
            with temp_path.open("w", encoding="utf-8") as f:
                f.write(f"[{DESKTOP_FILE_SECTION}]\n")

                # Write new entries
                for key, value in new_entries.items():
                    f.write(f"{key}={value}\n")

                # Preserve additional entries from existing file
                for key, value in existing_entries.items():
                    if key not in new_entries:
                        f.write(f"{key}={value}\n")

            # set proper executable permissions
            temp_path.chmod(temp_path.stat().st_mode | DESKTOP_ENTRY_FILE_MODE)

            # Replace original file with temp file (atomic operation)
            temp_path.replace(desktop_path)

            logger.info("Updated desktop entry at %s", desktop_path)
            return True
        except OSError as e:
            logger.error("Failed to write desktop file (OS error): %s", e)
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_error:
                    logger.warning("Failed to clean up temporary file: %s", cleanup_error)
            return False
        except Exception as e:
            logger.error("Unexpected error writing desktop file: %s", e)
            # Clean up temp file if it exists
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception as cleanup_error:
                    logger.warning("Failed to clean up temporary file: %s", cleanup_error)
            return False

    def create_or_update_desktop_entry(
        self,
        app_rename: str,
        appimage_path: str | Path,
        icon_path: str | Path | None = None,
        is_browser: bool | None = None,
    ) -> tuple[bool, str]:
        """Create or update a desktop entry file for an AppImage.

        Creates a standard conformant desktop entry file with proper permissions and icon support.
        Avoids unnecessary writes by comparing content with existing file.

        Args:
            app_rename: Unique identifier for the application
            appimage_path: Path to the AppImage executable
            icon_path: Optional path to the application icon
            is_browser: Optional explicit flag to mark app as browser. If None, auto-detects based on app name.

        Returns:
            tuple of (success, message)
                - success: True if desktop entry was created/updated/unchanged
                - message: Path to desktop file or error message

        """
        try:
            if not app_rename:
                return False, "Application identifier cannot be empty"

            # Convert paths to Path objects if they're strings
            if isinstance(appimage_path, str):
                appimage_path = Path(appimage_path)

            if icon_path and isinstance(icon_path, str):
                icon_path = Path(icon_path)

            # Create desktop file path
            desktop_file = f"{app_rename.lower()}.desktop"
            desktop_path = self.desktop_dir / desktop_file

            logger.info("Processing desktop entry at %s", desktop_path)

            # Read existing desktop file
            existing_entries = self.read_desktop_file(desktop_path)

            # Determine if this is a browser application
            if is_browser is None:
                is_browser = self.is_browser_app(app_rename)

            if is_browser:
                logger.info("Detected browser application: %s", app_rename)

            # Create Exec field - add %u for browsers to handle URLs
            exec_cmd = str(appimage_path)
            if is_browser:
                exec_cmd += " %u"
                logger.info("Added %u parameter for browser URL handling")

            # Create new desktop entry content
            new_entries = {
                "Type": "Application",
                "Name": app_rename,  # Use app_rename for display name
                "Exec": exec_cmd,
                "Terminal": "false",
                "Categories": BROWSER_CATEGORIES if is_browser else DEFAULT_CATEGORIES,
                "Comment": f"{'Web Browser' if is_browser else 'AppImage'} for {app_rename}",
            }

            # Add browser-specific MIME types
            if is_browser:
                new_entries["MimeType"] = ";".join(BROWSER_MIME_TYPES) + ";"
                new_entries["StartupNotify"] = "true"
                logger.info("Added browser MIME types and startup notification")

            # Add icon if available
            if icon_path:
                new_entries["Icon"] = str(icon_path)
                logger.info("Using icon from: %s", icon_path)
            else:
                logger.info("No icon specified for desktop entry")

            # Check if update is needed
            if not self.needs_update(existing_entries, new_entries):
                logger.info("Desktop entry %s is already up to date", desktop_path)
                return True, str(desktop_path)

            # Write updated desktop file
            if self.write_desktop_file(desktop_path, new_entries, existing_entries):
                return True, str(desktop_path)
            else:
                return False, f"Failed to write desktop entry at {desktop_path}"

        except OSError as e:
            logger.error("Failed to create desktop entry due to file system error: %s", e)
            return False, "Failed to create desktop entry due to file system error: %s" % e
        except Exception as e:
            logger.error("Unexpected error creating desktop entry: %s", e)
            return False, "Unexpected error creating desktop entry: %s" % e
