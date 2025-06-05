"""Hash calculation and comparison for AppImage verification.

This module provides functionality for computing file hashes and comparing
them with expected values using memory-efficient chunked reading.
"""

import fcntl
import hashlib
import logging
import os
from typing import BinaryIO


class HashCalculator:
    """Handles hash computation and comparison for file verification."""

    def __init__(self, hash_type: str) -> None:
        """Initialize the hash calculator.

        Args:
            hash_type: The hash algorithm to use (e.g., 'sha256', 'sha512')

        Raises:
            ValueError: If hash type is not available in the system
        """
        self.hash_type = hash_type.lower()

        # Skip validation for special hash types that don't use hashlib
        if self._is_special_hash_type():
            return

        if self.hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.hash_type} not available in this system")

    def _is_special_hash_type(self) -> bool:
        """Check if this is a special hash type that doesn't use hashlib."""
        return self.hash_type in ("no_hash", "asset_digest", "extracted_checksum")

    def calculate_file_hash(self, filepath: str) -> str:
        """Calculate hash of a file using memory-efficient chunked reading.

        Args:
            filepath: Path to the file to hash

        Returns:
            The calculated hash as a lowercase hexadecimal string

        Raises:
            OSError: If file cannot be read
            ValueError: If hash calculation fails
        """
        if self._is_special_hash_type():
            logging.warning(
                f"Attempted to calculate hash with special hash_type '{self.hash_type}'"
            )
            return ""

        if not os.path.exists(filepath):
            raise OSError(f"File not found: {filepath}")

        try:
            hash_func = hashlib.new(self.hash_type)
            chunk_size = 65536  # 64KB chunks for better performance

            with open(filepath, "rb") as f:
                try:
                    # Acquire shared lock to prevent writing while reading
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)

                    for chunk in iter(lambda: f.read(chunk_size), b""):
                        hash_func.update(chunk)

                except (OSError, IOError) as lock_error:
                    # If locking fails, proceed without lock but log warning
                    logging.warning(f"Could not acquire file lock for {filepath}: {lock_error}")
                    f.seek(0)  # Reset file position
                    for chunk in iter(lambda: f.read(chunk_size), b""):
                        hash_func.update(chunk)

            return hash_func.hexdigest().lower()

        except OSError as e:
            raise OSError(f"Failed to read file {filepath}: {e}")
        except Exception as e:
            raise ValueError(f"Hash calculation failed for {filepath}: {e}")

    def compare_hashes(self, actual_hash: str, expected_hash: str) -> bool:
        """Compare two hash values.

        Args:
            actual_hash: The computed hash value
            expected_hash: The expected hash value

        Returns:
            True if hashes match, False otherwise
        """
        return actual_hash.lower() == expected_hash.lower()

    def verify_file_hash(self, filepath: str, expected_hash: str) -> bool:
        """Calculate file hash and compare with expected value.

        Args:
            filepath: Path to the file to verify
            expected_hash: The expected hash value

        Returns:
            True if verification passes, False otherwise

        Raises:
            OSError: If file cannot be read
            ValueError: If hash calculation fails
        """
        actual_hash = self.calculate_file_hash(filepath)
        return self.compare_hashes(actual_hash, expected_hash)

    def validate_hash_format(self, hash_value: str) -> bool:
        """Validate that a hash string has the correct format.

        Args:
            hash_value: The hash string to validate

        Returns:
            True if hash format is valid, False otherwise
        """
        if self._is_special_hash_type():
            return True

        expected_length = self._get_expected_hash_length()

        if len(hash_value) != expected_length:
            return False

        # Check if all characters are valid hexadecimal
        try:
            int(hash_value, 16)
            return True
        except ValueError:
            return False

    def _get_expected_hash_length(self) -> int:
        """Get the expected length of hash for the current hash type.

        Returns:
            Expected hash length in characters
        """
        if self.hash_type == "sha256":
            return 64
        elif self.hash_type == "sha512":
            return 128
        else:
            # For other hash types, calculate based on digest size
            try:
                hash_func = hashlib.new(self.hash_type)
                return hash_func.digest_size * 2  # 2 hex chars per byte
            except ValueError:
                return 0
