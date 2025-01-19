import base64
import hashlib
import os
import subprocess
import sys
import logging
import json
import shutil
from dataclasses import dataclass, field
import requests
import yaml
from .decorators import handle_api_errors, handle_common_errors
from .app_image_downloader import AppImageDownloader


@dataclass
class FileHandler:
    downloader: AppImageDownloader = field(default_factory=AppImageDownloader)

    def __post_init__(self):
        # FIX: it can't load because it didn't select anything to load? function don't now what to load
        self.downloader.load_credentials()  # Directly call `FileHandler` methods

    @handle_common_errors
    def handle_file_operations(self, batch_mode=False):
        """Handle the file operations with one user's approval"""
        # 1. backup old appimage
        print(_("--------------------- CHANGES  ----------------------"))
        if self.choice == 1 or self.choice == 3:
            print(
                _("Moving old {repo}.AppImage to {backup}").format(
                    repo=self.repo, backup=self.appimage_folder_backup
                )
            )

        print(
            _("Changing {appimage_name} name to {repo}.AppImage").format(
                appimage_name=self.appimage_name, repo=self.repo
            )
        )
        print(
            _("Moving updated appimage to {folder}").format(folder=self.appimage_folder)
        )
        print(_("Updating credentials in {repo}.json").format(repo=self.repo))
        print(_("Deleting {sha_name}").format(sha_name=self.sha_name))
        print("-----------------------------------------------------")

        # 6. Ask user for approval if not in batch mode
        if not batch_mode:
            if input(_("Do you want to continue? (y/n): ")).lower() != "y":
                print(_("Appimage installed but not moved to the appimage folder"))
                print(
                    _("{appimage_name} saved in {cwd}").format(
                        appimage_name=self.appimage_name, cwd=os.getcwd()
                    )
                )
                return

        if self.choice == 1 or self.choice == 3:
            self.backup_old_appimage()

        self.change_name()
        self.move_appimage()
        self.update_version()
        os.remove(self.sha_name)

    def make_executable(self):
        """Make the appimage executable"""
        # if already executable, return
        if os.access(self.appimage_name, os.X_OK):
            return

        print("************************************")
        print(_("Making the appimage executable..."))
        subprocess.run(["chmod", "+x", self.appimage_name], check=True)
        print(_("\033[42mAppimage is now executable\033[0m"))
        print("************************************")

    @handle_common_errors
    def backup_old_appimage(self):
        """Save old {self.repo}.AppImage to a backup folder"""
        backup_folder = os.path.expanduser(f"{self.appimage_folder_backup}")
        old_appimage = os.path.expanduser(f"{self.appimage_folder}{self.repo}.AppImage")
        backup_file = os.path.expanduser(f"{backup_folder}{self.repo}.AppImage")

        # Create a backup folder if it doesn't exist
        if os.path.exists(backup_folder):
            print(
                _("Backup folder {backup_folder} found").format(
                    backup_folder=backup_folder
                )
            )
        else:
            if (
                input(
                    _(
                        "Backup folder {backup_folder} not found, do you want to create it (y/n): "
                    ).format(backup_folder=backup_folder)
                ).lower()
                == "y"
            ):
                os.makedirs(os.path.dirname(backup_folder), exist_ok=True)
                print(
                    _("Created backup folder: {backup_folder}").format(
                        backup_folder=backup_folder
                    )
                )
            else:
                print(_("Backup folder not created."))

        # Check if old appimage exists
        if os.path.exists(f"{self.appimage_folder}/{self.repo}.AppImage"):

            print(
                _("Found {repo}.AppImage in {folder}").format(
                    repo=self.repo, folder=self.appimage_folder
                )
            )

            # Move old appimage to backup folder
            try:
                # overwrite the old appimage to the backup folder if it already exists
                shutil.copy2(old_appimage, backup_file)
            except shutil.Error as error:
                logging.error(f"Error: {error}", exc_info=True)
                print(
                    _(
                        "\033[41;30mError moving {repo}.AppImage to {backup_folder}\033[0m"
                    ).format(repo=self.repo, backup_folder=backup_folder)
                )
            else:
                print(
                    _("Old {old_appimage} copied to {backup_folder}").format(
                        old_appimage=old_appimage, backup_folder=backup_folder
                    )
                )
                print("-----------------------------------------------------")
        else:
            print(
                _("{repo}.AppImage not found in {folder}").format(
                    repo=self.repo, folder=self.appimage_folder
                )
            )

    def change_name(self):
        """Change the appimage name to {self.repo}.AppImage"""
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name != new_name:
            print(
                _("Changing {appimage_name} name to {new_name}").format(
                    appimage_name=self.appimage_name, new_name=new_name
                )
            )
            shutil.move(self.appimage_name, new_name)
            self.appimage_name = new_name
        else:
            print(_("The appimage name is already the new name"))

    @handle_common_errors
    def move_appimage(self):
        """Move appimages to a appimage folder"""
        # check if appimage folder exists
        os.makedirs(os.path.dirname(self.appimage_folder), exist_ok=True)
        # move appimage to appimage folder
        try:
            shutil.copy2(f"{self.repo}.AppImage", self.appimage_folder)
        except shutil.Error as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(
                _("\033[41;30mError moving {repo}.AppImage to {folder}\033[0m").format(
                    repo=self.repo, folder=self.appimage_folder
                )
            )
        else:
            print(
                _("Moved {repo}.AppImage to {folder}").format(
                    repo=self.repo, folder=self.appimage_folder
                )
            )
            # remove the appimage from the current directory because shutil uses copy2
            os.remove(f"{self.repo}.AppImage")

    @handle_common_errors
    def update_version(self):
        """Update the version-appimage_name in the json file"""

        print(_("Updating credentials..."))
        # update the version, appimage_name
        self.appimages["version"] = self.version
        self.appimages["appimage"] = self.repo + "-" + self.version + ".AppImage"

        # write the updated version and appimage_name to the json file
        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(
            _("\033[42mCredentials updated to {repo}.json\033[0m").format(
                repo=self.repo
            )
        )
