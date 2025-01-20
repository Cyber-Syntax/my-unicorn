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

    appimage_name: str
    repo: str
    version: str
    appimage_folder: str
    backup_folder: str
    config_folder_path: str
    appimages: dict

    def ask_user_confirmation(self, message: str) -> bool:
        """Ask the user for a yes/no confirmation."""
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
            subprocess.run(["chmod", "+x", file_path], check=True)
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to make {file_path} executable: {e}")
        print(f"{file_path} is now executable.")

    def backup_old_appimage(self) -> None:
        """Backup the old AppImage to a backup folder."""
        old_appimage = os.path.join(self.appimage_folder, f"{self.repo}.AppImage")
        backup_file = os.path.join(self.backup_folder, f"{self.repo}.AppImage")

        if not os.path.exists(self.backup_folder):
            if self.ask_user_confirmation(
                f"Backup folder {self.backup_folder} not found. Create it?"
            ):
                os.makedirs(self.backup_folder, exist_ok=True)
                print(f"Created backup folder: {self.backup_folder}")
            else:
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
        os.makedirs(self.appimage_folder, exist_ok=True)
        target_path = os.path.join(self.appimage_folder, f"{self.repo}.AppImage")
        shutil.move(self.appimage_name, target_path)
        print(f"Moved {self.appimage_name} to {self.appimage_folder}")

    def update_version(self) -> None:
        """Update the version and AppImage name in the configuration file."""
        config_file = os.path.join(self.config_folder_path, f"{self.repo}.json")
        self.appimages["version"] = self.version
        self.appimages["appimage"] = f"{self.repo}-{self.version}.AppImage"

        with open(config_file, "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(f"Updated configuration in {config_file}")

    def handle_appimage_operations(self, batch_mode: bool = False) -> None:
        """Handle file operations with optional user approval."""
        print("--------- Summary of Operations ---------")
        print(f"1. Backup old AppImage to {self.backup_folder}")
        print(f"2. Rename AppImage to {self.repo}.AppImage")
        print(f"3. Move AppImage to {self.appimage_folder}")
        print(f"4. Update version information in {self.repo}.json")
        print("-----------------------------------------")

        if not batch_mode and not self.ask_user_confirmation(
            "Proceed with the above operations?"
        ):
            print("Operation canceled by user.")
            return

        self.backup_old_appimage()
        self.rename_appimage()
        self.move_appimage()
        self.update_version()
        print("All operations completed successfully.")
