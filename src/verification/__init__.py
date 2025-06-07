"""Verification package for AppImage hash verification.

This package provides modular components for verifying AppImage integrity
using various hash verification methods including SHA files, asset digests,
and extracted checksums.

Example:
    from src.verification import VerificationManager

    manager = VerificationManager(
        appimage_name="app.AppImage",
        hash_type="sha256",
        sha_url="https://example.com/checksums.sha256"
    )
    is_valid = manager.verify_appimage()
"""

from src.verification.manager import VerificationManager

__all__ = ["VerificationManager"]
