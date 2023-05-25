#!/usr/bin/python3
import json
import os
import subprocess
import hashlib
import base64
import sys
import requests
import yaml

class AppImageDownloader:
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
        self.url = None
        self.choice = None
        self.appimages = {}

    def ask_user(self):
        """New appimage installation options"""
        print("Choose one of the following options:")
        print("1. Download new appimage, save old appimage")
        print("2. Download new appimage, don't save old appimage")
        self.choice = int(input("Enter your choice: "))
        if self.choice not in [1, 2]:
            print("Invalid choice. Try again.")
            self.ask_user()                 
    
    def learn_owner_repo(self):
        while True:
            # Parse the owner and repo from the URL
            try:
                self.owner = self.url.split("/")[3]
                self.repo = self.url.split("/")[4]
                self.url = f"https://github.com/{self.owner}/{self.repo}"
                break
            except IndexError:
                print("Invalid URL, please try again.")
                self.ask_inputs()

    def list_json_files(self):
        """
        List the json files in the current directory, if json file exists.
        """
        json_files = [file for file in os.listdir() if file.endswith(".json")]
        if len(json_files) > 1:
            print("There are more than one .json file, please choose one of them:")
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
        while True:
            self.url = input("Enter the app github url: ").strip(" ")
            self.sha_name = input("Enter the sha name: ").strip(" ")
            self.appimage_folder = input("Which directory(e.g /Documents/appimages)to save appimage: ").strip(" ")
            self.hash_type = input("Enter the hash type for your sha (e.g md5, sha256, sha1) file: ").strip(" ")

            if self.url and self.sha_name and self.appimage_folder and self.hash_type:
                break
            else:
                print("Invalid inputs, please try again.")                

    def save_credentials(self):
        """Save the credentials to a file in json format, one file per owner and repo"""
        self.appimages["owner"] = self.owner
        self.appimages["repo"] = self.repo
        self.appimages["appimage"] = self.appimage_name
        self.appimages["version"] = self.version
        self.appimages["sha"] = self.sha_name                
        self.appimages["hash_type"] = self.hash_type

        if self.choice == 1:
            # save choice "3" to json file for future use
            self.appimages["choice"] = 3
        elif self.choice == 2:
            self.appimages["choice"] = 4        

        if not self.appimage_folder.endswith("/"):
            self.appimages["appimage_folder"] = self.appimage_folder + "/"            
        else:
            self.appimages["appimage_folder"] = self.appimage_folder

        if not self.appimage_folder.startswith("~"):
            self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimage_folder        
        else:
            self.appimages["appimage_folder"] = os.path.expanduser(self.appimage_folder)

        with open(f"{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(f"Saved credentials to {self.repo}.json file")
        self.load_credentials()

    def load_credentials(self):
        """Load the credentials from a file in json format, one file per owner and repo"""
        if os.path.exists(f"{self.repo}.json"):
            with open(f"{self.repo}.json", "r", encoding="utf-8") as file:
                self.appimages = json.load(file)
            self.owner = self.appimages["owner"]
            self.repo = self.appimages["repo"]
            self.appimage_name = self.appimages["appimage"]
            self.version = self.appimages["version"]
            self.sha_name = self.appimages["sha"]
            self.choice = self.appimages["choice"]
            self.hash_type = self.appimages["hash_type"]
            if self.appimages["appimage_folder"].startswith("~"):
                self.appimage_folder = os.path.expanduser(self.appimage_folder)
            else:
                self.appimage_folder = self.appimages["appimage_folder"]
        else:
            print(f"{self.repo}.json file not found while trying to load credentials")
            self.ask_user()

    def download(self):
        """ Download the appimage from the github api"""
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

        print(f"{self.appimage_name} and {self.sha_name} downloading. Take a cup of coffee :), it will take some time depending on your internet speed.")
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            with open(self.appimage_name, "wb") as file:
                file.write(response.content)
            print(f"\n{self.appimage_name} and {self.sha_name} downloaded ")
        else:
            print(f"Error downloading {self.appimage_name} and {self.sha_name} file")

        # update version in the json file
        self.appimages["version"] = self.version
        with open(f"{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)

    def update_json(self):
        """Update json files with new version and if user want to change appimage file, sha name etc."""
        if input("Do you want to change some credentials? (y/n): ").lower() == "y":
            with open(f"{self.repo}.json", "r", encoding="utf-8") as file:
                self.appimages = json.load(file)
            
            if input("Do you want to change the appimage folder? (y/n): ").lower() == "y":
                self.appimages["appimage_folder"] = input("Enter new appimage folder: ")
                if not self.appimages["appimage_folder"].endswith("/") and not self.appimages["appimage_folder"].startswith("~"):
                    self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimages["appimage_folder"] + "/"
                elif self.appimages["appimage_folder"].startswith("~") and self.appimages["appimage_folder"].endswith("/"):
                    self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimages["appimage_folder"]
                elif self.appimages["appimage_folder"].startswith("~") and not self.appimages["appimage_folder"].endswith("/"):
                    self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimages["appimage_folder"] + "/"
                else:
                    self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimages["appimage_folder"]
            
            # ask for sha_name and hash_type
            keys = {"sha_name", "hash_type"}
            for key in keys:
                if input(f"Do you want to change the {key}? (y/n): ").lower() == "y":
                    self.appimages[key] = input(f"Enter new {key}: ")  

            # ask for choice update
            if input("Do you want to change the choice? (y/n): ").lower() == "y":
                self.appimages["choice"] = int(input("Enter new choice: "))                          

            # write new credentials to json file
            with open(f"{self.repo}.json", "w", encoding="utf-8") as file:
                json.dump(self.appimages, file, indent=4)
        else:
            print("Not changing credentials") 
        self.load_credentials()   

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
                    appimage_sha = hashlib.new(self.hash_type, open(self.appimage_name, "rb").read()).hexdigest() 
                    
                    if appimage_sha == decoded_hash:
                        print(f"{self.appimage_name} verified")
                        self.make_executable()
                        if input("Do you want to delete the downloaded sha file? (y/n): ").lower() == "y":
                            os.remove(self.sha_name)
                            print(f"Deleted {self.sha_name}")
                        else:
                            print(f"Saved {self.sha_name}")                        
                    else:
                        print(f"Error verifying {self.appimage_name}")
                        if input("Do you want to delete the downloaded appimage? (y/n): ").lower() == "y":
                            os.remove(self.appimage_name)
                            print(f"Deleted {self.appimage_name}")
                        else:
                            if input("Do you want to continue without verification? (y/n): ").lower() == "y":
                                self.make_executable()                
                            else:
                                sys.exit(1)
            else:
                # if the sha_name doesn't endswith .yml or .yaml, then use the normal sha verification        
                print(f"Verifying {self.appimage_name}...")
                if hashlib.new(self.hash_type, open(self.appimage_name, "rb").read()).hexdigest() == \
                    requests.get(self.sha_url, timeout=10).text.split(" ")[0]:
                    print(f"{self.appimage_name} verified")
                    self.make_executable()
                else:
                    print(f"Error verifying {self.appimage_name}")
                    # ask user if he wants to delete the downloaded appimage
                    if input("Do you want to delete the downloaded appimage? (y/n): ").lower() == "y":
                        os.remove(self.appimage_name)
                        print(f"Deleted {self.appimage_name}")            
                    else:
                        if input("Do you want to continue without verification? (y/n): ").lower() == "y":
                            self.make_executable()
                        else:
                            print("Exiting...")
                            sys.exit()
        except KeyError:
            print(f"Error verifying {self.appimage_name}")
            if input("Do you want to delete the downloaded appimage? (y/n): ").lower() == "y":
                os.remove(self.appimage_name)
                print(f"Deleted {self.appimage_name}")            
            else:
                if input("Do you want to continue without verification? (y/n): ").lower() == "y":
                    self.make_executable()
                else:
                    print("Exiting...")
                    sys.exit()

    def make_executable(self):
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

        if not os.path.exists(backup_folder):
            if input(f"Backup folder {backup_folder} not found, do you want to create it (y/n): ") == "y":
                subprocess.run(["mkdir", "-p", backup_folder], check=True)
                print(f"Created backup folder: {backup_folder}")
            else:
                print(f"Overwriting {self.repo}.AppImage")
        else:
            print(f"Backup folder {backup_folder} found")
            if os.path.exists(f"{self.appimage_folder}{self.repo}.AppImage"):
                print(f"Found {self.repo}.AppImage in {self.appimage_folder}")
                if input(f"Do you want to backup {self.repo}.AppImage to {backup_folder} (y/n): ") == "y":
                  
                    try:
                        subprocess.run(["mv", f"{old_appimage_folder}", f"{backup_folder}"], check=True)
                    except subprocess.CalledProcessError:
                        print(f"Error moving {old_appimage_folder} to {backup_folder}")                        
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
        # ask user
        if input(f"Do you want to move {self.repo}.AppImage to {self.appimage_folder} (y/n): ") == "y":
            subprocess.run(["mv", f"{self.repo}.AppImage", f"{self.appimage_folder}"], check=True)
        else:
            print(f"Not moving {self.appimage_name} to {self.appimage_folder}")

def main():
    file_handler = FileHandler()

    functions = {
        1: ['ask_inputs', 'learn_owner_repo', 'download', 'save_credentials', 'verify_sha', 'backup_old_appimage'],
        2: ['ask_inputs', 'learn_owner_repo', 'download', 'save_credentials', 'verify_sha'],
        3: ['update_json', 'download', 'verify_sha', 'backup_old_appimage'],
        4: ['update_json', 'download', 'verify_sha']
    }

    print("Welcome to the my-unicorn 🦄!")
    print("Choose one of the following options:")
    print("1. Update appimage from JSON file")
    print("2. Download new appimage")
    print("3. Exit")
    choice = int(input("Enter your choice: "))

    if choice == 1:
        file_handler.list_json_files()
        if file_handler.choice in [3, 4]:
            for function in functions[file_handler.choice]:
                if function in dir(file_handler):
                    method = getattr(file_handler, function)
                    method()
                else:
                    print(f"Function {function} not found")
    elif choice == 2:
        print("Downloading new appimage")
        file_handler.ask_inputs()
        for function in functions[choice]:
            if function in dir(file_handler):
                method = getattr(file_handler, function)
                method()
            else:
                print(f"Function {function} not found")
    elif choice == 3:
        print("Exiting...")
        sys.exit()
    else:
        print("Invalid choice")
        sys.exit()
      

if __name__ == "__main__":
    main()