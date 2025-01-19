import os
import json
from dataclasses import dataclass, field
from src.decorators import handle_common_errors


@dataclass
class ConfigurationManager(DownloadManager):
    """Handles reading and writing app image configuration files."""

    # TODO: first 2 not need to be rely for the specific json files, send them with locale, batch
    # inside other_settings.json
    appimage_folder: str = field(default_factory=lambda: "~/Documents/appimages")
    appimage_folder_backup: str = field(init=False)
    # Maybe create them for another config setup?
    # hash_Type etc. maybe handle by parseURL which is already realated with something similar though
    # parsing url, on the download can get things and than save it the path
    # in this one, we can ask user initial this one like first function can be this one to create
    # locale, paths, backups etc., afterward parse url can be asked and download can initialize
    # and than specific config file can be created to path.
    config_folder_path: str = field(init=False)
    hash_type: str = None
    sha_name: str = None
    choice: int = None  # TODO: choice need to be different, keep backup or etc?
    appimages: dict = field(default_factory=dict)

    def __post_init__(self):
        self.appimage_folder = os.path.expanduser(self.appimage_folder)

        self.appimage_folder_backup = os.path.join(self.appimage_folder, "backup/")
        os.makedirs(self.appimage_folder_backup, exist_ok=True)

        self.config_folder_path = os.path.join(self.appimage_folder, "config_files/")
        os.makedirs(self.config_folder_path, exist_ok=True)

        other_settings_folder = os.path.join(self.config_folder_path, "other_settings")
        os.makedirs(other_settings_folder, exist_ok=True)

        # TODO: make those one file. Also lets add that config appimage_folder and backup too.
        self.config_file = os.path.join(other_settings_folder, "settings.json")

        self.config_batch_path = os.path.join(other_settings_folder, "batch_mode.json")
        self.config_path = os.path.join(other_settings_folder, "locale.json")

    @handle_common_errors
    def ask_inputs(self):
        while True:
            print("=================================================")
            self.appimage_folder = (
                input(
                    _(
                        "Which directory to save appimage \n(Default: '~/Documents/appimages/' if you leave it blank):"
                    )
                ).strip(" ")
                or self.appimage_folder
            )
            self.hash_type = input(
                _("Enter the hash type for your sha(sha256, sha512) file: ")
            ).strip(" ")
            print("=================================================")

            if self.appimage_folder and self.hash_type:
                break

    # TODO: Make this to ask_keep_backup last version on the config creation
    @handle_common_errors
    def ask_user(self):
        """New appimage installation options"""
        while True:
            print(_("Choose one of the following options:"))
            print("====================================")
            print(_("1. Keep backup the old appimage"))
            print(_("2. Overwrite old appimage"))
            print("====================================")
            try:
                self.choice = int(input(_("Enter your choice: ")))

                if self.choice not in [1, 2]:
                    print(_("Invalid choice. Try again."))
                    self.ask_user()
            except ValueError:
                print(_("Invalid input. Please enter a valid number."))

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

        with open(
            f"{self.config_folder_path}{self.repo}.json", "w", encoding="utf-8"
        ) as file:
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
        json_path = f"{self.config_folder_path}{self.repo}.json"
        if os.path.exists(json_path):
            with open(
                f"{self.config_folder_path}{self.repo}.json", "r", encoding="utf-8"
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
                ).format(path=self.config_folder_path, repo=self.repo)
            )
            self.ask_user()

    @handle_common_errors
    def update_json(self):
        """Update the json file with the new credentials (e.g change json file)"""
        with open(
            f"{self.config_folder_path}{self.repo}.json", "r", encoding="utf-8"
        ) as file:
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
        with open(
            f"{self.config_folder_path}{self.repo}.json", "w", encoding="utf-8"
        ) as file:
            json.dump(self.appimages, file, indent=4)

        print("-------------------------------------------------")
        print(_("\033[42mCredentials updated successfully\033[0m"))
        print("-------------------------------------------------")

    def list_json_files(self):
        """List the json files in the current directory, if json file exists."""
        try:
            json_files = [
                file
                for file in os.listdir(self.config_folder_path)
                if file.endswith(".json")
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

    def save_batch_mode(self, batch_mode):
        """Save batch_mode to a JSON file."""
        data = {"batch_mode": batch_mode}
        with open(self.config_batch_path, "w") as json_file:
            json.dump(data, json_file)

    def load_batch_mode(self):
        """Load batch_mode from a JSON file."""
        try:
            with open(self.config_batch_path, "r") as json_file:
                data = json.load(json_file)
                return data.get("batch_mode", None)
        except FileNotFoundError:
            return None
