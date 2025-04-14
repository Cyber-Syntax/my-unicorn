import os
import json
import logging
from typing import Optional, Tuple


class AppConfigManager:
    """Manages app-specific configuration settings."""

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
            owner (str, optional): GitHub repository owner
            repo (str, optional): Repository name
            version (str, optional): Application version
            sha_name (str, optional): SHA verification file name
            hash_type (str, optional): Hash type (sha256, sha512, etc.)
            appimage_name (str, optional): Name of the AppImage file
            arch_keyword (str, optional): Architecture keyword in filename
            config_folder (str, optional): Path to configuration folder
        """
        self.owner = owner
        self.repo = repo
        self.version = version
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.appimage_name = appimage_name
        self.arch_keyword = arch_keyword
        self.config_folder = os.path.expanduser(config_folder)
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
            new_version (Optional[str], optional): New version to update to
            new_appimage_name (Optional[str], optional): New AppImage filename
        """
        try:
            if new_version is not None:
                self.version = new_version
            if new_appimage_name is not None:
                self.appimage_name = new_appimage_name

            # Update the config_file attribute
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

            logging.info(f"Updated configuration in {self.config_file}")
        except json.JSONDecodeError as e:
            logging.error(f"Error decoding JSON: {e}")
        except Exception as e:
            logging.error(f"An error occurred: {e}")

    def create_desktop_file(
        self, appimage_path: str, icon_path: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Create a desktop entry file for the AppImage.

        Args:
            appimage_path (str): Full path to the AppImage file
            icon_path (Optional[str]): Path to the icon file, if available

        Returns:
            Tuple[bool, str]: Success status and error message if any
        """
        try:
            # Ensure repo name exists
            if not self.repo:
                return False, "Repository name not set"

            # Create the desktop applications directory if it doesn't exist
            desktop_dir = os.path.expanduser("~/.local/share/applications")
            os.makedirs(desktop_dir, exist_ok=True)

            # Determine display name (capitalize first letter of each word)
            display_name = " ".join(
                word.capitalize() for word in self.repo.replace("-", " ").split()
            )

            # Determine icon path
            icon = icon_path or ""
            if not icon_path:
                # Create icons directory if it doesn't exist
                icons_dir = os.path.join(os.path.dirname(appimage_path), "icons")
                os.makedirs(icons_dir, exist_ok=True)

                # Set default icon path - user can update this later
                icon = os.path.join(icons_dir, f"{self.repo.lower()}.svg")

            # Create the desktop file content
            desktop_content = [
                "[Desktop Entry]",
                f"Name={display_name}",
                f"Exec={appimage_path}",
                f"Icon={icon}",
                "Terminal=false",
                "Type=Application",
                f"Comment=AppImage for {display_name}",
                "Categories=Utility;",
            ]

            # Write to desktop file
            desktop_file_path = os.path.join(desktop_dir, f"{self.repo.lower()}.desktop")
            desktop_file_temp = f"{desktop_file_path}.tmp"

            with open(desktop_file_temp, "w", encoding="utf-8") as f:
                f.write("\n".join(desktop_content))

            # Atomic replace
            os.replace(desktop_file_temp, desktop_file_path)

            logging.info(f"Created desktop file at {desktop_file_path}")
            return True, desktop_file_path

        except Exception as e:
            error_msg = f"Failed to create desktop file: {e}"
            logging.error(error_msg)
            # Cleanup if temp file exists
            if "desktop_file_temp" in locals() and os.path.exists(desktop_file_temp):
                os.remove(desktop_file_temp)
            return False, error_msg

    def select_files(self):
        """
        List available JSON configuration files and allow the user to select multiple.
        Shows application names without the .json extension for better readability.

        Returns:
            list or None: List of selected JSON files or None if no selection made
        """
        json_files = self.list_json_files()
        if not json_files:
            logging.warning("No configuration files found. Please create one first.")
            print("No configuration files found. Please create one first.")
            return None

        # Display app names without the .json extension
        logging.info("Displaying available configuration files")
        print("Available applications:")
        for idx, json_file in enumerate(json_files, start=1):
            # Display just the app name without .json extension
            app_name = os.path.splitext(json_file)[0]
            print(f"{idx}. {app_name}")

        user_input = input(
            "Enter the numbers of the configuration files you want to update (comma-separated): "
        ).strip()

        try:
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
            if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                raise ValueError("Invalid selection.")
            logging.info(f"User selected files: {[json_files[idx] for idx in selected_indices]}")
            return [json_files[idx] for idx in selected_indices]
        except (ValueError, IndexError):
            logging.error("Invalid selection. Please enter valid numbers.")
            print("Invalid selection. Please enter valid numbers.")
            return None

    def load_appimage_config(self, config_file_name: str):
        """
        Load a specific AppImage configuration file.

        Args:
            config_file_name (str): Name of the configuration file

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
                    logging.info(f"Successfully loaded configuration from {config_file_name}")
                    return config
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON in the configuration file: {e}")
                raise ValueError("Failed to parse JSON from the configuration file.")
        else:
            logging.warning(f"Configuration file {config_file_name} not found.")
            return None

    def customize_appimage_config(self):
        """Customize the configuration settings for an AppImage."""
        json_files = self.list_json_files()
        if not json_files:
            logging.warning("No JSON configuration files found.")
            print("No JSON configuration files found.")
            return

        logging.info("Displaying available JSON files for customization")
        print("Available applications:")
        for idx, file in enumerate(json_files, 1):
            # Display just the app name without .json extension
            app_name = os.path.splitext(file)[0]
            print(f"{idx}. {app_name}")
        print(f"{len(json_files) + 1}. Cancel")

        while True:
            file_choice = input("Select an application (number) or cancel: ")
            if file_choice.isdigit():
                file_choice_num = int(file_choice)
                if 1 <= file_choice_num <= len(json_files):
                    selected_file = json_files[file_choice_num - 1]
                    break
                elif file_choice_num == len(json_files) + 1:
                    logging.info("Configuration customization cancelled by user")
                    print("Operation cancelled.")
                    return
                else:
                    logging.warning("Invalid choice. Please select a valid number.")
                    print("Invalid choice. Please select a valid number.")
            else:
                logging.warning("Invalid input. Please enter a number.")
                print("Please enter a number.")

        selected_file_path = os.path.join(self.config_folder, selected_file)
        self.load_appimage_config(selected_file)
        self.config_file = selected_file_path  # Override to ensure saving to the selected file

        # Show application name in title instead of filename
        app_name = os.path.splitext(selected_file)[0]
        logging.info(f"Displaying configuration options for {app_name}")
        print(f"Configuration options for {app_name}:")
        print("=================================================")
        print(f"1. Owner: {self.owner}")
        print(f"2. Repo: {self.repo}")
        print(f"3. Version: {self.version}")
        print(f"4. SHA Name: {self.sha_name}")
        print(f"5. Hash Type: {self.hash_type}")
        print(f"6. AppImage Name: {self.appimage_name}")
        print(f"7. Architecture Keyword: {self.arch_keyword}")
        print("8. Exit")
        print("=================================================")

        while True:
            choice = input("Enter your choice: ")
            if choice.isdigit() and 1 <= int(choice) <= 8:
                break
            else:
                logging.warning("Invalid choice, please enter a number between 1 and 8.")
                print("Invalid choice, please enter a number between 1 and 8.")

        if choice == "8":
            logging.info("User exited configuration customization without changes")
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
        logging.info(f"Updated {key} from '{old_value}' to '{new_value}' in {selected_file}")
        print(f"\033[42m{key.capitalize()} updated successfully in {app_name}\033[0m")
        print("=================================================")

    def temp_save_config(self):
        """
        Atomically save configuration using temporary file

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            if not self.config_file:
                logging.error("Config file path is not set")
                return False

            temp_file = f"{self.config_file}.tmp"
            os.makedirs(os.path.dirname(temp_file), exist_ok=True)

            # Write complete current state to temp file
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(self.to_dict(), file, indent=4)

            logging.info(f"Temporary config saved to {temp_file}")
            return True
        except Exception as e:
            logging.error(f"Temp config save failed: {e}")
            # Cleanup if possible
            if "temp_file" in locals() and os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def save_config(self):
        """
        Commit temporary config by replacing original

        Returns:
            bool: True if commit successful, False otherwise
        """
        if not self.config_file:
            logging.error("Config file path is not set")
            return False

        try:
            # First save to temporary file
            if not self.temp_save_config():
                return False

            temp_file = f"{self.config_file}.tmp"

            # Atomic replace operation
            os.replace(temp_file, self.config_file)
            logging.info(f"Configuration committed to {self.config_file}")
            return True

        except Exception as e:
            logging.error(f"Config commit failed: {e}")
            # Cleanup temp file if it exists
            temp_file = f"{self.config_file}.tmp"
            if os.path.exists(temp_file):
                os.remove(temp_file)
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
            logging.error(f"Error accessing configuration folder: {error}")
            raise FileNotFoundError(f"Configuration folder access error: {error}")

    def ask_sha_hash(self):
        """
        Set up app-specific configuration interactively.

        Returns:
            tuple: (sha_name, hash_type) - The hash file name and hash type
        """
        logging.info("Setting up app-specific configuration")
        self.sha_name = (
            input("Enter the SHA file name (Leave blank for auto detect): ").strip() or None
        )
        self.hash_type = (
            input("Enter the hash type (Leave blank for auto detect): ").strip() or "sha256"
        )

        logging.info(f"SHA file name: {self.sha_name}, hash type: {self.hash_type}")
        return self.sha_name, self.hash_type
