import os
import json
import logging
from typing import Optional


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
        config_folder: str = "~/Documents/appimages/config_files/",
    ):
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

    # HACK: config_file as a workaround to use it in the function for now.
    # config_file need to be used from the class but seems like it is coming None.
    def update_version(
        self, new_version: Optional[str] = None, new_appimage_name: Optional[str] = None
    ) -> None:
        """
        Update the configuration file with the new version and AppImage name.
        If new_version or new_appimage_name is provided, update the instance variables accordingly.
        """
        try:
            if new_version is not None:
                self.version = new_version
            if new_appimage_name is not None:
                self.appimage_name = new_appimage_name

            config_file = os.path.join(self.config_folder, f"{self.repo}.json")

            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as file:
                    config_data = json.load(file)
            else:
                config_data = {}

            # Update version and AppImage information in the configuration data.
            config_data["version"] = self.version
            config_data["appimage_name"] = self.appimage_name

            with open(config_file, "w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=4)
            print(f"Updated configuration in {self.config_file}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def select_files(self):
        """List available JSON configuration files and allow the user to select multiple."""
        json_files = self.list_json_files()
        if not json_files:
            print("No configuration files found. Please create one first.")
            return None

        print("Available configuration files:")
        for idx, json_file in enumerate(json_files, start=1):
            print(f"{idx}. {json_file}")

        user_input = input(
            "Enter the numbers of the configuration files you want to update (comma-separated): "
        ).strip()

        try:
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
            if any(idx < 0 or idx >= len(json_files) for idx in selected_indices):
                raise ValueError("Invalid selection.")
            return [json_files[idx] for idx in selected_indices]
        except (ValueError, IndexError):
            print("Invalid selection. Please enter valid numbers.")
            return None

    def load_appimage_config(self, config_file_name: str):
        """Load a specific AppImage configuration file."""
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
            print("No JSON configuration files found.")
            return

        print("Available JSON files:")
        for idx, file in enumerate(json_files, 1):
            print(f"{idx}. {file}")
        print(f"{len(json_files) + 1}. Cancel")

        while True:
            file_choice = input("Select a file (number) or cancel: ")
            if file_choice.isdigit():
                file_choice_num = int(file_choice)
                if 1 <= file_choice_num <= len(json_files):
                    selected_file = json_files[file_choice_num - 1]
                    break
                elif file_choice_num == len(json_files) + 1:
                    print("Operation cancelled.")
                    return
                else:
                    print("Invalid choice. Please select a valid number.")
            else:
                print("Please enter a number.")

        selected_file_path = os.path.join(self.config_folder, selected_file)
        self.load_appimage_config(selected_file)
        self.config_file = (
            selected_file_path  # Override to ensure saving to the selected file
        )

        print("Select which key to modify:")
        print("=================================================")
        print(f"1. Owner: {self.owner}")
        print(f"2. Repo: {self.repo}")
        print(f"3. Version: {self.version}")
        print(f"4. SHA Name: {self.sha_name}")
        print(f"5. Hash Type: {self.hash_type}")
        print(f"6. AppImage Name: {self.appimage_name}")
        print("7. Exit")
        print("=================================================")

        while True:
            choice = input("Enter your choice: ")
            if choice.isdigit() and 1 <= int(choice) <= 7:
                break
            else:
                print("Invalid choice, please enter a number between 1 and 7.")

        if choice == "7":
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
        setattr(self, key, new_value)
        self.save_config()
        print(
            f"\033[42m{key.capitalize()} updated successfully in {selected_file}\033[0m"
        )
        print("=================================================")

    def temp_save_config(self):
        """Atomically save configuration using temporary file"""
        try:
            temp_file = f"{self.config_file}.tmp"
            os.makedirs(os.path.dirname(temp_file), exist_ok=True)

            # Write complete current state to temp file
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(self.to_dict(), file, indent=4)

            print(f"Temporary config saved to {temp_file}")
            return True
        except Exception as e:
            logging.error(f"Temp config save failed: {e}")
            # Cleanup if possible
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def save_config(self):
        """Commit temporary config by replacing original"""
        try:
            temp_file = f"{self.config_file}.tmp"

            if not os.path.exists(temp_file):
                raise FileNotFoundError("No temporary config to commit")

            # Atomic replace operation
            os.replace(temp_file, self.config_file)
            print(f"Configuration committed to {self.config_file}")
            return True

        except Exception as e:
            logging.error(f"Config commit failed: {e}")
            # Cleanup temp file if it exists
            if os.path.exists(temp_file):
                os.remove(temp_file)
            return False

    def to_dict(self):
        """Convert the instance variables to a dictionary."""

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
        """List JSON files in the configuration directory."""
        try:
            json_files = [
                file
                for file in os.listdir(self.config_folder)
                if file.endswith(".json")
            ]
            return json_files if json_files else []
        except FileNotFoundError as error:
            logging.error(f"Error accessing configuration folder: {error}")
            raise FileNotFoundError("Configuration folder does not exist.")

    def ask_sha_hash(self):
        """Set up app-specific configuration interactively."""
        print("Setting up app-specific configuration...")

        # TODO: if detected, don't ask? Need to change command sorting
        # TODO: Debug is WIP:
        # joplin works, siyuan works
        self.sha_name = (
            input("Enter the SHA file name (Leave blank for auto detect): ").strip()
            or None
        )
        self.hash_type = (
            input("Enter the hash type (Leave blank for auto detect): ").strip()
            or "sha256"
        )

        return self.sha_name, self.hash_type
