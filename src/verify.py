"""Backwards compatibility module for AppImage verification.

This module provides backwards compatibility by re-exporting the new
modular VerificationManager while maintaining the same interface.
"""

# Re-export the new modular verification system
from src.verification import VerificationManager

# Re-export constants for backwards compatibility
from src.verification.config import SUPPORTED_HASH_TYPES
from src.verification.logger import STATUS_SUCCESS, STATUS_FAIL

__all__ = [
    "VerificationManager",
    "SUPPORTED_HASH_TYPES", 
    "STATUS_SUCCESS",
    "STATUS_FAIL"
]