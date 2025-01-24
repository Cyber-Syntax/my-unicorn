import os
import requests
import yaml
import hashlib
import base64
import logging
import gettext
from pathlib import Path

_ = gettext.gettext


# TODO: Not need to acces by github api, just load from config
# Config already going to use githubapi class to save them, I don't need to make it two request
# class HashManager:
#     """Handles hash generation and comparison."""
#
#     def __init__(self, hash_type="sha256"):
#         self.hash_type = hash_type
#
#     def calculate_hash(self, file_path):
#         """Calculate the hash of a file."""
#         with open(file_path, "rb") as file:
#             return hashlib.new(self.hash_type, file.read()).hexdigest()
#
#     def compare_hashes(self, hash1, hash2):
#         """Compare two hash values."""
#         return hash1 == hash2
#
#     @staticmethod
#     def decode_base64_hash(encoded_hash):
#         """Decode a base64-encoded hash."""
#         return base64.b64decode(encoded_hash).hex()
#


# class SHAFileManager:
#     """Handles downloading and parsing SHA files."""
#
#     def __init__(self, sha_name, sha_url):
#         self.sha_name = sha_name
#         self.sha_url = sha_url
#


class VerificationManager:
    """Coordinates the verification of downloaded AppImages."""

    # def __init__(self, hash_manager: HashManager, sha_manager: SHAFileManager):
    #     self.sha_manager = sha_manager
    #     self.hash_manager = hash_manager

    def __init__(
        self,
        sha_name: str = None,
        sha_url: str = None,
        appimage_name: str = None,
        hash_type: str = "sha256",
    ):
        self.sha_name = sha_name
        self.sha_url = sha_url
        self.appimage_name = appimage_name
        self.hash_type = hash_type

    def verify_appimage(self) -> bool:
        """Verify the AppImage using the SHA file from GitHub."""

        try:
            self.download_sha_file()
            self.parse_sha_file()
            return True
        except requests.RequestException as e:
            logging.error(f"Network error: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return False

    def download_sha_file(self):
        """Download the SHA file."""
        if not os.path.exists(self.sha_name):
            response = requests.get(self.sha_url, timeout=5)
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

    # TODO: separate functions later
    def _parse_yaml_sha(self):
        """Parse SHA hash from a YAML file."""
        # parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha = yaml.safe_load(file)

        # get the sha from the sha file
        sha = sha[self.hash_type]
        decoded_hash = base64.b64decode(sha).hex()

        # find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_sha = hashlib.new(self.hash_type, file.read()).hexdigest()

        # compare the two hashes
        if appimage_sha == decoded_hash:
            print(
                _("\033[42m{appimage_name} verified.\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("************************************")
            print(_("--------------------- HASHES ----------------------"))
            print(_("AppImage Hash: {appimage_sha}").format(appimage_sha=appimage_sha))
            print(_("Parsed Hash: {decoded_hash}").format(decoded_hash=decoded_hash))
            print("----------------------------------------------------")
            return True
        else:
            return False

    def _parse_text_sha(self):
        """Parse SHA hash from a plain text file."""
        print("parsing sha")
        # Parse the sha file
        with open(self.sha_name, "r", encoding="utf-8") as file:
            for line in file:
                if self.appimage_name in line:
                    decoded_hash = line.split()[0]
                    break

        # Find appimage sha
        with open(self.appimage_name, "rb") as file:
            appimage_hash = hashlib.new(self.hash_type, file.read()).hexdigest()

        # Compare the two hashes
        if appimage_hash == decoded_hash:
            print(
                _("\033[42m{appimage_name} verified.\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print("************************************")
            print(_("--------------------- HASHES ----------------------"))
            print(
                _("AppImage Hash: {appimage_hash}").format(appimage_hash=appimage_hash)
            )
            print(_("Parsed Hash: {decoded_hash}").format(decoded_hash=decoded_hash))
            print("----------------------------------------------------")
            return True
        else:
            return False
