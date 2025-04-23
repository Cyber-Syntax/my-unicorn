from src.commands.update_base import BaseUpdateCommand
import logging
from typing import List, Dict, Any, Optional
from src.app_config import AppConfigManager
from src.global_config import GlobalConfigManager
from src.api import GitHubAPI
from src.download import DownloadManager
from src.verify import VerificationManager
from src.file_handler import FileHandler
from src.auth_manager import GitHubAuthManager
import warnings


class UpdateCommand(BaseUpdateCommand):
    """
    DEPRECATED: Command to update selected AppImages using interactive selection.

    This command is now deprecated. Please use UpdateAsyncCommand instead, which provides
    more efficient concurrent updates with the same functionality.
    """

    def __init__(self):
        """Initialize with warning about deprecation."""
        super().__init__()
        warnings.warn(
            "UpdateCommand is deprecated. Use UpdateAsyncCommand for more efficient updates.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._logger.warning("UpdateCommand is deprecated. Use UpdateAsyncCommand instead.")

    def execute(self):
        """Main update execution flow with user selection."""
        print(
            "\n⚠️ DEPRECATED: This update method is deprecated and will be removed in a future version."
        )
        print(
            "Please use the Async Update option from the main menu instead for more efficient updates.\n"
        )

        try:
            # Load global configuration
            self.global_config.load_config()

            # Get available configuration files
            available_files = self.app_config.list_json_files()

            if not available_files:
                logging.warning("No AppImage configuration files found")
                print("No AppImage configuration files found. Use the Download option first.")
                return

            # Check current rate limits before any API operations
            remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

            # Show a warning if rate limits are low but don't prevent user from proceeding
            # This lets users make informed decisions about which specific apps to update
            if remaining < 10:  # Low threshold for warning
                print("\n--- GitHub API Rate Limit Warning ---")
                print(f"⚠️  Low API requests remaining: {remaining}/{limit}")
                if reset_time:
                    print(f"Limits reset at: {reset_time}")

                if not is_authenticated:
                    print(
                        "\n🔑 Consider adding a GitHub token using option 6 in the main menu to increase rate limits (5000/hour)."
                    )

                print(
                    "\nYou can still proceed, but you may not be able to update all selected apps."
                )
                print("Consider selecting fewer apps or only the most important ones.\n")

                # Give user a chance to abort
                try:
                    if input("Do you want to continue anyway? [y/N]: ").strip().lower() != "y":
                        print("Operation cancelled.")
                        return
                except KeyboardInterrupt:
                    print("\nOperation cancelled.")
                    return

            # 1. Find updatable apps via user selection
            updatable = self._find_updatable_apps()
            if not updatable:
                logging.info("No AppImages selected for update or all are up to date")
                return

            # 2. Get user confirmation
            if not self._confirm_updates(updatable):
                logging.info("Update cancelled by user")
                print("Update cancelled")
                return

            # 3. NOW check if we have enough rate limits for the SELECTED apps
            # This is the key change - we only check limits after user has made their selection
            can_proceed, filtered_apps, status_message = self._check_rate_limits(updatable)

            if not can_proceed:
                # Display rate limit status
                print("\n--- GitHub API Rate Limit Check ---")
                print(status_message)

                if not filtered_apps:
                    logging.warning("Update aborted: Insufficient API rate limits")
                    print("Update process aborted due to rate limit constraints.")
                    return

                # Ask user if they want to proceed with partial updates
                try:
                    continue_partial = (
                        input(
                            f"\nProceed with partial update ({len(filtered_apps)}/{len(updatable)} apps)? [y/N]: "
                        )
                        .strip()
                        .lower()
                        == "y"
                    )

                    if not continue_partial:
                        logging.info("User declined partial update")
                        print("Update cancelled.")
                        return
                except KeyboardInterrupt:
                    logging.info("Rate limit confirmation cancelled by user (Ctrl+C)")
                    print("\nUpdate cancelled by user (Ctrl+C)")
                    return

                # User confirmed - proceed with partial update
                updatable = filtered_apps
                print(f"\nProceeding with update of {len(updatable)} apps within rate limits.")

            # 4. Perform updates
            super()._update_apps(updatable)

        except KeyboardInterrupt:
            logging.info("Operation cancelled by user (Ctrl+C)")
            print("\nOperation cancelled by user (Ctrl+C)")
            return

    def _find_updatable_apps(self) -> List[Dict[str, Any]]:
        """
        Find applications that can be updated through user selection.

        This method handles rate limits during the scanning process by:
        1. Checking available rate limits before API calls
        2. Providing feedback about which apps could be checked
        3. Allowing users to make informed decisions about which apps to update

        Returns:
            list: A list of updatable applications.
        """
        updatable_apps = []

        # Let user select which config files to check
        selected_files = self.app_config.select_files()
        if not selected_files:
            print("No configuration files selected or available.")
            return updatable_apps

        # Check current rate limits before making API calls
        remaining, limit, reset_time, is_authenticated = GitHubAuthManager.get_rate_limit_info()

        # If we have fewer requests than selected files, warn the user
        if remaining < len(selected_files):
            print("\n--- GitHub API Rate Limit Warning ---")
            print(f"⚠️  Not enough API requests to check all selected apps.")
            print(f"Rate limit status: {remaining}/{limit} requests remaining")
            if reset_time:
                print(f"Limits reset at: {reset_time}")

            print(f"Selected apps: {len(selected_files)}")
            print(f"Available requests: {remaining}")

            if not is_authenticated:
                print(
                    "\n🔑 Consider adding a GitHub token using option 6 in the main menu to increase rate limits."
                )

            print("\nSome API requests will fail. Consider:")
            print("1. Selecting fewer apps")
            print("2. Adding a GitHub token")
            print("3. Waiting until rate limits reset")

            # Handle the case where we have 0 remaining requests
            if remaining == 0:
                print("\n❌ ERROR: No API requests available.")
                print("Please wait until rate limits reset or add a GitHub token.")
                logging.error("Update aborted: No API requests available (0 remaining)")
                return []

            # Ask user what to do
            try:
                choice = input(
                    "\nHow do you want to proceed?\n"
                    "1. Continue with all selected apps (some may fail)\n"
                    "2. Limit to available API requests\n"
                    "3. Cancel operation\n"
                    "Enter choice [1-3]: "
                ).strip()

                if choice == "2":
                    # Limit selection to available requests
                    limited_files = selected_files[:remaining]
                    # If this results in 0 files, abort with a clear message
                    if not limited_files:
                        print("\n❌ ERROR: Cannot proceed with 0 apps.")
                        print("Please wait until rate limits reset or add a GitHub token.")
                        logging.error("Update aborted: Rate limits allow 0 apps")
                        return []

                    selected_files = limited_files
                    print(
                        f"\nLimited selection to {len(selected_files)} apps based on available API requests."
                    )
                elif choice == "3":
                    print("Operation cancelled.")
                    return []
                else:
                    # Default to continuing with all selected (some will fail)
                    print("\nProceeding with all selected apps. Some API requests may fail.")
            except KeyboardInterrupt:
                print("\nOperation cancelled.")
                return []

        # Check each selected file for updates with progress indication
        print(f"\nChecking {len(selected_files)} selected apps for updates...")
        failed_checks = 0

        for idx, config_file in enumerate(selected_files, 1):
            app_name = config_file.split(".")[0]  # Extract name without extension
            print(f"[{idx}/{len(selected_files)}] Checking {app_name}...", end="", flush=True)

            try:
                app_data = self._check_single_app_version(self.app_config, config_file)
                if app_data:
                    if "error" in app_data:
                        print(f" Error: {app_data['error']}")
                        failed_checks += 1
                    else:
                        print(f" Update available: {app_data['current']} → {app_data['latest']}")
                        updatable_apps.append(app_data)
                else:
                    print(" Already up to date")
            except Exception as e:
                print(f" Failed: {str(e)}")
                failed_checks += 1
                # If we hit rate limits, provide clear feedback
                if "rate limit exceeded" in str(e).lower():
                    print("\n⚠️ GitHub API rate limit exceeded. Cannot check remaining apps.")
                    print("Consider adding a GitHub token or waiting until rate limits reset.")
                    break

        # Summary of check results
        if not selected_files:
            print("\nNo apps were checked due to rate limit constraints.")
        else:
            print(
                f"\nCheck completed: {len(updatable_apps)} updates available, {failed_checks} checks failed"
            )

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
