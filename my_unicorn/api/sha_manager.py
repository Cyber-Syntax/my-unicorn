"""SHA Manager module.

This module handles SHA-related operations for GitHub releases by coordinating
between different verification methods and managing SHA asset selection.
"""

import asyncio
import logging
import re  # For hash validation
from pathlib import Path

from my_unicorn.api.sha_asset_finder import SHAAssetFinder
from my_unicorn.utils import sha_utils, ui_utils

logger = logging.getLogger(__name__)


class SHAManager:
    """Handles SHA-related operations for GitHub releases."""

    def __init__(
        self,
        owner: str,
        repo: str,
        checksum_file_name: str,
        appimage_name: str | None = None,
        app_info=None,
    ):
        """Initialize the SHAManager.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            checksum_file_name: Name of the SHA algorithm used in the release assets
            appimage_name: Name of the selected AppImage
            app_info: AppInfo object containing app-specific settings

        """
        self.owner = owner
        self.repo = repo
        self.checksum_file_name = checksum_file_name
        self.appimage_name = appimage_name
        self.checksum_file_download_url = None
        self.checksum_hash_type = None
        self.extracted_hash_from_body: str | None = None  # For hash from release body
        self.asset_digest: str | None = None  # For GitHub API asset digest verification
        self._app_info = app_info
        self.skip_verification: bool = app_info.skip_verification if app_info else False

    def _try_extract_sha_from_release_body(self) -> bool:
        """Extract SHA256 checksum for the current AppImage from release description.

        Sets instance attributes if successful.

        Returns:
            True if a checksum was successfully extracted, False otherwise

        """
        if not self.appimage_name:
            logger.warning("Cannot extract SHA from release body: AppImage name not set.")
            return False

        logger.info(
            f"Attempting to extract SHA for {self.appimage_name} from release description..."
        )

        try:
            # Use local import to avoid circular dependency
            from my_unicorn.verification.release_desc_verifier import ReleaseDescVerifier

            # Create verifier and extract checksums to temporary file
            verifier = ReleaseDescVerifier(self.owner, self.repo)
            appimage_base_name = Path(self.appimage_name).name

            temp_sha_file = verifier.extract_checksums_to_file(appimage_base_name)
            if not temp_sha_file:
                logger.info("No checksums found in release description")
                return False

            # Read the first hash from the temporary file to set as extracted hash
            try:
                with open(temp_sha_file, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                    if first_line:
                        parts = first_line.split(maxsplit=1)
                        if len(parts) >= 1:
                            hash_value = parts[0]
                            if self._validate_sha256_hash(hash_value):
                                self.checksum_hash_type = "sha256"
                                self.extracted_hash_from_body = hash_value
                                self.checksum_file_name = "extracted_checksum"
                                self.checksum_file_download_url = None
                                logger.info(
                                    f"Successfully extracted SHA256 hash '{self.extracted_hash_from_body}' for {self.appimage_name} from release body."
                                )
                                # Clean up temporary file
                                Path(temp_sha_file).unlink(missing_ok=True)
                                return True
            except (OSError, UnicodeDecodeError) as e:
                logger.debug("Error reading temporary SHA file: %s", e)
                # Clean up temporary file on error
                Path(temp_sha_file).unlink(missing_ok=True)

            logger.info(
                f"No valid SHA256 hash found for {appimage_base_name} in release description"
            )

        except (ImportError, AttributeError, ValueError) as e:
            logger.error("Error during SHA extraction from release body: %s", e, exc_info=True)

        return False

    def _validate_sha256_hash(self, hash_value: str) -> bool:
        """Validate that a hash value is a valid SHA256 hash.

        Args:
            hash_value: Hash string to validate

        Returns:
            True if valid SHA256 hash, False otherwise

        """
        if re.fullmatch(r"[0-9a-f]{64}", hash_value, re.IGNORECASE):
            return True
        else:
            logger.warning(f"Extracted hash '{hash_value}' does not look like a valid SHA256 hash.")
            return False

    def find_sha_asset(self, assets: list[dict[str, str]]) -> None:
        """Find and select appropriate SHA file for verification.

        Args:
            assets: list of release assets from GitHub API

        """
        if self.skip_verification:
            logger.info("Skipping SHA verification per configuration")
            return

        if not self.appimage_name:
            logger.error("Cannot find SHA asset: AppImage name not set")
            return

        # Priority 1: Asset digest verification is handled by SHAAssetFinder
        # No need for separate check here - let SHAAssetFinder handle it

        # Priority 2: Try to extract from release body description
        if (
            self._app_info
            and getattr(self._app_info, "use_github_release_desc", False)
            and self._try_extract_sha_from_release_body()
        ):
            logger.info(
                f"Successfully extracted SHA for {self.appimage_name} from release description"
            )
            return

        # Priority 3: Try to find SHA asset file using SHAAssetFinder
        finder = SHAAssetFinder()
        sha_asset = finder.find_best_match(self.appimage_name, self._app_info, assets)

        if sha_asset:
            logger.debug("SHAAssetFinder returned: %s", sha_asset)
            # Check if this is a special asset digest response
            if sha_asset.get("checksum_hash_type") == "asset_digest":
                self.checksum_hash_type = "asset_digest"
                self.checksum_file_name = "asset_digest"
                self.checksum_file_download_url = None
                self.asset_digest = sha_asset["digest"]
                logger.info(
                    f"Successfully assigned asset digest verification for {self.appimage_name}"
                )
                logger.debug("Asset digest: %s", self.asset_digest)
                logger.debug("Hash type: %s", self.checksum_hash_type)
                logger.debug("SHA name: %s", self.checksum_file_name)
            else:
                self._select_sha_asset(sha_asset)
                logger.info(
                    "Found SHA file for {}: {}".format(self.appimage_name, sha_asset["name"])
                )
            return

        # Priority 4: Manual fallback - ask user
        logger.warning(f"No automatic verification method found for {self.appimage_name}")
        self._handle_sha_fallback(assets)

    def _select_sha_asset(self, asset: dict) -> None:
        """Select a SHA asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary

        """
        detected_checksum_hash_type = sha_utils.detect_checksum_hash_type(asset["name"])
        self.checksum_hash_type = detected_checksum_hash_type or "sha256"
        self.checksum_file_name = asset["name"]
        self.checksum_file_download_url = asset["browser_download_url"]

        if not detected_checksum_hash_type:
            logger.info(f"Could not detect hash type from {self.checksum_file_name}")
            # Always ask for hash type if not detected, regardless of is_batch
            self.checksum_hash_type = ui_utils.get_user_input("Enter hash type", default="sha256")

        logger.info(
            f"Selected SHA file: {self.checksum_file_name} (hash type: {self.checksum_hash_type})"
        )

    def _handle_sha_fallback(self, assets: list[dict[str, str]]) -> None:
        """Handle fallback when SHA file couldn't be automatically determined.

        Args:
            assets: list of release assets from GitHub API

        """
        return self._handle_sha_fallback_sync(assets)

    async def _handle_sha_fallback_async(self, assets: list[dict[str, str]]) -> None:
        """Async version of SHA fallback handler.

        Args:
            assets: list of release assets from GitHub API

        """
        logger.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")

        try:
            # Use asyncio.to_thread for input operations
            choice = await asyncio.to_thread(ui_utils.get_user_input, "Your choice (1-2)")

            if choice == "1":
                self.checksum_file_name = await asyncio.to_thread(
                    ui_utils.get_user_input, "Enter exact SHA filename"
                )
                for asset in assets:
                    if asset["name"] == self.checksum_file_name:
                        self._select_sha_asset(asset)
                        return
                raise ValueError(f"SHA file {self.checksum_file_name} not found")
            else:
                self.checksum_file_name = "no_sha_file"
                self.checksum_hash_type = "no_hash"
                self.skip_verification = True
                logger.info("User chose to skip SHA verification")

        except KeyboardInterrupt:
            logger.info("SHA fallback cancelled by user")
            raise

    def _handle_sha_fallback_sync(self, assets: list[dict[str, str]]) -> None:
        """Handle SHA fallback using synchronous operations.

        Args:
            assets: list of release assets from GitHub API

        """
        logger.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")

        try:
            choice = ui_utils.get_user_input("Your choice (1-2)")

            if choice == "1":
                self.checksum_file_name = ui_utils.get_user_input("Enter exact SHA filename")
                for asset in assets:
                    if asset["name"] == self.checksum_file_name:
                        self._select_sha_asset(asset)
                        return
                raise ValueError(f"SHA file {self.checksum_file_name} not found")
            else:
                self.checksum_file_name = "no_sha_file"
                self.checksum_hash_type = "no_hash"
                self.skip_verification = True
                logger.info("User chose to skip SHA verification")

        except KeyboardInterrupt:
            logger.info("SHA fallback cancelled by user")
            raise
