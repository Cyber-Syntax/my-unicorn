"""Verification utilities for AppImage integrity checking.

This module provides various verification methods including digest verification,
checksum file parsing, and hash computation for downloaded AppImages.
"""

import hashlib
from pathlib import Path
from typing import Any, Literal

import aiohttp

try:
    from .auth import GitHubAuthManager
    from .logger import get_logger
    from .utils import format_bytes
except ImportError:
    # Fallback for direct execution
    from auth import GitHubAuthManager
    from logger import get_logger
    from utils import format_bytes

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
            logger.debug(f"📁 File info: {self.file_path.name}")
            logger.debug(f"   Path: {self.file_path}")
            logger.debug(f"   Size: {format_bytes(file_size)} ({file_size:,} bytes)")
        else:
            logger.warning(f"⚠️  File does not exist: {self.file_path}")

    def verify_digest(self, expected_digest: str) -> None:
        """Verify file using GitHub API digest format.

        Args:
            expected_digest: Digest in format "algorithm:hash"

        Raises:
            ValueError: If digest format is invalid or verification fails

        """
        logger.debug(f"🔍 Starting digest verification for {self.file_path.name}")
        logger.debug(f"   Expected digest: {expected_digest}")

        if not expected_digest:
            logger.error("❌ Digest cannot be empty")
            raise ValueError("Digest cannot be empty")

        algo, _, hash_value = expected_digest.partition(":")
        if not hash_value:
            logger.error(f"❌ Invalid digest format: {expected_digest}")
            raise ValueError(f"Invalid digest format: {expected_digest}")

        if algo not in ["sha1", "sha256", "sha512", "md5"]:
            logger.error(f"❌ Unsupported digest algorithm: {algo}")
            raise ValueError(f"Unsupported digest algorithm: {algo}")

        logger.debug(f"   Algorithm: {algo.upper()}")
        logger.debug(f"   Expected hash: {hash_value}")

        logger.debug(f"🧮 Computing {algo.upper()} hash...")
        actual_hash = self.compute_hash(algo)  # type: ignore
        logger.debug(f"   Computed hash: {actual_hash}")

        if actual_hash.lower() != hash_value.lower():
            logger.error("❌ Digest verification FAILED!")
            logger.error(f"   Expected: {hash_value}")
            logger.error(f"   Actual:   {actual_hash}")
            logger.error(f"   Algorithm: {algo.upper()}")
            logger.error(f"   File: {self.file_path}")
            raise ValueError(
                f"Digest mismatch!\nExpected: {hash_value}\nActual:   {actual_hash}"
            )

        logger.debug("✅ Digest verification PASSED!")
        logger.debug(f"   Algorithm: {algo.upper()}")
        logger.debug(f"   Hash: {actual_hash}")

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
        logger.debug(f"   Expected hash: {expected_hash}")

        logger.debug(f"🧮 Computing {hash_type.upper()} hash...")
        actual_hash = self.compute_hash(hash_type)
        logger.debug(f"   Computed hash: {actual_hash}")

        if actual_hash.lower() != expected_hash.lower():
            logger.error(f"❌ {hash_type.upper()} verification FAILED!")
            logger.error(f"   Expected: {expected_hash}")
            logger.error(f"   Actual:   {actual_hash}")
            logger.error(f"   File: {self.file_path}")
            raise ValueError(
                f"{hash_type.upper()} mismatch!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )

        logger.debug(f"✅ {hash_type.upper()} verification PASSED!")
        logger.debug(f"   Hash: {actual_hash}")

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
            logger.error(f"❌ File not found: {self.file_path}")
            raise FileNotFoundError(f"File not found: {self.file_path}")

        hash_algorithms = {
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
            "md5": hashlib.md5,
        }

        if hash_type not in hash_algorithms:
            logger.error(f"❌ Unsupported hash type: {hash_type}")
            raise ValueError(f"Unsupported hash type: {hash_type}")

        logger.debug(f"🧮 Computing {hash_type.upper()} hash for {self.file_path.name}")

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
        logger.debug(f"   Hash: {computed_hash}")

        return computed_hash

    async def verify_from_checksum_file(
        self,
        checksum_url: str,
        hash_type: HashType,
        session: aiohttp.ClientSession,
        filename: str | None = None,
    ) -> None:
        """Verify file using remote checksum file.

        Args:
            checksum_url: URL to the checksum file
            hash_type: Type of hash used in checksum file
            session: aiohttp session for downloading
            filename: Specific filename to look for (defaults to file_path.name)

        Raises:
            ValueError: If verification fails or checksum not found

        """
        target_filename = filename or self.file_path.name

        logger.debug(f"🔍 Starting checksum file verification for {self.file_path.name}")
        logger.debug(f"   Checksum URL: {checksum_url}")
        logger.debug(f"   Target filename: {target_filename}")
        logger.debug(f"   Hash type: {hash_type.upper()}")

        # Download checksum file
        logger.debug("📥 Downloading checksum file...")
        checksum_content = await self._download_checksum_file(checksum_url, session)
        logger.debug(f"   Downloaded {len(checksum_content)} characters")

        # Parse checksum file to find our file's hash
        logger.debug(f"🔍 Parsing checksum file for {target_filename}...")
        expected_hash = self._parse_checksum_file(checksum_content, target_filename, hash_type)

        if not expected_hash:
            logger.error(f"❌ Hash for {target_filename} not found in checksum file")
            logger.debug(f"   Checksum file content:\n{checksum_content}")
            raise ValueError(f"Hash for {target_filename} not found in checksum file")

        logger.debug("✅ Found expected hash in checksum file")
        logger.debug(f"   Expected hash: {expected_hash}")

        # Verify the hash
        self.verify_hash(expected_hash, hash_type)

    async def _download_checksum_file(
        self, checksum_url: str, session: aiohttp.ClientSession
    ) -> str:
        """Download checksum file content.

        Args:
            checksum_url: URL to the checksum file
            session: aiohttp session for downloading

        Returns:
            Content of the checksum file

        Raises:
            aiohttp.ClientError: If download fails

        """
        headers = GitHubAuthManager.apply_auth({})

        try:
            async with session.get(checksum_url, headers=headers) as response:
                response.raise_for_status()
                content = await response.text()

                logger.debug("📄 Checksum file downloaded successfully")
                logger.debug(f"   Status: {response.status}")
                logger.debug(f"   Content length: {len(content)} characters")
                logger.debug(
                    f"   Content preview: {content[:200]}{'...' if len(content) > 200 else ''}"
                )

                return content

        except Exception as e:
            logger.error(f"❌ Failed to download checksum file: {e}")
            logger.error(f"   URL: {checksum_url}")
            raise

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
        lines = content.strip().split("\n")
        logger.debug(f"🔍 Parsing {len(lines)} lines in checksum file")

        found_entries = []

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#"):
                logger.debug(f"   Line {line_num}: Skipping (empty or comment)")
                continue

            logger.debug(f"   Line {line_num}: {line}")

            # Handle different checksum file formats
            hash_value = None
            file_name = None

            if self._is_sha256sums_format(line):
                hash_value, file_name = self._parse_sha256sums_line(line)
                logger.debug("      Format: SHA256SUMS")
            elif self._is_yml_format(line, hash_type):
                hash_value, file_name = self._parse_yml_line(line, filename)
                logger.debug("      Format: YAML")
            else:
                # Try generic "hash filename" format
                parts = line.split()
                if len(parts) >= 2:
                    hash_value, file_name = parts[0], parts[1]
                    logger.debug("      Format: Generic")
                else:
                    logger.debug("      Format: Unknown/Invalid")
                    continue

            if hash_value and file_name:
                logger.debug(f"      Parsed hash: {hash_value}")
                logger.debug(f"      Parsed filename: {file_name}")
                found_entries.append((hash_value, file_name, Path(file_name).name))

            # Remove path separators and compare just the filename
            if file_name and Path(file_name).name == filename:
                logger.debug(f"✅ Found matching entry for {filename}")
                logger.debug(f"   Hash: {hash_value}")
                logger.debug(f"   Full filename in checksum: {file_name}")
                return hash_value

        logger.warning(f"⚠️  Target file {filename} not found in checksum file")
        logger.debug(f"   Found {len(found_entries)} entries:")
        for hash_val, full_name, base_name in found_entries:
            logger.debug(f"      • {base_name} (full: {full_name}) -> {hash_val[:16]}...")

        return None

    def _is_sha256sums_format(self, line: str) -> bool:
        """Check if line is in SHA256SUMS format."""
        parts = line.split()
        return len(parts) >= 2 and len(parts[0]) == 64

    def _parse_sha256sums_line(self, line: str) -> tuple[str, str]:
        """Parse SHA256SUMS format line."""
        parts = line.split(None, 1)
        return parts[0], parts[1].strip("*")

    def _is_yml_format(self, line: str, hash_type: HashType) -> bool:
        """Check if line is in YAML format (e.g., latest-linux.yml)."""
        return f"{hash_type}:" in line.lower()

    def _parse_yml_line(self, line: str, filename: str) -> tuple[str, str]:
        """Parse YAML format line."""
        if ":" in line:
            _, hash_value = line.split(":", 1)
            return hash_value.strip(), filename
        return "", ""

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
        logger.debug(f"🔍 Verifying file size for {self.file_path.name}")
        logger.debug(
            f"   Expected size: {format_bytes(expected_size)} ({expected_size:,} bytes)"
        )

        actual_size = self.get_file_size()
        logger.debug(f"   Actual size: {format_bytes(actual_size)} ({actual_size:,} bytes)")

        if actual_size != expected_size:
            logger.error("❌ File size verification FAILED!")
            logger.error(
                f"   Expected: {format_bytes(expected_size)} ({expected_size:,} bytes)"
            )
            logger.error(f"   Actual: {format_bytes(actual_size)} ({actual_size:,} bytes)")
            logger.error(f"   Difference: {actual_size - expected_size:+,} bytes")
            raise ValueError(
                f"File size mismatch!\n"
                f"Expected: {expected_size} bytes\n"
                f"Actual:   {actual_size} bytes"
            )

        logger.debug("✅ File size verification PASSED!")
        logger.debug(f"   Size: {format_bytes(actual_size)} ({actual_size:,} bytes)")


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
        logger.debug(f"   Digest verification: {digest}")
        logger.debug(f"   Skip verification: {skip}")
        logger.debug(f"   Checksum file: {checksum_file or 'None'}")
        logger.debug(f"   Checksum hash type: {checksum_hash_type}")
        logger.debug(f"   Verify size: {verify_size}")

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
        logger.debug(f"   Source data: {data}")

        return config


def log_verification_summary(
    file_path: Path,
    app_config: dict[str, Any] | None = None,
    verification_performed: dict[str, Any] | None = None,
) -> None:
    """Log a comprehensive verification summary for debugging.

    Args:
        file_path: Path to the verified file
        app_config: Application configuration (for stored hash info)
        verification_performed: Dictionary of verification results

    """
    logger.debug(f"📋 Verification Summary for {file_path.name}")
    logger.debug("=" * 60)

    # File information
    if file_path.exists():
        file_size = file_path.stat().st_size
        logger.debug(f"📁 File: {file_path}")
        logger.debug(f"💾 Size: {format_bytes(file_size)} ({file_size:,} bytes)")
    else:
        logger.warning(f"⚠️  File not found: {file_path}")
        return

    # App config information
    if app_config:
        appimage_info = app_config.get("appimage", {})
        verification_info = app_config.get("verification", {})

        logger.debug("📦 App Info:")
        logger.debug(f"   Name: {appimage_info.get('name', 'Unknown')}")
        logger.debug(f"   Version: {appimage_info.get('version', 'Unknown')}")
        logger.debug(f"   Installed: {appimage_info.get('installed_date', 'Unknown')}")

        stored_digest = appimage_info.get("digest", "")
        if stored_digest:
            logger.debug(f"🔐 Stored Digest: {stored_digest}")

        logger.debug("⚙️  Verification Config:")
        logger.debug(f"   Digest enabled: {verification_info.get('digest', False)}")
        logger.debug(f"   Skip verification: {verification_info.get('skip', False)}")
        logger.debug(f"   Checksum file: {verification_info.get('checksum_file', 'None')}")
        logger.debug(f"   Hash type: {verification_info.get('checksum_hash_type', 'sha256')}")

    # Verification results
    if verification_performed:
        logger.debug("✅ Verification Results:")
        for check_type, result in verification_performed.items():
            status = "✅ PASSED" if result.get("passed", False) else "❌ FAILED"
            logger.debug(f"   {check_type}: {status}")
            if "hash" in result:
                logger.debug(f"      Digest/Hash: {result['hash']}")
            if "details" in result:
                logger.debug(f"      Details: {result['details']}")

    logger.debug("=" * 60)
