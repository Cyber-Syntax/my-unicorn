import base64
import hashlib
import os
import subprocess
import sys
import logging
import json
import shutil
from dataclasses import dataclass
import requests
import yaml
from src.decorators import handle_api_errors, handle_common_errors
from src.app_image_downloader import AppImageDownloader


@dataclass
class FileHandler(AppImageDownloader):
    """Handle the file operations"""

    sha_name: str = None
    sha_url: str = None

    def __post_init__(self):
        super().__init__()

    @staticmethod
    def sha_response_error(func):
        """Handle response errors"""

        def wrapper(self, response):
            if response.status_code == 200:
                self.download_sha(response=response)
                result = func(self, response)
            else:
                response.close()
                self.handle_connection_error()
                result = None
            return result

        return wrapper

    @handle_api_errors
    def get_sha(self):
        """Get the sha name and url"""
        print("************************************")
        print(f"Downloading {self.sha_name}...")
        response = requests.get(self.sha_url, timeout=10)
        return response

    def download_sha(self, response):
        """Install the sha file"""
        # Check if the sha file already exists
        if not os.path.exists(self.sha_name):
            with open(self.sha_name, "w", encoding="utf-8") as file:
                file.write(response.text)
            print(f"\033[42mDownloaded {self.sha_name}\033[0m")
        else:
            # If the sha file already exists, check if it is the same as the downloaded one
            with open(self.sha_name, "r", encoding="utf-8") as file:
                if response.text == file.read():
                    print(f"{self.sha_name} already exists")
                else:
                    print(
                        f"{self.sha_name} already exists but it is different from the downloaded one"
                    )
                    if input("Do you want to overwrite it? (y/n): ").lower() == "y":
                        with open(self.sha_name, "w", encoding="utf-8") as file:
                            file.write(response.text)
                        print(f"\033[42mDownloaded {self.sha_name}\033[0m")
                    else:
                        print("Exiting...")
                        sys.exit()

    def handle_verification_error(self):
        """Handle verification errors"""
        print(f"\033[41;30mError verifying {self.appimage_name}\033[0m")
        logging.error(f"Error verifying {self.appimage_name}")
        if (
            input("Do you want to delete the downloaded appimage? (y/n): ").lower()
            == "y"
        ):
            os.remove(self.appimage_name)
            print(f"Deleted {self.appimage_name}")
            # Delete the downloaded sha file too
            if (
                input("Do you want to delete the downloaded sha file? (y/n): ").lower()
                == "y"
            ):
                os.remove(self.sha_name)
                print(f"Deleted {self.sha_name}")
                sys.exit()
            else:
                if (
                    input(
                        "Do you want to continue without verification? (y/n): "
                    ).lower()
                    == "y"
                ):
                    self.make_executable()
                else:
                    print("Exiting...")
                    sys.exit()

    def handle_connection_error(self):
        """Handle connection errors"""
        print(f"\033[41;30mError connecting to {self.sha_url}\033[0m")
        logging.error(f"Error connecting to {self.sha_url}")
        sys.exit()

    def ask_delete_appimage(self):
        """Delete the downloaded appimage"""
        new_name = f"{self.repo}.AppImage"

        if (
            input("Do you want to delete the downloaded appimage? (y/n): ").lower()
            == "y"
        ):
            if self.appimage_name != new_name:
                os.remove(self.appimage_name)
                print(f"Deleted {self.appimage_name}")
            else:
                os.remove(new_name)
                print(f"Deleted {new_name}")

            print(f"Deleted {self.appimage_name}")
        else:
            print(f"{self.appimage_name} saved in {os.getcwd()}")

    @sha_response_error
    def verify_yml(self, response):
        """Verify yml/yaml sha files"""
        # parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha = yaml.safe_load(file)

        # get the sha from the sha file
        sha = sha[self.hash_type]
        decoded_hash = base64.b64decode(sha).hex()

        # find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_sha = hashlib.new(self.hash_type, file.read()).hexdigest()

        # compare the two hashes
        if appimage_sha == decoded_hash:
            print(f"\033[42m{self.appimage_name} verified.\033[0m")
            print("************************************")
            print("--------------------- HASHES ----------------------")
            print(f"AppImage Hash: {appimage_sha}")
            print(f"Parsed Hash: {decoded_hash}")
            print("----------------------------------------------------")
        else:
            self.handle_verification_error()

        # close response
        response.close()

    @sha_response_error
    def verify_other(self, response):
        """Verify other sha files"""
        # Parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            for line in file:
                if self.appimage_name in line:
                    decoded_hash = line.split()[0]
                    break

        # Find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_hash = hashlib.new(self.hash_type, file.read()).hexdigest()

        # Compare the two hashes
        if appimage_hash == decoded_hash:
            print(f"\033[42m{self.appimage_name} verified.\033[0m")
            print("************************************")
            print("--------------------- HASHES ----------------------")
            print(f"AppImage Hash: {appimage_hash}")
            print(f"Parsed Hash: {decoded_hash}")
            print("----------------------------------------------------")
        else:
            self.handle_verification_error()

    def verify_sha(self):
        """Verify the downloaded appimage"""
        if self.sha_name.endswith(".yml") or self.sha_name.endswith(".yaml"):
            self.verify_yml(response=self.get_sha())
        else:
            self.verify_other(response=self.get_sha())

    @handle_common_errors
    def handle_file_operations(self, batch_mode=False):
        """Handle the file operations with one user's approval"""
        # 1. backup old appimage
        print("--------------------- CHANGES  ----------------------")
        if self.choice == 1 or self.choice == 3:
            print(f"Moving old {self.repo}.AppImage to {self.appimage_folder_backup}")

        print(f"Changing {self.appimage_name} name to {self.repo}.AppImage")
        print(f"Moving updated appimage to {self.appimage_folder}")
        print(f"Updating credentials in {self.repo}.json")
        print(f"Deleting {self.sha_name}")
        print("-----------------------------------------------------")

        # 6. Ask user for approval if not in batch mode
        if not batch_mode:
            if input("Do you want to continue? (y/n): ").lower() != "y":
                print("Appimage installed but not moved to the appimage folder")
                print(f"{self.appimage_name} saved in {os.getcwd()}")
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
        print("Making the appimage executable...")
        subprocess.run(["chmod", "+x", self.appimage_name], check=True)
        print("\033[42mAppimage is now executable\033[0m")
        print("************************************")

    @handle_common_errors
    def backup_old_appimage(self):
        """Save old {self.repo}.AppImage to a backup folder"""
        backup_folder = os.path.expanduser(f"{self.appimage_folder_backup}")
        old_appimage = os.path.expanduser(f"{self.appimage_folder}{self.repo}.AppImage")
        backup_file = os.path.expanduser(f"{backup_folder}{self.repo}.AppImage")

        # Create a backup folder if it doesn't exist
        if os.path.exists(backup_folder):
            print(f"Backup folder {backup_folder} found")
        else:
            if (
                input(
                    f"Backup folder {backup_folder} not found,"
                    "do you want to create it (y/n): "
                )
                == "y"
            ):
                os.makedirs(os.path.dirname(backup_folder), exist_ok=True)
                print(f"Created backup folder: {backup_folder}")
            else:
                print("Backup folder not created.")

        # Check if old appimage exists
        if os.path.exists(f"{self.appimage_folder}/{self.repo}.AppImage"):

            print(f"Found {self.repo}.AppImage in {self.appimage_folder}")

            # Move old appimage to backup folder
            try:
                # overwrite the old appimage to the backup folder if it already exists
                shutil.copy2(old_appimage, backup_file)
            except shutil.Error as error:
                logging.error(f"Error: {error}", exc_info=True)
                print(
                    f"\033[41;30mError moving {self.repo}.AppImage to {backup_folder}\033[0m"
                )
            else:
                print(f"Old {old_appimage} copied to {backup_folder}")
                print("-----------------------------------------------------")
        else:
            print(f"{self.repo}.AppImage not found in {self.appimage_folder}")

    def change_name(self):
        """Change the appimage name to {self.repo}.AppImage"""
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name != new_name:
            print(f"Changing {self.appimage_name} name to {new_name}")
            shutil.move(self.appimage_name, new_name)
            self.appimage_name = new_name
        else:
            print("The appimage name is already the new name")

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
                f"\033[41;30mError moving"
                f" {self.repo}.AppImage to {self.appimage_folder}\033[0m"
            )
        else:
            print(f"Moved {self.repo}.AppImage to {self.appimage_folder}")
            # remove the appimage from the current directory because shutil uses copy2
            os.remove(f"{self.repo}.AppImage")

    @handle_common_errors
    def update_version(self):
        """Update the version-appimage_name in the json file"""

        print("\nUpdating credentials...")
        # update the version, appimage_name
        self.appimages["version"] = self.version
        self.appimages["appimage"] = self.repo + "-" + self.version + ".AppImage"

        # write the updated version and appimage_name to the json file
        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(f"\033[42mCredentials updated to {self.repo}.json\033[0m")

    # INFO: Cause API RATE LIMIT EXCEEDED if used more than 15 - 20 times
    # KeyError: 'tag_name' means that API RATE LIMIT EXCEEDED.
    @handle_common_errors
    def check_updates_json_all(self):
        """Check for updates for all JSON files"""
        json_files = [
            file for file in os.listdir(self.file_path) if file.endswith(".json")
        ]

        # Create a queue for not up-to-date appimages
        appimages_to_update = []

        # Print appimages name and versions from JSON files
        for file in json_files:
            with open(f"{self.file_path}{file}", "r", encoding="utf-8") as file:
                appimages = json.load(file)

            # Check version via GitHub API
            response = requests.get(
                f"https://api.github.com/repos/{appimages['owner']}/{appimages['repo']}/releases/latest"
            )
            latest_version = response.json()["tag_name"].replace("v", "")

            # Compare with above versions
            if latest_version == appimages["version"]:
                print(f"{appimages['appimage']} is up to date")
            else:
                print("-------------------------------------------------")
                print(f"{appimages['appimage']} is not up to date")
                print(f"\033[42mLatest version: {latest_version}\033[0m")
                print(f"Current version: {appimages['version']}")
                print("-------------------------------------------------")
                # Append to queue appimages that are not up to date
                appimages_to_update.append(appimages["repo"])

        # If all appimages are up to date
        if not appimages_to_update:
            print("All appimages are up to date")
            sys.exit()
        else:
            # Display the list of appimages to update
            print("=================================================")
            print("Appimages that are not up to date:")
            for idx, appimage in enumerate(appimages_to_update, start=1):
                print(f"{idx}. {appimage}")
            print("=================================================")

            # Ask the user to select which appimages to update or skip
            user_input = (
                input(
                    "Enter the numbers of the appimages you want to update (comma-separated) or type 'skip' to skip updates: "
                )
                .strip()
                .lower()
            )

            if user_input == "skip":
                print("No updates will be performed.")
                sys.exit()

            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]

            selected_appimages = [appimages_to_update[idx] for idx in selected_indices]

            # Update the selected appimages
            self.update_selected_appimages(selected_appimages)

    @handle_common_errors
    def update_selected_appimages(self, appimages_to_update):
        """Update all appimages"""
        if len(appimages_to_update) > 1:
            if input("Do you want to enable batch mode? (y/n): ").lower() != "y":
                batch_mode = False
            else:
                batch_mode = True
        else:
            batch_mode = False

        if batch_mode:
            print(
                "Batch mode is enabled. All selected appimages will be updated without further prompts."
            )
        else:
            print(
                "Batch mode is disabled. You will be prompted for each appimage update."
            )

        for appimage in appimages_to_update:
            print(f"Updating {appimage}...")
            self.repo = appimage
            self.load_credentials()
            self.get_response()
            self.download()
            self.verify_sha()
            self.make_executable()
            self.handle_file_operations(batch_mode=batch_mode)

        print("Update process completed for all selected appimages.")
