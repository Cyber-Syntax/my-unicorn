from src.commands.update_base import BaseUpdateCommand
import logging
from typing import List, Dict, Any, Optional
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler


class UpdateCommand(BaseUpdateCommand):
    """Command to update selected AppImages using interactive selection."""

    def execute(self):
        """Main update execution flow with user selection."""
        try:
            # Load global configuration
            self.global_config.load_config()

            # 1. Find updatable apps via user selection
            updatable = self._find_updatable_apps()
            if not updatable:
                logging.info("No AppImages selected for update or all are up to date")
                print("No AppImages selected for update or all are up to date!")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable):
                logging.info("Update cancelled by user")
                print("Update cancelled")
                return

            # 3. Perform updates
            self._update_apps(updatable)
        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return

    def _find_updatable_apps(self) -> List[Dict[str, Any]]:
        """
        Find applications that can be updated through user selection.

        Returns:
            list: A list of updatable applications.
        """
        updatable_apps = []

        # Let user select which config files to check
        selected_files = self.app_config.select_files()
        if not selected_files:
            print("No configuration files selected or available.")
            return updatable_apps

        # Check each selected file for updates
        for config_file in selected_files:
            app_data = self._check_single_app_version(self.app_config, config_file)
            if app_data:
                updatable_apps.append(app_data)

        return updatable_apps

    def _confirm_updates(self, updatable: List[Dict[str, Any]]) -> bool:
        """
        Handle user confirmation based on batch mode.

        Args:
            updatable: List of updatable apps

        Returns:
            bool: True if updates are confirmed, False otherwise
        """
        if self.global_config.batch_mode:
            logging.info("Batch mode: Auto-confirming updates")
            print("Batch mode: Auto-confirming updates")
            return True

        # Display list of apps to update
        self._display_update_list(updatable)
        try:
            return input("\nProceed with updates? [y/N]: ").strip().lower() == "y"
        except KeyboardInterrupt:
            logging.info("Confirmation cancelled by user (Ctrl+C)")
            print("\nConfirmation cancelled by user (Ctrl+C)")
            return False

    def _update_apps(self, apps_to_update: List[Dict[str, Any]]) -> None:
        """
        Update the specified apps using the base class implementation.

        Args:
            apps_to_update: List of app information dictionaries to update
        """
        # Call the base class implementation which now includes rate limit display
        super()._update_apps(apps_to_update)
