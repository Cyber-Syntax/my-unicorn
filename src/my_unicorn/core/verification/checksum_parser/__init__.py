"""Checksum file parsing utilities.

This module extracts checksum parsing responsibilities from :class:`Verifier`
so hash computation and parsing concerns remain separate.

The module includes encoding detection to differentiate between hexadecimal
and base64-encoded hashes, preventing corruption when normalizing hash values.
Hex detection is performed first to avoid incorrectly decoding hex hashes that
contain only valid base64 characters (e.g., "deadbeef12345678...").
"""

from __future__ import annotations

from my_unicorn.core.verification.checksum_parser.base import (
    ChecksumEntry,
    ChecksumFileResult,
    ChecksumParser,
)
from my_unicorn.core.verification.checksum_parser.bsd_parser import (
    BSDChecksumParser,
)
from my_unicorn.core.verification.checksum_parser.detector import (
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_all_checksums,
    parse_checksum_file,
)
from my_unicorn.core.verification.checksum_parser.normalizer import (
    convert_base64_to_hex,
)
from my_unicorn.core.verification.checksum_parser.traditional_parser import (
    StandardChecksumParser,
)
from my_unicorn.core.verification.checksum_parser.yaml_parser import (
    YAMLChecksumParser,
)

__all__ = [
    "BSDChecksumParser",
    "ChecksumEntry",
    "ChecksumFileResult",
    "ChecksumParser",
    "StandardChecksumParser",
    "YAMLChecksumParser",
    "convert_base64_to_hex",
    "detect_hash_type_from_checksum_filename",
    "find_checksum_entry",
    "parse_all_checksums",
    "parse_checksum_file",
]
