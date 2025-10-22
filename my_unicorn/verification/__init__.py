"""Simplified verification module for AppImage integrity checking.

This module provides a streamlined API for verifying downloaded AppImages
using digest verification and checksum file verification methods.
"""

from my_unicorn.verification.service import (
    VerificationConfig,
    VerificationResult,
    VerificationService,
)
from my_unicorn.verification.verifier import Verifier

__all__ = [
    "Verifier",
    "VerificationService",
    "VerificationResult",
    "VerificationConfig",
]
