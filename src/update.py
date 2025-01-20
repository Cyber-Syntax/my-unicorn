import os
import sys
import logging
import json
from .app_config import AppConfigManager
from .api import GitHubAPI
from .verify import VerificationManager


class AppImageUpdater:
    """Handles the AppImage update process."""

    def __init__(self, app_config):
        self.app_config = AppConfigManager()
        self.github_api_handler = GitHubAPI()
        self.verify = VerificationManager()
        self.appimages_to_update = []

    def update_all(self):
        """Check for updates for all JSON files containing app image configurations."""
        json_files = self.app_config.list_json_files()

        if not json_files:
            print(_("No JSON files found in the directory."))
            return

        print(
            f"Found the following config files in the directory: {self.app_config.config_folder_path}"
        )
        for json_file in json_files:
            print(f"- {json_file}")

        # self.appimages_to_update.clear()

        for json_file in json_files:
            self._check_appimage_update(json_file)

        if not self.appimages_to_update:
            print(_("All appimages are up to date."))
            return

        self._prompt_for_update_selection()

    def _check_appimage_update(self, json_file):
        """Check if the app image listed in the JSON file is up to date."""
        appimage_data = self.app_config.load_appimage_config(json_file)
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
        print(_("Appimages that are not up to date:"))
        for idx, appimage in enumerate(self.appimages_to_update, start=1):
            print(f"{idx}. {appimage['appimage']}")
        print("=================================================")

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
            return

        selected_indices = self._parse_user_input(user_input)
        if selected_indices:
            selected_appimages = [
                self.appimages_to_update[idx] for idx in selected_indices
            ]
            self.update_selected_appimages(selected_appimages)

    def _parse_user_input(self, user_input):
        """Parse user input and return selected indices."""
        try:
            selected_indices = [int(idx.strip()) - 1 for idx in user_input.split(",")]
            if any(
                idx < 0 or idx >= len(self.appimages_to_update)
                for idx in selected_indices
            ):
                raise ValueError
            return selected_indices
        except (ValueError, IndexError):
            print(_("Invalid selection. Please enter valid numbers."))
            return []

    def update_selected_appimages(self, appimages_to_update):
        """Update the selected appimages."""
        # TODO: load batch_mode from global config and ensure defined

        for appimage in appimages_to_update:
            self._update_appimage(appimage, batch_mode)

        print(_("Update process completed for all selected appimages."))

    def _update_appimage(self, appimage, batch_mode):
        """Update a single appimage."""
        print(f"Updating {appimage['appimage']}...")
        # Download, verify, and update appimage steps...
        self.repo = appimage["repo"]
        self.app_config.load_config()
        self.download()

        # Verify SHA and handle errors (now handled by verify_yml)
        if not self.verify.verify_appimage():  # Will return False if verification fails
            if batch_mode:
                print(_("Batch mode is being disabled due to an error."))
                batch_mode = False
            return  # Skip the current AppImage if verification fails

        self.make_executable()
        self.handle_file_operations(batch_mode=batch_mode)
