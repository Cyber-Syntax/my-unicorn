import base64
import gettext
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import requests
import yaml

_ = gettext.gettext

# Constants for status indicators
STATUS_SUCCESS = "✓ "  # Unicode check mark
STATUS_FAIL = "✗ "  # Unicode cross mark

# Supported hash types
SUPPORTED_HASH_TYPES = ["sha256", "sha512", "no_hash"]


@dataclass
class VerificationManager:
    """Coordinates the verification of downloaded AppImages.

    The VerificationManager performs hash verification on downloaded AppImage files
    before they are moved to their final installation location.
    """

    sha_name: Optional[str] = None
    sha_url: Optional[str] = None
    appimage_name: Optional[str] = None  # Original filename from GitHub
    hash_type: str = "sha256"
    appimage_path: Optional[str] = None  # Full path to the AppImage file for verification

    def __post_init__(self) -> None:
        """Initialize and validate the verification manager."""
        # Initialize appimage_path to appimage_name in downloads directory if not set
        if self.appimage_path is None and self.appimage_name is not None:
            # Always verify files from the downloads directory
            from src.download import DownloadManager

            downloads_dir = DownloadManager.get_downloads_dir()
            self.appimage_path = str(Path(downloads_dir) / self.appimage_name)

        # Convert hash_type to lowercase for consistent comparisons
        if self.hash_type:
            self.hash_type = self.hash_type.lower()

        # Validate the hash type
        self._validate_hash_type()

    def set_appimage_path(self, full_path: str) -> None:
        """Set the full path to the AppImage file for verification.

        Args:
            full_path: The complete path to the AppImage file

        """
        self.appimage_path = full_path
        logging.info(f"Set AppImage path for verification: {full_path}")

    def _validate_hash_type(self) -> None:
        """Ensure the hash type is supported"""
        if self.hash_type not in SUPPORTED_HASH_TYPES:
            raise ValueError(
                f"Unsupported hash type: {self.hash_type}. "
                f"Supported types are: {', '.join(SUPPORTED_HASH_TYPES)}"
            )

        if self.hash_type != "no_hash" and self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.hash_type} not available in this system")

    def verify_appimage(self, cleanup_on_failure: bool = False) -> bool:
        """Verify the AppImage using the SHA file with proper error handling and fallbacks.

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

        except (OSError, requests.RequestException) as e:
            logging.error(f"Verification failed: {e!s}")
            if cleanup_on_failure:
                self._cleanup_failed_file(self.appimage_path)
            return False
        except Exception as e:
            logging.error(f"Unexpected error during verification: {e!s}")
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
                raise OSError(f"Failed to remove existing SHA file: {e!s}")

        try:
            response = requests.get(self.sha_url, timeout=10)
            response.raise_for_status()
            with open(self.sha_name, "w", encoding="utf-8") as f:
                f.write(response.text)
            logging.info(f"Successfully downloaded {self.sha_name}")
        except requests.RequestException as e:
            raise OSError(f"Failed to download SHA file: {e!s}")
        except Exception as e:
            raise OSError(f"Failed to write SHA file: {e!s}")

    def _parse_sha_file(self) -> bool:
        """Dispatch to appropriate SHA parsing method based on file extension."""
        if self.hash_type == "no_hash":
            logging.info("Skipping hash verification as requested")
            return True

        if not os.path.exists(self.sha_name):
            raise OSError(f"SHA file not found: {self.sha_name}")

        ext = os.path.splitext(self.sha_name)[1].lower()
        parser = {
            ".yml": self._parse_yaml_sha,
            ".yaml": self._parse_yaml_sha,
            ".sha256": self._parse_simple_sha,
            ".sha512": self._parse_simple_sha,
        }.get(ext, self._parse_text_sha)

        try:
            # Try the standard parser first
            return parser()
        except ValueError as e:
            # If standard parsing fails with "No valid hash found", try the path-based parser
            if "No valid hash found" in str(e):
                logging.info("Standard hash parsing failed, trying path-based fallback...")
                return self._parse_path_sha()
            # Re-raise other value errors
            raise

    def _parse_yaml_sha(self) -> bool:
        """Parse SHA hash from YAML file with error handling."""
        try:
            with open(self.sha_name, encoding="utf-8") as f:
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
                raise ValueError(f"Failed to decode hash: {e!s}")

        except (yaml.YAMLError, ValueError, TypeError) as e:
            raise OSError(f"YAML parsing failed: {e!s}")

    def _parse_simple_sha(self) -> bool:
        """Parse SHA hash from simple hash file."""
        try:
            with open(self.sha_name, encoding="utf-8") as f:
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

        except OSError as e:
            raise OSError(f"Failed to read SHA file: {e!s}")

    def _parse_text_sha(self) -> bool:
        """Parse SHA hash from text file with pattern matching.

        This method handles multiple common formats:
        - <hash> <filename> (most common format)
        - <filename> <hash> (alternate format)
        - Entries prefixed with indicators like '*' or other markers
        - GitHub-style checksums with headers

        Args:
            None

        Returns:
            bool: True if verification passes, False otherwise

        Raises:
            ValueError: If no valid hash is found
            IOError: If file can't be read

        """
        target_name = os.path.basename(self.appimage_name).lower()

        try:
            with open(self.sha_name, encoding="utf-8") as f:
                content = f.read()

            # Try GitHub-style format with headers first
            # Look for headers like "## SHA256 Checksums" followed by hash entries
            sha_section_match = re.search(r"##\s+SHA2?56.+", content, re.MULTILINE | re.IGNORECASE)
            if sha_section_match:
                # Look for pattern like "hash *filename" or "hash filename"
                hash_pattern = rf"([0-9a-f]{{{64 if self.hash_type == 'sha256' else 128}}})\s+\*?{re.escape(target_name)}"
                hash_match = re.search(hash_pattern, content, re.MULTILINE | re.IGNORECASE)
                if hash_match:
                    hash_value = hash_match.group(1).lower()
                    logging.info(f"Found valid hash for {target_name} in GitHub-style SHA file")
                    return self._compare_hashes(hash_value)

            # Process the file line by line for common formats
            for line in content.splitlines():
                line = line.strip()
                if not line or len(line.split()) < 2:
                    continue

                # Normalize the line by removing common markers and extra spaces
                normalized_line = line.replace("*", " ").replace("  ", " ")
                parts = normalized_line.strip().split()

                # Skip lines that are too short after normalization
                if len(parts) < 2:
                    continue

                # Try multiple formats
                hash_value = None

                # Format: <hash> <filename> (most common)
                if len(parts[0]) in (64, 128) and parts[1].lower() == target_name:
                    hash_value = parts[0]
                # Format: <filename> <hash> (alternate format)
                elif parts[0].lower() == target_name and len(parts[1]) in (64, 128):
                    hash_value = parts[1]
                # Look for target filename anywhere in the line with a valid hash
                else:
                    # Find any hex string of appropriate length (hash) in the line
                    for part in parts:
                        if len(part) in (64, 128) and re.match(r"^[0-9a-f]+$", part, re.IGNORECASE):
                            # If we found a hash, check if the target filename is elsewhere on the line
                            if target_name in line.lower():
                                hash_value = part
                                break

                if hash_value:
                    # Validate hash format
                    expected_length = 64 if self.hash_type == "sha256" else 128
                    if len(hash_value) != expected_length:
                        logging.warning(
                            f"Hash for {target_name} has wrong length: {len(hash_value)}, "
                            f"expected {expected_length}"
                        )
                        continue

                    if not re.match(r"^[0-9a-f]+$", hash_value, re.IGNORECASE):
                        logging.warning(f"Invalid hex characters in hash: {hash_value}")
                        continue

                    logging.info(f"Found valid hash for {target_name} in SHA file")
                    return self._compare_hashes(hash_value.lower())

            raise ValueError(f"No valid hash found for {self.appimage_name} in SHA file")

        except OSError as e:
            raise OSError(f"Failed to read SHA file: {e!s}")
        except Exception as e:
            logging.error(f"Error parsing SHA file: {e!s}")
            raise

    def _parse_path_sha(self) -> bool:
        """Parse SHA hash from text file that contains relative paths.

        This handles formats like:
        <hash>  ./path/to/filename.AppImage

        Returns:
            bool: True if verification passes, False otherwise

        """
        target_filename = os.path.basename(self.appimage_name).lower()

        try:
            with open(self.sha_name, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue

                    # The hash is typically the first element, path is the second
                    hash_value = parts[0]
                    file_path = parts[1]

                    # Extract filename from the path and compare with target
                    path_filename = os.path.basename(file_path).lower()

                    if path_filename == target_filename:
                        # Validate hash format
                        expected_length = 64 if self.hash_type == "sha256" else 128
                        if len(hash_value) != expected_length:
                            logging.warning(
                                f"Hash for {path_filename} has wrong length: {len(hash_value)}, "
                                f"expected {expected_length}"
                            )
                            continue

                        if not re.match(r"^[0-9a-f]+$", hash_value.lower()):
                            logging.warning(f"Invalid hex characters in hash: {hash_value}")
                            continue

                        logging.info(f"Found valid hash for {path_filename} in path-based SHA file")
                        return self._compare_hashes(hash_value.lower())

            raise ValueError(f"No valid hash found for {target_filename} in path-based SHA file")

        except OSError as e:
            raise OSError(f"Failed to read SHA file: {e!s}")

    def _compare_hashes(self, expected_hash: str) -> bool:
        """Compare hashes using memory-efficient chunked reading."""
        # Always use appimage_path for file operations
        file_to_verify = self.appimage_path

        if not os.path.exists(file_to_verify):
            raise OSError(f"AppImage file not found: {file_to_verify}")

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

        except OSError as e:
            raise OSError(f"Failed to read AppImage file: {e!s}")
        except Exception as e:
            raise ValueError(f"Hash calculation failed: {e!s}")

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
            logging.warning(f"Failed to remove verification file: {e!s}")
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
        """Remove a file that failed verification after asking for user confirmation.

        Args:
            filepath: Path to the file that failed verification

        Returns:
            bool: True if cleanup succeeded or was declined, False on error

        """
        try:
            if not os.path.exists(filepath):
                logging.info(f"File not found, nothing to clean up: {filepath}")
                return True

            # Ask user for confirmation before removing the file
            confirmation = self._get_user_confirmation(filepath)
            if not confirmation:
                logging.info(
                    f"User chose to keep the file despite verification failure: {filepath}"
                )
                print(f"File kept: {filepath}")
                print(
                    "Note: You may want to investigate this verification failure or report it as an issue."
                )
                return True

            os.remove(filepath)
            logging.info(f"Cleaned up failed verification file: {filepath}")
            print(f"Removed failed file: {filepath}")
            return True

        except Exception as e:
            logging.error(f"Failed to remove file after verification failure: {e!s}")
            print(f"Warning: Could not remove failed file: {filepath}")
            return False

    def _get_user_confirmation(self, filepath: str) -> bool:
        """Ask the user for confirmation before removing a file that failed verification.

        Args:
            filepath: Path to the file that failed verification

        Returns:
            bool: True if user confirms removal, False otherwise

        """
        filename = os.path.basename(filepath)

        print("\n" + "=" * 70)
        print(f"WARNING: The file '{filename}' failed verification.")
        print("This could indicate tampering or download corruption.")
        print("You have two options:")
        print("  1. Remove the file (recommended for security)")
        print("  2. Keep the file (if you want to manually verify or report an issue)")
        print("=" * 70)

        while True:
            try:
                response = input("\nRemove the file? [y/N]: ").strip().lower()
                if response in ("y", "yes"):
                    return True
                if response in ("", "n", "no"):
                    return False
                print("Please answer 'y' for yes or 'n' for no.")
            except KeyboardInterrupt:
                print("\nOperation cancelled by user.")
                return False
