import logging
import platform
import re
import os
import requests
from datetime import datetime
from typing import Dict, Optional, List

from src.icon_manager import IconManager
from src.auth_manager import GitHubAuthManager


class GitHubAPI:
    """Handles interaction with the GitHub API to fetch release information."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = None,
        hash_type: str = "sha256",
        arch_keyword: str = None,
    ):
        """
        Initialize the GitHub API client with repository information.

        Args:
            owner: GitHub repository owner/organization
            repo: GitHub repository name
            sha_name: Name of SHA hash file (if known)
            hash_type: Type of hash for verification (sha256, sha512)
            arch_keyword: Architecture-specific keyword for file matching
        """
        self.owner = owner
        self.repo = repo
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.version = None
        self.sha_url = None
        self.appimage_url = None
        self.appimage_name = None
        self.arch_keyword = arch_keyword
        self.arch_keywords = self._get_arch_keywords()
        # Initialize headers with authentication if available
        self._headers = GitHubAuthManager.get_auth_headers()

    def _get_arch_keywords(self) -> List[str]:
        """
        Get architecture-specific keywords for the current system.

        Returns:
            list: Architecture keywords for the current platform
        """
        machine = platform.machine().lower()
        # Store the current system architecture for better matching
        self.current_arch = machine

        # Update keyword mapping with more specific keywords first (for better matching)
        return {
            "x86_64": ["x86_64", "x86-64", "amd64", "x64", "linux64"],
            "amd64": ["amd64", "x86_64", "x86-64", "x64", "linux64"],
            "armv7l": ["armv7l", "arm", "armhf"],
            "aarch64": ["aarch64", "arm64"],
        }.get(machine, [])

    def get_response(self):
        """
        Fetch release data with beta fallback handling.

        Returns:
            dict or None: Processed release data or None if request failed
        """
        try:
            # Try stable release first with auth headers
            response = requests.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest",
                headers=self._headers,
                timeout=10,
            )

            if response.status_code == 200:
                return self._process_release(response.json(), is_beta=False)

            # Fallback to beta releases
            response = requests.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/releases",
                headers=self._headers,
                timeout=10,
            )

            if response.status_code == 200 and response.json():
                return self._process_release(response.json()[0], is_beta=True)

            # Handle rate limit explicitly
            if response.status_code == 403 and "X-RateLimit-Remaining" in response.headers:
                remaining = response.headers["X-RateLimit-Remaining"]
                if remaining == "0":
                    reset_time = int(response.headers["X-RateLimit-Reset"])
                    reset_datetime = datetime.fromtimestamp(reset_time)
                    error_msg = f"GitHub API rate limit exceeded. Resets at {reset_datetime}"
                    logging.error(error_msg)
                    print(f"Error: {error_msg}")
                    print(
                        "Tip: Add or update your GitHub token using option 6 in the main menu to increase rate limits."
                    )
                    return None

            logging.error(f"Failed to fetch releases. Status code: {response.status_code}")
            return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            return None

    # HACK: to make the code work for complex version parsing
    # TODO: need to refactor this method
    def _process_release(self, release_data: dict, is_beta: bool):
        """Process release data with robust version parsing"""
        try:
            raw_tag = release_data["tag_name"]
            assets = release_data.get("assets", [])

            # First try to extract version from tag name
            version = self._extract_version(raw_tag, is_beta)

            # Find AppImage - THIS MUST SUCCEED
            self._find_appimage_asset(assets)
            if not self.appimage_name:
                raise ValueError("No AppImage found in release assets")

            if not version:
                version = self._extract_version_from_filename(self.appimage_name)

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
                "arch_keyword": self.arch_keyword,
                "appimage_url": self.appimage_url,
                "sha_url": self.sha_url,
            }

        except KeyError as e:
            logging.error(f"Missing expected key in release data: {e}")
            return None

    def _extract_version(self, tag: str, is_beta: bool) -> str:
        """Extract semantic version from tag string"""
        # Clean common prefixes/suffixes
        clean_tag = tag.lstrip("vV").replace("-beta", "").replace("-stable", "")

        # Match semantic version pattern
        version_match = re.search(r"\d+\.\d+\.\d+(?:\.\d+)*", clean_tag)
        if version_match:
            return version_match.group(0)

        # Try alternative patterns if standard semantic version not found
        alt_match = re.search(r"(\d+[\w\.]+)", clean_tag)
        return alt_match.group(1) if alt_match else None

    def _extract_version_from_filename(self, filename: str) -> str:
        """Fallback version extraction from appimage filename"""
        if not filename:
            return None

        # Try to find version in filename segments
        for part in filename.split("-"):
            version = self._extract_version(part, False)
            if version:
                return version

        # Final fallback to regex search
        version_match = re.search(r"\d+\.\d+\.\d+", filename)

        return version_match.group(0) if version_match else None

    def _find_appimage_asset(self, assets: list):
        """
        Reliable AppImage selection with architecture keywords.

        Args:
            assets: List of release assets from GitHub API
        """
        logging.info(f"Current arch_keyword: {self.arch_keyword}")
        logging.info(
            f"Current system architecture: {getattr(self, 'current_arch', platform.machine().lower())}"
        )

        # Filter all AppImage files
        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]

        if not appimages:
            raise ValueError("No AppImage files found in release")

        # 1. Try to match based on previously saved arch_keyword (exact ending)
        if self.arch_keyword:
            # Create a regex pattern that matches the arch_keyword at the end of the string.
            pattern = re.compile(re.escape(self.arch_keyword.strip().lower()) + r"\Z")
            logging.info(f"Trying to find match with arch keyword: {self.arch_keyword}")
            for asset in appimages:
                asset_name = asset["name"].strip().lower()
                logging.info(f"Checking asset: {asset_name}")
                if pattern.search(asset_name):
                    self._select_appimage(asset)
                    return

        # 2. Filter by current architecture keywords with stronger matching
        candidates = []
        exact_arch_match = None

        # Current architecture to find a perfect match
        current_arch = getattr(self, "current_arch", platform.machine().lower())

        for asset in appimages:
            name = asset["name"].lower()

            # Look for exact architecture match first (highest priority)
            if current_arch in name:
                exact_arch_match = asset
                break

            # Otherwise collect candidates based on architecture keywords
            if any(kw in name for kw in self.arch_keywords):
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
            self._select_from_list(candidates)
            return

        # Auto select if only one AppImage is left
        if len(appimages) == 1:
            self._select_appimage(appimages[0])
            return

        # 4. Fallback to asking user to choose from all AppImages
        logging.info("No architecture-specific builds found, select from all AppImages")
        print("No architecture-specific builds found, select from all AppImages:")
        self._select_from_list(appimages)

    def _select_from_list(self, appimages):
        """User selection handler with persistence"""
        for idx, asset in enumerate(appimages, 1):
            print(f"{idx}. {asset['name']}")

        while True:
            choice = input(f"Select AppImage (1-{len(appimages)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(appimages):
                selected = appimages[int(choice) - 1]
                self._select_appimage(selected)
                return
            logging.warning("Invalid input, try again")
            print("Invalid input, try again")

    def _select_appimage(self, asset):
        """
        Select an AppImage asset and set instance attributes.

        Args:
            asset: GitHub API asset information dictionary
        """
        self.appimage_url = asset["browser_download_url"]
        self.appimage_name = asset["name"]
        logging.info(f"Selected: {self.appimage_name}")
        print(f"Selected: {self.appimage_name}")
        # Extract an arch keyword from the selected asset name.
        # Prioritize more specific identifiers.
        lower_name = self.appimage_name.lower()
        for key in ["arm64", "aarch64", "amd64", "x86_64"]:
            if key in lower_name:
                self.arch_keyword = f"-{key}.appimage"
                break
        else:
            # If no specific keyword is found, fallback to a default pattern.
            # For instance, extract the substring starting with "-linux"
            match = re.search(r"(-linux(?:64)?\.appimage)$", lower_name)
            if match:
                self.arch_keyword = match.group(1)
            else:
                # Last resort: use the file extension (this is less specific)
                self.arch_keyword = ".appimage"

    def _find_sha_asset(self, assets: list):
        """Simplified SHA file detection with architecture awareness"""
        if self.sha_name == "no_sha_file":
            logging.info("Skipping SHA verification per configuration")
            return

        # 1. Try exact match first
        if self.sha_name:
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self._select_sha_asset(asset)
                    return

        # 2. Find architecture-specific SHA files
        candidates = []
        for asset in assets:
            name = asset["name"].lower()
            if not self._is_sha_file(name):
                continue

            # Match architecture keywords or common patterns
            if any(kw in name for kw in self.arch_keywords) or any(
                p in name for p in ["checksums", "sha256sums", "latest"]
            ):
                candidates.append(asset)

        # 3. Handle found candidates
        if len(candidates) == 1:
            self._select_sha_asset(candidates[0])
            return
        elif candidates:
            logging.info("Multiple SHA files found")
            print("Multiple SHA files found:")
            self._select_sha_from_list(candidates)
            return

        # 4. Fallback to any SHA file
        all_sha = [a for a in assets if self._is_sha_file(a["name"])]
        if len(all_sha) == 1:
            self._select_sha_asset(all_sha[0])
            return
        elif all_sha:
            logging.info("Found multiple SHA files")
            print("Found multiple SHA files:")
            self._select_sha_from_list(all_sha)
            return

        # 5. Final fallback to manual input
        self._handle_sha_fallback(assets)

    def _is_sha_file(self, filename: str) -> bool:
        """Check if file is a valid SHA file using simple rules"""
        name = filename.lower()
        return (
            any(
                name.endswith(ext)
                for ext in (
                    ".sha256",
                    ".sha512",
                    ".yml",
                    ".yaml",
                    ".txt",
                    ".sum",
                    ".sha",
                )
            )
            or "checksum" in name
            or "sha256" in name
            or "sha512" in name
        )

    def _select_sha_asset(self, asset):
        """Your original hash type detection with improvements"""
        self.sha_name = asset["name"]
        self.sha_url = asset["browser_download_url"]

        # Original auto-detection logic
        name_lower = self.sha_name.lower()
        if "sha256" in name_lower:
            self.hash_type = "sha256"
        elif "sha512" in name_lower:
            self.hash_type = "sha512"
        elif name_lower.endswith((".yml", ".yaml")):
            # Default for YAML files as in original code
            self.hash_type = "sha512"
        else:
            # Fallback to user input
            logging.info(f"Could not detect hash type from {self.sha_name}")
            print(f"Could not detect hash type from {self.sha_name}")
            default = "sha256"
            user_input = input(f"Enter hash type (default: {default}): ").strip()
            self.hash_type = user_input if user_input else default

        logging.info(f"Selected SHA file: {self.sha_name} (hash type: {self.hash_type})")
        print(f"Selected SHA file: {self.sha_name} (hash type: {self.hash_type})")

    def _select_sha_from_list(self, sha_assets):
        """Simple user selection prompt"""
        for idx, asset in enumerate(sha_assets, 1):
            print(f"{idx}. {asset['name']}")

        while True:
            choice = input(f"Select SHA file (1-{len(sha_assets)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(sha_assets):
                self._select_sha_asset(sha_assets[int(choice) - 1])
                return
            logging.warning("Invalid input, try again")
            print("Invalid input, try again")

    def _handle_sha_fallback(self, assets):
        """Original fallback logic with improved prompts"""
        logging.warning("Could not find SHA file automatically")
        print("Could not find SHA file automatically")
        print("1. Enter filename manually")
        print("2. Skip verification")
        choice = input("Your choice (1-2): ")

        if choice == "1":
            self.sha_name = input("Enter exact SHA filename: ")
            for asset in assets:
                if asset["name"] == self.sha_name:
                    self.sha_url = asset["browser_download_url"]
                    self._select_sha_asset(asset)  # Trigger hash type detection
                    return
            raise ValueError(f"SHA file {self.sha_name} not found")
        else:
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            logging.info("User chose to skip SHA verification")

    def check_latest_version(
        self, owner: Optional[str] = None, repo: Optional[str] = None
    ) -> Optional[str]:
        """
        Check the latest version available for a repository.

        Args:
            owner: Repository owner/organization (defaults to self.owner)
            repo: Repository name (defaults to self.repo)

        Returns:
            str or None: Latest version string or None if request failed
        """
        # Use instance values if parameters not provided
        owner = owner or self.owner
        repo = repo or self.repo

        try:
            # Ensure we have the latest authentication headers
            headers = GitHubAuthManager.get_auth_headers()

            # Fetch latest or beta latest release data with authentication
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
                headers=headers,
                timeout=10,
            )
            response_beta = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases",
                headers=headers,
                timeout=10,
            )

            if response.status_code == 200:
                latest_version = response.json()["tag_name"].replace("v", "")
                logging.info(f"Found latest version: {latest_version}")
                return latest_version
            elif response_beta.status_code == 200 and response_beta.json():
                latest_version = (
                    response_beta.json()[0]["tag_name"].replace("v", "").replace("-beta", "")
                )
                logging.info(f"Found latest beta version: {latest_version}")
                return latest_version
            else:
                # Check for rate limit issues
                if response.status_code == 403 and "X-RateLimit-Remaining" in response.headers:
                    remaining = response.headers["X-RateLimit-Remaining"]
                    if remaining == "0":
                        reset_time = int(response.headers["X-RateLimit-Reset"])
                        reset_datetime = datetime.fromtimestamp(reset_time)
                        logging.error(f"GitHub API rate limit exceeded. Resets at {reset_datetime}")
                        print(f"Error: GitHub API rate limit exceeded. Resets at {reset_datetime}")
                        print(
                            "Tip: Add or update your GitHub token using option 6 in the main menu to increase rate limits."
                        )
                        return None

                logging.error(f"Failed to fetch releases. Status code: {response.status_code}")
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed: {e}")
            return None

    def find_app_icon(self) -> Optional[Dict[str, any]]:
        """
        Find the best icon for the app using IconManager.

        Returns:
            dict or None: Icon asset information or None if no suitable icon found.
        """
        # Use IconManager for icon discovery with proper authentication
        icon_manager = IconManager()
        # Use the auth headers we already have
        icon_info = icon_manager.find_icon(self.owner, self.repo, headers=self._headers)
        return icon_info  # May be None if not found

    def refresh_auth(self) -> None:
        """
        Refresh the authentication headers to ensure token is current.

        Call this method before making API requests if the token might have changed.
        """
        self._headers = GitHubAuthManager.get_auth_headers()
