import os
import json
import logging


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
        exact_appimage_name: str = None,
        config_folder: str = "~/Documents/appimages/config_files/",
    ):
        self.owner = owner
        self.repo = repo
        self.version = version
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.appimage_name = appimage_name
        self.exact_appimage_name = exact_appimage_name
        self.config_folder = os.path.expanduser(config_folder)
        self.config_file_name = f"{self.repo}.json" if self.repo else None
        self.config_file = (
            os.path.join(self.config_folder, self.config_file_name)
            if self.config_file_name
            else None
        )
        # Ensure the configuration directory exists
        os.makedirs(self.config_folder, exist_ok=True)

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
                    self.exact_appimage_name = config.get(
                        "exact_appimage_name", self.exact_appimage_name
                    )
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
            "exact_appimage_name": self.exact_appimage_name,
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

    # def save_config(self):
    #     """Save the current configuration settings to a JSON file."""
    #     try:
    #         os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
    #         config_data = self.to_dict()
    #         with open(self.config_file, "w", encoding="utf-8") as file:
    #             json.dump(config_data, file, indent=4)
    #     except Exception as e:
    #         logging.error(f"Error saving configuration to {self.config_file}: {e}")
    #         raise ValueError("Failed to save configuration.")

    def to_dict(self):
        """Convert the instance variables to a dictionary."""

        return {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "sha_name": self.sha_name,
            "hash_type": self.hash_type,
            "appimage_name": self.appimage_name,
            "exact_appimage_name": self.exact_appimage_name,
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
            input(
                "Enter the SHA file name (Leave blank if you want auto detect): "
            ).strip()
            or None
        )
        self.hash_type = (
            input("Enter the hash type (default: 'sha256'): ").strip() or "sha256"
        )

        return self.sha_name, self.hash_type
