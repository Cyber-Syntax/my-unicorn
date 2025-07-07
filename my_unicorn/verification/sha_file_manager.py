"""SHA file management for AppImage verification.

This module handles downloading SHA files and parsing various SHA file formats
including YAML, simple hash files, text files, and path-based formats.
"""

import base64
import logging
import os
import re

import requests
import yaml


class ShaFileManager:
    """Manages SHA file operations including downloading and parsing."""

    def __init__(self, checksum_hash_type: str) -> None:
        """Initialize the SHA file manager.

        Args:
            checksum_hash_type: The hash algorithm type (e.g., 'sha256', 'sha512')

        """
        self.checksum_hash_type = checksum_hash_type.lower()

    def download_sha_file(self, checksum_file_download_url: str, sha_path: str) -> None:
        """Download SHA file with proper cleanup and error handling.

        Args:
            checksum_file_download_url: URL to download the SHA file from
            sha_path: Local path where the SHA file should be saved

        Raises:
            OSError: If download or file operations fail

        """
        if os.path.exists(sha_path):
            try:
                os.remove(sha_path)
                logging.info("Removed existing SHA file: %s", sha_path)
            except OSError as e:
                raise OSError(f"Failed to remove existing SHA file: {e}")

        try:
            response = requests.get(checksum_file_download_url, timeout=10)
            response.raise_for_status()

            with open(sha_path, "w", encoding="utf-8") as f:
                f.write(response.text)
            logging.info("Successfully downloaded SHA file: %s", sha_path)

        except requests.RequestException as e:
            raise OSError(f"Failed to download SHA file from {checksum_file_download_url}: {e}")
        except Exception as e:
            raise OSError(f"Failed to write SHA file to {sha_path}: {e}")

    def parse_sha_file(self, sha_path: str, appimage_name: str) -> str:
        """Parse SHA file and extract hash for the specified AppImage.

        Args:
            sha_path: Path to the SHA file
            appimage_name: Name of the AppImage to find hash for

        Returns:
            The extracted hash value

        Raises:
            OSError: If file cannot be read
            ValueError: If no valid hash is found

        """
        if not os.path.exists(sha_path):
            raise OSError(f"SHA file not found: {sha_path}")

        ext = os.path.splitext(sha_path)[1].lower()

        # Select parser based on file extension
        parser_map = {
            ".yml": self._parse_yaml_sha,
            ".yaml": self._parse_yaml_sha,
            ".sha256": self._parse_simple_sha,
            ".sha512": self._parse_simple_sha,
        }

        parser = parser_map.get(ext, self._parse_text_sha)

        try:
            return parser(sha_path, appimage_name)
        except ValueError as e:
            # If standard parsing fails, try path-based parser as fallback
            if "No valid hash found" in str(e):
                logging.info("Standard hash parsing failed, trying path-based fallback")
                return self._parse_path_sha(sha_path, appimage_name)
            raise

    def _parse_yaml_sha(self, sha_path: str, appimage_name: str) -> str:
        """Parse hash from YAML file.

        Args:
            sha_path: Path to the YAML SHA file
            appimage_name: Name of the AppImage (not used for YAML parsing)

        Returns:
            The decoded hash value

        Raises:
            OSError: If YAML parsing fails
            ValueError: If hash is not found or invalid

        """
        try:
            with open(sha_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                raise ValueError("Empty YAML file")

            encoded_hash = data.get(self.checksum_hash_type)
            if not encoded_hash:
                raise ValueError(f"No {self.checksum_hash_type} hash found in YAML")

            try:
                decoded_hash = base64.b64decode(encoded_hash).hex()
                return decoded_hash
            except Exception as e:
                raise ValueError(f"Failed to decode hash: {e}")

        except (yaml.YAMLError, ValueError, TypeError) as e:
            raise OSError(f"YAML parsing failed: {e}")

    def _parse_simple_sha(self, sha_path: str, appimage_name: str) -> str:
        """Parse hash from simple hash file.

        Args:
            sha_path: Path to the simple SHA file
            appimage_name: Name of the AppImage (not used for simple parsing)

        Returns:
            The hash value

        Raises:
            OSError: If file cannot be read
            ValueError: If hash is invalid

        """
        try:
            with open(sha_path, encoding="utf-8") as f:
                content = f.read().strip()

            if not content:
                raise ValueError("Empty SHA file")

            hash_value = content.split()[0]

            # Validate hash format
            expected_length = 64 if self.checksum_hash_type == "sha256" else 128
            if len(hash_value) != expected_length:
                raise ValueError(f"Invalid {self.checksum_hash_type} hash length")

            if not all(c in "0123456789abcdefABCDEF" for c in hash_value):
                raise ValueError(f"Invalid {self.checksum_hash_type} hash format")

            return hash_value

        except OSError as e:
            raise OSError(f"Failed to read SHA file: {e}")

    def _parse_text_sha(self, sha_path: str, appimage_name: str) -> str:
        """Parse hash from text file with pattern matching.

        This handles multiple common formats:
        - <hash> <filename> (most common format)
        - <filename> <hash> (alternate format)
        - GitHub-style checksums with headers

        Args:
            sha_path: Path to the text SHA file
            appimage_name: Name of the AppImage to find hash for

        Returns:
            The hash value for the specified AppImage

        Raises:
            OSError: If file cannot be read
            ValueError: If no valid hash is found

        """
        target_name = os.path.basename(appimage_name).lower()

        try:
            with open(sha_path, encoding="utf-8") as f:
                content = f.read()

            # Try GitHub-style format with headers first
            sha_section_match = re.search(r"##\s+SHA2?56.+", content, re.MULTILINE | re.IGNORECASE)
            if sha_section_match:
                expected_length = 64 if self.checksum_hash_type == "sha256" else 128
                hash_pattern = rf"([0-9a-f]{{{expected_length}}})\s+\*?{re.escape(target_name)}"
                hash_match = re.search(hash_pattern, content, re.MULTILINE | re.IGNORECASE)
                if hash_match:
                    hash_value = hash_match.group(1).lower()
                    logging.info("Found valid hash for %s in GitHub-style SHA file", target_name)
                    return hash_value

            # Process line by line for common formats
            for line in content.splitlines():
                line = line.strip()
                if not line or len(line.split()) < 2:
                    continue

                # Normalize line by removing markers and extra spaces
                normalized_line = line.replace("*", " ").replace("  ", " ")
                parts = normalized_line.strip().split()

                if len(parts) < 2:
                    continue

                hash_value = self._extract_hash_from_line(parts, target_name, line)
                if hash_value:
                    logging.info("Found valid hash for %s in SHA file", target_name)
                    return hash_value

            raise ValueError("No valid hash found for %s in SHA file", appimage_name)

        except OSError as e:
            raise OSError(f"Failed to read SHA file: {e}")
        except Exception as e:
            logging.error("Error parsing SHA file: %s", e)
            raise

    def _extract_hash_from_line(self, parts: list[str], target_name: str, line: str) -> str | None:
        """Extract hash from a line parts if target filename is found.

        Args:
            parts: Split line parts
            target_name: Target filename to match
            line: Original line for additional matching

        Returns:
            Hash value if found, None otherwise

        """
        # Format: <hash> <filename> (most common)
        if len(parts[0]) in (64, 128) and parts[1].lower() == target_name:
            return self._validate_and_return_hash(parts[0])

        # Format: <filename> <hash> (alternate format)
        if parts[0].lower() == target_name and len(parts[1]) in (64, 128):
            return self._validate_and_return_hash(parts[1])

        # Look for target filename anywhere with a valid hash
        for part in parts:
            if len(part) in (64, 128) and re.match(r"^[0-9a-f]+$", part, re.IGNORECASE):
                if target_name in line.lower():
                    return self._validate_and_return_hash(part)

        return None

    def _validate_and_return_hash(self, hash_value: str) -> str | None:
        """Validate hash format and return if valid.

        Args:
            hash_value: Hash string to validate

        Returns:
            Validated hash value or None if invalid

        """
        expected_length = 64 if self.checksum_hash_type == "sha256" else 128
        len_hash_value = len(hash_value)
        if len_hash_value != expected_length:
            logging.warning(
                "Hash has wrong length: %s, expected %s", len_hash_value, expected_length
            )
            return None

        if not re.match(r"^[0-9a-f]+$", hash_value, re.IGNORECASE):
            logging.warning("Invalid hex characters in hash: %s", hash_value)
            return None

        return hash_value.lower()

    def _parse_path_sha(self, sha_path: str, appimage_name: str) -> str:
        """Parse hash from text file containing relative paths.

        This handles formats like:
        <hash>  ./path/to/filename.AppImage

        Args:
            sha_path: Path to the SHA file
            appimage_name: Name of the AppImage to find hash for

        Returns:
            The hash value for the specified AppImage

        Raises:
            OSError: If file cannot be read
            ValueError: If no valid hash is found

        """
        target_filename = os.path.basename(appimage_name).lower()

        try:
            with open(sha_path, encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) < 2:
                        continue

                    hash_value = parts[0]
                    file_path = parts[1]

                    # Extract filename from path and compare
                    path_filename = os.path.basename(file_path).lower()

                    if path_filename == target_filename:
                        validated_hash = self._validate_and_return_hash(hash_value)
                        if validated_hash:
                            logging.info(
                                f"Found valid hash for {path_filename} in path-based SHA file"
                            )
                            return validated_hash

            raise ValueError(f"No valid hash found for {target_filename} in path-based SHA file")

        except OSError as e:
            logging.error("Failed to read SHA file: %s", e)
            raise OSError("Failed to read SHA file: %s" % e)
