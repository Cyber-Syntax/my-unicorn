import os
import json
import logging
import re
from typing import Optional, Tuple

# Configure module logger
logger = logging.getLogger(__name__)


class AppConfigManager:
    """
    Manages app-specific configuration settings.

    This class handles operations related to application configuration including
    creating desktop files, managing versions, and storing app-specific settings.
    """

    def __init__(
        self,
        owner: str = None,
        repo: str = None,
        version: str = None,
        sha_name: str = None,
        hash_type: str = "sha256",
        appimage_name: str = None,
        arch_keyword: str = None,
        config_folder: str = "~/.config/myunicorn/apps/",
    ):
        """
        Initialize the AppConfigManager with application-specific settings.

        Args:
            owner: GitHub repository owner/organization
            repo: Repository name
            version: Application version
            sha_name: SHA verification file name
            hash_type: Hash type (sha256, sha512, etc.)
            appimage_name: Name of the AppImage file
            arch_keyword: Architecture keyword in filename
            config_folder: Path to configuration folder
        """
        self.owner = owner
        self.repo = repo
        self.version = version
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.appimage_name = appimage_name
        self.arch_keyword = arch_keyword
        self.config_folder = os.path.expanduser(config_folder)

        # Use repo directly for app identifier
        self.config_file_name = f"{self.repo}.json" if self.repo else None
        self.config_file = (
            os.path.join(self.config_folder, self.config_file_name)
            if self.config_file_name
            else None
        )

        # Ensure the configuration directory exists
        os.makedirs(self.config_folder, exist_ok=True)

    def update_version(
        self, new_version: Optional[str] = None, new_appimage_name: Optional[str] = None
    ) -> None:
        """
        Update the configuration file with the new version and AppImage name.
        If new_version or new_appimage_name is provided, update the instance variables accordingly.

        Args:
            new_version: New version to update to
            new_appimage_name: New AppImage filename
        """
        try:
            if new_version is not None:
                self.version = new_version
            if new_appimage_name is not None:
                self.appimage_name = new_appimage_name

            self.config_file = os.path.join(self.config_folder, f"{self.repo}.json")
            config_data = {}

            if os.path.exists(self.config_file):
                with open(self.config_file, "r", encoding="utf-8") as file:
                    config_data = json.load(file)

            # Update version and AppImage information in the configuration data.
            config_data["version"] = self.version
            config_data["appimage_name"] = self.appimage_name

            with open(self.config_file, "w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=4)

            logger.info(f"Updated configuration in {self.config_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
        except Exception as e:
            logger.error(f"An error occurred while updating version: {e}")

    def create_desktop_file(
        self, appimage_path: str, icon_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create or update a desktop entry file for the AppImage.

        Compares existing desktop entry content with new content to avoid
        unnecessary writes when nothing has changed. This preserves user
        customizations and prevents excessive file operations.

        Args:
            appimage_path: Full path to the AppImage file
            icon_path: Path to the icon file, if available

        Returns:
            Tuple[bool, str]: Success status and error message or filepath if successful
        """
        try:
            if not self.repo:
                return False, "Application identifier not available"

            # Ensure desktop file directory exists
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)

            desktop_file_path = os.path.join(desktop_dir, f"{self.repo.lower()}.desktop")
            desktop_file_temp = f"{desktop_file_path}.tmp"

            # Determine display name (preserve original case of repo name for better desktop integration)
            display_name = self.repo

            # Determine icon path - start with the provided icon path if available
            final_icon_path = icon_path

            if not final_icon_path:
                icon_base_dir = os.path.expanduser("~/.local/share/icons/myunicorn")
                app_icon_dir = os.path.join(icon_base_dir, self.repo)
                repo_icon_dir = os.path.join(
                    icon_base_dir, self.repo
                )  # Fallback for backward compatibility

                # Check standard icon file names in both directories
                icon_locations = []

                # First check app directory (primary for generic repos)
                if self.repo != self.repo.lower():
                    icon_locations.extend(
                        [
                            os.path.join(app_icon_dir, "icon.svg"),
                            os.path.join(app_icon_dir, "icon.png"),
                            os.path.join(app_icon_dir, "icon.jpg"),
                            os.path.join(app_icon_dir, "logo.svg"),
                            os.path.join(app_icon_dir, "logo.png"),
                        ]
                    )

                # Also check repo directory (for backward compatibility)
                icon_locations.extend(
                    [
                        # Repository-specific directory with standard names
                        os.path.join(repo_icon_dir, "icon.svg"),
                        os.path.join(repo_icon_dir, "icon.png"),
                        os.path.join(repo_icon_dir, "icon.jpg"),
                        os.path.join(repo_icon_dir, "logo.svg"),
                        os.path.join(repo_icon_dir, "logo.png"),
                        # Legacy locations for backward compatibility
                        os.path.join(icon_base_dir, "scalable/apps", f"{self.repo}.svg"),
                        os.path.join(icon_base_dir, "256x256/apps", f"{self.repo}.png"),
                        os.path.join(icon_base_dir, "128x128/apps", f"{self.repo}.png"),
                        os.path.join(icon_base_dir, "scalable/apps", f"{self.repo}.svg"),
                        os.path.join(icon_base_dir, "256x256/apps", f"{self.repo}.png"),
                        os.path.join(icon_base_dir, "128x128/apps", f"{self.repo}.png"),
                    ]
                )

                # Check each location for an existing icon
                for location in icon_locations:
                    if os.path.exists(location):
                        final_icon_path = location
                        logger.info(f"Using existing icon at: {final_icon_path}")
                        break

                for check_dir in [app_icon_dir, repo_icon_dir]:
                    if (
                        os.path.exists(check_dir)
                        and os.path.isdir(check_dir)
                        and not final_icon_path
                    ):
                        for filename in os.listdir(check_dir):
                            file_path = os.path.join(check_dir, filename)
                            if os.path.isfile(file_path) and any(
                                file_path.lower().endswith(ext)
                                for ext in [".svg", ".png", ".jpg", ".jpeg"]
                            ):
                                final_icon_path = file_path
                                logger.info(f"Using first image file found: {final_icon_path}")
                                break
                        # Break the outer loop if we found an icon
                        if final_icon_path:
                            break

            # If still no icon found, use the repo name as fallback
            # This allows desktop environments to find the icon in standard theme directories
            if not final_icon_path:
                final_icon_path = self.repo  # Use original case for better theme matching
                logger.info(f"Using fallback icon name: {final_icon_path}")

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
                                section = line[1:-1]  # Extract section name without brackets
                                continue

                            # Only process lines with key=value format in Desktop Entry section
                            if section == "Desktop Entry" and "=" in line:
                                key, value = line.split("=", 1)
                                existing_entries[key.strip()] = value.strip()

                    logger.info(f"Found existing desktop file: {desktop_file_path}")
                except Exception as e:
                    logger.warning(f"Error reading existing desktop file: {e}")

            # Create new desktop file content - only include standard desktop entry keys
            new_entries = {
                "Name": display_name,
                "Exec": appimage_path,  # Use the provided appimage_path directly
                "Terminal": "false",
                "Type": "Application",
                "Comment": f"AppImage for {display_name}",
                "Categories": "Utility;",
            }

            # Add icon only if we have a path (don't include if using default repo name)
            if final_icon_path:
                new_entries["Icon"] = final_icon_path

            # Check if content would actually change to avoid unnecessary writes
            needs_update = False

            # Compare existing vs new entries for required fields
            for key, value in new_entries.items():
                if key not in existing_entries or existing_entries[key] != value:
                    needs_update = True
                    logger.info(f"Desktop entry needs update: {key} changed")
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
                    if key not in new_entries and key not in [key.lower() for key in new_entries]:
                        f.write(f"{key}={value}\n")

            # Ensure proper permissions on the temp file
            os.chmod(desktop_file_temp, 0o755)  # Make executable

            # Atomic replace
            os.replace(desktop_file_temp, desktop_file_path)

            logger.info(f"Updated desktop file at {desktop_file_path}")
            return True, desktop_file_path

        except Exception as e:
            error_msg = f"Failed to create/update desktop file: {e}"
            logger.error(error_msg)
            # Clean up temp file if exists
            if "desktop_file_temp" in locals() and os.path.exists(desktop_file_temp):
                try:
                    os.remove(desktop_file_temp)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
            return False, error_msg

    def select_files(self):
        """
        List available JSON configuration files and allow the user to select multiple.
        Shows application names without the .json extension for better readability.

        Returns:
            list or None: List of selected JSON files or None if no selection made
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
                app_name = os.path.splitext(json_file)[0]
                print(f"{idx}. {app_name}")

            user_input = input(
                "Select application(s) (comma-separated numbers) or cancel: "
            ).strip()

            try:
                selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
                if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                    raise ValueError("Invalid selection.")
                logger.info(f"User selected files: {[json_files[idx] for idx in selected_indices]}")
                return [json_files[idx] for idx in selected_indices]
            except (ValueError, IndexError):
                logger.error("Invalid selection. Please enter valid numbers.")
                return None
        except KeyboardInterrupt:
            logger.info("User cancelled the selection.")
            print("\nSelection cancelled.")
            return None

    def load_appimage_config(self, config_file_name: str):
        """
        Load a specific AppImage configuration file.

        Args:
            config_file_name: Name of the configuration file

        Returns:
            dict or None: Loaded configuration or None if file not found

        Raises:
            ValueError: If JSON parsing fails
        """
        config_file_path = os.path.join(self.config_folder, config_file_name)
        if os.path.isfile(config_file_path):
            try:
                with open(config_file_path, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    # Update instance variables with the loaded config
                    self.owner = config.get("owner", self.owner)
                    self.repo = config.get("repo", self.repo)
                    self.version = config.get("version", self.version)
                    self.sha_name = config.get("sha_name", self.sha_name)
                    self.hash_type = config.get("hash_type", self.hash_type)
                    self.appimage_name = config.get("appimage_name", self.appimage_name)
                    self.arch_keyword = config.get("arch_keyword", self.arch_keyword)
                    logger.info(f"Successfully loaded configuration from {config_file_name}")
                    return config
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in the configuration file: {e}")
                raise ValueError("Failed to parse JSON from the configuration file.")
        else:
            logger.warning(f"Configuration file {config_file_name} not found.")
            return None

    def customize_appimage_config(self):
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
            app_name = os.path.splitext(file)[0]
            print(f"{idx}. {app_name}")
        print(f"{len(json_files) + 1}. Cancel")

        # Continue with standard interface
        while True:
            file_choice = input("Select an application (number) or cancel: ")
            if file_choice.isdigit():
                file_choice_num = int(file_choice)
                if 1 <= file_choice_num <= len(json_files):
                    selected_file = json_files[file_choice_num - 1]
                    break
                elif file_choice_num == len(json_files) + 1:
                    logger.info("Configuration customization cancelled by user")
                    print("Operation cancelled.")
                    return
                else:
                    logger.warning("Invalid choice. Please select a valid number.")
                    print("Invalid choice. Please select a valid number.")
            else:
                logger.warning("Invalid input. Please enter a number.")
                print("Please enter a number.")

        selected_file_path = os.path.join(self.config_folder, selected_file)
        self.load_appimage_config(selected_file)
        self.config_file = selected_file_path  # Override to ensure saving to the selected file

        # Show application name in title instead of filename
        app_name = os.path.splitext(selected_file)[0]
        logger.info(f"Displaying configuration options for {app_name}")

        # Show current configuration values
        print("\n" + "=" * 60)
        print(f"Configuration for: {app_name}")
        print("-" * 60)
        print(f"Owner: {self.owner or 'Not set'}")
        print(f"Repository: {self.repo or 'Not set'}")
        print(f"Version: {self.version or 'Not set'}")
        print(f"SHA Name: {self.sha_name or 'Auto-detect'}")
        print(f"Hash Type: {self.hash_type or 'sha256'}")
        print(f"AppImage Name: {self.appimage_name or 'Not set'}")
        print(f"Architecture Keyword: {self.arch_keyword or 'Not set'}")
        print("=" * 60)

        print("\nConfiguration options:")
        print("-" * 60)
        print("Repository Settings:")
        print("1. Owner")
        print("2. Repository")
        print("3. Version")
        print("4. SHA Name")
        print("\nAppImage Settings:")
        print("5. Hash Type")
        print("6. AppImage Name")
        print("7. Architecture Keyword")
        print("8. Exit")
        print("-" * 60)

        while True:
            choice = input("Enter your choice (1-8): ")
            if choice.isdigit() and 1 <= int(choice) <= 8:
                break
            else:
                logger.warning("Invalid choice, please enter a number between 1 and 8.")
                print("Invalid choice, please enter a number between 1 and 8.")

        if choice == "8":
            logger.info("User exited configuration customization without changes")
            print("Exiting without changes.")
            return

        config_dict = {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "sha_name": self.sha_name,
            "hash_type": self.hash_type,
            "appimage_name": self.appimage_name,
            "arch_keyword": self.arch_keyword,
        }
        key = list(config_dict.keys())[int(choice) - 1]
        new_value = input(f"Enter the new value for {key}: ")
        old_value = getattr(self, key)
        setattr(self, key, new_value)
        self.save_config()
        logger.info(f"Updated {key} from '{old_value}' to '{new_value}' in {selected_file}")
        print(f"\033[42m{key.capitalize()} updated successfully in {app_name}\033[0m")
        print("=" * 60)

    def temp_save_config(self):
        """
        Atomically save configuration using temporary file.

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if not self.config_file:
                logger.error("Config file path is not set")
                return False

            temp_file = f"{self.config_file}.tmp"
            os.makedirs(os.path.dirname(temp_file), exist_ok=True)

            # Write complete current state to temp file
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(self.to_dict(), file, indent=4)

            logger.info(f"Temporary config saved to {temp_file}")
            return True
        except Exception as e:
            logger.error(f"Temp config save failed: {e}")
            # Cleanup if possible
            if "temp_file" in locals() and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
            return False

    def save_config(self):
        """
        Commit temporary config by replacing original.

        Returns:
            bool: True if commit successful, False otherwise
        """
        if not self.config_file:
            logger.error("Config file path is not set")
            return False

        try:
            # First save to temporary file
            if not self.temp_save_config():
                return False

            temp_file = f"{self.config_file}.tmp"

            # Atomic replace operation
            os.replace(temp_file, self.config_file)
            logger.info(f"Configuration committed to {self.config_file}")
            return True

        except Exception as e:
            logger.error(f"Config commit failed: {e}")
            # Cleanup temp file if it exists
            temp_file = f"{self.config_file}.tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception as cleanup_error:
                    logger.warning(f"Failed to clean up temporary file: {cleanup_error}")
            return False

    def to_dict(self):
        """
        Convert the instance variables to a dictionary.

        Returns:
            dict: Dictionary representation of app configuration
        """
        return {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "sha_name": self.sha_name,
            "hash_type": self.hash_type,
            "appimage_name": self.appimage_name,
            "arch_keyword": self.arch_keyword,
        }

    def list_json_files(self):
        """
        List JSON files in the configuration directory.

        Returns:
            list: List of JSON files in the configuration directory

        Raises:
            FileNotFoundError: If the configuration folder doesn't exist
        """
        try:
            os.makedirs(self.config_folder, exist_ok=True)
            json_files = [file for file in os.listdir(self.config_folder) if file.endswith(".json")]
            return json_files if json_files else []
        except (FileNotFoundError, PermissionError) as error:
            logger.error(f"Error accessing configuration folder: {error}")
            raise FileNotFoundError(f"Configuration folder access error: {error}")

    def ask_sha_hash(self):
        """
        Set up app-specific configuration interactively.

        Returns:
            tuple: (sha_name, hash_type) - The hash file name and hash type
        """
        logger.info("Setting up app-specific configuration")
        self.sha_name = (
            input("Enter the SHA file name (Leave blank for auto detect): ").strip() or None
        )
        self.hash_type = (
            input("Enter the hash type (Leave blank for auto detect): ").strip() or "sha256"
        )

        logger.info(f"SHA file name: {self.sha_name}, hash type: {self.hash_type}")
        return self.sha_name, self.hash_type
