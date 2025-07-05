"""Backwards compatibility module for AppImage verification.

This module provides backwards compatibility by re-exporting the new
modular VerificationManager while maintaining the same interface.
"""

# Re-export the new modular verification system
from my_unicorn.verification import VerificationManager

# Re-export constants for backwards compatibility
from my_unicorn.verification.config import SUPPORTED_checksum_hash_typeS
from my_unicorn.verification.logger import STATUS_SUCCESS, STATUS_FAIL

__all__ = ["VerificationManager", "SUPPORTED_checksum_hash_typeS", "STATUS_SUCCESS", "STATUS_FAIL"]
