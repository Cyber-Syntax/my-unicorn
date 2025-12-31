"""Verifier class for AppImage integrity checking.

This module provides the core Verifier class that handles hash computation,
digest verification, and checksum file parsing for downloaded AppImages.
"""

import base64
import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

from my_unicorn.constants import (
    DEFAULT_HASH_TYPE,
    HASH_PREFERENCE_ORDER,
    SUPPORTED_HASH_ALGORITHMS,
    YAML_DEFAULT_HASH,
    HashType,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils import format_bytes

if TYPE_CHECKING:
    from my_unicorn.download import DownloadService


# Try to import yaml for YAML checksum file support
try:
    import yaml

    _YAML_AVAILABLE = True
except ImportError:
    yaml = None
    _YAML_AVAILABLE = False


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
            logger.debug(
                "   Size: %s (%s bytes)",
                format_bytes(file_size),
                f"{file_size:,}",
            )
        else:
            logger.warning("⚠️  File does not exist: %s", self.file_path)

    def verify_digest(self, expected_digest: str) -> None:
        """Verify file using GitHub API digest format.

        Args:
            expected_digest: Digest in format "algorithm:hash"

        Raises:
            ValueError: If digest format is invalid or verification fails

        """
        logger.debug(
            "🔍 Starting digest verification for %s", self.file_path.name
        )
        logger.debug("   Expected digest: %s", expected_digest)

        if not expected_digest:
            logger.error("❌ Digest cannot be empty")
            raise ValueError("Digest cannot be empty")

        algo, _, hash_value = expected_digest.partition(":")
        if not hash_value:
            logger.error("❌ Invalid digest format: %s", expected_digest)
            raise ValueError(f"Invalid digest format: {expected_digest}")

        if algo not in SUPPORTED_HASH_ALGORITHMS:
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
                f"Digest mismatch!\nExpected: {hash_value}\n"
                f"Actual:   {actual_hash}"
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
            "🔍 Starting %s hash verification for %s",
            hash_type.upper(),
            self.file_path.name,
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

        logger.debug(
            "🧮 Computing %s hash for %s",
            hash_type.upper(),
            self.file_path.name,
        )

        hasher = hash_algorithms[hash_type]()
        bytes_processed = 0
        chunk_size = 8192

        with open(self.file_path, "rb") as f:
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
        download_service: "DownloadService",
        filename: str | None = None,
    ) -> None:
        """Verify file using remote checksum file.

        Args:
            checksum_url: URL to the checksum file
            hash_type: Type of hash used in checksum file
            download_service: DownloadService for downloading file
            filename: Specific filename to look for (default: file_path.name)

        Raises:
            ValueError: If verification fails or checksum not found

        """
        target_filename = filename or self.file_path.name

        logger.debug(
            "🔍 Starting checksum file verification for %s",
            self.file_path.name,
        )
        logger.debug("   Checksum URL: %s", checksum_url)
        logger.debug("   Target filename: %s", target_filename)
        logger.debug("   Hash type: %s", hash_type.upper())

        # Download checksum file
        logger.debug("📥 Downloading checksum file...")
        checksum_content = await download_service.download_checksum_file(
            checksum_url
        )
        logger.debug("   Downloaded %d characters", len(checksum_content))

        # Parse checksum file to find our file's hash
        logger.debug("🔍 Parsing checksum file for %s...", target_filename)
        expected_hash = self._parse_checksum_file(
            checksum_content, target_filename, hash_type
        )

        if not expected_hash:
            logger.error(
                "❌ Hash for %s not found in checksum file", target_filename
            )
            logger.debug("   Checksum file content:\n%s", checksum_content)
            raise ValueError(
                f"Hash for {target_filename} not found in checksum file"
            )

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
        return self._parse_traditional_checksum_file(
            content, filename, hash_type
        )

    def _is_yaml_content(self, content: str) -> bool:
        """Detect if content is YAML format.

        Args:
            content: File content to check

        Returns:
            True if content appears to be YAML, False otherwise

        """
        if not _YAML_AVAILABLE:
            return False

        # Quick heuristic checks before attempting YAML parsing
        content_stripped = content.strip()

        # Empty content is not YAML
        if not content_stripped:
            return False

        # Check for YAML indicators
        yaml_indicators = [
            "version:",  # Common YAML key
            "files:",  # Common YAML key for checksum files
            "\n  ",  # Indentation is common in YAML
        ]

        has_yaml_indicator = any(
            indicator in content_stripped for indicator in yaml_indicators
        )

        # Check for traditional checksum format indicators
        lines = content_stripped.split("\n")
        if lines:
            first_line = lines[0].strip()
            # Traditional format: "hash filename" or "hash *filename"
            # Hash is typically 32 (MD5), 40 (SHA1), 64 (SHA256),
            # or 128 (SHA512) hex chars
            min_parts = 2
            parts = first_line.split()
            if len(parts) >= min_parts:
                potential_hash = parts[0]
                # Check if first part looks like a hash
                # (hex string of expected length)
                if len(potential_hash) in {32, 40, 64, 128} and all(
                    c in "0123456789abcdefABCDEF" for c in potential_hash
                ):
                    # This looks like a traditional checksum file
                    return False

        # If we found YAML indicators and no strong traditional indicators,
        # try parsing as YAML
        if has_yaml_indicator:
            try:
                data = yaml.safe_load(content_stripped)
                # Valid YAML that's also a dict with expected structure
                if isinstance(data, dict) and (
                    "files" in data or "version" in data
                ):
                    logger.debug("   Detected YAML format checksum file")
                    return True
            except yaml.YAMLError:
                # Not valid YAML
                return False

        return False

    def _try_hash_from_dict(self, data: dict, context: str = "") -> str | None:
        """Extract hash from dict trying preferred algorithms in order.

        Handles both direct hash values and nested hash dicts, converting
        base64 to hex when needed.

        Args:
            data: Dictionary containing hash key-value pairs
            context: Optional context string for logging

        Returns:
            Hex hash string or None if not found

        """
        for algo in HASH_PREFERENCE_ORDER:
            if algo in data:
                hash_value = data[algo]
                if context:
                    logger.debug("   Found %s hash %s", algo, context)
                return self._normalize_hash_value(hash_value)

        # Fallback: return first available hash if any
        if data:
            first_hash = next(iter(data.values()), None)
            if first_hash:
                return self._normalize_hash_value(first_hash)

        return None

    def _normalize_hash_value(self, hash_value: str) -> str:
        """Normalize hash value by removing prefix and converting base64.

        Args:
            hash_value: Raw hash value (may be prefixed or base64)

        Returns:
            Normalized hex hash string

        """
        if not isinstance(hash_value, str):
            return str(hash_value)

        # Remove algorithm prefix if present (e.g., "sha256:hash")
        if ":" in hash_value:
            _, _, hash_value = hash_value.partition(":")

        # Convert base64 to hex if needed
        try:
            return self._convert_base64_to_hex(hash_value)
        except ValueError:
            # If conversion fails, assume it's already hex
            return hash_value

    def _parse_yaml_checksum_file(
        self, content: str, filename: str
    ) -> str | None:
        """Parse YAML format checksum file.

        Delegates to specialized parsers based on YAML structure.

        Args:
            content: YAML content
            filename: Target filename to find

        Returns:
            Hash value or None if not found

        """
        if not _YAML_AVAILABLE:
            logger.warning("⚠️  YAML parsing not available")
            return None

        try:
            data = yaml.safe_load(content)
            logger.debug("   Parsed YAML checksum file")
            logger.debug("   Structure keys: %s", list(data.keys()))

            # Check for root-level hash first (e.g., path: file, sha512: hash)
            if "files" not in data:
                return self._parse_yaml_root_level(data, filename)

            files = data["files"]
            logger.debug("   Files section type: %s", type(files))
            logger.debug("   Looking for: %s", filename)

            # Delegate to specialized parsers based on files structure
            if isinstance(files, dict):
                return self._parse_yaml_files_dict(files, filename)
            if isinstance(files, list):
                return self._parse_yaml_files_list(files, filename)

            logger.debug("   Hash not found for %s in YAML", filename)
            return None

        except yaml.YAMLError as e:
            logger.error("❌ Failed to parse YAML checksum file: %s", e)
            return None

    def _parse_yaml_root_level(self, data: dict, filename: str) -> str | None:
        """Parse YAML with hash at root level (e.g., path: file, sha512: hash).

        Args:
            data: Parsed YAML data
            filename: Target filename to find

        Returns:
            Hash value or None if not found

        """
        logger.debug("   No 'files' section in YAML")
        if "path" in data and data["path"] == filename:
            logger.debug("   Found root-level hash structure")
            result = self._try_hash_from_dict(data, "at root level")
            if result:
                return result

        logger.debug("   No matching hash found at root level")
        return None

    def _parse_yaml_files_dict(self, files: dict, filename: str) -> str | None:
        """Parse YAML files dict structure: {filename: hash, ...}.

        Args:
            files: Files dict from YAML
            filename: Target filename to find

        Returns:
            Hash value or None if not found

        """
        hash_value = files.get(filename)
        if not hash_value:
            return None

        logger.debug("   Found hash in dict structure")

        if isinstance(hash_value, str):
            return self._normalize_hash_value(hash_value)
        if isinstance(hash_value, dict):
            return self._try_hash_from_dict(hash_value, "in nested dict")

        return None

    def _parse_yaml_files_list(self, files: list, filename: str) -> str | None:
        """Parse YAML files list structure: [{url: filename, sha512: value}, ...].

        Args:
            files: Files list from YAML
            filename: Target filename to find

        Returns:
            Hash value or None if not found

        """
        for file_entry in files:
            if not isinstance(file_entry, dict):
                continue

            # Check both 'name' and 'url' fields for filename match
            file_name = file_entry.get("name") or file_entry.get("url")
            if file_name != filename:
                continue

            logger.debug("   Found hash in list structure")

            # Try to get hash from various possible keys
            hash_value = (
                file_entry.get("hash")
                or file_entry.get(YAML_DEFAULT_HASH)
                or file_entry.get("sha256")
            )
            if hash_value:
                return self._normalize_hash_value(hash_value)

        return None

    def _parse_traditional_checksum_file(
        self, content: str, filename: str, hash_type: HashType
    ) -> str | None:
        """Parse traditional checksum file format.

        Supports multiple formats:
        - Standard: "hash  filename" or "hash *filename"
        - SHA256SUMS: "hash filename"
        - With paths: "hash  ./path/to/filename"

        Args:
            content: Checksum file content
            filename: Target filename to find
            hash_type: Type of hash being used

        Returns:
            Hash value or None if not found

        """
        logger.debug("   Parsing as traditional checksum file format")
        logger.debug("   Looking for: %s", filename)
        logger.debug("   Hash type: %s", hash_type)

        lines = content.strip().split("\n")
        logger.debug("   Total lines: %d", len(lines))

        # Pre-compute relaxed variants for target filename to allow
        # matching checksum files that omit build tokens (e.g. "-1").
        def _generate_variants(name: str) -> set[str]:
            variants = {name}
            # Remove numeric build tokens like '-1' that appear before
            # an architecture or before the extension, e.g.
            # 'KeePassXC-2.7.11-1-x86_64.AppImage' ->
            # 'KeePassXC-2.7.11-x86_64.AppImage'
            import re

            # pattern: hyphen + digits that are followed by -arch or .AppImage
            variants.update(
                re.sub(r"-\d+(?=-[a-z0-9_]+\.AppImage$)", "", name)
                for _ in (0,)  # single expression to use re.sub
            )
            # Also try removing any '-<number>' before the extension
            variants.add(re.sub(r"-\d+(?=\.AppImage$)", "", name))
            # Try removing build tokens anywhere (conservative)
            variants.add(re.sub(r"-\d+", "", name))

            # Strip duplicates and empty
            return {v for v in variants if v}

        target_variants = _generate_variants(filename)

        for line_num, raw_line in enumerate(lines, 1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue

            # Try to parse the line
            parsed = self._parse_sha256sums_line(line)
            if not parsed:
                continue

            hash_value, file_in_checksum = parsed

            logger.debug(
                "   Line %d: hash=%s... file=%s",
                line_num,
                hash_value[:16],
                file_in_checksum,
            )

            # Check if this is our file (match exact or basename)
            if file_in_checksum == filename or file_in_checksum.endswith(
                f"/{filename}"
            ):
                logger.debug("   ✅ Match found on line %d", line_num)
                logger.debug("   Hash: %s", hash_value)
                return hash_value

            # Relaxed matching: compare generated filename variants
            file_variants = _generate_variants(file_in_checksum)
            # If any variant intersects, treat as a match
            if target_variants.intersection(file_variants):
                logger.debug(
                    "   ⚠️ Relaxed match found on line %d (variants): %s",
                    line_num,
                    file_in_checksum,
                )
                logger.debug("   Hash: %s", hash_value)
                return hash_value

        logger.debug("   No match found for %s", filename)
        return None

    def _is_sha256sums_format(self, line: str) -> bool:
        """Check if line is in SHA256SUMS format.

        Args:
            line: Line to check

        Returns:
            True if line appears to be SHA256SUMS format

        """
        return " " in line and not line.startswith(" ")

    def _parse_sha256sums_line(self, line: str) -> tuple[str, str] | None:
        """Parse a single line from checksum file.

        Args:
            line: Line to parse

        Returns:
            Tuple of (hash, filename) or None if parsing fails

        """
        # Split on whitespace, expecting "hash filename" or "hash *filename"
        expected_parts = 2
        parts = line.split(None, 1)
        if len(parts) != expected_parts:
            return None

        hash_value = parts[0]
        filename_part = parts[1]

        # Remove binary mode indicator if present
        filename_part = filename_part.removeprefix("*")

        # Remove leading ./ if present
        filename_part = filename_part.removeprefix("./")

        return hash_value, filename_part

    def detect_hash_type_from_filename(self, filename: str) -> HashType:
        """Detect hash type from checksum filename.

        Args:
            filename: Checksum filename

        Returns:
            Detected hash type or default

        """
        detected = self._detect_hash_type_from_filename(filename)
        return detected if detected else DEFAULT_HASH_TYPE

    def _detect_hash_type_from_filename(
        self, filename: str
    ) -> HashType | None:
        """Detect hash type from checksum filename.

        Args:
            filename: Checksum filename

        Returns:
            Detected hash type or None

        """
        filename_lower = filename.lower()

        # Check for explicit hash type in filename
        hash_patterns = {
            "sha512": ["sha512", "sha-512"],
            "sha256": ["sha256", "sha-256"],
            "sha1": ["sha1", "sha-1"],
            "md5": ["md5"],
        }

        for hash_type, patterns in hash_patterns.items():
            if any(pattern in filename_lower for pattern in patterns):
                logger.debug(
                    "   Detected %s hash type from filename", hash_type
                )
                return hash_type  # type: ignore[return-value]

        return None

    def _convert_base64_to_hex(self, base64_hash: str) -> str:
        """Convert base64 encoded hash to hexadecimal.

        Args:
            base64_hash: Base64 encoded hash

        Returns:
            Hexadecimal hash string

        Raises:
            ValueError: If base64 decoding fails

        """
        try:
            # Decode base64
            hash_bytes = base64.b64decode(base64_hash)
            # Convert to hex
            hex_hash = hash_bytes.hex()
            logger.debug("   Converted base64 to hex: %s", hex_hash)
            return hex_hash
        except Exception as e:
            logger.error("❌ Failed to convert base64 to hex: %s", e)
            raise ValueError(f"Invalid base64 hash: {base64_hash}") from e
