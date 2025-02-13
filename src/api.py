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
        self.sha_name = sha_name
        self.hash_type = hash_type
        self.api_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        )
        self.version = None
        self.sha_url = None
        self.appimage_url = None
        self.appimage_name = None

    def get_response(self):
        """Fetch the latest release data from GitHub API."""
        response = requests.get(self.api_url, timeout=10)
        if response.status_code == 200:
            data = json.loads(response.text)
            self.version = data["tag_name"].replace("v", "")

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

            # Iterate over assets to find AppImage and SHA file based on the criteria.
            for asset in data["assets"]:
                if asset["name"].endswith(".AppImage"):
                    self.appimage_name = asset["name"]
                    self.appimage_url = asset["browser_download_url"]
                elif any(keyword in asset["name"] for keyword in keywords) and asset[
                    "name"
                ].endswith(tuple(valid_extensions)):
                    self.sha_name = asset["name"]
                    self.sha_url = asset["browser_download_url"]

            # If sha_url is not set, try matching the already provided sha_name
            if not hasattr(self, "sha_url") or self.sha_url is None:
                for asset in data["assets"]:
                    if asset["name"] == self.sha_name:
                        self.sha_url = asset["browser_download_url"]
                        break

                # If still not found, prompt the user.
                if self.sha_url is None:
                    print(
                        "Couldn't automatically find the SHA file using keywords and extensions."
                    )
                    self.sha_name = input("Enter the exact SHA file name: ")
                    for asset in data["assets"]:
                        if asset["name"] == self.sha_name:
                            self.sha_url = asset["browser_download_url"]
                            break
                    if self.sha_url is None:
                        raise ValueError(
                            "SHA file URL could not be determined based on the provided name."
                        )
        else:
            print(f"Failed to get response from API: {self.api_url}")
            return None
        return self.sha_url

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
