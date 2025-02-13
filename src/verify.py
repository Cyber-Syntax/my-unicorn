import os
import requests
import yaml
import hashlib
import base64
import logging
import gettext

_ = gettext.gettext


class VerificationManager:
    """Coordinates the verification of downloaded AppImages."""

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
        """Verify the AppImage using the SHA file."""
        try:
            self.download_sha_file()
            is_valid = self.parse_sha_file()
            return is_valid
        except requests.RequestException as e:
            logging.error(f"Network error: {e}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            return False

    def download_sha_file(self):
        """Download the SHA file, overwriting any existing file."""
        # If the file exists, remove it first.
        if os.path.exists(self.sha_name):
            try:
                os.remove(self.sha_name)
                print(f"Removed existing {self.sha_name}.")
            except OSError as error:
                raise OSError(f"Error removing {self.sha_name}: {error}")

        try:
            # Proceed to download the file.
            response = requests.get(self.sha_url, timeout=5)
            if response.status_code == 200:
                with open(self.sha_name, "w", encoding="utf-8") as file:
                    file.write(response.text)
                print(f"\033[42mDownloaded {self.sha_name}\033[0m")
            else:
                raise ConnectionError(f"Failed to download {self.sha_url}.")
        except Exception as e:
            print(f"Error while installing sha file: {e}")

    def parse_sha_file(self):
        """Parse the SHA file and extract hashes."""
        if self.sha_name.endswith((".yml", ".yaml")):
            return self._parse_yaml_sha()
        elif self.sha_name.endswith((".sha512", ".sha256")):
            return self._parse_simple_sha()
        else:
            return self._parse_text_sha()

    def _parse_yaml_sha(self):
        """Parse SHA hash from a YAML file."""
        print("parsing hash from yaml file")
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha_data = yaml.safe_load(file)

        sha_value = sha_data.get(self.hash_type)
        if not sha_value:
            raise ValueError(f"No {self.hash_type} hash found in the YAML file.")

        decoded_hash = base64.b64decode(sha_value).hex()

        return self._compare_hashes(decoded_hash)

    def _parse_simple_sha(self):
        """Parse SHA hash from a simple .sha512 or .sha256 file."""
        with open(self.sha_name, "r", encoding="utf-8") as file:
            sha_line = file.readline().strip()

        return self._compare_hashes(sha_line)

    def _parse_text_sha(self):
        """Parse SHA hash from a plain text file."""
        print("parsing hash from sha file")
        with open(self.sha_name, "r", encoding="utf-8") as file:
            for line in file:
                if self.appimage_name in line:
                    sha_value = line.split()[0]
                    return self._compare_hashes(sha_value)

        raise ValueError(
            f"No matching hash found for {self.appimage_name} in the SHA file."
        )

    def _compare_hashes(self, expected_hash: str) -> bool:
        """Compare the expected hash with the AppImage's hash."""
        with open(self.appimage_name, "rb") as file:
            appimage_hash = hashlib.new(self.hash_type, file.read()).hexdigest()

        if appimage_hash == expected_hash:
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
            print(
                _("Expected Hash: {expected_hash}").format(expected_hash=expected_hash)
            )
            print("----------------------------------------------------")
            return True
        else:
            print(
                _("\033[41m{appimage_name} verification failed.\033[0m").format(
                    appimage_name=self.appimage_name
                )
            )
            print(
                _("AppImage Hash: {appimage_hash}").format(appimage_hash=appimage_hash)
            )
            print(
                _("Expected Hash: {expected_hash}").format(expected_hash=expected_hash)
            )
            return False
