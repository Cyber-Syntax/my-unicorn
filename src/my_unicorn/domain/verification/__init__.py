"""Simplified verification module for AppImage integrity checking.

This module provides a streamlined API for verifying downloaded AppImages
using digest verification and checksum file verification methods.
"""

from my_unicorn.domain.verification.service import (
    MethodResult,
    VerificationConfig,
    VerificationResult,
    VerificationService,
)
from my_unicorn.domain.verification.verifier import Verifier

__all__ = [
    "MethodResult",
    "VerificationConfig",
    "VerificationResult",
    "VerificationService",
    "Verifier",
]
