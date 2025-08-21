"""Verification utilities for AppImage integrity checking.

This module provides various verification methods including digest verification,
checksum file parsing, and hash computation for downloaded AppImages.
"""

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from .download import DownloadService

from .logger import get_logger
from .utils import format_bytes

# Try to import yaml for YAML checksum file support
try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    _YAML_AVAILABLE = False

# Import base64 for hash conversion
import base64

HashType = Literal["sha1", "sha256", "sha512", "md5"]
logger = get_logger(__name__)


class Verifier:
    """Handles verification of downloaded AppImage files."""

    def __init__(self, file_path: Path) -> None:
        """Initialize verifier with file path.

        Args:
            file_path: Path to the file to verify

        """
        self.file_path: Path = file_path
        self._log_file_info()

    def _log_file_info(self) -> None:
        """Log basic file information for debugging."""
        if self.file_path.exists():
            file_size = self.file_path.stat().st_size
            logger.debug("📁 File info: %s", self.file_path.name)
            logger.debug("   Path: %s", self.file_path)
            logger.debug("   Size: %s (%s bytes)", format_bytes(file_size), f"{file_size:,}")
        else:
            logger.warning("⚠️  File does not exist: %s", self.file_path)

    def verify_digest(self, expected_digest: str) -> None:
        """Verify file using GitHub API digest format.

        Args:
            expected_digest: Digest in format "algorithm:hash"

        Raises:
            ValueError: If digest format is invalid or verification fails

        """
        logger.debug("🔍 Starting digest verification for %s", self.file_path.name)
        logger.debug("   Expected digest: %s", expected_digest)

        if not expected_digest:
            logger.error("❌ Digest cannot be empty")
            raise ValueError("Digest cannot be empty")

        algo, _, hash_value = expected_digest.partition(":")
        if not hash_value:
            logger.error("❌ Invalid digest format: %s", expected_digest)
            raise ValueError(f"Invalid digest format: {expected_digest}")

        if algo not in ["sha1", "sha256", "sha512", "md5"]:
            logger.error("❌ Unsupported digest algorithm: %s", algo)
            raise ValueError(f"Unsupported digest algorithm: {algo}")

        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Expected hash: %s", hash_value)

        logger.debug("🧮 Computing %s hash...", algo.upper())
        actual_hash = self.compute_hash(algo)  # type: ignore[arg-type]
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != hash_value.lower():
            logger.error("❌ Digest verification FAILED!")
            logger.error("   Expected: %s", hash_value)
            logger.error("   Actual:   %s", actual_hash)
            logger.error("   Algorithm: %s", algo.upper())
            logger.error("   File: %s", self.file_path)
            raise ValueError(
                f"Digest mismatch!\nExpected: {hash_value}\nActual:   {actual_hash}"
            )

        logger.debug("✅ Digest verification PASSED!")
        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Hash: %s", actual_hash)

    def verify_hash(self, expected_hash: str, hash_type: HashType) -> None:
        """Verify file using specific hash type.

        Args:
            expected_hash: Expected hash value
            hash_type: Type of hash (sha1, sha256, sha512, md5)

        Raises:
            ValueError: If verification fails

        """
        logger.debug(
            f"🔍 Starting {hash_type.upper()} hash verification for {self.file_path.name}"
        )
        logger.debug("   Expected hash: %s", expected_hash)

        logger.debug("🧮 Computing %s hash...", hash_type.upper())
        actual_hash = self.compute_hash(hash_type)
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != expected_hash.lower():
            logger.error("❌ %s verification FAILED!", hash_type.upper())
            logger.error("   Expected: %s", expected_hash)
            logger.error("   Actual:   %s", actual_hash)
            logger.error("   File: %s", self.file_path)
            raise ValueError(
                f"{hash_type.upper()} mismatch!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        logger.debug("✅ %s verification PASSED!", hash_type.upper())
        logger.debug("   Hash: %s", actual_hash)

    def compute_hash(self, hash_type: HashType) -> str:
        """Compute hash of the file.

        Args:
            hash_type: Type of hash to compute

        Returns:
            Hexadecimal hash string

        Raises:
            ValueError: If hash type is unsupported
            FileNotFoundError: If file doesn't exist

        """
        if not self.file_path.exists():
            logger.error("❌ File not found: %s", self.file_path)
            raise FileNotFoundError(f"File not found: {self.file_path}")

        hash_algorithms = {
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
            "md5": hashlib.md5,
        }

        if hash_type not in hash_algorithms:
            logger.error("❌ Unsupported hash type: %s", hash_type)
            raise ValueError(f"Unsupported hash type: {hash_type}")

        logger.debug("🧮 Computing %s hash for %s", hash_type.upper(), self.file_path.name)

        hasher = hash_algorithms[hash_type]()
        bytes_processed = 0
        chunk_size = 8192

        with open(self.file_path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
                bytes_processed += len(chunk)

        computed_hash = hasher.hexdigest()

        logger.debug(
            f"   Processed: {format_bytes(bytes_processed)} ({bytes_processed:,} bytes)"
        )
        logger.debug("   Hash: %s", computed_hash)

        return computed_hash

    async def verify_from_checksum_file(
        self,
        checksum_url: str,
        hash_type: HashType,
        download_service: "DownloadService",
        filename: str | None = None,
    ) -> None:
        """Verify file using remote checksum file.

        Args:
            checksum_url: URL to the checksum file
            hash_type: Type of hash used in checksum file
            download_service: DownloadService instance for downloading checksum file
            filename: Specific filename to look for (defaults to file_path.name)

        Raises:
            ValueError: If verification fails or checksum not found

        """
        target_filename = filename or self.file_path.name

        logger.debug("🔍 Starting checksum file verification for %s", self.file_path.name)
        logger.debug("   Checksum URL: %s", checksum_url)
        logger.debug("   Target filename: %s", target_filename)
        logger.debug("   Hash type: %s", hash_type.upper())

        # Download checksum file
        logger.debug("📥 Downloading checksum file...")
        checksum_content = await download_service.download_checksum_file(checksum_url)
        logger.debug("   Downloaded %d characters", len(checksum_content))

        # Parse checksum file to find our file's hash
        logger.debug("🔍 Parsing checksum file for %s...", target_filename)
        expected_hash = self._parse_checksum_file(checksum_content, target_filename, hash_type)

        if not expected_hash:
            logger.error("❌ Hash for %s not found in checksum file", target_filename)
            logger.debug("   Checksum file content:\n%s", checksum_content)
            raise ValueError(f"Hash for {target_filename} not found in checksum file")

        logger.debug("✅ Found expected hash in checksum file")
        logger.debug("   Expected hash: %s", expected_hash)

        # Verify the hash
        self.verify_hash(expected_hash, hash_type)

    def parse_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Parse checksum file to extract hash for specific file.

        This is a public method that can be used by external services.

        Args:
            content: Content of the checksum file
            filename: Target filename to find hash for
            hash_type: Type of hash being used

        Returns:
            Hash value for the file or None if not found

        """
        return self._parse_checksum_file(content, filename, hash_type)

    def _parse_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Parse checksum file to extract hash for specific file.

        Args:
            content: Content of the checksum file
            filename: Target filename to find hash for
            hash_type: Type of hash being used

        Returns:
            Hash value for the file or None if not found

        """
        # First, try to detect if this is a YAML file
        if self._is_yaml_content(content):
            return self._parse_yaml_checksum_file(content, filename)

        # Otherwise, parse as traditional checksum file
        return self._parse_traditional_checksum_file(content, filename, hash_type)

    def _is_yaml_content(self, content: str) -> bool:
        """Check if content appears to be YAML format.

        Args:
            content: File content to check

        Returns:
            True if content appears to be YAML

        """
        if not _YAML_AVAILABLE or yaml is None:
            return False

        # Basic YAML detection heuristics
        lines = content.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Look for YAML key-value pairs or lists
            if (":" in line and not line.startswith("-")) or line.startswith("- "):
                return True
        return False

    def _parse_yaml_checksum_file(self, content: str, target_filename: str) -> str | None:
        """Parse YAML format checksum file (like latest-linux.yml).

        Args:
            content: YAML file content
            target_filename: Name of file to find hash for

        Returns:
            Hash value for the file or None if not found (converted from Base64 to hex)

        """
        if not _YAML_AVAILABLE or yaml is None:
            logger.warning("PyYAML not available - cannot parse YAML checksum files")
            return None

        try:
            data = yaml.safe_load(content)

            # Handle Electron auto-updater format
            if isinstance(data, dict):
                # Check if it's the main file referenced at root level
                if data.get("path") == target_filename and "sha512" in data:
                    logger.debug("✅ Found hash for %s in YAML root level", target_filename)
                    base64_hash = data["sha512"]
                    return self._convert_base64_to_hex(base64_hash)

                # Check in files array
                files = data.get("files", [])
                if isinstance(files, list):
                    for file_info in files:
                        if (
                            isinstance(file_info, dict)
                            and file_info.get("url") == target_filename
                        ):
                            # Look for any hash type
                            for hash_type in ["sha512", "sha256", "sha1", "md5"]:
                                if hash_type in file_info:
                                    logger.debug(
                                        "✅ Found %s hash for %s in YAML files array",
                                        hash_type,
                                        target_filename,
                                    )
                                    base64_hash = file_info[hash_type]
                                    return self._convert_base64_to_hex(base64_hash)

            logger.info("Could not find hash for %s in YAML checksum file", target_filename)
            return None

        except Exception as e:
            logger.error("Error parsing YAML checksum file: %s", e)
            return None

    def _parse_traditional_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Parse traditional format checksum file.

        Args:
            content: Checksum file content
            filename: Target filename to find hash for
            hash_type: Type of hash being used

        Returns:
            Hash value for the file or None if not found

        """
        lines = content.strip().split("\n")
        logger.debug("🔍 Parsing %d lines in traditional checksum file", len(lines))

        found_entries = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                logger.debug("   Line %d: Skipping (empty or comment)", line_num)
                continue

            logger.debug("   Line %d: %s", line_num, line)

            # Handle different checksum file formats
            hash_value = None
            file_name = None

            if self._is_sha256sums_format(line):
                hash_value, file_name = self._parse_sha256sums_line(line)
                logger.debug("      Format: SHA256SUMS")
            else:
                # Try generic "hash filename" format
                parts = line.split()
                if len(parts) >= 2:
                    hash_value, file_name = (
                        parts[0],
                        parts[1].lstrip("*"),
                    )  # Remove optional * prefix
                    logger.debug("      Format: Generic")
                else:
                    logger.debug("      Format: Unknown/Invalid")
                    continue

            if hash_value and file_name:
                logger.debug("      Parsed hash: %s", hash_value)
                logger.debug("      Parsed filename: %s", file_name)
                found_entries.append((hash_value, file_name, Path(file_name).name))

            # Remove path separators and compare just the filename
            if file_name and Path(file_name).name == filename:
                logger.debug("✅ Found matching entry for %s", filename)
                logger.debug("   Hash: %s", hash_value)
                logger.debug("   Full filename in checksum: %s", file_name)
                return hash_value

        logger.info("⚠️  Target file %s not found in traditional checksum file", filename)
        logger.debug("   Found %d entries:", len(found_entries))
        for hash_val, full_name, base_name in found_entries:
            logger.debug("      • %s (full: %s) -> %s...", base_name, full_name, hash_val[:16])

        return None

    def _is_sha256sums_format(self, line: str) -> bool:
        """Check if line is in SHA256SUMS format."""
        parts = line.split()
        return len(parts) >= 2 and len(parts[0]) == 64

    def _parse_sha256sums_line(self, line: str) -> tuple[str, str]:
        """Parse SHA256SUMS format line."""
        parts = line.split(None, 1)
        return parts[0], parts[1].strip("*")

    def detect_hash_type_from_filename(self, filename: str) -> HashType:
        """Detect hash type from checksum filename.

        This is a public method that can be used by external services.

        Args:
            filename: Checksum file name

        Returns:
            Detected hash type (defaults to sha256)

        """
        return self._detect_hash_type_from_filename(filename)

    def _detect_hash_type_from_filename(self, filename: str) -> HashType:
        """Detect hash type from checksum filename.

        Args:
            filename: Checksum file name

        Returns:
            Detected hash type (defaults to sha256)

        """
        filename_lower = filename.lower()

        if "sha512" in filename_lower or "512" in filename_lower:
            return "sha512"
        elif "sha256" in filename_lower or "256" in filename_lower:
            return "sha256"
        elif "sha1" in filename_lower:
            return "sha1"
        elif "md5" in filename_lower:
            return "md5"
        elif filename_lower.endswith(".digest"):
            return "sha256"  # .DIGEST files typically use sha256
        else:
            return "sha256"  # Default fallback

    def _convert_base64_to_hex(self, base64_hash: str) -> str:
        """Convert Base64 encoded hash to hexadecimal format.

        Args:
            base64_hash: Base64 encoded hash string

        Returns:
            Hexadecimal hash string

        Raises:
            ValueError: If Base64 decoding fails

        """
        try:
            # Decode Base64 to bytes
            hash_bytes = base64.b64decode(base64_hash)
            # Convert bytes to hexadecimal string
            hex_hash = hash_bytes.hex()
            logger.debug("🔄 Converted Base64 hash to hex:")
            logger.debug("   Base64: %s", base64_hash)
            logger.debug("   Hex:    %s", hex_hash)
            return hex_hash
        except Exception as e:
            logger.error("❌ Failed to convert Base64 hash to hex: %s", e)
            raise ValueError(f"Invalid Base64 hash: {base64_hash}") from e

    def get_file_size(self) -> int:
        """Get size of the file in bytes.

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist

        """
        if not self.file_path.exists():
            raise FileNotFoundError(f"File not found: {self.file_path}")

        return self.file_path.stat().st_size

    def verify_size(self, expected_size: int) -> None:
        """Verify file size matches expected size.

        Args:
            expected_size: Expected file size in bytes

        Raises:
            ValueError: If size doesn't match

        """
        logger.debug("🔍 Verifying file size for %s", self.file_path.name)
        logger.debug(
            f"   Expected size: {format_bytes(expected_size)} ({expected_size:,} bytes)"
        )

        actual_size = self.get_file_size()
        logger.debug("   Actual size: %s (%d bytes)", format_bytes(actual_size), actual_size)

        if actual_size != expected_size:
            logger.error("❌ File size verification FAILED!")
            logger.error(
                "   Expected: %s (%d bytes)", format_bytes(expected_size), expected_size
            )
            logger.error("   Actual: %s (%d bytes)", format_bytes(actual_size), actual_size)
            logger.error("   Difference: %+d bytes", actual_size - expected_size)
            raise ValueError(
                f"File size mismatch!\n"
                f"Expected: {expected_size} bytes\n"
                f"Actual:   {actual_size} bytes"
            )

        logger.debug("✅ File size verification PASSED!")
        logger.debug("   Size: %s (%d bytes)", format_bytes(actual_size), actual_size)


class VerificationConfig:
    """Configuration for verification operations."""

    def __init__(
        self,
        digest: bool = True,
        skip: bool = False,
        checksum_file: str = "",
        checksum_hash_type: HashType = "sha256",
        verify_size: bool = True,
    ):
        """Initialize verification configuration.

        Args:
            digest: Whether to verify using GitHub API digest
            skip: Whether to skip all verification
            checksum_file: URL or filename of checksum file
            checksum_hash_type: Hash type used in checksum file
            verify_size: Whether to verify file size

        """
        self.digest = digest
        self.skip = skip
        self.checksum_file = checksum_file
        self.checksum_hash_type = checksum_hash_type
        self.verify_size = verify_size

        logger.debug("🔧 Verification config initialized:")
        logger.debug("   Digest verification: %s", digest)
        logger.debug("   Skip verification: %s", skip)
        logger.debug("   Checksum file: %s", checksum_file or "None")
        logger.debug("   Checksum hash type: %s", checksum_hash_type)
        logger.debug("   Verify size: %s", verify_size)

    # TODO: is it better to save verify_size to app specific config file?
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VerificationConfig":
        """Create VerificationConfig from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            VerificationConfig instance

        """
        config = cls(
            digest=data.get("digest", True),
            skip=data.get("skip", False),
            checksum_file=data.get("checksum_file", ""),
            checksum_hash_type=data.get("checksum_hash_type", "sha256"),
            verify_size=data.get("verify_size", True),
        )

        logger.debug("🔧 VerificationConfig created from dict:")
        logger.debug("   Source data: %s", data)

        return config
