"""Verification package for AppImage hash verification.

This package provides modular components for verifying AppImage integrity
using various hash verification methods including SHA files, asset digests,
release description checksums, and extracted checksums.

Example:
    # Traditional SHA file verification
    from src.verification import VerificationManager

    manager = VerificationManager(
        appimage_name="app.AppImage",
        checksum_hash_type="sha256",
        checksum_file_download_url="https://example.com/checksums.sha256"
    )
    is_valid = manager.verify_appimage()

    # Release description checksum verification
    from src.verification import ReleaseDescVerifier

    # With known repository info
    verifier = ReleaseDescVerifier("owner", "repo")
    is_valid = verifier.verify_appimage("/path/to/app.AppImage")

    # With auto-detection
    is_valid = ReleaseDescVerifier.verify_appimage_standalone("/path/to/app.AppImage")
"""

from src.verification.manager import VerificationManager
from src.verification.release_desc_verifier import ReleaseDescVerifier

__all__ = ["VerificationManager", "ReleaseDescVerifier"]
