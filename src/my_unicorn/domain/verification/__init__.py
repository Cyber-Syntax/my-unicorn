"""Simplified verification module for AppImage integrity checking.

This module provides a streamlined API for verifying downloaded AppImages
using digest verification and checksum file verification methods.
"""

from my_unicorn.domain.verification.checksum_parser import (
    ChecksumEntry,
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_checksum_file,
)
from my_unicorn.domain.verification.service import (
    MethodResult,
    VerificationConfig,
    VerificationResult,
    VerificationService,
)
from my_unicorn.domain.verification.verifier import Verifier

__all__ = [
    "ChecksumEntry",
    "MethodResult",
    "VerificationConfig",
    "VerificationResult",
    "VerificationService",
    "Verifier",
    "detect_hash_type_from_checksum_filename",
    "find_checksum_entry",
    "parse_checksum_file",
]
