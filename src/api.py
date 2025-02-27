import requests
import json
import logging
import os
import platform
import re


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

    def _get_arch_keywords(self):
        """Static architecture keywords including linux variants"""
        machine = platform.machine().lower()
        return {
            "x86_64": ["x86_64", "amd64", "linux", "linux64"],
            "amd64": ["amd64", "x86_64", "linux"],
            "armv7l": ["arm", "armv7l", "armhf"],
            "aarch64": ["aarch64", "arm64"],
        }.get(machine, [])

    def get_response(self):
        """Fetch release data with beta fallback handling"""
        try:
            # Try stable release first
            response = requests.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest",
                timeout=10,
            )

            if response.status_code == 200:
                return self._process_release(response.json(), is_beta=False)

            # Fallback to beta releases
            response = requests.get(
                f"https://api.github.com/repos/{self.owner}/{self.repo}/releases",
                timeout=10,
            )

            if response.status_code == 200 and response.json():
                return self._process_release(response.json()[0], is_beta=True)

            logging.error(
                f"Failed to fetch releases. Status code: {response.status_code}"
            )
            return None

        except requests.exceptions.RequestException as e:
            logging.error(f"Request failed: {e}")
            return None

    def _process_release(self, release_data: dict, is_beta: bool):
        """Process release data from either stable or beta releases"""
        try:
            if is_beta:
                self.version = (
                    release_data["tag_name"].replace("v", "").replace("-beta", "")
                )
            else:
                self.version = release_data["tag_name"].replace("v", "")

            assets = release_data.get("assets", [])
            self._find_appimage_asset(assets)
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

    def _find_appimage_asset(self, assets: list):
        """Reliable AppImage selection with architecture keywords"""
        print("Current arch_keyword:", self.arch_keyword)

        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]

        if not appimages:
            raise ValueError("No AppImage files found in release")

        # 1. Try to match based on previously saved arch_keyword (exact ending)
        if self.arch_keyword:
            # Create a regex pattern that matches the arch_keyword at the end of the string.
            pattern = re.compile(re.escape(self.arch_keyword.strip().lower()) + r"\Z")
            print(f"Trying to find match with arch keyword: {self.arch_keyword}")
            for asset in appimages:
                asset_name = asset["name"].strip().lower()
                print(f"Checking asset: {asset_name}")
                if pattern.search(asset_name):
                    self._select_appimage(asset)
                    return

        # 2. Filter by current architecture keywords list
        candidates = []
        for asset in appimages:
            name = asset["name"].lower()
            if any(kw in name for kw in self.arch_keywords):
                candidates.append(asset)

        # 3. Handle candidate selection
        if len(candidates) == 1:
            self._select_appimage(candidates[0])
            return
        elif candidates:
            print(f"Found {len(candidates)} architecture-matched AppImages:")
            self._select_from_list(candidates)
            return

        # Auto select if only one AppImage is left
        if len(appimages) == 1:
            self._select_appimage(appimages[0])
            return

        # 4. Fallback to asking user to choose from all AppImages
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
            print("Invalid input, try again")

    def _select_appimage(self, asset):
        self.appimage_url = asset["browser_download_url"]
        self.appimage_name = asset["name"]
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
        """Find SHA checksum asset with fallback logic"""

        if self.sha_name == "no_sha_file":
            logging.info("Skipping SHA verification per configuration")
            return

        sha_keywords = {
            "sha",
            "sha256",
            "sha512",
            "sha-256",
            "sha-512",
            "checksum",
            "checksums",
            "latest-linux",
            "sha256sums",
        }
        valid_extensions = {
            ".sha256",
            ".sha512",
            ".yml",
            ".yaml",
            ".txt",
            ".sum",
            ".sha",
        }
        # Check assets with reliable extension/keyword matching
        for asset in assets:
            name_lower = asset["name"].lower()
            _, ext = os.path.splitext(name_lower)  # Gets extension with dot

            # Match both keywords and valid extensions
            if any(kw in name_lower for kw in sha_keywords) and ext in valid_extensions:
                sha_asset = asset
                break

        # TESTING: hash detection
        if sha_asset:
            self.sha_name = sha_asset["name"]
            self.sha_url = sha_asset["browser_download_url"]
            # Automatically detect hash type from the filename
            ext = os.path.splitext(sha_asset["name"])[1].lower()
            if ext == ".sha256" or "sha256" in sha_asset["name"].lower():
                self.hash_type = "sha256"
            elif ext == ".sha512" or "sha512" in sha_asset["name"].lower():
                self.hash_type = "sha512"
            elif ext == ".yml" or ext == ".yaml" in sha_asset["name"].lower():
                self.hash_type = "sha512"
            else:
                # Fall back to asking user for hash type if not found
                default = "sha256"
                print(f"Could not detect hash type from filename: {sha_asset['name']}")
                user_input = input(f"Enter hash type (default: {default}): ")
                self.hash_type = user_input if user_input else default

            return

        # Fallback to asking user for the SHA file if not found
        print("Could not find SHA file. Options:")
        print("1. Enter filename manually")
        print("2. Skip verification")
        choice = input("Your choice (1 or 2): ")

        if choice == "2":
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            return

        self.sha_name = input("Enter exact SHA filename: ")
        for asset in assets:
            if asset["name"] == self.sha_name:
                self.sha_url = asset["browser_download_url"]
                # After manual selection, prompt for hash type as a fallback
                default = "sha256"
                user_input = input(f"Enter hash type (default: {default}): ")
                self.hash_type = user_input if user_input else default
                return

        raise ValueError("Specified SHA file not found in release assets")

    def check_latest_version(self, owner, repo):
        """Check if the latest version is already installed"""
        try:
            # Fetch latest or beta latest release data
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
                timeout=10,
            )
            response_beta = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases",
                timeout=10,
            )

            if response.status_code == 200:
                latest_version = response.json()["tag_name"].replace("v", "")
                return latest_version
            elif response_beta.status_code == 200:
                latest_version = (
                    response_beta.json()[0]["tag_name"]
                    .replace("v", "")
                    .replace("-beta", "")
                )
                return latest_version
            else:
                logging.error(
                    f"Failed to fetch releases. Status code: {response.status_code}"
                )
                return None

        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed: {e}")
            return None
