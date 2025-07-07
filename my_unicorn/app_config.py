"""Application configuration management module.

This module provides functionality for managing application-specific configurations
including creating desktop entries, managing versions, and storing app settings.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Local imports
from my_unicorn.catalog import load_app_definition
from my_unicorn.utils.desktop_entry import DesktopEntryManager

# Configure module logger
logger = logging.getLogger(__name__)

# Constants
DEFAULT_CONFIG_PATH = "~/.config/myunicorn/apps/"
DESKTOP_ENTRY_DIR = "~/.local/share/applications"
ICON_BASE_DIR = "~/.local/share/icons/myunicorn"
DESKTOP_ENTRY_PERMISSIONS = 0o755

# Image file extensions
IMAGE_EXTENSIONS = [".svg", ".png", ".jpg", ".jpeg"]

# Maximum configuration option for selection
MAX_CONFIG_OPTION = 3


@dataclass
class AppConfigManager:
    """Manages app-specific configuration settings.

    This class handles operations related to application configuration including
    creating desktop files, managing versions, and storing app-specific settings.

    Note: Static app metadata (owner, repo, checksum_file_name, etc.) is now loaded from
    JSON app definitions. Only user-specific data is stored in config files.
    """

    # Core user-specific fields (stored in config files)
    version: str | None = None
    appimage_name: str | None = None

    # Configuration management
    config_folder: Path = field(default_factory=lambda: Path(DEFAULT_CONFIG_PATH).expanduser())

    # App identification (set when loading config)
    app_name: str | None = field(init=False, default=None)

    # These fields are calculated in __post_init__ and not directly initialized
    config_file_name: str | None = field(init=False, default=None)
    config_file: Path | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        """Post-initialization to handle derived attributes."""
        # Ensure the configuration directory exists
        self.config_folder.mkdir(parents=True, exist_ok=True)

    def set_app_name(self, app_name: str) -> None:
        """Set the app name and update derived paths.

        Args:
            app_name: Name of the application (used for config file naming)

        """
        self.app_name = app_name
        self.config_file_name = f"{app_name}.json"
        self.config_file = self.config_folder / self.config_file_name

    def get_app_info(self):
        """Get app info from JSON definition.

        Returns:
            AppInfo object if found, None otherwise

        """
        if not self.app_name:
            logger.warning("Cannot get app info: app_name not set")
            return None
        return load_app_definition(self.app_name)

    @property
    def owner(self) -> str | None:
        """Get owner from app definition."""
        app_info = self.get_app_info()
        return app_info.owner if app_info else None

    @property
    def repo(self) -> str | None:
        """Get repo from app definition."""
        app_info = self.get_app_info()
        return app_info.repo if app_info else None

    @property
    def app_rename(self) -> str | None:
        """Get display name from app definition."""
        app_info = self.get_app_info()
        return app_info.app_rename if app_info else self.app_name

    @property
    def skip_verification(self) -> bool:
        """Get skip verification flag from app definition."""
        app_info = self.get_app_info()
        return app_info.skip_verification if app_info else False

    @property
    def use_asset_digest(self) -> bool:
        """Get use asset digest flag from app definition."""
        app_info = self.get_app_info()
        return app_info.use_asset_digest if app_info else False

    @property
    def use_github_release_desc(self) -> bool:
        """Get use_github_release_desc flag from app definition."""
        app_info = self.get_app_info()
        return app_info.use_github_release_desc if app_info else False

    @property
    def checksum_file_name(self) -> str | None:
        """Get SHA name from app definition."""
        app_info = self.get_app_info()
        if app_info and app_info.use_asset_digest:
            return "asset_digest"
        if app_info and app_info.use_github_release_desc:
            return "extracted_checksum"
        return app_info.checksum_file_name if app_info else None

    @property
    def checksum_hash_type(self) -> str | None:
        """Get hash type from app definition."""
        app_info = self.get_app_info()
        if app_info and app_info.use_asset_digest:
            return "asset_digest"
        if app_info and app_info.use_github_release_desc:
            return "extracted_checksum"
        return app_info.checksum_hash_type if app_info else None

    @property
    def preferred_characteristic_suffixes(self) -> list[str]:
        """Get preferred characteristic suffixes from app definition."""
        app_info = self.get_app_info()
        return app_info.preferred_characteristic_suffixes if app_info else []

    @property
    def icon_info(self) -> str | None:
        """Get icon info from app definition."""
        app_info = self.get_app_info()
        return app_info.icon_info if app_info else None

    @property
    def icon_file_name(self) -> str | None:
        """Get icon file name from app definition."""
        app_info = self.get_app_info()
        return app_info.icon_file_name if app_info else None

    @property
    def icon_repo_path(self) -> str | None:
        """Get icon repo path from app definition."""
        app_info = self.get_app_info()
        return app_info.icon_repo_path if app_info else None

    def update_version(
        self, new_version: str | None = None, new_appimage_name: str | None = None
    ) -> None:
        """Update the configuration file with the new version and AppImage name.

        Args:
            new_version: New version to update to
            new_appimage_name: New AppImage filename

        """
        try:
            if new_version is not None:
                self.version = new_version
            if new_appimage_name is not None:
                self.appimage_name = new_appimage_name

            if not self.config_file:
                logger.error("Config file path is not set")
                return

            config_data: dict[str, Any] = {}

            if self.config_file.exists():
                with self.config_file.open("r", encoding="utf-8") as file:
                    config_data = json.load(file)

            # Update only user-specific information in the configuration data
            config_data["version"] = self.version
            config_data["appimage_name"] = self.appimage_name

            with self.config_file.open("w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=4)

            logger.info("Updated configuration in %s", self.config_file)
        except json.JSONDecodeError as e:
            logger.error("Error decoding JSON: %s", e)
        except Exception as e:
            logger.error("An error occurred while updating version: %s", e)

    def create_desktop_file(
        self, appimage_path: str | Path, icon_path: str | Path | None = None
    ) -> tuple[bool, str]:
        """Create or update a desktop entry file for the AppImage.

        Args:
            appimage_path: Path to the AppImage executable
            icon_path: Optional path to the application icon

        Returns:
            tuple[bool, str]: Success status and path to desktop file or error message

        """
        try:
            if not self.app_rename:
                return False, "Application identifier not available"

            # Convert paths to Path objects if they're strings
            if isinstance(appimage_path, str):
                appimage_path_obj = Path(appimage_path)
            else:
                appimage_path_obj = appimage_path

            if icon_path and isinstance(icon_path, str):
                icon_path_obj = Path(icon_path)
            elif icon_path:
                icon_path_obj = icon_path
            else:
                icon_path_obj = None

            # Use the DesktopEntryManager to handle desktop entry operations
            desktop_manager = DesktopEntryManager()
            return desktop_manager.create_or_update_desktop_entry(
                app_rename=self.app_rename,
                appimage_path=appimage_path_obj,
                icon_path=icon_path_obj,
            )

        except Exception as e:
            logger.error("Failed to create/update desktop file: %s", e)
            return False, "Failed to create/update desktop file: %s" % e

    def list_json_files(self) -> list[str]:
        """List JSON files in the configuration directory.

        Returns:
            list[str]: list of JSON files in the configuration directory

        Raises:
            FileNotFoundError: If the configuration folder doesn't exist

        """
        try:
            self.config_folder.mkdir(parents=True, exist_ok=True)
            json_files = [
                file.name for file in self.config_folder.iterdir() if file.suffix == ".json"
            ]
            return sorted(json_files) if json_files else []
        except (FileNotFoundError, PermissionError) as error:
            logger.error("Error accessing configuration folder: %s", error)
            raise FileNotFoundError("Configuration folder access error: %s" % error) from error

    def temp_save_config(self) -> bool:
        """Atomically save configuration using temporary file.

        Returns:
            bool: True if save successful, False otherwise

        """
        if not self.config_file:
            logger.error("Config file path is not set")
            return False

        temp_file = Path(f"{self.config_file}.tmp")
        try:
            temp_file.parent.mkdir(parents=True, exist_ok=True)

            # Write complete current state to temp file
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(self.to_dict(), file, indent=4)

            logger.info("Temporary config saved to %s", temp_file)
            return True
        except Exception as e:
            logger.error("Temp config save failed: %s", e)
            # Cleanup if possible
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as cleanup_error:
                    logger.warning("Failed to clean up temporary file: %s", cleanup_error)
            return False

    def save_config(self) -> bool:
        """Commit temporary config by replacing original.

        Returns:
            bool: True if commit successful, False otherwise

        """
        if not self.config_file:
            logger.error("Config file path is not set")
            return False

        temp_file = Path(f"{self.config_file}.tmp")
        try:
            # First save to temporary file
            if not self.temp_save_config():
                return False

            # Atomic replace operation
            temp_file.replace(self.config_file)
            logger.info("Configuration committed to %s", self.config_file)
            return True

        except Exception as e:
            logger.error("Config commit failed: %s", e)
            # Cleanup temp file if it exists
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except Exception as cleanup_error:
                    logger.warning("Failed to clean up temporary file: %s", cleanup_error)
            return False

    def select_files(self) -> list[str] | None:
        """List available JSON configuration files and allow the user to select multiple.

        Shows application names without the .json extension for better readability.

        Returns:
            list[str] or None: list of selected JSON files or None if no selection made

        """
        try:
            json_files = self.list_json_files()
            if not json_files:
                logger.warning("No configuration files found. Please create one first.")
                print("No configuration files found. Please create one first.")
                return None

            # Display app names without the .json extension
            logger.info("Displaying available configuration files")
            print("Available applications:")
            for idx, json_file in enumerate(json_files, start=1):
                # Display just the app name without .json extension
                app_name = Path(json_file).stem
                print(f"{idx}. {app_name}")

            user_input = input(
                "Select application(s) (comma-separated numbers) or cancel: "
            ).strip()

            try:
                selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
                if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                    raise ValueError("Invalid selection.")
                logger.info(
                    "User selected files: %s", [json_files[idx] for idx in selected_indices]
                )
                return [json_files[idx] for idx in selected_indices]
            except (ValueError, IndexError):
                logger.error("Invalid selection. Please enter valid numbers.")
                return None
        except KeyboardInterrupt:
            logger.info("User cancelled the selection.")
            print("\nSelection cancelled.")
            return None

    def load_appimage_config(self, config_file_name: str) -> dict[str, Any] | None:
        """Load a specific AppImage configuration file.

        Args:
            config_file_name: Name of the configuration file

        Returns:
            tuple or None: Loaded configuration or None if file not found

        Raises:
            ValueError: If JSON parsing fails

        """
        config_file_path = self.config_folder / config_file_name
        if config_file_path.is_file():
            try:
                with config_file_path.open("r", encoding="utf-8") as file:
                    config = json.load(file)

                    # Extract app name from filename and set it
                    app_name = Path(config_file_name).stem
                    self.set_app_name(app_name)

                    # Update instance variables with the loaded user-specific config
                    self.version = config.get("version", self.version)
                    self.appimage_name = config.get("appimage_name", self.appimage_name)

                    logger.info("Successfully loaded configuration from %s", config_file_name)
                    return config
            except json.JSONDecodeError as e:
                logger.error("Invalid JSON in the configuration file: %s", e)
                raise ValueError("Failed to parse JSON from the configuration file.") from e
        else:
            logger.warning("Configuration file %s not found.", config_file_name)
            return None

    def reload(self) -> bool:
        """Explicitly reload the current app configuration from disk.

        Reloads the configuration for the currently loaded app, if any.
        This ensures any external changes to the configuration file are loaded.

        Returns:
            bool: True if config was successfully reloaded, False otherwise

        """
        logger.info("Explicitly reloading app configuration from disk")
        if self.config_file_name is None:
            logger.warning("Cannot reload: No app configuration is currently loaded")
            return False

        try:
            self.load_appimage_config(self.config_file_name)
            return True
        except Exception as e:
            logger.error("Failed to reload app configuration: %s", e)
            return False

    def customize_appimage_config(self) -> None:
        """Customize the configuration settings for an AppImage."""
        json_files = self.list_json_files()
        if not json_files:
            logger.warning("No JSON configuration files found.")
            print("No JSON configuration files found.")
            return

        logger.info("Displaying available JSON files for customization")
        print("Available applications:")
        for idx, file in enumerate(json_files, 1):
            # Display just the app name without .json extension
            app_name = Path(file).stem
            print(f"{idx}. {app_name}")
        print(f"{len(json_files) + 1}. Cancel")

        # Continue with standard interface
        selected_file = self._get_user_selection(json_files)
        if not selected_file:
            return

        selected_file_path = self.config_folder / selected_file
        self.load_appimage_config(selected_file)
        self.config_file = selected_file_path  # Override to ensure saving to the selected file

        # Show application name in title instead of filename
        app_name = Path(selected_file).stem
        logger.info("Displaying configuration options for %s", app_name)

        # Show current configuration and menu
        self._display_config_info(app_name)
        self._handle_config_customization(app_name)

    def _get_user_selection(self, json_files: list[str]) -> str | None:
        """Get user's file selection.

        Args:
            json_files: list of JSON files to choose from

        Returns:
            Selected file name or None if cancelled

        """
        while True:
            file_choice = input("Select an application (number) or cancel: ")
            if not file_choice.isdigit():
                logger.warning("Invalid input. Please enter a number.")
                print("Please enter a number.")
                continue

            file_choice_num = int(file_choice)
            if 1 <= file_choice_num <= len(json_files):
                return json_files[file_choice_num - 1]
            elif file_choice_num == len(json_files) + 1:
                logger.info("Configuration customization cancelled by user")
                print("Operation cancelled.")
                return None
            else:
                logger.warning("Invalid choice. Please select a valid number.")
                print("Invalid choice. Please select a valid number.")

    def _display_config_info(self, app_name: str) -> None:
        """Display current configuration information.

        Args:
            app_name: Name of the application

        """
        print("\n" + "=" * 60)
        print(f"Configuration for: {app_name}")
        print("-" * 60)
        print("Static Information (from app definition):")
        print(f"  Owner: {self.owner or 'Not found'}")
        print(f"  Repository: {self.repo or 'Not found'}")
        print(f"  SHA Name: {self.checksum_file_name or 'Not found'}")
        print(f"  Hash Type: {self.checksum_hash_type}")
        print(f"  Preferred Suffixes: {self.preferred_characteristic_suffixes}")
        print(f"  Icon Info: {self.icon_info or 'Not found'}")
        print("-" * 60)
        print("User-specific Information (editable):")
        print(f"  Version: {self.version or 'Not set'}")
        print(f"  AppImage Name: {self.appimage_name or 'Not set'}")
        print("=" * 60)

        print("\nConfiguration options:")
        print("-" * 60)
        print("1. Version")
        print("2. AppImage Name")
        print("3. Exit")
        print("-" * 60)

    def _handle_config_customization(self, app_name: str) -> None:
        """Handle configuration customization based on user input.

        Args:
            app_name: Name of the application

        """
        while True:
            choice = input("Enter your choice (1-3): ")
            if choice.isdigit() and 1 <= int(choice) <= MAX_CONFIG_OPTION:
                break
            else:
                logger.warning("Invalid choice, please enter a number between 1 and 3.")
                print("Invalid choice, please enter a number between 1 and 3.")

        if choice == str(MAX_CONFIG_OPTION):
            logger.info("User exited configuration customization without changes")
            print("Exiting without changes.")
            return

        config_dict = {
            "version": self.version,
            "appimage_name": self.appimage_name,
        }
        key = list(config_dict.keys())[int(choice) - 1]
        new_value = input(f"Enter the new value for {key}: ")
        old_value = getattr(self, key)
        setattr(self, key, new_value)
        self.save_config()
        logger.info("Updated %s from '%s' to '%s'", key, old_value, new_value)
        print(f"\033[42m{key.capitalize()} updated successfully in {app_name}\033[0m")
        print("=" * 60)

    def to_dict(self) -> dict[str, Any]:
        """Convert the user-specific configuration to a dictionary.

        Returns:
            tuple[str, Any]: Dictionary representation of user-specific app configuration

        """
        return {
            "version": self.version,
            "appimage_name": self.appimage_name,
        }
