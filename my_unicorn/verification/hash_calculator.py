"""Hash calculation and comparison for AppImage verification.

This module provides secure, memory-efficient hash calculation and verification utilities for AppImage 
files. It implements chunked file reading and file locking to ensure data integrity during hash 
computation.
"""

import fcntl
import hashlib
import logging
import os
from pathlib import Path


class HashCalculator:
    """Handles hash computation and comparison for file verification."""

    def __init__(self, checksum_hash_type: str) -> None:
        """Initialize the hash calculator with specified algorithm.

        Creates a hash calculator instance configured to use the specified hash algorithm.
        Validates that the requested algorithm is available on the system.

        Args:
            checksum_hash_type: Hash algorithm to use (e.g., 'sha256', 'sha512')

        Raises:
            ValueError: If specified hash algorithm is not available on the system
        """
        self.checksum_hash_type = checksum_hash_type.lower()

        # Skip validation for special hash types that don't use hashlib
        if self._is_special_checksum_hash_type():
            return

        if self.checksum_hash_type not in hashlib.algorithms_available:
            raise ValueError(f"Hash type {self.checksum_hash_type} not available in this system")

    def _is_special_checksum_hash_type(self) -> bool:
        """Check if this is a special hash type that doesn't use hashlib."""
        return self.checksum_hash_type in ("no_hash", "asset_digest", "extracted_checksum")

    def calculate_file_hash(self, filepath: str | Path) -> str:
        """Calculate file hash using memory-efficient chunked reading.

        Args:
            filepath: Path to file to hash (str or Path object)

        Returns:
            Calculated hash as lowercase hexadecimal string

        Raises:
            OSError: If file cannot be opened or read
            ValueError: If hash calculation fails for any reason

        Example:
            >>> calc = HashCalculator('sha256')
            >>> calc.calculate_file_hash('myfile.AppImage')
            '8d969eef6ecad3c29a3a629280e686cf0c3f5d5a86aff3ca12020c923adc6c92'
        """
        if self._is_special_checksum_hash_type():
            logging.warning(
                f"Attempted to calculate hash with special checksum_hash_type '{self.checksum_hash_type}'"
            )
            return ""

        if not os.path.exists(filepath):
            raise OSError(f"File not found: {filepath}")

        try:
            hash_func = hashlib.new(self.checksum_hash_type)
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

    def verify_file_hash(self, filepath: str | Path, expected_hash: str) -> bool:
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
        if self._is_special_checksum_hash_type():
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
        if self.checksum_hash_type == "sha256":
            return 64
        elif self.checksum_hash_type == "sha512":
            return 128
        else:
            # For other hash types, calculate based on digest size
            try:
                hash_func = hashlib.new(self.checksum_hash_type)
                return hash_func.digest_size * 2  # 2 hex chars per byte
            except ValueError:
                return 0
