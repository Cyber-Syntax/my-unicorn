"""
This script downloads the latest AppImage from a given
repository and saves the credentials to a file.
"""
import json
import os
import subprocess
import hashlib
import requests

class AppImageDownloader:
    """
    This class downloads the latest AppImage from a given
    repository and saves the credentials to a file.
    """
    def __init__(self):
        self.owner = None
        self.repo = None
        self.api_url = None
        self.sha_name = None
        self.sha_url = None
        self.appimage_name = None
        self.version = None
        self.appimage_folder = None
        self.hash_type = None
        self.appimages = {}

    def ask_user(self):
        """
        All questions are asked to the user and their answers are recorded. 
        Based on the recorded answers, 
        it is learned which functions to go and in which order, and these functions are called accordingly.
        """
        print("Welcome to the AppImage Downloader")
        print("Choose one of the following options:")
        print("1. Download the new latest AppImage, save old AppImage")
        print("2. Download the new latest AppImage, don't save old AppImage")
        print("3. Update the latest AppImage from a json file, save old AppImage")
        print("4. Update the latest AppImage from a json file, don't save old AppImage")
        print("5. List the json files in the current directory")
        print("6. Exit")
        choice = int(input("Enter your choice: "))
        if choice == 1:
            self.ask_inputs()
            self.save_credentials()
            self.download()
            self.backup_old_appimage()
            self.verify_sha()                     
        elif choice == 2:
            self.ask_inputs()
            self.save_credentials()
            self.download()
            self.verify_sha()
        elif choice == 3:
            self.list_json_files()
            self.backup_old_appimage()
            self.download()
            self.verify_sha()
        elif choice == 4:
            self.list_json_files()
            self.download()
            self.verify_sha()
        else:
            print("Invalid choice, try again")
            self.ask_user()

    def list_json_files(self):
        """
        List the json files in the current directory, if json file exists,
        then ask user to backup old appimage
        """        
        json_files = [file for file in os.listdir() if file.endswith(".json")]
        if len(json_files) > 1:
            print("There are more than one .json file, please choose one of them.")
            for index, file in enumerate(json_files):
                print(f"{index + 1}. {file}")
            choice = int(input("Enter your choice: "))
            self.repo = json_files[choice - 1].replace(".json", "")
            self.load_credentials()
        elif len(json_files) == 1:
            self.repo = json_files[0].replace(".json", "")
            self.load_credentials()
        else:
            print("There is no .json file in the current directory")
            self.ask_inputs()

    def ask_inputs(self):
        """Ask the user for the owner and repo"""
        self.owner = input("Enter the owner: ")
        self.repo = input("Enter the repo: ")
        self.sha_name = input("Enter the sha name: ")
        self.appimage_folder = input("Which directory to save appimage: ")
        self.hash_type = input("Enter the hash type for your sha (e.g md5, sha256, sha1) file: ")


    def save_credentials(self):
        """Save the credentials to a file in json format, one file per owner and repo"""
        self.download()
        self.appimages["owner"] = self.owner
        self.appimages["repo"] = self.repo
        self.appimages["appimage"] = self.appimage_name
        self.appimages["version"] = self.version
        self.appimages["sha"] = self.sha_name
        self.appimages["hash_type"] = self.hash_type
        self.appimages["appimage_folder"] = "~" + self.appimage_folder
        with open(f"{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(f"Saved credentials to {self.repo}.json file")

    def load_credentials(self):
        """
        Load the credentials from a file in json format, one file per owner and repo
        """
        if os.path.exists(f"{self.repo}.json"):
            with open(f"{self.repo}.json", "r", encoding="utf-8") as file:
                self.appimages = json.load(file)
            self.owner = self.appimages["owner"]
            self.repo = self.appimages["repo"]
            self.appimage_name = self.appimages["appimage"]
            self.version = self.appimages["version"]
            self.sha_name = self.appimages["sha"]
            self.hash_type = self.appimages["hash_type"]
            self.appimage_folder = self.appimages["appimage_folder"]
        else:
            print(f"{self.repo}.json file not found while trying to load credentials")

    def download(self):
        """Get the credentials, urls from the api"""
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            data = json.loads(response.text)
            self.version = data["tag_name"].replace("v", "")
            for asset in data["assets"]:
                if asset["name"].endswith(".AppImage"):
                    self.api_url = asset["browser_download_url"]
                    self.appimage_name = asset["name"]
                elif asset["name"] == self.sha_name:
                    self.sha_url = asset["browser_download_url"]
                    self.sha_name = asset["name"]

        print(f"Downloading {self.appimage_name}...")
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            with open(self.appimage_name, "wb") as file:
                file.write(response.content)
            print(f"Downloaded {self.appimage_name} and {self.sha_name} file")
        else:
            print(f"Error downloading {self.appimage_name} and {self.sha_name} file")

    def verify_sha(self):
        """ Verify the sha of the downloaded appimage """
        print(f"Verifying {self.appimage_name}...")
        if hashlib.new(self.hash_type, open(self.appimage_name, "rb").read()).hexdigest() == \
                requests.get(self.sha_url, timeout=10).text.split(" ")[0]:
            print(f"{self.appimage_name} verified")
            self.make_executable()
        else:
            print(f"Error verifying {self.appimage_name}")

    def make_executable(self):
        """ Make the downloaded appimage executable """
        # if already executable, return
        if os.access(self.appimage_name, os.X_OK):
            return
        print("Making the appimage executable...")
        subprocess.run(["chmod", "+x", self.appimage_name], check=True)
        print("Appimage is now executable")
        self.change_name()

    def backup_old_appimage(self):
        """ Save old {self.repo}.AppImage to a backup folder, ask user for approval """
        backup_folder = f"{self.appimage_folder}backup" # ~/Documents/appimages/backup

        if not os.path.exists(backup_folder):
            if input(f"Backup folder {backup_folder} not found, do you want to create it (y/n): ") == "y":
                os.makedirs(backup_folder, exist_ok=True)
                print(f"Created backup folder: {backup_folder}")
            else:
                print(f"Overwriting {self.repo}.AppImage")
                self.download()
                return
        else:
            print(f"Backup folder {backup_folder} found")                
            if os.path.exists(f"{self.appimage_folder}{self.repo}.AppImage"):
                print(f"Found {self.repo}.AppImage in {self.appimage_folder}")
                if input(f"Do you want to backup {self.repo}.AppImage to {backup_folder} (y/n): ") == "y":
                    print(f"Backing up {self.repo}.AppImage to backup folder")
                    subprocess.run(["mv", f"{self.appimage_folder}{self.repo}.AppImage", f"{backup_folder}"], check=True)
                else:
                    print(f"Not backing up {self.repo}.AppImage")
            else:
                print(f"{self.repo}.AppImage not found in {self.appimage_folder}")


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
        subprocess.run(["mv", f"{self.repo}.AppImage", f"{self.appimage_folder}"], check=True)

# main
if __name__ == "__main__":
    appimage = AppImageDownloader()
    appimage.list_json_files()

