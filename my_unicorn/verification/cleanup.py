"""Cleanup operations for AppImage verification.

This module handles cleanup of verification files, failed downloads,
and provides utilities for maintaining a clean verification environment.
"""

import logging
import os
from pathlib import Path
from typing import Any

from my_unicorn.utils.cleanup_utils import (
    cleanup_failed_verification_files,
    cleanup_single_failed_file,
    remove_single_file,
)


class VerificationCleanup:
    """Manages cleanup operations for verification processes."""

    def __init__(self) -> None:
        """Initialize the verification cleanup manager."""
        pass

    def cleanup_verification_file(self, sha_path: str | None) -> bool:
        """Remove SHA file after verification to keep the system clean.

        Args:
            sha_path: Path to the SHA file to remove

        Returns:
            True if cleanup succeeded or file didn't exist, False otherwise
        """
        if not sha_path or not os.path.exists(sha_path):
            logging.debug("No SHA file to clean up: %s", sha_path)
            return True

        return remove_single_file(sha_path, verbose=False)

    def cleanup_failed_file(self, filepath: str, ask_confirmation: bool = True) -> bool:
        """Remove a file that failed verification.

        Args:
            filepath: Path to the file that failed verification
            ask_confirmation: Whether to ask user for confirmation before removal

        Returns:
            True if cleanup succeeded or was declined, False on error
        """
        return cleanup_single_failed_file(
            filepath=filepath, ask_confirmation=ask_confirmation, verbose=True
        )

    def cleanup_batch_failed_files(
        self,
        app_name: str,
        appimage_name: str | None = None,
        checksum_file_name: str | None = None,
        ask_confirmation: bool = True,
    ) -> list[str]:
        """Clean up AppImage and SHA files for batch operations when update fails.

        This method is designed for use by update commands when multiple apps
        are being processed and individual verification failures need cleanup.

        Args:
            app_name: Name of the app to clean up files for
            appimage_name: Exact AppImage filename if known, otherwise use patterns
            checksum_file_name: Exact SHA filename if known, otherwise use patterns
            ask_confirmation: Whether to ask user for confirmation before removal

        Returns:
            list of file paths that were successfully removed
        """
        return cleanup_failed_verification_files(
            app_name=app_name,
            appimage_name=appimage_name,
            checksum_file_name=checksum_file_name,
            ask_confirmation=ask_confirmation,
            verbose=True,
        )

    def cleanup_on_failure(
        self, appimage_path: str | None, sha_path: str | None = None, ask_confirmation: bool = True
    ) -> None:
        """Cleanup files when verification fails.

        Args:
            appimage_path: Path to the AppImage file to cleanup
            sha_path: Path to the SHA file to cleanup (optional)
            ask_confirmation: Whether to ask for user confirmation
        """
        if appimage_path:
            self.cleanup_failed_file(appimage_path, ask_confirmation)

        if sha_path:
            self.cleanup_verification_file(sha_path)

    def ensure_clean_verification_environment(self, downloads_dir: str, app_name: str) -> None:
        """Ensure the verification environment is clean before starting.

        This removes any leftover files from previous failed verification attempts.

        Args:
            downloads_dir: Directory where downloads are stored
            app_name: Name of the app being verified
        """
        downloads_path = Path(downloads_dir)

        # Look for leftover SHA files for this app
        sha_patterns = [
            f"{app_name}_*.sha256",
            f"{app_name}_*.sha512",
            f"{app_name}_*.yml",
            f"{app_name}_*.yaml",
        ]

        for pattern in sha_patterns:
            for file_path in downloads_path.glob(pattern):
                try:
                    file_path.unlink()
                    logging.debug("Removed leftover verification file: %s", file_path)
                except OSError as e:
                    logging.warning("Could not remove leftover file %s: %s", file_path, e)
