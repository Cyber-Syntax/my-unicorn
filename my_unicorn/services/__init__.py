"""Shared services package for eliminating code duplication."""

from .icon_service import IconConfig, IconResult, IconService
from .verification_service import VerificationConfig, VerificationResult, VerificationService

__all__ = [
    "IconConfig",
    "IconResult",
    "IconService",
    "VerificationConfig",
    "VerificationResult",
    "VerificationService",
]
