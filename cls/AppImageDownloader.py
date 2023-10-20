import os
import json
import sys
import logging
import requests
from tqdm import tqdm

class AppImageDownloader:
    """This class downloads the appimage from the github release page"""
    # The path to the json files
    file_path = "json_files/"

    def __init__(self):
        self.owner: str = None
        self.repo: str = None
        self.api_url: str = None
        self.sha_name: str = None
        self.sha_url = None
        self.appimage_name: str = None
        self.version = None
        self.appimage_folder: str = None
        self.hash_type: str = None
        self.url: str = None
        self.choice: int = None
        self.appimages: dict = {}

    def ask_user(self):
        """New appimage installation options"""
        print("Choose one of the following options:")
        print("====================================")
        print("1. Download new appimage, save old appimage")
        print("2. Download new appimage, don't save old appimage")
        try:
            self.choice = int(input("Enter your choice: "))
        except (ValueError, KeyboardInterrupt) as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError: {error}. Exiting...\033[0m")
            sys.exit(1)
        else:
            if self.choice not in [1, 2]:
                print("Invalid choice. Try again.")
                self.ask_user()

    def learn_owner_repo(self):
        """Learn the owner and repo from the url"""
        while True:
            # Parse the owner and repo from the URL
            print("Parsing the owner and repo from the url...")
            try:
                self.owner = self.url.split("/")[3]
                self.repo = self.url.split("/")[4]
                self.url = f"https://github.com/{self.owner}/{self.repo}"
                break
            except IndexError as error:
                logging.error(f"Error: {error}", exc_info=True)
                print("Invalid URL, please try again.")
                self.ask_inputs()
            except KeyboardInterrupt as error2:
                logging.error(f"Error: {error2}", exc_info=True)
                print("\nExiting...")
                sys.exit()

    def list_json_files(self):
        """
        List the json files in the current directory, if json file exists.
        """
        try:
            json_files = [file for file in os.listdir(self.file_path)
                         if file.endswith(".json")]
        except FileNotFoundError as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError: {error}. Exiting...\033[0m")
            self.ask_inputs()
        if len(json_files) > 1:
            print("\nThere are more than one .json file, please choose one of them:")
            print("================================================================")
            for index, file in enumerate(json_files):
                print(f"{index + 1}. {file}")
            try:
                choice = int(input("Enter your choice: "))
            except ValueError as error2:
                logging.error(f"Error: {error2}", exc_info=True)
                print(f"Invalid choice. Please write a number. \n Error: {error2}")
            else:
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
            try:
                self.url = input("Enter the app github url: ").strip(" ")
                self.appimage_folder = input(
                    "Which directory to save appimage \n"
                    "(Default: '/Documents/appimages' if you leave it blank):" 
                    ).strip(" ")
                # setup default appimage folder
                if not self.appimage_folder:
                    self.appimage_folder = "/Documents/appimages"

                self.hash_type = input(
                    "Enter the hash type for your sha(sha256, sha512) file: "
                    ).strip(" ")
            except (KeyboardInterrupt, EOFError, ValueError) as error:
                logging.error(f"Error: {error}", exc_info=True)
                print(f"\n\033[41;30mError: {error}. Exiting...\033[0m")
                sys.exit()

            if self.url and self.appimage_folder and self.hash_type:
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
        if not self.appimage_folder.endswith("/"):
            self.appimage_folder += "/"

        if not self.appimage_folder.startswith("/"):
            self.appimage_folder = "/" + self.appimage_folder

        if self.appimage_folder.startswith("~"):
            self.appimage_folder = os.path.expanduser(self.appimage_folder)
        else:
            self.appimage_folder = os.path.expanduser("~") + self.appimage_folder

        self.appimages["appimage_folder"] = self.appimage_folder

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
            except KeyError as error:
                logging.error(f"Error: {error}", exc_info=True)
                print(f"appimage_folder key not found in json file. \n Error: {error}")
                self.ask_user()
        else:
            print(f"{self.file_path}{self.repo}.json"
                  "File not found while trying to load credentials or unknown error.")
            self.ask_user()

    def get_response(self):
        """ get the api response from the github api"""
        self.api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        try:
            # get the api response
            response = requests.get(self.api_url, timeout=10)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError: {error}. Exiting...\033[0m")
            sys.exit()
        else:
            # check the response status code
            if response.status_code == 200:
                # get the download url from the api
                data = json.loads(response.text)
                # get the version from the tag_name, remove the v from the version
                self.version = data["tag_name"].replace("v", "")
                
                # version control
                if self.choice in [3, 4]:
                    if self.version == self.appimages["version"]:
                        print(f"{self.repo}.AppImage is up to date")
                        print(f"Version: {self.version}")
                        print("Exiting...")
                        sys.exit()
                print("-------------------------------------------------")
                print(f"Current version: {self.appimages['version']}")
                print(f"Latest version: {self.version}")
                print(f"{self.repo} downloading..."
                    "Grab a cup of coffee :), "
                    "it will take some time depending on your internet speed."
                    )
                print("-------------------------------------------------")

                # Define keywords for the assets
                keywords = {"linux", "sum", "sha", "SHA", "SHA256", "SHA512", "SHA-256", "SHA-512", "checksum", "checksums"}
                valid_extensions = {".sha256", ".sha512", ".yml", ".yaml", ".txt", ".sum", ".sha"}
                
                # get the download url from the assets
                for asset in data["assets"]:
                    if asset["name"].endswith(".AppImage"):
                        self.appimage_name = asset["name"]
                        self.url = asset["browser_download_url"]
                    elif any(keyword in asset["name"] for keyword in keywords) and \
                            asset["name"].endswith(tuple(valid_extensions)):
                        self.sha_name = asset["name"]
                        self.sha_url = asset["browser_download_url"]
                        if self.sha_name is None:
                            print("Couldn't find the sha file")
                            logging.error("Couldn't find the sha file")
                            # ask user exact SHA name
                            self.sha_name = input("Enter the exact sha name: ")
                            self.sha_url = asset["browser_download_url"]

    def download(self):
        """ Download the appimage from the github api"""
        # Check if the appimage already exists
        if os.path.exists(self.appimage_name) or os.path.exists(self.repo + ".AppImage"):
            print(f"{self.appimage_name} already exists in the current directory")
            return
        
        # Request the appimage from the url
        try:
            response = requests.get(self.url, timeout=10, stream=True)
            total_size_in_bytes = int(response.headers.get("content-length", 0))
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                requests.exceptions.RequestException) as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError: {error}. Exiting...\033[0m")
            sys.exit()
        else:
            if response.status_code == 200:
                # save the appimage to the appimage folder
                with open(f"{self.appimage_name}", "wb") as file, tqdm(
                    desc=self.appimage_name,
                    total=total_size_in_bytes,
                    unit="iB",
                    unit_scale=True,
                    unit_divisor=1024,
                ) as progress_bar:
                    for data in response.iter_content(chunk_size=8192):
                        size = file.write(data)
                        progress_bar.update(size)
            else:
                print(f"\033[41;30mError downloading {self.appimage_name}\033[0m")
                logging.error(f"Error downloading {self.appimage_name}")
                sys.exit()
        finally:
            # save the credentials to a json file
            with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
                json.dump(self.appimages, file, indent=4)

            # make sure to close the response
            if response is not None:
                response.close()
                print("-------------------------------------------------")
                print(f"\033[42mDownload completed! {self.appimage_name} installed.\033[0m")
                print("-------------------------------------------------")
            else:
                print("-------------------------------------------------")
                print(f"\033[41;30mError downloading {self.appimage_name}\033[0m")
                print("-------------------------------------------------")


    def update_json(self):
        """Update the json file with the new credentials"""
        try:
            if input("\nDo you want to change some credentials? (y/n): ").lower() == "y":
                with open(f"{self.file_path}{self.repo}.json", "r", encoding="utf-8") as file:
                    self.appimages = json.load(file)
                if input("Do you want to change the appimage folder? (y/n): ").lower() == "y":
                    new_folder = input("Enter new appimage folder: ")
                    if not new_folder.endswith("/"):
                        new_folder += "/"

                    if not new_folder.startswith("/"):
                        new_folder = "/" + new_folder

                    if new_folder.startswith("~"):
                        new_folder = os.path.expanduser(new_folder)
                    else:
                        new_folder = os.path.expanduser("~") + new_folder

                    self.appimages["appimage_folder"] = new_folder

                # ask for sha_name and hash_type
                keys = {"sha_name", "hash_type", "choice"}
                for key in keys:
                    if input(f"Do you want to change the {key}? (y/n): ").lower() == "y":
                        if key == "choice":
                            new_choice = input("Enter new choice (3: backup, 4: don't backup): ")
                            while new_choice not in ["3", "4"]:
                                new_choice = input("Invalid input. Enter new choice (3: backup, 4: don't backup): ")
                            self.appimages[key] = int(new_choice)
                        else:
                            self.appimages[key] = input(f"Enter new {key}: ")

                        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
                            json.dump(self.appimages, file, indent=4)

                        # load the credentials
                        self.load_credentials()

                    else:
                        print("Not changing credentials")
                        self.load_credentials()

        except (KeyboardInterrupt, EOFError, ValueError, KeyError) as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(f"\033[41;30mError: {error}. Exiting...\033[0m")
            sys.exit()
