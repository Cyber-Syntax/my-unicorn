import os
import requests
import yaml
import hashlib
import base64
import logging
from .api import GitHubAPI
import gettext

_ = gettext.gettext


# TODO: Not need to acces by github api, just load from config
# Config already going to use githubapi class to save them, I don't need to make it two request
class HashManager:
    """Handles hash generation and comparison."""

    def __init__(self, hash_type="sha256"):
        self.hash_type = hash_type

    def calculate_hash(self, file_path):
        """Calculate the hash of a file."""
        with open(file_path, "rb") as file:
            return hashlib.new(self.hash_type, file.read()).hexdigest()

    def compare_hashes(self, hash1, hash2):
        """Compare two hash values."""
        return hash1 == hash2

    @staticmethod
    def decode_base64_hash(encoded_hash):
        """Decode a base64-encoded hash."""
        return base64.b64decode(encoded_hash).hex()


class SHAFileManager:
    """Handles downloading and parsing SHA files."""

    def __init__(self, sha_name, sha_url):
        self.sha_name = sha_name
        self.sha_url = sha_url

    def download_sha_file(self):
        """Download the SHA file."""
        if not os.path.exists(self.sha_name):
            response = requests.get(self.sha_url, timeout=10)
            if response.status_code == 200:
                with open(self.sha_name, "w", encoding="utf-8") as file:
                    file.write(response.text)
                print(f"\033[42mDownloaded {self.sha_name}\033[0m")
            else:
                raise ConnectionError(f"Failed to download {self.sha_url}.")
        else:
            print(f"{self.sha_name} already exists.")

    def parse_sha_file(self):
        """Parse the SHA file and extract hashes."""
        if self.sha_name.endswith((".yml", ".yaml")):
            return self._parse_yaml_sha()
        else:
            return self._parse_text_sha()

    def _parse_yaml_sha(self):
        """Parse SHA hash from a YAML file."""
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha_data = yaml.safe_load(file)
        return sha_data

    def _parse_text_sha(self):
        """Parse SHA hash from a plain text file."""
        with open(self.sha_name, "r", encoding="utf-8") as file:
            for line in file:
                if self.sha_name in line:
                    return line.split()[0]
        return None


class VerificationManager:
    """Coordinates the verification of downloaded AppImages."""

    def __init__(
        self, appimage_path: str, github_api: GitHubAPI, hash_type: str = "sha256"
    ):
        self.appimage_path = appimage_path
        self.github_api = github_api  # Dependency injection
        self.sha_manager = SHAFileManager(
            sha_name=github_api.sha_name, sha_url=github_api.sha_url
        )
        self.hash_manager = HashManager(hash_type)

    def handle_verification_error(
        self, appimage_hash: str = None, expected_hash: str = None
    ):
        """Handle verification errors with user prompts."""
        print(f"\033[41;30mError verifying {self.github_api.appimage_name}.\033[0m")
        logging.error(f"Verification failed for {self.github_api.appimage_name}")

        if appimage_hash and expected_hash:
            print(f"AppImage Hash: {appimage_hash}")
            print(f"Expected Hash: {expected_hash}")

        if (
            input("Do you want to delete the downloaded AppImage? (y/n): ")
            .strip()
            .lower()
            == "y"
        ):
            os.remove(self.appimage_path)
            print(f"Deleted {self.github_api.appimage_name}")

        if input("Do you want to delete the SHA file? (y/n): ").strip().lower() == "y":
            os.remove(self.github_api.sha_name)
            print(f"Deleted {self.github_api.sha_name}")

        if (
            input("Do you want to continue without verification? (y/n): ")
            .strip()
            .lower()
            == "y"
        ):
            self._make_executable()
        else:
            print("Exiting...")
            sys.exit()

    def handle_connection_error(self):
        """Handle connection errors when fetching the SHA file."""
        print(f"\033[41;30mError connecting to {self.github_api.sha_url}.\033[0m")
        logging.error(f"Connection error while accessing {self.github_api.sha_url}")
        sys.exit()

    def verify_appimage(self) -> bool:
        """Verify the AppImage using the SHA file from GitHub."""
        try:
            # Step 1: Download the SHA file
            self.sha_manager.download_sha_file()

            # Step 2: Parse the SHA file to get the expected hash
            expected_hash = self._get_expected_hash()

            # Step 3: Calculate the AppImage hash
            appimage_hash = self.hash_manager.calculate_hash(self.appimage_path)

            # Step 4: Compare the hashes
            if self.hash_manager.compare_hashes(appimage_hash, expected_hash):
                print(
                    f"\033[42m{self.github_api.appimage_name} verified successfully.\033[0m"
                )
                return True
            else:
                self.handle_verification_error(appimage_hash, expected_hash)
                return False

        except requests.RequestException as e:
            logging.error(f"Network error: {e}")
            self.handle_connection_error()
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            self.handle_verification_error()
            return False

    def _get_expected_hash(self) -> str:
        """Parse the SHA file and extract the expected hash."""
        sha_data = self.sha_manager.parse_sha_file()

        if isinstance(sha_data, dict):
            expected_hash = sha_data.get(self.hash_manager.hash_type)
            if isinstance(expected_hash, str):
                return self.hash_manager.decode_base64_hash(expected_hash)
        elif isinstance(sha_data, str):
            return sha_data

        raise ValueError(f"Hash not found in {self.github_api.sha_name}")
