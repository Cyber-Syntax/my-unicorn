import base64
import hashlib
import os
import subprocess
import sys
import requests
import yaml
from classes.AppImageDownloader import AppImageDownloader

class FileHandler(AppImageDownloader):
    """Handle the file operations"""
    def __init__(self):
        super().__init__()

    def verify_sha(self):
        print(f"Verifying {self.appimage_name}...")
        # if the sha_name endswith .yml or .yaml, then use the yaml module to parse the file
        try:
            if self.sha_name.endswith(".yml") or self.sha_name.endswith(".yaml"):
                response = requests.get(self.sha_url, timeout=10)
                if response.status_code == 200:
                    with open(self.sha_name, "w", encoding="utf-8") as file:
                        file.write(response.text)
                    # parse the sha file
                    with open(self.sha_name, "r", encoding="utf-8") as file:
                        sha = yaml.load(file, Loader=yaml.FullLoader)
                    # get the sha from the sha file
                    sha = sha[self.hash_type]
                    decoded_hash = base64.b64decode(sha).hex()
                    # find appimage sha
                    appimage_sha = hashlib.new(self.hash_type,
                                   open(self.appimage_name, "rb").read()).hexdigest()
                    if appimage_sha == decoded_hash:
                        print(f"{self.appimage_name} verified")
                        self.make_executable()
                        if input("Do you want to delete the downloaded sha file? (y/n): "
                                ).lower() == "y":
                            os.remove(self.sha_name)
                            print(f"Deleted {self.sha_name}")
                        else:
                            print(f"Saved {self.sha_name}")
                    else:
                        print(f"Error verifying {self.appimage_name}")
                        if input("Do you want to delete the downloaded appimage? (y/n): "
                                ).lower() == "y":
                            os.remove(self.appimage_name)
                            print(f"Deleted {self.appimage_name}")
                        else:
                            if input("Do you want to continue without verification? (y/n): "
                                    ).lower() == "y":
                                self.make_executable()
                            else:
                                sys.exit(1)
            else:
                # if the sha_name doesn't endswith .yml or .yaml,
                # then use the normal sha verification
                print(f"Verifying {self.appimage_name}...")
                if hashlib.new(self.hash_type, open(self.appimage_name, "rb"
                                ).read()).hexdigest() == \
                    requests.get(self.sha_url, timeout=10).text.split(" ")[0]:
                    print(f"{self.appimage_name} verified")
                    self.make_executable()
                else:
                    print(f"Error verifying {self.appimage_name}")
                    # ask user if he wants to delete the downloaded appimage
                    if input("Do you want to delete the downloaded appimage? (y/n): "
                            ).lower() == "y":
                        os.remove(self.appimage_name)
                        print(f"Deleted {self.appimage_name}")
                    else:
                        if input("Do you want to continue without verification? (y/n): "
                                ).lower() == "y":
                            self.make_executable()
                        else:
                            print("Exiting...")
                            sys.exit()
        except KeyError as error:
            print(f"Error verifying {self.appimage_name}: {error}")
            if input("Do you want to delete the downloaded appimage and verify file? (y/n): "
                    ).lower() == "y":
                try:
                    os.remove(self.appimage_name)
                    os.remove(self.sha_name)
                except FileNotFoundError as error:
                    print(f"Error deleting {self.appimage_name} or {self.sha_name}: {error}")
                else:
                    print(f"Deleted {self.appimage_name}")
                    print("Exiting...")
                    sys.exit()
            else:
                if input("Do you want to continue without verification? (y/n): "
                        ).lower() == "y":
                    self.make_executable()
                else:
                    print("Exiting...")
                    sys.exit()

    def make_executable(self):
        """Make the appimage executable"""
        # if already executable, return
        if os.access(self.appimage_name, os.X_OK):
            return
        print("Making the appimage executable...")
        subprocess.run(["chmod", "+x", self.appimage_name], check=True)
        print("Appimage is now executable")
        self.change_name()

    def backup_old_appimage(self):
        """ Save old {self.repo}.AppImage to a backup folder, ask user for approval """

        backup_folder = os.path.expanduser(f"{self.appimage_folder}backup/")

        old_appimage_folder = os.path.expanduser(f"{self.appimage_folder}{self.repo}.AppImage")

        print(f"Moving {old_appimage_folder} to {backup_folder}")

        if os.path.exists(backup_folder):
            print(f"Backup folder {backup_folder} found")
            if os.path.exists(f"{self.appimage_folder}{self.repo}.AppImage"):
                print(f"Found {self.repo}.AppImage in {self.appimage_folder}")
                if input(f"Do you want to backup"
                        f"{self.repo}.AppImage to {backup_folder} (y/n):") == "y":
                    try:
                        subprocess.run(["mv", f"{old_appimage_folder}",
                                     f"{backup_folder}"], check=True)
                    except subprocess.CalledProcessError:
                        print(f"Error moving {old_appimage_folder} to {backup_folder}")
                else:
                    print(f"Not backing up {self.repo}.AppImage")
            else:
                print(f"{self.repo}.AppImage not found in {self.appimage_folder}")
        else:
            if input(f"Backup folder {backup_folder} not found,"
                    "do you want to create it (y/n): ") == "y":
                subprocess.run(["mkdir", "-p", backup_folder], check=True)
                print(f"Created backup folder: {backup_folder}")
            else:
                print(f"Overwriting {self.repo}.AppImage")

    def change_name(self):
        """ Change appimage name for .desktop file on linux, ask user for approval """
        new_name = f"{self.repo}.AppImage"
        if self.appimage_name != new_name:
            print(f"Changing {self.appimage_name} to {new_name}")
            subprocess.run(["mv", f"{self.appimage_name}", f"{new_name}"], check=True)
            self.appimage_name = new_name
            self.move_appimage()
        else:
            print("The appimage name is already the new name")

    def move_appimage(self):
        """ Move appimages to a appimage folder """
        print(f"Moving {self.appimage_name} to {self.appimage_folder}")
        # ask user
        if input(f"Do you want to move"
                f"{self.repo}.AppImage to {self.appimage_folder} (y/n):") == "y":
            subprocess.run(["mv", f"{self.repo}.AppImage", f"{self.appimage_folder}"], check=True)
        else:
            print(f"Not moving {self.appimage_name} to {self.appimage_folder}")
