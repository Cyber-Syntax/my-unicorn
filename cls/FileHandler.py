import base64
import hashlib
import os
import subprocess
import sys
import logging
import json
import requests
import yaml
from cls.AppImageDownloader import AppImageDownloader

class FileHandler(AppImageDownloader):
    """Handle the file operations"""
    def __init__(self):
        super().__init__()

    def get_sha(self):
        """ Get the sha name and url """
        try:
            print("************************************")
            print(f"Downloading {self.sha_name}...")
            response = requests.get(self.sha_url, timeout=10)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout,
                requests.exceptions.HTTPError, requests.exceptions.RequestException) as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError downloading {self.sha_name}. Error:{error} Exiting...\033[0m")
            sys.exit(1)
        return response

    def download_sha(self, response):
        """ Install the sha file """
        if response.status_code == 200:
            # Check if the sha file already exists
            if not os.path.exists(self.sha_name):
                with open(self.sha_name, "w", encoding="utf-8") as file:
                    file.write(response.text)

                print(f"\033[42mDownloaded {self.sha_name}\033[0m")
                print("************************************")
            else:
                print(f"{self.sha_name} already exists")
                print("************************************")
        else:
            self.handle_connection_error()

    def handle_verification_error(self):
        """ Handle verification errors """
        print(f"\033[41;30mError verifying {self.appimage_name}\033[0m")
        logging.error(f"Error verifying {self.appimage_name}")
        if input("Do you want to delete the downloaded appimage? (y/n): "
                ).lower() == "y":
            os.remove(self.appimage_name)
            print(f"Deleted {self.appimage_name}")
            # Delete the downloaded sha file too
            if input("Do you want to delete the downloaded sha file? (y/n): "
                    ).lower() == "y":
                os.remove(self.sha_name)
                print(f"Deleted {self.sha_name}")
                sys.exit()
            else:
                if input("Do you want to continue without verification? (y/n): "
                        ).lower() == "y":
                    self.make_executable()
                else:
                    print("Exiting...")
                    sys.exit()

    def handle_connection_error(self):
        """ Handle connection errors """
        print(f"\033[41;30mError connecting to {self.sha_url}\033[0m")
        logging.error(f"Error connecting to {self.sha_url}")
        sys.exit()

    def delete_sha(self):
        """ Delete the downloaded sha file """
        if input("Do you want to delete the downloaded sha file? (y/n): "
                ).lower() == "y":
            os.remove(self.sha_name)
            print(f"Deleted {self.sha_name}")
        else:
            print(f"{self.sha_name} saved in {os.getcwd()}")

    def verify_yml(self, response):
        """ Verify yml/yaml sha files """
        if response.status_code == 200:
            self.download_sha(response=response)

            # parse the sha file
            with open(self.sha_name, "r", encoding="utf-8") as file:
                sha = yaml.load(file, Loader=yaml.FullLoader)
            # get the sha from the sha file
            sha = sha[self.hash_type]
            decoded_hash = base64.b64decode(sha).hex()
            # find appimage sha
            with open(self.appimage_name, "rb") as file:
                appimage_sha = hashlib.new(self.hash_type, file.read()).hexdigest()

            # compare the two hashes
            if appimage_sha == decoded_hash:
                print(f"\033[42m{self.appimage_name} verified.\033[0m")
                self.make_executable()
                self.delete_sha()
            else:
                self.handle_verification_error()
        else:
            self.handle_connection_error()

        # close response
        response.close()

    def verify_other(self, response):
        """ Verify other sha files """
        if response.status_code == 200:
            self.download_sha(response=response)

            # parse the sha file
            with open(self.sha_name, "r", encoding="utf-8") as file:
                for line in file:
                    if self.appimage_name in line:
                        appimage_sha = line.split()[0]
                        break
                    else:
                        print(f"{self.appimage_name} not found in {self.sha_name}")

                # compare the two hashes
                if appimage_sha == response.text.split()[0]:
                    print(f"\033[42m{self.appimage_name} verified.\033[0m")
                    print("************************************")
                    self.make_executable()
                    self.delete_sha()
                else:
                    self.handle_verification_error()
        else:
            self.handle_connection_error()

        # close response
        response.close()

    def verify_sha(self):
        """ Verify the downloaded appimage """
        if self.sha_name.endswith(".yml") or self.sha_name.endswith(".yaml"):
            self.verify_yml(response=self.get_sha())
        else:
            self.verify_other(response=self.get_sha())

    def make_executable(self):
        """Make the appimage executable"""
        # if already executable, return
        if os.access(self.appimage_name, os.X_OK):
            print("Appimage is already executable")
            self.move_appimage()
            return
        print("************************************")
        print("Making the appimage executable...")
        subprocess.run(["chmod", "+x", self.appimage_name], check=True)
        print("\033[42mAppimage is now executable\033[0m")
        print("************************************")
        self.move_appimage()

    def backup_old_appimage(self):
        """ Save old {self.repo}.AppImage to a backup folder, ask user for approval"""
        backup_folder = os.path.expanduser(f"{self.appimage_folder}backup")
        old_appimage = os.path.expanduser(f"{self.appimage_folder}{self.repo}.AppImage")

        print(f"Moving {old_appimage} to {backup_folder}")
        print("----------------------------------------")
        # Create a backup folder if it doesn't exist
        if os.path.exists(backup_folder):
            print(f"Backup folder {backup_folder} found")
        else:
            if input(f"Backup folder {backup_folder} not found,"
                    "do you want to create it (y/n): ") == "y":
                subprocess.run(["mkdir", "-p", backup_folder], check=True)
                print(f"Created backup folder: {backup_folder}")
            else:
                print("Backup folder not created.")

        # Move old appimage to backup folder
        if os.path.exists(f"{self.appimage_folder}/{self.repo}.AppImage"):
            print(f"Found {self.repo}.AppImage in {self.appimage_folder}")
            if input(f"Do you want to backup "
                    f"{self.repo}.AppImage to {backup_folder} (y/n):") == "y":
                try:
                    subprocess.run(["mv", f"{old_appimage}",
                                    f"{backup_folder}"], check=True)
                except subprocess.CalledProcessError as error:
                    logging.error(f"Error: {error}", exc_info=True)
                    print(f"\033[41;30mError moving {self.repo}.AppImage to {backup_folder}\033[0m")
            else:
                print(f"Overwriting {self.repo}.AppImage")
        else:
            print(f"{self.repo}.AppImage not found in {self.appimage_folder}")

    def change_name(self):
        """ Change appimage name for .desktop file on linux"""
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name != new_name:
            print(f"Changing {self.appimage_name} name to {new_name}")
            subprocess.run(["mv", f"{self.appimage_name}", f"{new_name}"], check=True)
            self.appimage_name = new_name
        else:
            print("The appimage name is already the new name")

    def move_appimage(self):
        """ Move appimages to a appimage folder """        
        if input(f"Do you want to move {self.appimage_name} to {self.appimage_folder} (y/n):") == "y":
            print(f"Moving {self.appimage_name} to {self.appimage_folder}")
            print("-----------------------------------------------------")

            # Change name before moving
            self.change_name()

            # check if appimage folder exists
            if not os.path.exists(self.appimage_folder):
                subprocess.run(["mkdir", "-p", self.appimage_folder], check=True)
                print(f"Created {self.appimage_folder}")

            # move appimage to appimage folder
            try:
                subprocess.run(["mv", f"{self.repo}.AppImage", f"{self.appimage_folder}"], check=True)
            except subprocess.CalledProcessError as error:
                logging.error(f"Error: {error}", exc_info=True)
                print(f"\033[41;30mError moving {self.repo}.AppImage to {self.appimage_folder}\033[0m")

        else:
            print(f"Not moving {self.appimage_name} to {self.appimage_folder}")
            print(f"{self.appimage_name} saved in {os.getcwd()}")
            print("-----------------------------------------------------")
            # ask user if he wants to delete the downloaded appimage
            new_name = f"{self.repo}.AppImage"
            if input("Do you want to delete the downloaded appimage? (y/n): "
                    ).lower() == "y":
                os.remove(new_name)
                print(f"Deleted {self.repo}.AppImage")
            else:
                print(f"{self.repo}.AppImage saved in {os.getcwd()}")

    def update_version(self):
        """Update the version-appimage_name in the json file"""
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name == new_name:
            print("\nUpdating credentials...")

            # update the version, appimage_name
            self.appimages["version"] = self.version
            self.appimages["appimage"] = self.repo + "-" + self.version + ".AppImage"

            # write the updated version and appimage_name to the json file
            with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
                json.dump(self.appimages, file, indent=4)
            print(f"\033[42mCredentials updated to {self.repo}.json\033[0m")
