"""
This script downloads the latest AppImage from a given
repository and saves the credentials to a file.
"""
import json
import os
import subprocess
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

    def ask_inputs(self):
        """Ask the user for the owner and repo"""
        # Check if the credentials file exists
        # if it does, load the credentials
        # if it doesn't, ask the user for the credentials
        if len(os.listdir()) > 0:
            self.load_credentials()
        else:
            self.owner = input("Enter the owner: ")
            self.repo = input("Enter the repo: ")
            self.sha_name = input("Enter the sha name: ")
            self.appimage_folder = input("Where do you want to save appimage: ")
            self.hash_type = input("Enter the hash type for your sha file: ")
            # ask user the save the credentials to a file
            save_credentials = input("Save credentials to file? (y/n): ")
            if save_credentials == "y":
                self.save_credentials()
            else:
                self.load_credentials()

    def save_credentials(self):
        """Save the credentials to a file in json format, one file per owner and repo"""
        self.download()
        self.appimages["owner"] = self.owner
        self.appimages["repo"] = self.repo
        self.appimages["appimage"] = self.appimage_name
        self.appimages["version"] = self.version
        self.appimages["sha"] = self.sha_name
        self.appimages["hash_type"] = self.hash_type
        self.appimages["appimage_folder"] = self.appimage_folder
        with open(f"{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        # if json needs to be update with new credentials
        if self.appimage_name is None or self.sha_name is None:
            self.load_credentials()

    def load_credentials(self):
        """
        If there are more than one file, ask the user to choose one of them.
        Load the credentials from a file in json format, one file per owner and repo
        """
        if len(os.listdir()) >= 1:
            json_files = []
            for file in os.listdir():
                if file.endswith(".json"):
                    json_files.append(file)
            if len(json_files) > 1:
                print("There are more than one .json file, please choose one of them.")
                for index, file in enumerate(json_files):
                    print(f"{index + 1}. {file}")
                choice = int(input("Enter your choice: "))
                self.repo = json_files[choice - 1].replace(".json", "")
            else:
                self.repo = json_files[0].replace(".json", "")

            with open(f"{self.repo}.json", "r", encoding="utf-8") as file:
                data = json.load(file)
                self.owner = data["owner"]
                self.repo = data["repo"]
                self.appimage_name = data["appimage"]
                self.version = data["version"]
                self.sha_name = data["sha"]
                self.hash_type = data["hash_type"]
                self.appimage_folder = data["appimage_folder"]
                print(f"Loaded owner: {self.owner}, repo: {self.repo}, appimage: {self.appimage_name}")
                print(f"Loaded {self.repo}.json")

    def download(self):
        """Get the credentials, urls from the api"""
        # get the appimage name on credentials file, if not found, get it from the api
        # find appimage name from latest release api with endswifh .AppImage
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
            print(f"Downloaded {self.appimage_name}")
        else:
            print(f"Error downloading {self.appimage_name} and {self.sha_name} file")

    def verify_sha(self):
        """ Verify the sha of the downloaded appimage """
        """! TODO: Solve the problem with subprocess.run() returning zero even if the appimage is not verified"""
        if self.hash_type == "sha256":
            cmd = subprocess.run(["sha256sum", self.appimage_name, "-c", self.sha_name], check=True, text=False)
            result = subprocess.run(cmd, capture_output=True, text=False, check=True)
            if result.returncode == 0:
                print(f"{self.appimage_name} is verified")
            else:
                print(f"{self.appimage_name} is not verified")
        elif self.hash_type == "sha512":
            cmd = subprocess.run(["sha512sum", self.appimage_name, "-c", self.sha_name], check=True)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if result.returncode == 0:
                print(f"{self.appimage_name} is verified")
            else:
                print(f"{self.appimage_name} is not verified")             

    def save_old_appimage(self):
        """ Save old {self.repo}.AppImage to a backup folder, ask user for approval """
        if os.path.exists(f"{self.appimage_folder}/{self.repo}.AppImage"):
            if input(f"Do you want to save the old {self.repo}.AppImage? (y/n): ") == "y":
                if not os.path.exists(f"{self.appimage_folder}/backup"):
                    os.mkdir(f"{self.appimage_folder}/backup")
                subprocess.run(["mv", f"{self.appimage_folder}/{self.repo}.AppImage",
                                 f"{self.appimage_folder}/backup"], check=True)

    def change_name(self):
        """ Change appimage name for .desktop file on linux, ask user for approval """
        new_name = f"{self.repo}.AppImage"
        # ask user if he wants to change the name
        if input(f"Do you want to change the name of the appimage to {new_name}? (y/n): ") == "y":
            if self.appimage_name != new_name:
                print(f"Changing {self.appimage_name} to {new_name}")
                subprocess.run(["mv", f"{self.appimage_name}", f"{new_name}"], check=True)
                self.appimage_name = new_name
            else:
                print("The appimage name is already the new name")

    def move_appimage(self):
        """ Move appimages to a appimage folder """
        if not os.path.exists(self.appimage_folder):
            os.mkdir(self.appimage_folder)
        subprocess.run(["mv", self.appimage_name, self.appimage_folder], check=True)



# main
if __name__ == "__main__":
    appimage = AppImageDownloader()
    appimage.ask_inputs()
    appimage.download()
    appimage.verify_sha()
    appimage.save_old_appimage()
    appimage.change_name()
