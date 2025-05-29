import base64
import gettext
import hashlib
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import requests
import yaml

_ = gettext.gettext

# Constants for status indicators
STATUS_SUCCESS = "✓ "  # Unicode check mark
STATUS_FAIL = "✗ "  # Unicode cross mark

# Supported hash types
SUPPORTED_HASH_TYPES = [
    "sha256",
    "sha512",
    "no_hash",
    "extracted_checksum",
]  # Removed "from_release_description"


@dataclass
class VerificationManager:
    """Coordinates the verification of downloaded AppImages.

    The VerificationManager performs hash verification on downloaded AppImage files
    before they are moved to their final installation location.
    """

    sha_name: str | None = None
    sha_url: str | None = None
    appimage_name: str | None = None  # Original filename from GitHub
    hash_type: str = "sha256"
    appimage_path: str | None = None  # Full path to the AppImage file for verification
    direct_expected_hash: str | None = None  # For hashes extracted from release body

    def __post_init__(self) -> None:
        """Initialize and validate the verification manager."""
        # Initialize appimage_path to appimage_name in downloads directory if not set
        if self.appimage_path is None and self.appimage_name is not None:
            # Always verify files from the downloads directory
            from src.global_config import GlobalConfigManager

            downloads_dir = GlobalConfigManager().expanded_app_download_path
            self.appimage_path = str(Path(downloads_dir) / self.appimage_name)

        # Initialize sha_name with full path if only filename is provided
        if self.sha_name and not os.path.isabs(self.sha_name):
            # Only construct path if sha_name is not already a full path and is not a special value
            if self.sha_name not in ("no_sha_file", "extracted_checksum"):
                from src.global_config import GlobalConfigManager

                downloads_dir = GlobalConfigManager().expanded_app_download_path
                self.sha_name = str(Path(downloads_dir) / self.sha_name)

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

        # Skip hashlib validation for special verification types
        # "extracted_checksum" can now mean direct hash or legacy path, both might have non-standard hash_type initially
        if (
            self.hash_type == "no_hash"
            or self.sha_name == "extracted_checksum"
            or self.sha_name == "no_sha_file"
        ):
            return

        if self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.hash_type} not available in this system")

    def verify_appimage(self, cleanup_on_failure: bool = False) -> bool:
        """Verify the AppImage using the SHA file with proper error handling and fallbacks.

        Args:
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            bool: True if verification passed or skipped due to fallback, False otherwise

        """
        try:
            # Handle "extracted_checksum":
            # 1. If direct_expected_hash is provided, use it.
            # 2. Else, fall back to the legacy path (verify_with_release_checksums).
            if self.sha_name == "extracted_checksum":
                if self.direct_expected_hash:
                    logging.info(
                        f"Verifying {self.appimage_name} using directly provided hash (type: {self.hash_type}) for 'extracted_checksum'."
                    )
                    if not self.appimage_path:
                        logging.error(
                            f"AppImage path not set for direct hash verification of {self.appimage_name}."
                        )
                        return False
                    if not os.path.exists(self.appimage_path):
                        logging.error(
                            f"AppImage file not found for direct hash verification: {self.appimage_path}"
                        )
                        if cleanup_on_failure:
                            self._cleanup_failed_file(self.appimage_path)
                        return False

                    # Ensure hash_type is valid for hashlib if it's not 'no_hash'
                    # This is important because self.hash_type would be "sha256" from SHAManager
                    if (
                        self.hash_type != "no_hash"
                        and self.hash_type not in hashlib.algorithms_available
                    ):
                        logging.error(
                            f"Hash type {self.hash_type} not available in this system for direct comparison with 'extracted_checksum'."
                        )
                        if cleanup_on_failure and self.appimage_path:
                            self._cleanup_failed_file(self.appimage_path)
                        return False

                    is_valid = self._compare_hashes(self.direct_expected_hash)
                    if not is_valid and cleanup_on_failure and self.appimage_path:
                        self._cleanup_failed_file(self.appimage_path)
                    return is_valid
                else:
                    # Fallback to legacy path if direct_expected_hash is not provided
                    logging.info(
                        "Using GitHub release description for verification (legacy path for 'extracted_checksum')"
                    )
                    # Import the utility outside the main module to avoid circular imports
                # We need owner/repo information from app_catalog
                from src.app_catalog import find_app_by_name_in_filename
                from src.utils.checksums import verify_with_release_checksums

                if not self.appimage_name:
                    logging.error("No AppImage name provided, cannot extract checksums")
                    return False

                # Get owner/repo from app catalog based on AppImage filename
                app_info = find_app_by_name_in_filename(self.appimage_name)

                if app_info:
                    if not self.appimage_path:
                        logging.error(
                            f"AppImage path not set for 'extracted_checksum' verification of {self.appimage_name}."
                        )
                        return False
                    # Use extracted owner/repo to verify with release checksums
                    return verify_with_release_checksums(
                        owner=app_info.owner,
                        repo=app_info.repo,
                        appimage_path=self.appimage_path,  # Now checked for None
                        cleanup_on_failure=cleanup_on_failure,
                    )
                else:
                    logging.error(f"Could not find app info for {self.appimage_name}")
                    return False

            # Skip verification if hash_type is set to no_hash or no SHA file name available
            if self.hash_type == "no_hash" or not self.sha_name:
                logging.info("Verification skipped - no hash file information available")
                print("Note: Verification skipped - no hash file provided")
                return True

            # Use appimage_path for existence check. It should be set by now if appimage_name was provided.
            if not self.appimage_path:
                logging.error(f"AppImage path is not set for {self.appimage_name}.")
                return False  # Cannot proceed without a path to the AppImage

            if not os.path.exists(self.appimage_path):
                logging.error(f"AppImage file not found: {self.appimage_path}")
                return False

            # FALLBACK CASE: If sha_name matches appimage_name, this indicates
            # our API fallback was triggered where no SHA file was found
            if self.sha_name == self.appimage_name:
                logging.info("Verification fallback: No SHA file available for this release")
                print("Note: Verification skipped - no hash file provided by the developer")
                logging.info(f"Proceeding with unverified AppImage: {self.appimage_name}")
                return True

            # Download SHA file only if URL is provided and file doesn't exist
            if self.sha_url:  # Check if sha_url is set
                if self.sha_name is None:
                    logging.error(
                        "SHA URL is present, but SHA name is not set. Cannot download SHA file."
                    )
                    return False  # Critical error
                if not os.path.exists(self.sha_name):
                    self._download_sha_file()  # self.sha_name and self.sha_url must be valid here

            # Check if the SHA file exists before proceeding
            if self.sha_name is None:  # If no sha_name (e.g. skipped or error in SHAManager)
                logging.info("No SHA file name specified, skipping file-based verification.")
                # This case should ideally be caught by hash_type == "no_hash" or sha_name == "from_release_description"
                # If it reaches here, it implies a logic gap or an unexpected state.
                return True  # Or False, depending on desired strictness for unhandled cases

            if not os.path.exists(self.sha_name):
                logging.error(f"SHA file not found: {self.sha_name}")
                return False

            is_valid = self._parse_sha_file()  # self.sha_name must be valid str here

            if not is_valid and cleanup_on_failure and self.appimage_path:
                self._cleanup_failed_file(self.appimage_path)

            return is_valid

        except (OSError, requests.RequestException) as e:
            logging.error(f"Verification failed: {e!s}")
            if cleanup_on_failure and self.appimage_path:
                self._cleanup_failed_file(self.appimage_path)
            return False
        except Exception as e:
            logging.error(f"Unexpected error during verification: {e!s}")
            if cleanup_on_failure and self.appimage_path:
                self._cleanup_failed_file(self.appimage_path)
            return False

    def _download_sha_file(self):
        """Download the SHA file with retries and proper cleanup."""
        # Assumes self.sha_name and self.sha_url are not None when this is called
        if self.sha_name is None or self.sha_url is None:
            raise ValueError("SHA name or URL not set for download.")

        if os.path.exists(self.sha_name):
            try:
                os.remove(self.sha_name)
                logging.info(f"Removed existing {self.sha_name}")
            except OSError as e:
                raise OSError(f"Failed to remove existing SHA file: {e!s}")

        try:
            response = requests.get(self.sha_url, timeout=10)  # self.sha_url is now checked
            response.raise_for_status()
            with open(self.sha_name, "w", encoding="utf-8") as f:  # self.sha_name is now checked
                f.write(response.text)
            logging.info(f"Successfully downloaded {self.sha_name}")
        except requests.RequestException as e:
            raise OSError(f"Failed to download SHA file: {e!s}")
        except Exception as e:
            raise OSError(f"Failed to write SHA file: {e!s}")

    def _parse_sha_file(self) -> bool:
        """Dispatch to appropriate SHA parsing method based on file extension."""
        # Assumes self.sha_name is not None when this is called
        if self.sha_name is None:
            raise ValueError("SHA name not set for parsing.")

        if self.hash_type == "no_hash":
            logging.info("Skipping hash verification as requested")
            return True

        if not os.path.exists(self.sha_name):  # self.sha_name is now checked
            raise OSError(f"SHA file not found: {self.sha_name}")

        ext = os.path.splitext(self.sha_name)[1].lower()  # self.sha_name is now checked
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
            # self.sha_name is asserted to be str by _parse_sha_file caller context
            with open(self.sha_name, encoding="utf-8") as f:  # type: ignore
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
            # self.sha_name is asserted to be str by _parse_sha_file caller context
            with open(self.sha_name, encoding="utf-8") as f:  # type: ignore
                content = f.read().strip()

            if not content:
                raise ValueError("Empty SHA file")

            hash_value = content.split()[0]
            # Validate hash format (self.hash_type should be 'sha256' or 'sha512' here)
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
        if not self.appimage_name:
            raise ValueError("AppImage name not set for text SHA parsing.")
        target_name = os.path.basename(self.appimage_name).lower()

        try:
            # self.sha_name is asserted to be str by _parse_sha_file caller context
            with open(self.sha_name, encoding="utf-8") as f:  # type: ignore
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
        if not self.appimage_name:
            raise ValueError("AppImage name not set for path SHA parsing.")
        target_filename = os.path.basename(self.appimage_name).lower()

        try:
            # self.sha_name is asserted to be str by _parse_sha_file caller context
            with open(self.sha_name, encoding="utf-8") as f:  # type: ignore
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
        if not self.appimage_path:
            raise ValueError("AppImage path not set for hash comparison.")
        file_to_verify = self.appimage_path  # Now we know it's a str

        if not os.path.exists(file_to_verify):  # file_to_verify is str
            raise OSError(f"AppImage file not found: {file_to_verify}")

        try:
            # self.hash_type should be a valid algorithm string here,
            # or "no_hash" (which shouldn't reach _compare_hashes if logic is correct)
            # or "from_release_description" (where hash_type is set to sha256 by SHAManager)
            # or "extracted_checksum" (where hash_type might be sha256)
            # The _validate_hash_type and the new check in verify_appimage for "from_release_description"
            # should ensure self.hash_type is usable by hashlib.new() if it's not a special skip type.
            if self.hash_type == "no_hash":  # Should not happen if called for actual comparison
                logging.warning("Attempted to compare hashes with hash_type 'no_hash'. Skipping.")
                return True  # Or False, as this is an inconsistent state for comparison

            hash_func = hashlib.new(self.hash_type)

            # Use larger chunk size for better performance with large files
            chunk_size = 65536  # 64KB chunks

            with open(file_to_verify, "rb") as f:  # file_to_verify is str
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
        from src.utils.cleanup_utils import remove_single_file

        if not self.sha_name or not os.path.exists(self.sha_name):
            logging.debug(f"No SHA file to clean up: {self.sha_name}")
            return True

        return remove_single_file(self.sha_name, verbose=False)

    def cleanup_batch_failed_files(
        self,
        app_name: str,
        appimage_name: str | None = None,
        sha_name: str | None = None,
        ask_confirmation: bool = True,
    ) -> list[str]:
        """Clean up AppImage and SHA files for batch operations when update fails.

        This method is designed for use by update commands when multiple apps
        are being processed and individual verification failures need cleanup.

        Args:
            app_name: Name of the app to clean up files for
            appimage_name: Exact AppImage filename if known, otherwise use patterns
            sha_name: Exact SHA filename if known, otherwise use patterns
            ask_confirmation: Whether to ask user for confirmation before removal

        Returns:
            List of file paths that were successfully removed

        """
        from src.utils.cleanup_utils import cleanup_failed_verification_files

        # Use the unified cleanup function
        return cleanup_failed_verification_files(
            app_name=app_name,
            appimage_name=appimage_name,
            sha_name=sha_name,
            ask_confirmation=ask_confirmation,
            verbose=True
        )

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
        from src.utils.cleanup_utils import cleanup_single_failed_file

        # Use the unified cleanup function
        return cleanup_single_failed_file(
            filepath=filepath,
            ask_confirmation=True,
            verbose=True
        )
