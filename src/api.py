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
        # Handle Standard Notes special case - they use "@standardnotes/desktop@X.Y.Z" format
        if self.repo.lower() == "app" and self.owner.lower() == "standardnotes":
            # Extract version after the last @ symbol
            std_notes_match = re.search(r"@([0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?$)", tag)
            if std_notes_match:
                return std_notes_match.group(1)

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
                tag_name = response.json()["tag_name"]
                # Handle Standard Notes specific version format
                if owner.lower() == "standardnotes" and repo.lower() == "app":
                    latest_version = self._parse_standard_notes_version(tag_name)
                    if latest_version:
                        logging.info(f"Parsed Standard Notes version: {latest_version}")
                        return latest_version

                # Default handling for other apps
                latest_version = tag_name.replace("v", "")
                logging.info(f"Found latest version: {latest_version}")
                return latest_version
            elif response_beta.status_code == 200 and response_beta.json():
                tag_name = response_beta.json()[0]["tag_name"]
                # Handle Standard Notes specific version format for beta
                if owner.lower() == "standardnotes" and repo.lower() == "app":
                    latest_version = self._parse_standard_notes_version(tag_name)
                    if latest_version:
                        logging.info(f"Parsed Standard Notes beta version: {latest_version}")
                        return latest_version

                # Default handling for other apps
                latest_version = tag_name.replace("v", "").replace("-beta", "")
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

    def _parse_standard_notes_version(self, tag_name: str) -> Optional[str]:
        """
        Parse Standard Notes specific version format.

        Standard Notes uses tag format like "@standardnotes/desktop@X.Y.Z"

        Args:
            tag_name: The tag name to parse

        Returns:
            str or None: Parsed version or None if no match
        """
        # Extract version after the last @ symbol
        match = re.search(r"@([0-9]+\.[0-9]+\.[0-9]+(?:-[a-zA-Z0-9.]+)?$)", tag_name)
        if match:
            return match.group(1)
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

    def _find_appimage_asset(self, assets: list) -> Optional[str]:
        """
        Find AppImage asset from release assets.

        Args:
            assets: List of release assets objects from GitHub API

        Returns:
            str or None: AppImage URL if found, None otherwise
        """
        best_match = None
        best_score = -1

        # Special case for Standard Notes which has specific naming pattern
        is_standard_notes = self.repo.lower() == "app" and self.owner.lower() == "standardnotes"

        for asset in assets:
            name = asset.get("name", "").lower()

            # Skip non-AppImage files
            if ".appimage" not in name:
                continue

            # For Standard Notes, look for linux-x86_64.AppImage pattern
            if is_standard_notes:
                if "linux-x86_64.appimage" in name:
                    self.appimage_name = asset["name"]
                    self.appimage_url = asset["browser_download_url"]
                    logging.info(f"Found Standard Notes AppImage: {self.appimage_name}")
                    return self.appimage_url

            # For other apps, use architecture matching
            score = self._score_arch_match(name)

            # If better match, update
            if score > best_score:
                best_match = asset
                best_score = score

        if best_match:
            self.appimage_name = best_match["name"]
            self.appimage_url = best_match["browser_download_url"]
            logging.info(f"Found AppImage: {self.appimage_name}")
            return self.appimage_url

        return None

    def _score_arch_match(self, filename: str) -> int:
        """
        Score how well a filename matches the current architecture.

        Args:
            filename: Filename to check against architecture keywords

        Returns:
            int: Match score (higher is better)
        """
        filename = filename.lower()

        # First check if we have any architecture keywords to match against
        if not self.arch_keywords:
            # No architecture specified, just make sure it's an AppImage
            return 1 if ".appimage" in filename else 0

        # If user provided a specific architecture keyword, prioritize matches
        if self.arch_keyword and self.arch_keyword.lower() in filename:
            return 100

        # Score by position of match in keyword list (more specific keywords come first)
        for i, keyword in enumerate(self.arch_keywords):
            if keyword in filename:
                # Earlier matches (more specific) get higher scores
                return 50 - i

        # If no keyword matches were found, this is a generic AppImage
        # Better than nothing, but low priority
        return 0

    def _find_sha_asset(self, assets: list) -> Optional[str]:
        """
        Find SHA file asset from release assets.

        Looks for files with SHA256/SHA512 in name, or .sha256/.sha512 extensions.
        For Standard Notes, special handling of specific naming patterns.

        Args:
            assets: List of release assets objects from GitHub API

        Returns:
            str or None: SHA URL if found, None otherwise
        """
        if not self.appimage_name:
            logging.warning("AppImage name not set, cannot find matching SHA asset")
            return None

        # Special case for Standard Notes which might not have SHA files
        is_standard_notes = self.repo.lower() == "app" and self.owner.lower() == "standardnotes"
        if is_standard_notes and not any(
            "sha" in asset.get("name", "").lower() for asset in assets
        ):
            logging.info("No SHA file found for Standard Notes, skipping verification")
            self.sha_name = "no_sha_file"
            self.sha_url = None
            return None

        appimage_base = os.path.splitext(self.appimage_name)[0]

        # If SHA name was provided, use it directly if it exists
        if self.sha_name and self.sha_name != "auto":
            for asset in assets:
                name = asset.get("name", "")
                if name == self.sha_name:
                    self.sha_url = asset["browser_download_url"]
                    logging.info(f"Found specified SHA file: {self.sha_name}")
                    return self.sha_url

        # Auto detection
        best_match = None
        best_score = -1

        for asset in assets:
            name = asset.get("name", "").lower()
            score = 0

            # Extension matches our hash type
            if name.endswith(f".{self.hash_type}"):
                score += 5

            # Name contains our hash type
            if self.hash_type in name:
                score += 3

            # Contains any hash type word
            if "sha" in name:
                score += 1

            # Contains basename of AppImage
            base_tokens = appimage_base.lower().split("-")
            for token in base_tokens:
                if len(token) > 2 and token in name:
                    score += 2

            # It's either a checksums file or has yaml/yml extension
            if any(word in name for word in ["checksum", "sum", "hash", ".yml", ".yaml"]):
                score += 2

            # Update if better match
            if score > best_score:
                best_match = asset
                best_score = score

        # If a reasonable match was found (score > 2)
        if best_match and best_score > 2:
            self.sha_name = best_match["name"]
            self.sha_url = best_match["browser_download_url"]
            logging.info(f"Found SHA file: {self.sha_name}")
            return self.sha_url

        # No SHA file found, mark for skipping verification
        logging.warning("No SHA file found in release assets")
        self.sha_name = "no_sha_file"
        self.sha_url = None
        return None
