import requests
import json
import logging


class GitHubAPI:
    """Handles interaction with the GitHub API to fetch release information."""

    def __init__(
        self, owner: str, repo: str, sha_name: str = None, hash_type: str = "sha256"
    ):
        """Initialize the GitHubAPI object with owner, repo, and other optional params."""
        self.owner = owner
        self.repo = repo
        self._sha_name = sha_name
        self._hash_type = hash_type
        self.api_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        )
        self._version = None
        self._sha_url = None
        self._appimage_url = None
        self._appimage_name = None

    def get_response(self):
        """Fetch the latest release data from GitHub API."""
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            data = json.loads(response.text)
            self._version = data["tag_name"].replace("v", "")

            # Keywords and valid extensions to identify SHA files
            keywords = {
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

            # Iterate over assets to find appimage and sha file based on the criteria
            for asset in data["assets"]:
                if asset["name"].endswith(".AppImage"):
                    self._appimage_name = asset["name"]
                    self._appimage_url = asset["browser_download_url"]
                elif any(keyword in asset["name"] for keyword in keywords) and asset[
                    "name"
                ].endswith(tuple(valid_extensions)):
                    self._sha_name = asset["name"]
                    self._sha_url = asset["browser_download_url"]

            # If sha_url is not found based on keywords, prompt user input (fallback)
            if self._sha_name is None:
                print("Couldn't find the sha file using keywords and extensions.")
                self._sha_name = input("Enter the exact sha file name: ")

        else:
            print(f"Failed to get response from API: {self.api_url}")
            return None
        return self._sha_url

    def check_latest_version(self, owner, repo):
        """Fetch the latest release version from GitHub."""
        try:
            response = requests.get(
                f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
            )
            response.raise_for_status()
            return response.json()["tag_name"].replace("v", "")
        except requests.exceptions.RequestException as e:
            logging.error(f"GitHub API request failed: {e}")
            return None

    @property
    def version(self):
        """Return the version from the API response."""
        return self._version

    @property
    def sha_url(self):
        """Return the verification file URL."""
        return self._sha_url

    @property
    def sha_name(self):
        """Return the verification file name"""
        return self._sha_name

    @sha_name.setter
    def sha_name(self, value):
        """Setter for _sha_name."""
        self._sha_name = value

    @property
    def hash_type(self):
        """Return the hash type."""
        return self._hash_type

    @hash_type.setter
    def hash_type(self, value):
        """Setter for _hash_type."""
        self._hash_type = value

    @property
    def appimage_url(self):
        """Return the AppImage download URL."""
        return self._appimage_url

    @property
    def appimage_name(self):
        """Return the AppImage name."""
        return self._appimage_name
