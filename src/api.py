import requests
import json
import logging
import os


class GitHubAPI:
    """Handles interaction with the GitHub API to fetch release information."""

    def __init__(
        self,
        owner: str,
        repo: str,
        sha_name: str = None,
        hash_type: str = "sha256",
    ):
        self.owner = owner
        self.repo = repo
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.version = None
        self.sha_url = None
        self.appimage_url = None
        self.appimage_name = None
        self.exact_appimage_name = None

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
                "exact_appimage_name": self.exact_appimage_name,
                "appimage_url": self.appimage_url,
                "sha_url": self.sha_url,
            }

        except KeyError as e:
            logging.error(f"Missing expected key in release data: {e}")
            return None

    def _find_appimage_asset(self, assets: list):
        """Find AppImage asset with user selection when multiple exist"""
        appimages = [a for a in assets if a["name"].lower().endswith(".appimage")]

        if not appimages:
            raise ValueError("No AppImage files found in release")

        # Try to find exact match from previous config
        if self.exact_appimage_name:
            for asset in appimages:
                if asset["name"] == self.exact_appimage_name:
                    self._select_appimage(asset)
                    return

        # Auto-select if only one found
        if len(appimages) == 1:
            self._select_appimage(appimages[0])
            self.exact_appimage_name = self.appimage_name  # Save for return
            return

        # Multiple found - prompt user
        print("Multiple AppImage versions found:")
        for idx, asset in enumerate(appimages, 1):
            print(f"{idx}. {asset['name']}")

        while True:
            choice = input(f"Select version (1-{len(appimages)}): ")
            if choice.isdigit() and 1 <= int(choice) <= len(appimages):
                selected = appimages[int(choice) - 1]
                self._select_appimage(selected)
                self.exact_appimage_name = self.appimage_name  # Save for return
                return
            print("Invalid input, please try again")

    def _select_appimage(self, asset):
        self.appimage_url = asset["browser_download_url"]
        self.appimage_name = asset["name"]
        print(f"Selected: {self.appimage_name}")

    def _find_sha_asset(self, assets: list):
        """Find SHA checksum asset with fallback logic"""

        if self.sha_name == "no_sha_file":
            logging.info("Skipping SHA verification per configuration")
            return

        sha_keywords = {
            "sha",
            "SHA",
            "SHA256",
            "SHA512",
            "SHA-256",
            "SHA-512",
            "checksum",
            "checksums",
            "CHECKSUM",
            "CHECKSUMS",
            "latest-linux",
            "SHA256SUMS",
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
                self.sha_name = asset["name"]
                self.sha_url = asset["browser_download_url"]
                return

        # Manual fallback
        print("Could not find SHA file. Options:")
        print("1. Enter filename manually")
        print("2. Skip verification")
        choice = input("Your choice (1/2): ")

        if choice == "2":
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            return

        self.sha_name = input("Enter exact SHA filename: ")
        for asset in assets:
            if asset["name"] == self.sha_name:
                self.sha_url = asset["browser_download_url"]
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
