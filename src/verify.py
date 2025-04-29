import base64
import gettext
import hashlib
import logging
import os
import re
import requests
import yaml
from pathlib import Path
from typing import Optional

_ = gettext.gettext

# Constants for status indicators
STATUS_SUCCESS = "✓ "  # Unicode check mark
STATUS_FAIL = "✗ "  # Unicode cross mark

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
        self.appimage_name = appimage_name  # File name without path
        self.appimage_path = appimage_name  # Full path to the AppImage file, initialized to same value as appimage_name
        self.hash_type = hash_type.lower()
        self._validate_hash_type()

    def set_appimage_path(self, full_path: str) -> None:
        """
        Set the full path to the AppImage file for verification.

        Args:
            full_path: The complete path to the AppImage file
        """
        self.appimage_path = full_path
        logging.info(f"Set AppImage path for verification: {full_path}")

    def _validate_hash_type(self):
        """Ensure the hash type is supported"""
        if self.hash_type not in SUPPORTED_HASH_TYPES:
            raise ValueError(
                f"Unsupported hash type: {self.hash_type}. "
                f"Supported types are: {', '.join(SUPPORTED_HASH_TYPES)}"
            )

        if self.hash_type != "no_hash" and self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.hash_type} not available in this system")

    def verify_appimage(self, cleanup_on_failure: bool = False) -> bool:
        """
        Verify the AppImage using the SHA file with proper error handling and fallbacks.

        Args:
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            bool: True if verification passed or skipped due to fallback, False otherwise
        """
        try:
            # Skip verification if hash_type is set to no_hash or no SHA file name available
            if self.hash_type == "no_hash" or not self.sha_name:
                logging.info("Verification skipped - no hash file information available")
                print("Note: Verification skipped - no hash file provided")
                return True

            # Use appimage_path for existence check if available, otherwise fall back to appimage_name
            check_path = self.appimage_path

            if not check_path or not os.path.exists(check_path):
                logging.error(f"AppImage file not found: {check_path}")
                return False

            # FALLBACK CASE: If sha_name matches appimage_name, this indicates
            # our API fallback was triggered where no SHA file was found
            if self.sha_name == self.appimage_name:
                logging.info("Verification fallback: No SHA file available for this release")
                print("Note: Verification skipped - no hash file provided by the developer")
                logging.info(f"Proceeding with unverified AppImage: {self.appimage_name}")
                return True

            # Download SHA file only if URL is provided and file doesn't exist
            if self.sha_url and not os.path.exists(self.sha_name):
                self._download_sha_file()

            # Check if the SHA file exists before proceeding
            if not os.path.exists(self.sha_name):
                logging.error(f"SHA file not found: {self.sha_name}")
                return False

            is_valid = self._parse_sha_file()

            if not is_valid and cleanup_on_failure:
                self._cleanup_failed_file(check_path)  # Use the same path for cleanup

            return is_valid

        except (requests.RequestException, IOError) as e:
            logging.error(f"Verification failed: {str(e)}")
            if cleanup_on_failure:
                self._cleanup_failed_file(self.appimage_path)
            return False
        except Exception as e:
            logging.error(f"Unexpected error during verification: {str(e)}")
            if cleanup_on_failure:
                self._cleanup_failed_file(self.appimage_path)
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

                    # Check for both standard patterns:
                    # 1. HASH FILENAME format (common for sha256sum output)
                    # 2. FILENAME HASH format (used by some projects)
                    hash_value = None
                    if parts[1].lower() == target_name:
                        hash_value = parts[0]
                    elif len(parts) > 2 and parts[0].lower() == target_name:
                        hash_value = parts[1]

                    if hash_value:
                        # Validate hash format with proper hex check
                        expected_length = 64 if self.hash_type == "sha256" else 128
                        if len(hash_value) != expected_length:
                            logging.warning(
                                f"Hash for {target_name} has wrong length: {len(hash_value)}, "
                                f"expected {expected_length}"
                            )
                            continue

                        if not re.match(r"^[0-9a-f]+$", hash_value.lower()):
                            logging.warning(f"Invalid hex characters in hash: {hash_value}")
                            continue

                        logging.info(f"Found valid hash for {target_name} in SHA file")
                        return self._compare_hashes(hash_value.lower())

            raise ValueError(f"No valid hash found for {self.appimage_name} in SHA file")

        except IOError as e:
            raise IOError(f"Failed to read SHA file: {str(e)}")

    def _compare_hashes(self, expected_hash: str) -> bool:
        """Compare hashes using memory-efficient chunked reading."""
        # Always use appimage_path for file operations
        file_to_verify = self.appimage_path

        if not os.path.exists(file_to_verify):
            raise IOError(f"AppImage file not found: {file_to_verify}")

        try:
            hash_func = hashlib.new(self.hash_type)

            # Use larger chunk size for better performance with large files
            chunk_size = 65536  # 64KB chunks

            with open(file_to_verify, "rb") as f:
                for chunk in iter(lambda: f.read(chunk_size), b""):
                    hash_func.update(chunk)

            actual_hash = hash_func.hexdigest().lower()  # Always use lowercase for comparison
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
        """Format and log hash comparison results.

        Successful verifications are only logged, not printed to console.
        Failed verifications are both logged and printed to console.
        """
        is_verified = actual == expected
        status = STATUS_SUCCESS if is_verified else STATUS_FAIL

        log_lines = [
            f"{status}{_('VERIFIED') if is_verified else _('VERIFICATION FAILED')}",
            _("File: {name}").format(name=self.appimage_name),
            _("Algorithm: {type}").format(type=self.hash_type.upper()),
            _("Expected: {hash}").format(hash=expected),
            _("Actual:   {hash}").format(hash=actual),
            "----------------------------------------",
        ]

        # Always log the verification results
        logging.info("\n".join(log_lines))

        # Only print to console if verification failed
        if not is_verified:
            print("\n".join(log_lines))

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
