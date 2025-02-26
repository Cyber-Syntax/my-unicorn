import os
import shutil
import subprocess
import json
import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class FileHandler:
    """Handles file operations for managing AppImages."""

    appimage_download_folder_path: str
    appimage_download_backup_folder_path: str
    config_file: str  # global
    # app_config attributes
    config_folder: str  # config folder path
    config_file_name: str  # self.repo.json
    repo: str
    version: str
    sha_name: str
    appimage_name: str
    # appimages: dict
    # global config attributes
    batch_mode: bool
    keep_backup: bool

    def ask_user_confirmation(self, message: str) -> bool:
        """Handle confirmations based on batch mode"""
        if self.batch_mode:
            print(f"Batch mode: Auto-confirming '{message}'")
            return True  # or False depending on safe default
        return input(f"{message} (y/n): ").strip().lower() == "y"

    def delete_file(self, file_path: str) -> None:
        """Delete a file if it exists."""
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted {file_path}")
        else:
            print(f"File not found: {file_path}")

    def make_executable(self, file_path: Optional[str] = None) -> None:
        """Make a file executable."""
        file_path = file_path or self.appimage_name
        if os.access(file_path, os.X_OK):
            print(f"{file_path} is already executable.")
            return

        try:
            subprocess.run(["chmod", "+x", file_path], check=True, timeout=5)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to make {file_path} executable: {e}")
        print(f"{file_path} is now executable.")

    def backup_old_appimage(self) -> None:
        """Backup the old AppImage to a backup folder."""
        logging.info("Backup the old AppImage")

        old_appimage = os.path.join(
            self.appimage_download_folder_path, f"{self.repo}.AppImage"
        )
        backup_file = os.path.join(
            self.appimage_download_backup_folder_path, f"{self.repo}.AppImage"
        )

        if not os.path.exists(self.appimage_download_backup_folder_path):
            if self.batch_mode:
                # Auto-create in batch mode
                try:
                    os.makedirs(
                        self.appimage_download_backup_folder_path, exist_ok=True
                    )
                    print(
                        f"Auto-created backup folder: {self.appimage_download_backup_folder_path}"
                    )
                except OSError as e:
                    logging.error(f"Failed to create backup folder: {e}")
                    print(f"Error creating backup folder: {e}")
                    return
            else:
                if not self.ask_user_confirmation(
                    f"Backup folder {self.appimage_download_backup_folder_path} not found. Create it?"
                ):
                    print("Backup operation canceled.")
                    return

        if os.path.exists(old_appimage):
            shutil.copy2(old_appimage, backup_file)
            print(f"Backed up {old_appimage} to {backup_file}")
        else:
            print(f"Old AppImage not found: {old_appimage}")

    def rename_appimage(self) -> None:
        """Rename the AppImage to the repository's name."""
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name != new_name:
            shutil.move(self.appimage_name, new_name)
            self.appimage_name = new_name
            print(f"Renamed AppImage to {new_name}")
        else:
            print(f"AppImage is already named {new_name}")

    def move_appimage(self) -> None:
        """Move the AppImage to the specified folder."""
        os.makedirs(self.appimage_download_folder_path, exist_ok=True)
        target_path = os.path.join(
            self.appimage_download_folder_path, f"{self.repo}.AppImage"
        )
        shutil.move(self.appimage_name, target_path)
        print(f"Moved {self.appimage_name} to {self.appimage_download_folder_path}")

    def update_version(self) -> None:
        config_file = os.path.join(self.config_folder, f"{self.repo}.json")

        try:
            # Check if config file exists
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as file:
                    config_data = json.load(file)
            else:
                config_data = {}
            # Update version and appimage information
            config_data["version"] = self.version
            config_data["appimage_name"] = self.appimage_name

            with open(config_file, "w", encoding="utf-8") as file:
                json.dump(config_data, file, indent=4)
            print(f"Updated configuration in {config_file}")
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

    def handle_appimage_operations(self) -> bool:
        """Handle file operations with batch mode support."""
        try:
            print("--------- Summary of Operations ---------")
            if self.keep_backup:
                print(
                    f"Backup old AppImage to {self.appimage_download_backup_folder_path}"
                )

            print(f"Rename AppImage to {self.repo}.AppImage")
            print(f"Move AppImage to {self.appimage_download_folder_path}")
            print(f"Update version information in {self.repo}.json")
            print("-----------------------------------------")

            if not self.batch_mode and not self.ask_user_confirmation("Proceed?"):
                print("Operation canceled by user.")
                return False

            # Critical operations that should stop on failure
            if self.keep_backup:
                self.backup_old_appimage()

            self.make_executable()
            self.rename_appimage()
            self.move_appimage()
            self.update_version()

            # Delete old sha file if it is exist
            if self.sha_name != "no_sha_file":
                self.delete_file(self.sha_name)

            print("File operations completed successfully.")
            return True

        except Exception as e:
            logging.error(f"Critical error during file operations: {e}")
            if self.batch_mode:
                raise  # Halt entire process in batch mode
            else:
                print(f"Error: {e}. Continue with other operations?")
                if not self.ask_user_confirmation("Continue?"):
                    raise  # Halt entire process in interactive mode
