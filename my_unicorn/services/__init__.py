"""Shared services package for eliminating code duplication."""

from my_unicorn.github_client import ChecksumFileInfo
from .icon_service import IconConfig, IconResult, IconService
from .verification_service import VerificationConfig, VerificationResult, VerificationService

__all__ = [
    "ChecksumFileInfo",
    "IconConfig",
    "IconResult",
    "IconService",
    "VerificationConfig",
    "VerificationResult",
    "VerificationService",
]
