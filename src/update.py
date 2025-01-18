class AppImageUpdater:
    """Handles the appimage update process, including checking for updates and user interaction."""

    def __init__(self, config_manager, github_api_handler):
        self.config_manager = config_manager
        self.github_api_handler = github_api_handler
        self.appimages_to_update = []

    def check_updates_json_all(self):
        """Check for updates for all JSON files containing app image configurations."""
        json_files = self.config_manager.list_json_files()

        if json_files:
            print(
                f"Found the following config files in the directory: {self.config_manager.config_folder_path}"
            )
            for json_file in json_files:
                print(f"- {json_file}")
        else:
            print("No JSON files found in the directory.")
            return

        self.appimages_to_update.clear()

        for json_file in json_files:
            self._check_appimage_update(json_file)

        if not self.appimages_to_update:
            print("All appimages are up to date.")
            sys.exit()

        self._prompt_for_update_selection()

    # FIX: duplicate??
    def _check_appimage_update(self, json_file):
        """Check if the app image listed in the JSON file is up to date."""
        appimage_data = self.config_manager.load_appimage_config(json_file)

        if not appimage_data:
            return

        latest_version = self.github_api_handler.check_latest_version(
            appimage_data["owner"], appimage_data["repo"]
        )

        if latest_version and latest_version != appimage_data["version"]:
            print(f"{appimage_data['appimage']} is not up to date.")
            print(f"Latest version: {latest_version}")
            print(f"Current version: {appimage_data['version']}")
            self.appimages_to_update.append(appimage_data)

    def _prompt_for_update_selection(self):
        """Prompt user to select which appimages to update."""
        print("=================================================")
        print("Appimages that are not up to date:")

        for idx, appimage in enumerate(self.appimages_to_update, start=1):
            print(f"{idx}. {appimage['appimage']}")

        print("=================================================")

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
        selected_appimages = [self.appimages_to_update[idx] for idx in selected_indices]

        self.update_selected_appimages(selected_appimages)

    def update_selected_appimages(self, appimages_to_update):
        """Update the selected appimages."""
        batch_mode = self.config_manager.load_batch_mode()

        if batch_mode is None:
            batch_mode = (
                input(
                    "Enable batch mode to continue without asking for approval? (y/n): "
                )
                .strip()
                .lower()
                == "y"
            )

            self.config_manager.save_batch_mode(batch_mode)

        if batch_mode:
            print(
                "Batch mode is enabled. All selected appimages will be updated without further prompts."
            )
        else:
            print(
                "Batch mode is disabled. You will be prompted for each appimage update."
            )

        for appimage in appimages_to_update:
            self._update_appimage(appimage, batch_mode)

        print("Update process completed for all selected appimages.")

    def _update_appimage(self, appimage, batch_mode):
        """Update a single appimage."""
        print(f"Updating {appimage['appimage']}...")
        # Download, verify, and update appimage steps...

    # TODO: comprise with above

    # INFO: Cause API RATE LIMIT EXCEEDED if used more than 15 - 20 times
    # KeyError: 'tag_name' means that API RATE LIMIT EXCEEDED.
    @handle_common_errors
    def check_updates_json_all(self):
        """Check for updates for all JSON files"""
        json_files = [
            file for file in os.listdir(self.file_path) if file.endswith(".json")
        ]

        # Output the list of JSON files found
        if json_files:
            print(
                _("Found the following config files in the\n[{file_path}]:").format(
                    file_path=self.file_path
                )
            )
            for json_file in json_files:
                print(_("- {json_file}").format(json_file=json_file))
        else:
            print(_("No JSON files found in the directory."))

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
                print(
                    _("{appimage} is up to date").format(appimage=appimages["appimage"])
                )
            else:
                print("-------------------------------------------------")
                print(
                    _("{appimage} is not up to date").format(
                        appimage=appimages["appimage"]
                    )
                )
                print(
                    _("\033[42mLatest version: {version}\033[0m").format(
                        version=latest_version
                    )
                )
                print(
                    _("Current version: {version}").format(version=appimages["version"])
                )
                print("-------------------------------------------------")
                # Append to queue appimages that are not up to date
                appimages_to_update.append(appimages["repo"])

        # If all appimages are up to date
        if not appimages_to_update:
            print(_("All appimages are up to date"))
            sys.exit()
        else:
            # Display the list of appimages to update
            print("=================================================")
            print(_("Appimages that are not up to date:"))
            for idx, appimage in enumerate(appimages_to_update, start=1):
                print(_("{idx}. {appimage}").format(idx=idx, appimage=appimage))
            print("=================================================")

            # Ask the user to select which appimages to update or skip
            user_input = (
                input(
                    _(
                        "Enter the numbers of the appimages you want to update (comma-separated) or type 'skip' to skip updates: "
                    )
                )
                .strip()
                .lower()
            )

            if user_input == "skip":
                print(_("No updates will be performed."))
                sys.exit()

            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]

            selected_appimages = [appimages_to_update[idx] for idx in selected_indices]

            # Update the selected appimages
            self.update_selected_appimages(selected_appimages)

    @handle_common_errors
    def update_selected_appimages(self, appimages_to_update):
        """Update all appimages"""
        batch_mode = self.load_batch_mode()

        if batch_mode is None:  # If no saved value is found, prompt for it
            if (
                input(
                    _(
                        "Enable batch mode to continue without asking for approval? (y/n): "
                    )
                ).lower()
                != "y"
            ):
                batch_mode = False
            else:
                batch_mode = True
            # Save the batch_mode value to a file
            self.save_batch_mode(batch_mode)

        if batch_mode:
            print(
                _(
                    "Batch mode is enabled. All selected appimages will be updated without further prompts."
                )
            )
        else:
            print(
                _(
                    "Batch mode is disabled. You will be prompted for each appimage update."
                )
            )

        for appimage in appimages_to_update:
            print(_("Updating {appimage}...").format(appimage=appimage))
            self.repo = appimage
            self.load_credentials()
            self.get_response()
            self.download()

            # Verify SHA and handle errors (now handled by verify_yml)
            if not self.verify_sha():  # Will return False if verification fails
                if batch_mode:
                    print(_("Batch mode is being disabled due to an error."))
                    batch_mode = False
                continue  # Skip the current AppImage if verification fails

            self.make_executable()
            self.handle_file_operations(batch_mode=batch_mode)

        print(_("Update process completed for all selected appimages."))

    def save_batch_mode(self, batch_mode):
        """Save batch_mode to a JSON file"""

        data = {"batch_mode": batch_mode}
        with open(self.config_batch_path, "w") as json_file:
            json.dump(data, json_file)

    def load_batch_mode(self):
        """Load batch_mode from a JSON file"""
        try:
            with open(self.config_batch_path, "r") as json_file:
                data = json.load(json_file)
                return data.get("batch_mode", None)  # Return None if not found
        except FileNotFoundError:
            return None  # Return None if the file doesn't exist
