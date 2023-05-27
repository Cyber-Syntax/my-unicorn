import os
import json
import requests

class AppImageDownloader:
    """This class downloads the appimage from the github release page"""
    # The path to the json files
    file_path = "json_files/"

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
        """Learn the owner and repo from the url"""
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
        json_files = [file for file in os.listdir(self.file_path) if file.endswith(".json")]
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
        """Ask the user for the inputs"""
        while True:
            self.url = input("Enter the app github url: ").strip(" ")
            self.sha_name = input("Enter the sha name: ").strip(" ")
            self.appimage_folder = input(
                "Which directory(e.g /Documents/appimages)to save appimage: " 
                ).strip(" ")
            self.hash_type = input(
                "Enter the hash type for your sha(e.g md5, sha256, sha1) file: "
                ).strip(" ")

            if self.url and self.sha_name and self.appimage_folder and self.hash_type:
                break
            else:
                print("Invalid inputs, please try again.")

    def save_credentials(self):
        """Save the credentials to a file in json format"""
        self.appimages["owner"] = self.owner
        self.appimages["repo"] = self.repo
        self.appimages["appimage"] = self.appimage_name
        self.appimages["version"] = self.version
        self.appimages["sha"] = self.sha_name
        self.appimages["hash_type"] = self.hash_type
        self.appimages["choice"] = 3 if self.choice == 1 else 4

        # Handle expansion of ~ in the path
        if self.appimage_folder.endswith("/"):
            self.appimages["appimage_folder"] = self.appimage_folder
        else:
            self.appimages["appimage_folder"] = self.appimage_folder + "/"

        if self.appimage_folder.startswith("~"):
            self.appimages["appimage_folder"] = os.path.expanduser(self.appimage_folder)
        else:
            self.appimages["appimage_folder"] = os.path.expanduser("~") + self.appimage_folder

        # save the credentials to a json_files folder
        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(f"Saved credentials to json_files/{self.repo}.json file")
        self.load_credentials()

    def load_credentials(self):
        """Load the credentials from a json file"""
        if os.path.exists(f"{self.file_path}{self.repo}.json"):
            with open(f"{self.file_path}{self.repo}.json", "r", encoding="utf-8") as file:
                self.appimages = json.load(file)
            self.owner = self.appimages["owner"]
            self.repo = self.appimages["repo"]
            self.appimage_name = self.appimages["appimage"]
            self.version = self.appimages["version"]
            self.sha_name = self.appimages["sha"]
            self.choice = self.appimages["choice"]
            self.hash_type = self.appimages["hash_type"]
            try:
                if self.appimages["appimage_folder"].startswith("~"):
                    self.appimage_folder = os.path.expanduser(self.appimage_folder)
                else:
                    self.appimage_folder = self.appimages["appimage_folder"]
            except KeyError:
                print("appimage_folder key not found in json file")
        else:
            print(f"{self.file_path}{self.repo}.json"
                  "file not found while trying to load credentials")
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

        print(f"{self.appimage_name} and {self.sha_name} downloading."
              "Grab a cup of coffee :), it will take some time depending on your internet speed."
              )
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            with open(self.appimage_name, "wb") as file:
                file.write(response.content)
            print(f"\n{self.appimage_name} and {self.sha_name} downloaded ")
        else:
            print(f"Error downloading {self.appimage_name} and {self.sha_name} file")
        # update version in the json file
        self.appimages["version"] = self.version
        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)

    def update_json(self):
        """Update the json file with the new version"""
        if input("Do you want to change some credentials? (y/n): ").lower() == "y":
            with open(f"{self.file_path}{self.repo}.json", "r", encoding="utf-8") as file:
                self.appimages = json.load(file)

            if input("Do you want to change the appimage folder? (y/n): ").lower() == "y":
                new_folder = input("Enter new appimage folder: ")
                if not new_folder.endswith("/"):
                    new_folder += "/"

                if new_folder.startswith("~"):
                    new_folder = os.path.expanduser(new_folder)
                else:
                    new_folder = os.path.expanduser("~") + new_folder

                self.appimages["appimage_folder"] = new_folder

            # ask for sha_name and hash_type
            keys = {"sha_name", "hash_type"}
            for key in keys:
                if input(f"Do you want to change the {key}? (y/n): ").lower() == "y":
                    self.appimages[key] = input(f"Enter new {key}: ")

            # ask for choice update
            if input("Do you want to change the choice?"
                    "(3: backup, 4: don't backup) (y/n): ").lower() == "y":
                self.appimages["choice"] = int(input("Enter new choice: "))

            # write new credentials to json file
            with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
                json.dump(self.appimages, file, indent=4)
        else:
            print("Not changing credentials")
        self.load_credentials()
      