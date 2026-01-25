"""Verifier class for AppImage integrity checking.

This module provides the core Verifier class that handles hash computation
and digest verification for downloaded AppImages.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    SUPPORTED_HASH_ALGORITHMS,
    HashType,
)
from my_unicorn.core.verification.checksum_parser import (
    convert_base64_to_hex,
    detect_hash_type_from_checksum_filename,
    parse_checksum_file,
)
from my_unicorn.logger import get_logger

if TYPE_CHECKING:
    from pathlib import Path

    from my_unicorn.core.download import DownloadService

logger = get_logger(__name__)

BYTES_PER_UNIT = 1024.0


def format_bytes(num_bytes: float) -> str:
    """Convert a byte count to a human-readable string.

    Uses binary multiples (KiB, MiB, GiB, ...) with one decimal place.
    Raises ``ValueError`` if the input is negative to avoid silent errors.
    """

    if num_bytes < 0:
        message = "Byte size cannot be negative"
        raise ValueError(message)

    units = ["B", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(num_bytes)
    unit_index = 0

    while size >= BYTES_PER_UNIT and unit_index < len(units) - 1:
        size /= BYTES_PER_UNIT
        unit_index += 1

    return f"{size:.1f} {units[unit_index]}"


class Verifier:
    """Handles verification of downloaded AppImage files."""

    def __init__(self, file_path: Path) -> None:
        """Create verifier for a downloaded file."""
        self.file_path: Path = file_path
        self._log_file_info()

    def _log_file_info(self) -> None:
        if self.file_path.exists():
            file_size = self.file_path.stat().st_size
            logger.debug("📁 File info: %s", self.file_path.name)
            logger.debug("   Path: %s", self.file_path)
            logger.debug(
                "   Size: %s (%s bytes)",
                format_bytes(file_size),
                f"{file_size:,}",
            )
        else:
            logger.warning("⚠️  File does not exist: %s", self.file_path)

    def verify_digest(self, expected_digest: str) -> None:
        """Verify file against GitHub API digest format."""
        logger.debug(
            "🔍 Starting digest verification for %s", self.file_path.name
        )
        logger.debug("   Expected digest: %s", expected_digest)

        if not expected_digest:
            message = "Digest cannot be empty"
            logger.error("❌ %s", message)
            raise ValueError(message)

        algo, _, hash_value = expected_digest.partition(":")
        if not hash_value:
            message = f"Invalid digest format: {expected_digest}"
            logger.error("❌ %s", message)
            raise ValueError(message)

        if algo not in SUPPORTED_HASH_ALGORITHMS:
            message = f"Unsupported digest algorithm: {algo}"
            logger.error("❌ %s", message)
            raise ValueError(message)

        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Expected hash: %s", hash_value)

        logger.debug("🧮 Computing %s hash...", algo.upper())
        actual_hash = self.compute_hash(algo)  # type: ignore[arg-type]
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != hash_value.lower():
            message = (
                "Digest mismatch!\n"
                f"Expected: {hash_value}\n"
                f"Actual:   {actual_hash}"
            )
            logger.error("❌ Digest verification FAILED!")
            logger.error("   Expected: %s", hash_value)
            logger.error("   Actual:   %s", actual_hash)
            logger.error("   Algorithm: %s", algo.upper())
            logger.error("   File: %s", self.file_path)
            raise ValueError(message)

        logger.debug("✅ Digest verification PASSED!")
        logger.debug("   Algorithm: %s", algo.upper())
        logger.debug("   Hash: %s", actual_hash)

    def verify_hash(self, expected_hash: str, hash_type: HashType) -> None:
        """Verify file using a specific hash algorithm."""
        logger.debug(
            "🔍 Starting %s hash verification for %s",
            hash_type.upper(),
            self.file_path.name,
        )
        logger.debug("   Expected hash: %s", expected_hash)

        logger.debug("🧮 Computing %s hash...", hash_type.upper())
        actual_hash = self.compute_hash(hash_type)
        logger.debug("   Computed hash: %s", actual_hash)

        if actual_hash.lower() != expected_hash.lower():
            message = (
                f"{hash_type.upper()} mismatch!\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}"
            )
            logger.error("❌ %s verification FAILED!", hash_type.upper())
            logger.error("   Expected: %s", expected_hash)
            logger.error("   Actual:   %s", actual_hash)
            logger.error("   File: %s", self.file_path)
            raise ValueError(message)

        logger.debug("✅ %s verification PASSED!", hash_type.upper())
        logger.debug("   Hash: %s", actual_hash)

    def compute_hash(self, hash_type: HashType) -> str:
        """Compute a hash for the target file using the given algorithm."""
        if not self.file_path.exists():
            message = f"File not found: {self.file_path}"
            logger.error("❌ %s", message)
            raise FileNotFoundError(message)

        hash_algorithms = {
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
            "md5": hashlib.md5,
        }

        if hash_type not in hash_algorithms:
            message = f"Unsupported hash type: {hash_type}"
            logger.error("❌ %s", message)
            raise ValueError(message)

        logger.debug(
            "🧮 Computing %s hash for %s",
            hash_type.upper(),
            self.file_path.name,
        )

        hasher = hash_algorithms[hash_type]()
        bytes_processed = 0
        chunk_size = 8192

        with self.file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                hasher.update(chunk)
                bytes_processed += len(chunk)

        computed_hash = hasher.hexdigest()

        logger.debug(
            "   Processed: %s (%d bytes)",
            format_bytes(bytes_processed),
            bytes_processed,
        )
        logger.debug("   Hash: %s", computed_hash)

        return computed_hash

    async def verify_from_checksum_file(
        self,
        checksum_url: str,
        hash_type: HashType,
        download_service: DownloadService,
        filename: str | None = None,
    ) -> None:
        """Verify the file using a downloaded checksum file."""
        target_filename = filename or self.file_path.name

        logger.debug(
            "🔍 Starting checksum file verification for %s",
            self.file_path.name,
        )
        logger.debug("   Checksum URL: %s", checksum_url)
        logger.debug("   Target filename: %s", target_filename)
        logger.debug("   Hash type: %s", hash_type.upper())

        checksum_content = await download_service.download_checksum_file(
            checksum_url
        )
        logger.debug("   Downloaded %d characters", len(checksum_content))

        expected_hash = parse_checksum_file(
            checksum_content, target_filename, hash_type
        )

        if not expected_hash:
            message = f"Hash for {target_filename} not found in checksum file"
            logger.error("❌ %s", message)
            logger.debug("   Checksum file content:\n%s", checksum_content)
            raise ValueError(message)

        logger.debug("✅ Found expected hash in checksum file")
        logger.debug("   Expected hash: %s", expected_hash)

        self.verify_hash(expected_hash, hash_type)

    def parse_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Expose checksum parsing for callers that already fetched content."""
        return parse_checksum_file(content, filename, hash_type)

    def detect_hash_type_from_filename(self, filename: str) -> HashType:
        """Infer hash type from checksum filename, defaulting when unknown."""
        detected = detect_hash_type_from_checksum_filename(filename)
        return detected if detected else DEFAULT_HASH_TYPE

    def _convert_base64_to_hex(self, base64_hash: str) -> str:
        """Convert a base64-encoded digest into hexadecimal."""
        return convert_base64_to_hex(base64_hash)
