import os
import json
import sys
import logging
import requests
from tqdm import tqdm
from dataclasses import dataclass, field
from .decorators import handle_api_errors, handle_common_errors
import gettext

_ = gettext.gettext


@dataclass
class AppImageDownloader:
    """This class downloads the appimage from the github release page"""

    owner: str = None
    repo: str = None
    api_url: str = None
    sha_name: str = None
    sha_url: str = None
    appimage_name: str = None
    version: str = None
    appimage_folder: str = field(default_factory=lambda: "~/Documents/appimages")
    appimage_folder_backup: str = field(
        default_factory=lambda: "~/Documents/appimages/backup"
    )
    hash_type: str = None
    url: str = None
    choice: int = None
    appimages: dict = field(default_factory=dict)
    file_path: str = field(init=False)

    def __post_init__(self):
        self.appimage_folder = os.path.expanduser(self.appimage_folder)

        self.file_path = os.path.join(self.appimage_folder, "config_files/")
        os.makedirs(self.file_path, exist_ok=True)

        other_settings_folder = os.path.join(self.file_path, "other_settings")
        os.makedirs(other_settings_folder, exist_ok=True)

        self.config_batch_path = os.path.join(other_settings_folder, "batch_mode.json")
        self.config_path = os.path.join(other_settings_folder, "locale.json")

    @handle_common_errors
    def ask_user(self):
        """New appimage installation options"""
        while True:
            print(_("Choose one of the following options:"))
            print("====================================")
            print(_("1. Download new appimage, save old appimage"))
            print(_("2. Download new appimage, don't save old appimage"))
            print("====================================")
            try:
                self.choice = int(input(_("Enter your choice: ")))

                if self.choice not in [1, 2]:
                    print(_("Invalid choice. Try again."))
                    self.ask_user()
            except ValueError:
                print(_("Invalid input. Please enter a valid number."))

    @handle_common_errors
    def learn_owner_repo(self):
        while True:
            print(_("Parsing the owner and repo from the url..."))
            self.owner = self.url.split("/")[3]
            self.repo = self.url.split("/")[4]
            self.url = f"https://github.com/{self.owner}/{self.repo}"
            break

    def list_json_files(self):
        """List the json files in the current directory, if json file exists."""
        try:
            json_files = [
                file for file in os.listdir(self.file_path) if file.endswith(".json")
            ]
        except FileNotFoundError as error:
            logging.error(f"Error: {error}", exc_info=True)
            print(_("\033[41;30mError: {error}. Exiting...\033[0m").format(error=error))
            self.ask_inputs()

        if len(json_files) > 1:
            print(_("Available json files:"))
            print("================================================================")
            for index, file in enumerate(json_files):
                print(f"{index + 1}. {file}")
            try:
                print(
                    "================================================================"
                )
                choice = int(input(_("Enter your choice: ")))
            except ValueError as error2:
                logging.error(f"Error: {error2}", exc_info=True)
                print(_("Invalid choice. Please write a number."))
                self.list_json_files()
            else:
                self.repo = json_files[choice - 1].replace(".json", "")
                self.load_credentials()
        elif len(json_files) == 1:
            self.repo = json_files[0].replace(".json", "")
            self.load_credentials()
        else:
            print(_("There is no .json file in the current directory"))
            self.ask_inputs()

    @handle_common_errors
    def ask_inputs(self):
        while True:
            print("=================================================")
            self.url = input(_("Enter the app github url: ")).strip(" ")
            self.appimage_folder = (
                input(
                    _(
                        "Which directory to save appimage \n(Default: '~/Documents/appimages/' if you leave it blank):"
                    )
                ).strip(" ")
                or self.appimage_folder
            )
            self.appimage_folder_backup = (
                input(
                    _(
                        "Which directory to save old appimage \n(Default: '~/Documents/appimages/backup/' if you leave it blank):"
                    )
                ).strip(" ")
                or self.appimage_folder_backup
            )

            self.hash_type = input(
                _("Enter the hash type for your sha(sha256, sha512) file: ")
            ).strip(" ")
            print("=================================================")

            if (
                self.url
                and self.appimage_folder
                and self.hash_type
                and self.appimage_folder_backup
            ):
                break

    @handle_common_errors
    def save_credentials(self):
        """Save the credentials to a file in json format from response"""
        self.appimages["owner"] = self.owner
        self.appimages["repo"] = self.repo
        self.appimages["appimage"] = self.appimage_name
        self.appimages["version"] = self.version
        self.appimages["sha"] = self.sha_name
        self.appimages["hash_type"] = self.hash_type
        self.appimages["choice"] = 3 if self.choice == 1 else 4

        self.appimage_folder_backup = os.path.join(self.appimage_folder_backup, "")
        self.appimage_folder = os.path.join(self.appimage_folder, "")

        self.appimages["appimage_folder_backup"] = self.appimage_folder_backup
        self.appimages["appimage_folder"] = self.appimage_folder

        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)
        print(
            _("Saved credentials to config_files/{repo}.json file").format(
                repo=self.repo
            )
        )
        self.load_credentials()

    @handle_common_errors
    def load_credentials(self):
        """Load the credentials from a json file"""
        json_path = f"{self.file_path}{self.repo}.json"
        if os.path.exists(json_path):
            with open(
                f"{self.file_path}{self.repo}.json", "r", encoding="utf-8"
            ) as file:
                self.appimages = json.load(file)
            self.owner = self.appimages["owner"]
            self.repo = self.appimages["repo"]
            self.appimage_name = self.appimages["appimage"]
            self.version = self.appimages["version"]
            self.sha_name = self.appimages["sha"]
            self.choice = self.appimages["choice"]
            self.hash_type = self.appimages["hash_type"]

            if self.appimages["appimage_folder"].startswith("~"):
                self.appimage_folder = os.path.expanduser(
                    self.appimages["appimage_folder"]
                )
            else:
                self.appimage_folder = self.appimages["appimage_folder"]

            if self.appimages["appimage_folder_backup"].startswith("~"):
                self.appimage_folder_backup = os.path.expanduser(
                    self.appimages["appimage_folder_backup"]
                )
            else:
                self.appimage_folder_backup = self.appimages["appimage_folder_backup"]
        else:
            print(
                _(
                    "{path}{repo}.json File not found while trying to load credentials or unknown error."
                ).format(path=self.file_path, repo=self.repo)
            )
            self.ask_user()

    @handle_api_errors
    def get_response(self):
        """get the api response from the github api"""
        self.api_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        )

        response = requests.get(self.api_url, timeout=10)

        if response is None:
            print("-------------------------------------------------")
            print(
                _("Failed to get response from API: {api_url}").format(
                    api_url=self.api_url
                )
            )
            print("-------------------------------------------------")
            return

        if response.status_code == 200:
            data = json.loads(response.text)
            self.version = data["tag_name"].replace("v", "")

            if self.choice in [3, 4]:
                if self.version == self.appimages["version"]:
                    print(_("{repo}.AppImage is up to date").format(repo=self.repo))
                    print(_("Version: {version}").format(version=self.version))
                    print(_("Exiting..."))
                    sys.exit()
                else:
                    print("-------------------------------------------------")
                    print(
                        _("Current version: {version}").format(
                            version=self.appimages["version"]
                        )
                    )
                    print(
                        _("\033[42mLatest version: {version}\033[0m").format(
                            version=self.version
                        )
                    )
                    print("-------------------------------------------------")

            keywords = {
                "linux",
                "sum",
                "sha",
                "SHA",
                "SHA256",
                "SHA512",
                "SHA-256",
                "SHA-512",
                "checksum",
                "checksums",
                "CHECKSUM",
                "CHECKSUMS",
            }
            valid_extensions = {
                ".sha256",
                ".sha512",
                ".yml",
                ".yaml",
                ".txt",
                ".sum",
                ".sha",
            }

            for asset in data["assets"]:
                if asset["name"].endswith(".AppImage"):
                    self.appimage_name = asset["name"]
                    self.url = asset["browser_download_url"]
                elif any(keyword in asset["name"] for keyword in keywords) and asset[
                    "name"
                ].endswith(tuple(valid_extensions)):
                    self.sha_name = asset["name"]
                    self.sha_url = asset["browser_download_url"]
                    if self.sha_name is None:
                        print(_("Couldn't find the sha file"))
                        logging.error(_("Couldn't find the sha file"))
                        self.sha_name = input(_("Enter the exact sha name: "))
                        self.sha_url = asset["browser_download_url"]

    @handle_api_errors
    def download(self):
        """Download the appimage from the github api"""
        if os.path.exists(self.appimage_name) or os.path.exists(
            self.repo + ".AppImage"
        ):
            print(
                _("{appimage_name} already exists in the current directory").format(
                    appimage_name=self.appimage_name
                )
            )
            return

        print(
            _(
                "{repo} downloading... Grab a cup of coffee :), it will take some time depending on your internet speed."
            ).format(repo=self.repo)
        )
        response = requests.get(self.url, timeout=10, stream=True)

        total_size_in_bytes = int(response.headers.get("content-length", 0))

        if response.status_code == 200:
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
            print(
                _("\033[41;30mError downloading {appimage_name}\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            logging.error(f"Error downloading {self.appimage_name}")
            sys.exit()

        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)

        if response is not None:
            response.close()
            print("-------------------------------------------------")
            print(
                _(
                    "\033[42mDownload completed! {appimage_name} installed.\033[0m"
                ).format(appimage_name=self.appimage_name)
            )
            print("-------------------------------------------------")
        else:
            print("-------------------------------------------------")
            print(
                _("\033[41;30mError downloading {appimage_name}\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("-------------------------------------------------")

    @handle_common_errors
    def update_json(self):
        """Update the json file with the new credentials (e.g change json file)"""
        with open(f"{self.file_path}{self.repo}.json", "r", encoding="utf-8") as file:
            self.appimages = json.load(file)

        print("=================================================")
        print(_("1. SHA file name"))
        print(_("2. hash type"))
        print(_("3. choice"))
        print(_("4. appimage folder"))
        print(_("5. appimage folder backup"))
        print(_("6. Exit"))
        print("=================================================")

        choice = int(input(_("Enter your choice: ")))
        if choice == 1:
            self.appimages["sha_name"] = input(_("Enter the sha name: "))
        elif choice == 2:
            self.appimages["hash_type"] = input(_("Enter the hash type: "))
        elif choice == 3:
            self.appimages["choice"] = int(input(_("Enter the choice: ")))
        elif choice == 4:
            new_folder = input(_("Enter new appimage folder: "))
            if not new_folder.endswith("/"):
                new_folder += "/"

            self.appimages["appimage_folder"] = new_folder
        elif choice == 5:
            new_folder = input(_("Enter new appimage folder backup: "))
            if not new_folder.endswith("/"):
                new_folder += "/"

            self.appimages["appimage_folder_backup"] = new_folder
        elif choice == 6:
            sys.exit()
        else:
            print(_("Invalid choice"))
            sys.exit()
        with open(f"{self.file_path}{self.repo}.json", "w", encoding="utf-8") as file:
            json.dump(self.appimages, file, indent=4)

        print("-------------------------------------------------")
        print(_("\033[42mCredentials updated successfully\033[0m"))
        print("-------------------------------------------------")
