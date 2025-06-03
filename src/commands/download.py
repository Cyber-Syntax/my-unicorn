import logging

from src.api.github_api import GitHubAPI
from src.app_config import AppConfigManager
from src.commands.base import Command
from src.download import DownloadManager
from src.file_handler import FileHandler
from src.global_config import GlobalConfigManager
from src.icon_manager import IconManager
from src.parser import ParseURL
from src.verify import VerificationManager


class DownloadCommand(Command):
    """Command to download the latest release's AppImage."""

    def execute(self):
        """Execute the download command with improved verification handling."""
        # 1. Initialize the URL parser
        parser = ParseURL()
        parser.ask_url()  # Get owner and repo by asking the user for the URL

        # 2. Get the owner and repo from ParseURL instance
        owner, repo = parser.owner, parser.repo

        # Initialize AppConfigManager and set app name
        app_config = AppConfigManager()
        app_config.set_app_name(repo)
        
        # Get app info from catalog to get hash_type and sha_name
        app_info = app_config.get_app_info()
        if app_info:
            sha_name = app_info.sha_name or "auto"
            hash_type = app_info.hash_type or "auto"
        else:
            # Fallback if app not in catalog
            sha_name = "auto"
            hash_type = "auto"

        # 3. Initialize the GitHubAPI with the parsed owner and repo
        api = GitHubAPI(
            owner=owner,
            repo=repo,
            sha_name=sha_name,
            hash_type=hash_type,
            arch_keyword=None,
        )

        # Maximum number of download/verification attempts
        max_attempts = 3
        verification_success = False
        verification_skipped = False  # New flag to track if verification was skipped

        for attempt in range(1, max_attempts + 1):
            try:
                # Get release data from GitHub API
                api.get_response()

                # Update user-specific fields (version and appimage_name are stored in config)
                app_config.version = api.version
                app_config.appimage_name = api.appimage_name

                # Save temporary configuration
                app_config.temp_save_config()

                # 4. Use DownloadManager to download the AppImage or get existing file
                download = DownloadManager(api)
                downloaded_file_path, was_existing_file = download.download()
                
                if was_existing_file:
                    print(f"Found existing file: {api.appimage_name}")
                else:
                    print(f"✓ Downloaded {api.appimage_name}")

                global_config = GlobalConfigManager()
                global_config.load_config()

                # Handle verification based on skip_verification flag
                if app_config.skip_verification or api.skip_verification:
                    logging.info("Skipping verification due to skip_verification setting.")
                    print("Note: Verification skipped - verification disabled for this app")
                    verification_success = True
                    verification_skipped = True  # Set the flag that verification was skipped
                    break
                else:
                    # Single verification point for both existing and downloaded files
                    if was_existing_file:
                        print("Verifying existing file...")
                    else:
                        print("Verifying download integrity...")
                    # Perform verification with cleanup on failure
                    verification_manager = VerificationManager(
                        sha_name=api.sha_name,
                        sha_url=api.sha_url,
                        appimage_name=api.appimage_name,  # Keep the original filename for logging
                        hash_type=api.hash_type,
                        asset_digest=api.asset_digest,
                    )

                    # Set the full path to the downloaded file
                    verification_manager.set_appimage_path(downloaded_file_path)

                    is_valid = verification_manager.verify_appimage(cleanup_on_failure=True)

                    if is_valid:
                        verification_success = True
                        break
                    # Verification failed
                    elif attempt == max_attempts:
                        print(
                            f"Verification failed. Maximum retry attempts ({max_attempts}) reached."
                        )
                        return
                    else:
                        print(f"Verification failed. Attempt {attempt} of {max_attempts}.")
                        retry = input("Retry download? (y/N): ").strip().lower()
                        if retry != "y":
                            print("Download cancelled.")
                            return
                            # Continue to next attempt

            except Exception as e:
                logging.error(f"Download attempt {attempt} failed: {e!s}")
                print(f"Error during download: {e!s}")

                if attempt == max_attempts:
                    print(f"Maximum retry attempts ({max_attempts}) reached.")
                    return
                else:
                    print(f"Download failed. Attempt {attempt} of {max_attempts}.")
                    retry = input("Retry download? (y/N): ").strip().lower()
                    if retry != "y":
                        print("Download cancelled.")
                        return

        # If verification wasn't successful after all attempts, exit
        if not verification_success:
            return

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name,
            repo=api.repo,  # Preserve original case of repo name
            version=api.version,
            sha_name=api.sha_name,
            config_file=global_config.config_file,
            app_storage_path=global_config.expanded_app_storage_path,
            app_backup_storage_path=global_config.expanded_app_backup_storage_path,
            config_folder=app_config.config_folder,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
            max_backups=global_config.max_backups,
        )

        # Download app icon if possible
        icon_manager = IconManager()
        # Get the app_rename from catalog info
        app_rename = app_config.app_rename if app_info else None
        icon_manager.ensure_app_icon(api.owner, api.repo, app_rename=app_rename)

        # Check if the file operations were successful
        success = file_handler.handle_appimage_operations()
        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()

            # Use different log/print messages based on verification status
            if verification_skipped:
                logging.info(
                    "AppImage downloaded but not verified because developers not provided "
                    "sha file for this appimage."
                )
                print(
                    "AppImage downloaded but not verified because developers not provided "
                    "sha file for this appimage."
                )
            else:
                logging.info(
                    "AppImage downloaded and verified successfully and saved in DownloadCommand."
                )
                print("AppImage downloaded and verified successfully and saved.")
        else:
            logging.error("An error occurred during file operations in DownloadCommand.")
            print("An error occurred during file operations.")
