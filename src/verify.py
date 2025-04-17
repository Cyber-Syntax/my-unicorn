import base64
import gettext
import hashlib
import logging
import os
import re
import requests
import yaml

_ = gettext.gettext

# Constants for color formatting
COLOR_SUCCESS = "\033[92m"
COLOR_FAIL = "\033[41m"
COLOR_RESET = "\033[0m"

# Supported hash types
SUPPORTED_HASH_TYPES = ["sha256", "sha512", "no_hash"]


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
        if self.hash_type not in SUPPORTED_HASH_TYPES:
            raise ValueError(
                f"Unsupported hash type: {self.hash_type}. "
                f"Supported types are: {', '.join(SUPPORTED_HASH_TYPES)}"
            )

        if self.hash_type != "no_hash" and self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.hash_type} not available in this system")

    def _handle_sha_fallback(self, assets=None):
        """
        Original fallback logic with improved prompts.

        Args:
            assets: List of release assets from GitHub API
        """
        logging.warning("Could not find SHA file automatically")
        print("Could not find SHA file automatically")
        print("1. Enter filename manually")
        print("2. Skip verification")
        choice = input("Your choice (1-2): ")

        if choice == "1":
            self.sha_name = input("Enter exact SHA filename: ")
            if assets:
                for asset in assets:
                    if asset["name"] == self.sha_name:
                        self.sha_url = asset["browser_download_url"]
                        # Set hash type based on filename
                        if "sha256" in self.sha_name.lower():
                            self.hash_type = "sha256"
                        elif "sha512" in self.sha_name.lower():
                            self.hash_type = "sha512"
                        return
                raise ValueError(f"SHA file {self.sha_name} not found")
            else:
                logging.warning("No assets provided, can't verify SHA file existence")
                self.sha_url = None
        else:
            self.sha_name = "no_sha_file"
            self.hash_type = "no_hash"
            logging.info("User chose to skip SHA verification")

    def verify_appimage(self, cleanup_on_failure: bool = False) -> bool:
        """
        Verify the AppImage using the SHA file with proper error handling and fallbacks.

        Args:
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            bool: True if verification passed or skipped due to fallback, False otherwise
        """
        try:
            # Skip verification if hash_type is set to no_hash or no SHA info available
            if self.hash_type == "no_hash" or not self.sha_name or not self.sha_url:
                logging.info("Verification skipped - no hash file information available")
                print("Note: Verification skipped - no hash file provided")
                return True

            if not self.appimage_name or not os.path.exists(self.appimage_name):
                logging.error(f"AppImage file not found: {self.appimage_name}")
                return False

            # FALLBACK CASE: If sha_name matches appimage_name, this indicates
            # our API fallback was triggered where no SHA file was found
            if self.sha_name == self.appimage_name:
                logging.info("Verification fallback: No SHA file available for this release")
                print("Note: Verification skipped - no hash file provided by the developer")
                logging.info(f"Proceeding with unverified AppImage: {self.appimage_name}")
                return True

            self._download_sha_file()
            is_valid = self._parse_sha_file()

            if not is_valid and cleanup_on_failure:
                self._cleanup_failed_file(self.appimage_name)

            return is_valid

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
        except Exception as e:
            raise IOError(f"Failed to write SHA file: {str(e)}")

    def _parse_sha_file(self) -> bool:
        """Dispatch to appropriate SHA parsing method based on file extension."""
        if self.hash_type == "no_hash":
            logging.info("Skipping hash verification as requested")
            return True

        if not os.path.exists(self.sha_name):
            raise IOError(f"SHA file not found: {self.sha_name}")

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

            try:
                decoded_hash = base64.b64decode(encoded_hash).hex()
                return self._compare_hashes(decoded_hash)
            except Exception as e:
                raise ValueError(f"Failed to decode hash: {str(e)}")

        except (yaml.YAMLError, ValueError, TypeError) as e:
            raise IOError(f"YAML parsing failed: {str(e)}")

    def _parse_simple_sha(self) -> bool:
        """Parse SHA hash from simple hash file."""
        try:
            with open(self.sha_name, "r", encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                raise ValueError("Empty SHA file")

            hash_value = content.split()[0]
            # Validate hash format
            expected_length = 64 if self.hash_type == "sha256" else 128
            if len(hash_value) != expected_length or not all(
                c in "0123456789abcdefABCDEF" for c in hash_value
            ):
                raise ValueError(f"Invalid {self.hash_type} hash format")

            return self._compare_hashes(hash_value)

        except IOError as e:
            raise IOError(f"Failed to read SHA file: {str(e)}")

    def _parse_text_sha(self) -> bool:
        """Parse SHA hash from text file with pattern matching."""
        target_name = os.path.basename(self.appimage_name).lower()

        try:
            with open(self.sha_name, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue

                    filename = parts[1].lower()
                    if filename == target_name:
                        hash_value = parts[0]
                        # Validate hash format
                        expected_length = 64 if self.hash_type == "sha256" else 128
                        if len(hash_value) != expected_length or not all(
                            c in "0123456789abcdefABCDEF" for c in hash_value
                        ):
                            raise ValueError(f"Invalid {self.hash_type} hash format")
                        return self._compare_hashes(hash_value)

            raise ValueError(f"No hash found for {self.appimage_name} in SHA file")

        except IOError as e:
            raise IOError(f"Failed to read SHA file: {str(e)}")

    def _compare_hashes(self, expected_hash: str) -> bool:
        """Compare hashes using memory-efficient chunked reading."""
        if not os.path.exists(self.appimage_name):
            raise IOError(f"AppImage file not found: {self.appimage_name}")

        try:
            hash_func = hashlib.new(self.hash_type)

            with open(self.appimage_name, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_func.update(chunk)

            actual_hash = hash_func.hexdigest()
            self._log_comparison(actual_hash, expected_hash)

            # Delete the SHA file after verification
            self._cleanup_verification_file()

            return actual_hash == expected_hash

        except IOError as e:
            raise IOError(f"Failed to read AppImage file: {str(e)}")
        except Exception as e:
            raise ValueError(f"Hash calculation failed: {str(e)}")

    def _cleanup_verification_file(self) -> bool:
        """Remove SHA file after verification to keep the system clean.

        Returns:
            bool: True if cleanup succeeded or file didn't exist, False otherwise
        """
        if not self.sha_name or not os.path.exists(self.sha_name):
            logging.debug(f"No SHA file to clean up: {self.sha_name}")
            return True

        try:
            os.remove(self.sha_name)
            logging.info(f"Removed verification file: {self.sha_name}")
            return True
        except OSError as e:
            logging.warning(f"Failed to remove verification file: {str(e)}")
            return False

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

    def _cleanup_failed_file(self, filepath: str) -> bool:
        """Remove a file that failed verification to prevent future update issues."""
        try:
            if not os.path.exists(filepath):
                logging.info(f"File not found, nothing to clean up: {filepath}")
                return True

            os.remove(filepath)
            logging.info(f"Cleaned up failed verification file: {filepath}")
            print(f"Removed failed file: {filepath}")
            return True

        except Exception as e:
            logging.error(f"Failed to remove file after verification failure: {str(e)}")
            print(f"Warning: Could not remove failed file: {filepath}")
            return False
