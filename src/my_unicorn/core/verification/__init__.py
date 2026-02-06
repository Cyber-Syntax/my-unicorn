"""Simplified verification module for AppImage integrity checking.

This module provides a streamlined API for verifying downloaded AppImages
using digest verification and checksum file verification methods.
"""

from my_unicorn.core.verification.checksum_parser import (
    ChecksumEntry,
    detect_hash_type_from_checksum_filename,
    find_checksum_entry,
    parse_checksum_file,
)
from my_unicorn.core.verification.context import VerificationConfig
from my_unicorn.core.verification.results import (
    MethodResult,
    VerificationResult,
)
from my_unicorn.core.verification.service import VerificationService
from my_unicorn.core.verification.verifier import Verifier

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
