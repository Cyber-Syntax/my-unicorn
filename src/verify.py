import os
import requests
import yaml
import hashlib
import base64
import logging
import gettext
from typing import Optional

_ = gettext.gettext

# Constants for color formatting
COLOR_SUCCESS = "\033[92m"
COLOR_FAIL = "\033[41m"
COLOR_RESET = "\033[0m"


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
        self.hash_type = hash_type.lower()
        self._validate_hash_type()

    def _validate_hash_type(self):
        """Ensure the hash type is supported"""
        if self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Unsupported hash type: {self.hash_type}")

    def verify_appimage(self) -> bool:
        """Verify the AppImage using the SHA file with proper error handling."""
        try:
            if not self.sha_url or not self.sha_name:
                raise ValueError("Missing SHA file information for verification")

            self._download_sha_file()
            return self._parse_sha_file()

        except (requests.RequestException, IOError) as e:
            logging.error(f"Verification failed: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Unexpected error during verification: {str(e)}")
            return False

    def _download_sha_file(self):
        """Download the SHA file with retries and proper cleanup."""
        if os.path.exists(self.sha_name):
            try:
                os.remove(self.sha_name)
                logging.info(f"Removed existing {self.sha_name}")
            except OSError as e:
                raise IOError(f"Failed to remove existing SHA file: {str(e)}")

        try:
            response = requests.get(self.sha_url, timeout=10)
            response.raise_for_status()
            with open(self.sha_name, "w", encoding="utf-8") as f:
                f.write(response.text)
            logging.info(f"Successfully downloaded {self.sha_name}")
        except requests.RequestException as e:
            raise IOError(f"Failed to download SHA file: {str(e)}")

    def _parse_sha_file(self) -> bool:
        """Dispatch to appropriate SHA parsing method based on file extension."""
        ext = os.path.splitext(self.sha_name)[1].lower()
        parser = {
            ".yml": self._parse_yaml_sha,
            ".yaml": self._parse_yaml_sha,
            ".sha256": self._parse_simple_sha,
            ".sha512": self._parse_simple_sha,
        }.get(ext, self._parse_text_sha)

        return parser()

    def _parse_yaml_sha(self) -> bool:
        """Parse SHA hash from YAML file with error handling."""
        try:
            with open(self.sha_name, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError("Empty YAML file")

            encoded_hash = data.get(self.hash_type)
            if not encoded_hash:
                raise ValueError(f"No {self.hash_type} hash found in YAML")

            decoded_hash = base64.b64decode(encoded_hash).hex()
            return self._compare_hashes(decoded_hash)

        except (yaml.YAMLError, ValueError, TypeError) as e:
            raise IOError(f"YAML parsing failed: {str(e)}")

    def _parse_simple_sha(self) -> bool:
        """Parse SHA hash from simple hash file."""
        with open(self.sha_name, "r", encoding="utf-8") as f:
            content = f.read().strip()

        if not content:
            raise ValueError("Empty SHA file")

        return self._compare_hashes(content.split()[0])

    def _parse_text_sha(self) -> bool:
        """Parse SHA hash from text file with pattern matching."""
        target_name = os.path.basename(self.appimage_name).lower()

        with open(self.sha_name, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 2:
                    continue

                filename = parts[1].lower()
                if filename == target_name:
                    return self._compare_hashes(parts[0])

        raise ValueError(f"No hash found for {self.appimage_name} in SHA file")

    def _compare_hashes(self, expected_hash: str) -> bool:
        """Compare hashes using memory-efficient chunked reading."""
        hash_func = hashlib.new(self.hash_type)

        with open(self.appimage_name, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_func.update(chunk)

        actual_hash = hash_func.hexdigest()
        self._log_comparison(actual_hash, expected_hash)
        return actual_hash == expected_hash

    def _log_comparison(self, actual: str, expected: str):
        """Format and log hash comparison results."""
        status = _("VERIFIED") if actual == expected else _("VERIFICATION FAILED")
        color = COLOR_SUCCESS if actual == expected else COLOR_FAIL

        log_lines = [
            f"{color}{status}{COLOR_RESET}",
            _("File: {name}").format(name=self.appimage_name),
            _("Algorithm: {type}").format(type=self.hash_type.upper()),
            _("Expected: {hash}").format(hash=expected),
            _("Actual:   {hash}").format(hash=actual),
            "----------------------------------------",
        ]

        print("\n".join(log_lines))
        logging.info("\n".join(log_lines))
