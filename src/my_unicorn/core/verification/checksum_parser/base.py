"""Base classes and dataclasses for checksum parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from my_unicorn.constants import HashType


@dataclass(frozen=True)
class ChecksumEntry:
    """Parsed checksum entry."""

    filename: str
    hash_value: str
    algorithm: HashType


@dataclass(frozen=True)
class ChecksumFileResult:
    """Complete parsed checksum file data for caching.

    Attributes:
        source: Download URL for the checksum file.
        filename: Filename of the checksum file.
        algorithm: Hash algorithm used (SHA256, SHA512).
        hashes: Mapping of asset filename to hash value.

    """

    source: str
    filename: str
    algorithm: str
    hashes: dict[str, str]

    def to_cache_dict(self) -> dict[str, str | dict[str, str]]:
        """Convert to dictionary format for cache storage.

        Returns:
            Dictionary with source, filename, algorithm, and hashes fields.

        """
        return {
            "source": self.source,
            "filename": self.filename,
            "algorithm": self.algorithm,
            "hashes": self.hashes,
        }


class ChecksumParser:
    """Abstract base class for parsing checksum files.

    This class defines the interface for parsers that extract checksum
    information from various checksum file formats (e.g., SHA256SUMS,
    BSD checksums, YAML checksums). Concrete implementations must
    override the parse method to handle specific formats.

    The parser is responsible for finding the hash value for a given
    filename within the checksum content and returning it as a
    ChecksumEntry object.
    """

    def parse(
        self, content: str, filename: str, hash_type: HashType | None = None
    ) -> ChecksumEntry | None:
        """Parse checksum content for a specific file.

        Args:
            content: The checksum file content.
            filename: The filename to find.
            hash_type: Optional expected hash type.

        Returns:
            A ChecksumEntry or None if not found.
        """
        raise NotImplementedError
