#!/usr/bin/env python3
"""GitHub API handler module.

This module provides functionality for interacting with the GitHub API.
"""

import logging
import os
import re
from typing import Any, Dict, Optional, Tuple, Union

import requests

from src.auth_manager import GitHubAuthManager
from src.icon_manager import IconManager
from src.utils import arch_utils, sha_utils, ui_utils, version_utils

# Configure module logger
logger = logging.getLogger(__name__)


class GitHubAPI:
    """Handler for GitHub API requests."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = "sha256",
        hash_type: str = "sha256",
        arch_keyword: Optional[str] = None,
    ):
        """Initialize the GitHub API handler.

        Args:
            owner: Repository owner/organization
            repo: Repository name
            sha_name: Name of the sha algorithm used in the release assets
            hash_type: Type of hash to use for file verification
            arch_keyword: Architecture keyword to filter releases

        """
        self.owner = owner
        self.repo = repo
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.version = None
        self.sha_url = None
        self.appimage_url = None
        self.appimage_name = None
        self._arch_keyword = arch_keyword
        self.arch_keywords = arch_utils.get_arch_keywords(arch_keyword)
        # Get authentication headers from GitHubAuthManager
        self._headers = GitHubAuthManager.get_auth_headers()
        self._icon_manager = IconManager()
        logger.debug(f"API initialized for {owner}/{repo} with auth headers")

    @property
    def arch_keyword(self) -> Optional[str]:
        """Get the architecture keyword.

        Returns:
            str or None: The architecture keyword

        """
        return self._arch_keyword

    def get_latest_release(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Get the latest stable release from GitHub API.

        Returns:
            tuple: (Success flag, Release data or error message)

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"

        try:
            logger.debug(f"Fetching latest release from {api_url}")
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_latest_release",
            )

            if response.status_code == 200:
                release = response.json()
                self._process_release(release, release.get("prerelease", False))
                return True, release
            elif response.status_code == 404:
                logger.info(
                    f"No stable release found for {self.owner}/{self.repo}, checking for beta releases"
                )
                return self.get_beta_releases()
            elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
                logger.warning("GitHub API rate limit exceeded, refreshing authentication")
                self.refresh_auth()
                return False, "GitHub API rate limit exceeded. Please try again in a few minutes."
            else:
                error_msg = (
                    f"Failed to fetch latest release: {response.status_code} - {response.text}"
                )
                logger.error(error_msg)
                return False, error_msg

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error fetching latest release: {e!s}")
            return False, f"Network error: {e!s}"
        except Exception as e:
            logger.error(f"Unexpected error fetching latest release: {e!s}")
            return False, f"Error: {e!s}"

    def get_beta_releases(self) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Get all releases including pre-releases/betas.

        Returns:
            tuple: (Success flag, Latest release data or error message)

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"

        try:
            logger.debug(f"Fetching all releases from {api_url}")
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_beta_releases",
            )

            if response.status_code == 200:
                releases = response.json()
                if not releases:
                    return False, "No releases found (including pre-releases)"

                # Get the first (latest) release
                latest_release = releases[0]
                self._process_release(latest_release, latest_release.get("prerelease", False))
                return True, latest_release
            else:
                error_msg = f"Failed to fetch releases: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return False, error_msg

        except Exception as e:
            logger.error(f"Error checking beta releases: {e!s}")
            return False, f"Error checking beta releases: {e!s}"

    def get_response(self, per_page: int = 100) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Get the response from the GitHub API for releases.
        Simplified to use dedicated endpoints for latest and all releases.

        Returns:
            tuple: (Success flag, Response data or error message)

        """
        # First try to get the latest stable release
        success, response = self.get_latest_release()

        if success:
            return True, response

        # If no stable release is found, the get_latest_release method will already
        # try to get beta releases through the get_beta_releases method
        return success, response

    def check_latest_version(
        self, current_version: Optional[str] = None
    ) -> Tuple[bool, Dict[str, str]]:
        """Check if there's a newer version available.

        Args:
            current_version: Current version to compare against

        Returns:
            tuple: (Update available flag, Version information)

        """
        # Get latest release info (will try stable first, then fall back to beta if needed)
        success, response = self.get_response()

        if not success:
            return False, {"error": str(response)}

        try:
            # Check for empty or invalid response
            if not response or not isinstance(response, dict):
                return False, {
                    "error": "Error parsing release information: empty or invalid response"
                }

            latest_release = response
            latest_version = latest_release.get("tag_name", "")
            is_prerelease = latest_release.get("prerelease", False)

            # Early return if no latest version found
            if not latest_version:
                return False, {"error": "No version information found in release"}

            # Normalize version strings for proper comparison
            current_version_clean = version_utils.normalize_version_for_comparison(current_version)
            latest_version_clean = version_utils.normalize_version_for_comparison(latest_version)

            logger.debug(
                f"Comparing versions: Current '{current_version_clean}' vs Latest '{latest_version_clean}'"
            )

            # Initialize update_available as False
            update_available = False

            # Only check for updates if we have a current version to compare against
            if current_version_clean:
                # For repos that use beta versions
                if version_utils.repo_uses_beta(self.repo):
                    current_base = version_utils.extract_base_version(current_version_clean)
                    latest_base = version_utils.extract_base_version(latest_version_clean)
                    # Update available if base versions are different
                    update_available = current_base != latest_base
                else:
                    # For regular repos
                    update_available = (
                        latest_version_clean != current_version_clean
                        and latest_version_clean > current_version_clean
                    )
                    if update_available:
                        logger.info(f"Update available: {current_version} → {latest_version}")

            # Get architecture keywords
            arch_keywords = arch_utils.get_arch_keywords(self._arch_keyword)

            # Filter assets by architecture
            compatible_assets = []
            for asset in latest_release.get("assets", []):
                asset_name = asset.get("name", "").lower()
                if any(keyword.lower() in asset_name for keyword in arch_keywords):
                    compatible_assets.append(asset)

            return update_available, {
                "current_version": current_version,
                "latest_version": latest_version,
                "release_notes": latest_release.get("body", ""),
                "release_url": latest_release.get("html_url", ""),
                "compatible_assets": compatible_assets,
                "is_prerelease": is_prerelease,
                "published_at": latest_release.get("published_at", ""),
            }

        except Exception as e:
            logger.error(f"Error parsing release information: {e!s}")
            return False, {"error": f"Error parsing release information: {e!s}"}

    def find_app_icon(self) -> Optional[Dict[str, Any]]:
        """Find application icon for the repository.

        Uses IconManager with the current authentication headers.

        Returns:
            dict or None: Icon information dictionary or None if not found

        """
        try:
            # Use the IconManager with current authentication headers
            icon_info = self._icon_manager.find_icon(self.owner, self.repo, headers=self._headers)

            if icon_info:
                logger.info(f"Found app icon: {icon_info.get('name')}")
                return icon_info

            return None
        except Exception as e:
            logger.error(f"Error finding app icon: {e!s}")
            return None

    def refresh_auth(self) -> None:
        """Refresh authentication headers.

        This method should be called when encountering rate limits
        or authentication issues.
        """
        logger.debug("Refreshing authentication headers")
        # Clear cached headers in GitHubAuthManager
        GitHubAuthManager.clear_cached_headers()
        # Get fresh headers
        self._headers = GitHubAuthManager.get_auth_headers()
        logger.info("Authentication headers refreshed")

    def _process_release(self, release_data: dict, is_beta: bool):
        """Process release data to extract version and asset information.

        Args:
            release_data: Release data from GitHub API
            is_beta: Whether this is a beta release

        Returns:
            dict or None: Processed release data or None if processing failed

        """
        try:
            raw_tag = release_data["tag_name"]
            assets = release_data.get("assets", [])

            # First try to extract version from tag name
            version = version_utils.extract_version(raw_tag, is_beta)

            # Find AppImage - THIS MUST SUCCEED
            self._find_appimage_asset(assets)
            if not self.appimage_name:
                raise ValueError("No AppImage found in release assets")

            if not version:
                version = version_utils.extract_version_from_filename(self.appimage_name)

            if not version:
                raise ValueError(f"Could not determine version from tag: {raw_tag}")

            self.version = version
            self._find_sha_asset(assets)

            return {
                "owner": self.owner,
                "repo": self.repo,
                "version": self.version,
                "sha_name": self.sha_name,
                "hash_type": self.hash_type,
                "appimage_name": self.appimage_name,
                "arch_keyword": self._arch_keyword,
                "appimage_url": self.appimage_url,
                "sha_url": self.sha_url,
            }

        except KeyError as e:
            logging.error(f"Missing expected key in release data: {e}")
            return None

    def _find_appimage_asset(self, assets: list):
        """Find and select appropriate AppImage asset based on system architecture.

        Args:
            assets: List of release assets from GitHub API

        """
        # Current system architecture for logging
        current_arch = arch_utils.get_current_arch()
        logging.info(f"Current arch_keyword: {self._arch_keyword}")
        logging.info(f"Current system architecture: {current_arch}")

        # Get incompatible architectures to explicitly filter out
        incompatible_archs = arch_utils.get_incompatible_archs(current_arch)
        logging.info(f"Filtering out incompatible architectures: {incompatible_archs}")

        # Filter all AppImage files
        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]

        # First filter out incompatible architectures
        compatible_appimages = []
        for appimage in appimages:
            asset_name = appimage["name"].lower()
            # Skip assets with incompatible architecture markers
            if any(arch in asset_name for arch in incompatible_archs):
                logging.info(f"Skipping incompatible architecture: {asset_name}")
                continue
            compatible_appimages.append(appimage)

        # Use compatible AppImages for further processing, or fall back to all if none are compatible
        filtered_appimages = compatible_appimages if compatible_appimages else appimages

        if not filtered_appimages:
            raise ValueError("No AppImage files found in release")

        logging.info(f"Found {len(filtered_appimages)} potentially compatible AppImages")

        # 1. Try to match based on previously saved arch_keyword (exact ending)
        if self._arch_keyword:
            # Create a regex pattern that matches the arch_keyword at the end of the string.
            pattern = re.compile(re.escape(self._arch_keyword.strip().lower()) + r"\Z")
            logging.info(f"Trying to find match with arch keyword: {self._arch_keyword}")
            for asset in filtered_appimages:
                asset_name = asset["name"].strip().lower()
                logging.info(f"Checking asset: {asset_name}")
                if pattern.search(asset_name):
                    self._select_appimage(asset)
                    return

        # 2. Filter by current architecture keywords with stronger matching
        candidates = []
        exact_arch_match = None
        current_arch_keywords = self.arch_keywords

        for asset in filtered_appimages:
            name = asset["name"].lower()

            # Look for exact architecture match first (highest priority)
            if current_arch in name:
                exact_arch_match = asset
                break

            # Otherwise collect candidates based on architecture keywords
            if any(kw in name for kw in current_arch_keywords):
                candidates.append(asset)

        # If we found an exact architecture match, use it immediately
        if exact_arch_match:
            logging.info(f"Found exact architecture match: {exact_arch_match['name']}")
            self._select_appimage(exact_arch_match)
            return

        # 3. Handle candidate selection
        if len(candidates) == 1:
            self._select_appimage(candidates[0])
            return
        elif candidates:
            logging.info(f"Found {len(candidates)} architecture-matched AppImages")
            print(f"Found {len(candidates)} architecture-matched AppImages:")
            ui_utils.select_from_list(candidates, "Select AppImage", callback=self._select_appimage)
            return

        # 4. For generic Linux builds without architecture in name, prefer those
        generic_linux_builds = [
            asset
            for asset in filtered_appimages
            if "linux" in asset["name"].lower()
            and not any(
                arch in asset["name"].lower()
                for arch in [
                    "arm",
                    "arm64",
                    "aarch64",
                    "armhf",
                    "arm32",
                    "x86_64",
                    "amd64",
                    "i686",
                    "i386",
                ]
            )
        ]

        if len(generic_linux_builds) == 1:
            logging.info(f"Found generic Linux build: {generic_linux_builds[0]['name']}")
            self._select_appimage(generic_linux_builds[0])
            return
        elif generic_linux_builds:
            logging.info(f"Found {len(generic_linux_builds)} generic Linux builds")
            print(f"Found {len(generic_linux_builds)} generic Linux builds:")
            ui_utils.select_from_list(
                generic_linux_builds, "Select AppImage", callback=self._select_appimage
            )
            return

        # 5. Auto select if only one AppImage is left
        if len(filtered_appimages) == 1:
            self._select_appimage(filtered_appimages[0])
            return

        # 6. Fallback to asking user to choose from all compatible AppImages
        logging.info("No architecture-specific builds found, select from compatible AppImages")
        print("Please select the AppImage appropriate for your system:")
        ui_utils.select_from_list(
            filtered_appimages, "Select AppImage", callback=self._select_appimage
        )

    def _select_appimage(self, asset):
        """Select an AppImage asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary

        """
        self.appimage_url = asset["browser_download_url"]
        self.appimage_name = asset["name"]
        logging.info(f"Selected: {self.appimage_name}")

        # Extract an arch keyword from the selected asset name.
        lower_name = self.appimage_name.lower()

        # Improved architecture extraction that keeps additional components like Qt6
        # First try to identify the architecture component in the filename
        arch_found = False
        for key in ["arm64", "aarch64", "amd64", "x86_64", "x86", "i686", "i386"]:
            if key in lower_name:
                # Find position of architecture in name
                pos = lower_name.find(key)
                if pos >= 0:
                    # Extract everything from the dash before architecture to the end of filename
                    # But remove the .appimage extension
                    dash_pos = lower_name.rfind("-", 0, pos)
                    if dash_pos >= 0:
                        # Extract suffix from dash through end (without extension)
                        suffix = lower_name[dash_pos:]
                        if suffix.endswith(".appimage"):
                            suffix = suffix[:-9]  # Remove .appimage
                        self._arch_keyword = f"{suffix}.appimage"
                        arch_found = True
                        logging.info(f"Extracted architecture keyword: {self._arch_keyword}")
                        break

        # Fallbacks if we couldn't extract using the improved method
        if not arch_found:
            # Check for Linux pattern
            match = re.search(r"(-linux(?:64)?\.appimage)$", lower_name)
            if match:
                self._arch_keyword = match.group(1)
            else:
                # Last resort: use the file extension
                self._arch_keyword = ".appimage"

    def _find_sha_asset(self, assets: list):
        """Find and select appropriate SHA file for verification.

        Args:
            assets: List of release assets from GitHub API

        """
        # Skip if SHA verification is disabled
        if self.sha_name == "no_sha_file":
            logging.info("Skipping SHA verification per configuration")
            return

        # Extract architecture from selected AppImage name for better SHA matching
        appimage_arch = arch_utils.extract_arch_from_filename(self.appimage_name)
        appimage_base_name = os.path.basename(self.appimage_name)
        logging.info(f"Extracted architecture from AppImage: {appimage_arch}")
        logging.info(f"AppImage base name: {appimage_base_name}")

        # 1. Try exact match first if SHA name is provided
        if self.sha_name and self.sha_name != "sha256" and self.sha_name != "sha512":
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self._select_sha_asset(asset)
                    return

        # Initialize category buckets for SHA files
        direct_appimage_sha = None  # Highest priority: AppImage name with .sha512/.sha256 extension
        arch_specific_sha_candidates = []  # Architecture-specific SHA files
        linux_yml = None  # Linux YML file (common in Electron apps)
        latest_yml = None  # Generic latest.yml (usually for other platforms)
        sha256sums = None  # Common SHA256SUMS file
        generic_sha_candidates = []  # Other generic SHA files
        all_sha_files = []  # All SHA files as fallback

        # 2. Categorize all SHA files
        for asset in assets:
            name = asset["name"].lower()

            # Skip the AppImage itself - this is critical for test cases
            if name == appimage_base_name.lower() or name.endswith(".appimage"):
                continue

            # Only process files that appear to be SHA files or specific known formats
            if (
                not sha_utils.is_sha_file(name)
                and not name.endswith(".yml")
                and "sha" not in name
                and "sum" not in name
            ):
                continue

            # Add to all SHA files list for fallback
            all_sha_files.append(asset)

            # Check for direct AppImage SHA file (e.g., "Joplin-3.2.13.AppImage.sha512")
            appimage_sha_pattern = f"{appimage_base_name.lower()}.sha"
            if name.startswith(appimage_base_name.lower()) and (
                name.endswith(".sha256") or name.endswith(".sha512")
            ):
                direct_appimage_sha = asset
                logging.info(f"Found direct AppImage SHA file: {asset['name']}")
                break  # Highest priority, exit loop immediately

            # Special handling for common SHA files
            if name == "sha256sums" or name == "sha256sums.txt":
                sha256sums = asset
                continue

            if name == "latest-linux.yml":
                linux_yml = asset
                continue

            if name == "latest.yml":
                latest_yml = asset
                continue

            # Match architecture-specific SHA files with the AppImage architecture
            asset_arch = arch_utils.extract_arch_from_filename(name)

            if asset_arch:
                # Only include architecture-specific files if they match the AppImage architecture
                if asset_arch == appimage_arch:
                    arch_specific_sha_candidates.append(asset)
                # Skip SHA files that are for other architectures
                continue

            # Include generic SHA files (no specific architecture in name)
            # Only include files that appear to be for Linux/generic platforms
            if "mac" not in name and "windows" not in name and "win" not in name:
                generic_sha_candidates.append(asset)

        # 3. Select SHA file based on improved prioritization

        # Highest priority: Direct AppImage SHA file
        if direct_appimage_sha:
            logging.info(f"Selected direct AppImage SHA file: {direct_appimage_sha['name']}")
            self._select_sha_asset(direct_appimage_sha)
            return

        # Second priority: Architecture-specific SHA files
        if len(arch_specific_sha_candidates) == 1:
            logging.info(
                f"Found architecture-specific SHA file: {arch_specific_sha_candidates[0]['name']}"
            )
            self._select_sha_asset(arch_specific_sha_candidates[0])
            return
        elif len(arch_specific_sha_candidates) > 1:
            logging.info("Multiple architecture-specific SHA files found")
            # During tests, automatically select the first option
            if os.environ.get("PYTEST_CURRENT_TEST"):
                self._select_sha_asset(arch_specific_sha_candidates[0])
                return
            print("Multiple architecture-specific SHA files found:")
            ui_utils.select_from_list(
                arch_specific_sha_candidates, "Select SHA file", callback=self._select_sha_asset
            )
            return

        # Third priority: Linux YML file for Linux AppImages
        if linux_yml:
            logging.info("Using latest-linux.yml file as default SHA for Linux")
            self._select_sha_asset(linux_yml)
            return

        # Fourth priority: Common SHA256SUMS file
        if sha256sums:
            logging.info("Using SHA256SUMS file as default SHA256 checksums file")
            self._select_sha_asset(sha256sums)
            return

        # Fifth priority: Generic SHA candidates
        if len(generic_sha_candidates) == 1:
            logging.info(f"Using generic SHA file: {generic_sha_candidates[0]['name']}")
            self._select_sha_asset(generic_sha_candidates[0])
            return
        elif len(generic_sha_candidates) > 0:
            logging.info("Multiple generic SHA files found")
            # During tests, automatically select the first option
            if os.environ.get("PYTEST_CURRENT_TEST"):
                self._select_sha_asset(generic_sha_candidates[0])
                return
            print("SHA files compatible with your architecture:")
            ui_utils.select_from_list(
                generic_sha_candidates, "Select SHA file", callback=self._select_sha_asset
            )
            return

        # Sixth priority: Latest.yml as fallback for non-Linux platforms
        if latest_yml:
            logging.info("Using latest.yml file as fallback SHA (non-Linux platform)")
            self._select_sha_asset(latest_yml)
            return

        # Last resort: any SHA file
        if len(all_sha_files) == 1:
            logging.info(f"Using only available SHA file: {all_sha_files[0]['name']}")
            self._select_sha_asset(all_sha_files[0])
            return
        elif len(all_sha_files) > 0:
            logging.info("Found multiple SHA files")
            # During tests, automatically select the first option
            if os.environ.get("PYTEST_CURRENT_TEST"):
                self._select_sha_asset(all_sha_files[0])
                return
            print("Found multiple SHA files:")
            ui_utils.select_from_list(
                all_sha_files, "Select SHA file", callback=self._select_sha_asset
            )
            return

        # Final fallback to manual input
        self._handle_sha_fallback(assets)

    def _select_sha_asset(self, asset):
        """Select a SHA asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary

        """
        self.sha_name = asset["name"]
        self.sha_url = asset["browser_download_url"]

        # Auto-detect hash type
        self.hash_type = sha_utils.detect_hash_type(self.sha_name)

        # If hash type couldn't be detected, ask user
        if not self.hash_type:
            logging.info(f"Could not detect hash type from {self.sha_name}")
            print(f"Could not detect hash type from {self.sha_name}")
            self.hash_type = ui_utils.get_user_input("Enter hash type", default="sha256")

        logging.info(f"Selected SHA file: {self.sha_name} (hash type: {self.hash_type})")

    def _handle_sha_fallback(self, assets):
        """Handle fallback when SHA file couldn't be automatically determined.

        Args:
            assets: List of release assets from GitHub API

        """
        # Check if this app uses release description for checksums
        from src.app_catalog import find_app_by_owner_repo

        app_info = find_app_by_owner_repo(self.owner, self.repo)

        if app_info and hasattr(app_info, "sha_name") and app_info.sha_name == "extracted_checksum":
            logging.info(f"App {self.owner}/{self.repo} uses release description for checksums")
            self.sha_name = "extracted_checksum"
            self.hash_type = getattr(app_info, "hash_type", "sha256") or "sha256"
            logging.info("Will extract checksums from release description for verification")
            return

        # Original fallback code continues for other cases...
        logging.warning("Could not find SHA file automatically")
        print(f"Could not find SHA file automatically for {self.appimage_name}")
        print("1. Enter filename manually")
        print("2. Skip verification")

        choice = ui_utils.get_user_input("Your choice (1-2)")

        if choice == "1":
            self.sha_name = ui_utils.get_user_input("Enter exact SHA filename")
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self.sha_url = asset["browser_download_url"]
                    self._select_sha_asset(asset)
                    return
            raise ValueError(f"SHA file {self.sha_name} not found")
        else:
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            logging.info("User chose to skip SHA verification")
