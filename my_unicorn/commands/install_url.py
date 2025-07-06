"""Command to download and install AppImage from GitHub URL.

This module provides the DownloadCommand class for downloading, verifying,
and installing AppImage files from GitHub repositories.
"""

import logging
from pathlib import Path

from my_unicorn.api.github_api import GitHubAPI
from my_unicorn.app_config import AppConfigManager
from my_unicorn.commands.base import Command
from my_unicorn.download import DownloadManager
from my_unicorn.file_handler import FileHandler
from my_unicorn.global_config import GlobalConfigManager
from my_unicorn.icon_manager import IconManager
from my_unicorn.parser import ParseURL
from my_unicorn.verify import VerificationManager


class DownloadCommand(Command):
    """Command to download the latest release's AppImage."""

    def __init__(self, url: str | None = None):
        """Initialize with optional URL for CLI usage."""
        super().__init__()
        self.url = url

    def execute(self) -> None:
        """Execute the download command."""
        repo_info = self._parse_url_and_get_repo_info()
        if repo_info is None:
            return  # Error message already displayed in _parse_url_and_get_repo_info

        owner, repo = repo_info

        # 2. Get the owner and repo from ParseURL instance
        owner, repo = repo_info

        # 3. Initialize the GitHubAPI with the parsed owner and repo
        api, app_config = self._setup_api_and_config(owner, repo)

        # Maximum number of download/verification attempts
        max_attempts = 3
        verification_success = False
        verification_skipped = False  # New flag to track if verification was skipped

        # Initialize progress bar for single download
        DownloadManager.get_or_create_progress(1)

        for attempt in range(1, max_attempts + 1):
            try:
                # Get release data from GitHub API
                success, full_response = api.get_latest_release()

                if not success:
                    print(f"Error during processing: {full_response}")
                    return

                # Check if essential attributes are available after API call
                if not api.appimage_name:
                    print("Error: Could not find a suitable AppImage file in the release.")
                    return

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

                # Handle verification based on skip_verification flag
                verification_success, verification_skipped = self._handle_verification(
                    api, app_config, downloaded_file_path, was_existing_file
                )
                if verification_success:
                    break

                # Verification failed
                elif attempt == max_attempts:
                    print(f"Verification failed. Maximum retry attempts ({max_attempts}) reached.")
                    return
                else:
                    print(f"Verification failed. Attempt {attempt} of {max_attempts}.")
                    retry = input("Retry download? (y/N): ").strip().lower()
                    if retry != "y":
                        print("Download cancelled.")
                        return
                    # Continue to next attempt

            except (ValueError, RuntimeError) as e:
                logging.error("Download attempt %d failed: %s", attempt, str(e))
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
            # Clean up progress display
            DownloadManager.stop_progress()
            return

        # 5. Finalize the installation process
        app_info = app_config.get_app_info()
        success = self._finalize_installation(api, app_config, app_info, verification_skipped)

        if not success:
            print("Error during finalization. Installation failed.")
            return

    def _parse_url_and_get_repo_info(self) -> tuple[str, str] | None:
        """Parse URL and return owner, repo tuple or None if failed."""
        if self.url:
            # CLI mode - use provided URL
            try:
                parser = ParseURL(url=self.url)
                parser._validate_url()  # Using protected method as intended
                parser._parse_owner_repo()  # Using protected method as intended
            except (ValueError, RuntimeError) as e:
                print(f"Error parsing URL '{self.url}': {e}")
                return None
        else:
            # Interactive mode - ask for URL
            parser = ParseURL()
            parser.ask_url()  # Get owner and repo by asking the user for the URL

        # Return the owner and repo from ParseURL instance
        return parser.owner, parser.repo

    def _setup_api_and_config(self, owner: str, repo: str) -> tuple[GitHubAPI, AppConfigManager]:
        """Set up API and config managers."""
        # Initialize AppConfigManager and set app name
        app_config = AppConfigManager()
        app_config.set_app_name(repo)

        # Get app info from catalog to get checksum_hash_type and checksum_file_name
        app_info = app_config.get_app_info()
        if app_info:
            checksum_file_name = app_info.checksum_file_name or "auto"
            checksum_hash_type = app_info.checksum_hash_type or "auto"
        else:
            # Fallback if app not in catalog
            checksum_file_name = "auto"
            checksum_hash_type = "auto"

        # Initialize the GitHubAPI with the parsed owner and repo
        api = GitHubAPI(
            owner=owner,
            repo=repo,
            checksum_file_name=checksum_file_name,
            checksum_hash_type=checksum_hash_type,
            arch_keyword=None,
        )

        return api, app_config

    def _handle_verification(
        self,
        api: GitHubAPI,
        app_config: AppConfigManager,
        downloaded_file_path: str,
        was_existing_file: bool,
    ) -> tuple[bool, bool]:
        """Handle verification logic. Returns (success, skipped) tuple."""
        # Handle verification based on skip_verification flag
        if app_config.skip_verification or api.skip_verification:
            logging.info("Skipping verification due to skip_verification setting.")
            print("Note: Verification skipped - verification disabled for this app")
            return True, True

        # Check if verification data is available and valid
        has_sha_data = api.checksum_file_name and api.checksum_file_name != "no_sha_file"
        has_asset_digest = api.asset_digest

        if not has_sha_data and not has_asset_digest:
            logging.info("No SHA file or asset digest found - verification cannot be performed.")
            print("Note: Verification skipped - no hash file available")
            return True, True

        # Single verification point for both existing and downloaded files
        if was_existing_file:
            print("Verifying existing file...")
        else:
            print("Verifying download integrity...")

        # Debug logging for API values
        logging.debug("API values before VerificationManager creation:")
        logging.debug("  api.checksum_file_name: %s", api.checksum_file_name)
        logging.debug("  api.checksum_hash_type: %s", api.checksum_hash_type)
        logging.debug("  api.asset_digest: %s", api.asset_digest)
        logging.debug("  api.skip_verification: %s", api.skip_verification)

        # Perform verification with cleanup on failure
        verification_manager = VerificationManager(
            checksum_file_name=api.checksum_file_name,
            checksum_file_download_url=api.checksum_file_download_url,
            appimage_name=api.appimage_name,  # Keep the original filename for logging
            checksum_hash_type=api.checksum_hash_type or "sha256",  # Default to sha256
            asset_digest=api.asset_digest,
        )

        # set the full path to the downloaded file
        verification_manager.set_appimage_path(downloaded_file_path)

        is_valid = verification_manager.verify_appimage(cleanup_on_failure=True)

        if is_valid:
            # Check if verification was actually performed or skipped
            if verification_manager.config.is_verification_skipped():
                return True, True
            else:
                print("✓ Verification successful!")
                return True, False

        return False, False

    def _finalize_installation(
        self, api: GitHubAPI, app_config: AppConfigManager, app_info, verification_skipped: bool
    ) -> bool:
        """Finalize the installation process."""
        global_config = GlobalConfigManager()

        # Handle file operations
        file_handler = FileHandler(
            appimage_name=api.appimage_name or "unknown.AppImage",  # Provide default
            repo=api.repo,  # Preserve original case of repo name
            owner=api.owner,
            version=api.version,
            checksum_file_name=api.checksum_file_name,
            config_file=str(global_config.config_file),
            app_storage_path=Path(global_config.expanded_app_storage_path),
            app_backup_storage_path=Path(global_config.expanded_app_backup_storage_path),
            config_folder=str(app_config.config_folder) if app_config.config_folder else None,
            config_file_name=app_config.config_file_name,
            batch_mode=global_config.batch_mode,
            keep_backup=global_config.keep_backup,
            max_backups=global_config.max_backups,
            app_rename=app_config.app_rename if app_info else None,
        )

        # Download app icon if possible
        icon_manager = IconManager()
        # Get the app_rename from catalog info
        app_rename = app_config.app_rename if app_info else None
        icon_success, icon_path = icon_manager.ensure_app_icon(
            api.owner, api.repo, app_rename=app_rename
        )

        # Check if the file operations were successful
        success = file_handler.handle_appimage_operations(
            github_api=api, icon_path=icon_path if icon_success else None
        )

        # Clean up progress display
        DownloadManager.stop_progress()

        if success:
            # Save the configuration only if all previous steps succeed
            app_config.save_config()

            # Display success message with paths
            if verification_skipped:
                print(f"\n✅ {api.repo} successfully installed!")
                print("⚠️  Note: AppImage was not verified (no verification data available)")
            else:
                print(f"\n✅ {api.repo} successfully installed and verified!")

            # Show config file location
            if app_config.config_file:
                config_path = Path(app_config.config_file)
                print(f"Config file created at: {config_path}")

            # Show location of executable
            if api.appimage_name:
                app_path = Path(global_config.expanded_app_storage_path) / api.appimage_name
                print(f"Application installed to: {app_path}")
                print("You can run it from the command line or create a desktop shortcut.")
            return True
        else:
            print("Error during file operations. Installation failed.")
            return False
