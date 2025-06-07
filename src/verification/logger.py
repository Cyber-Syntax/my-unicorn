"""Logging and user feedback for AppImage verification.

This module provides structured logging and user feedback functionality
for verification operations, including status messages and comparison results.
"""

import gettext
import logging
from typing import Any

_ = gettext.gettext

# Status indicators
STATUS_SUCCESS = "✓ "  # Unicode check mark
STATUS_FAIL = "✗ "  # Unicode cross mark


class VerificationLogger:
    """Handles logging and user feedback for verification operations."""

    def __init__(self) -> None:
        """Initialize the verification logger."""
        pass

    def log_verification_start(self, appimage_name: str, hash_type: str) -> None:
        """Log the start of verification process.

        Args:
            appimage_name: Name of the AppImage being verified
            hash_type: Type of hash being used for verification
        """
        logging.info(f"Starting verification of {appimage_name} using {hash_type}")

    def log_verification_skipped(self, reason: str) -> None:
        """Log and print when verification is skipped.

        Args:
            reason: Reason why verification was skipped
        """
        message = f"Note: Verification skipped - {reason}"
        logging.info(message)
        print(message)

    def log_hash_comparison(
        self,
        appimage_name: str | None,
        hash_type: str,
        actual_hash: str,
        expected_hash: str,
        is_verified: bool,
    ) -> None:
        """Log hash comparison results with detailed information.

        Args:
            appimage_name: Name of the AppImage file
            hash_type: Hash algorithm used
            actual_hash: Calculated hash value
            expected_hash: Expected hash value
            is_verified: Whether verification passed
        """
        status = STATUS_SUCCESS if is_verified else STATUS_FAIL
        status_text = _("VERIFIED") if is_verified else _("VERIFICATION FAILED")

        log_lines = [
            f"{status}{status_text}",
            _("File: {name}").format(name=appimage_name or "Unknown"),
            _("Algorithm: {type}").format(type=hash_type.upper()),
            _("Expected: {hash}").format(hash=expected_hash),
            _("Actual:   {hash}").format(hash=actual_hash),
            "----------------------------------------",
        ]

        # Always log the verification results
        logging.info("\n".join(log_lines))

        # Only print to console if verification failed
        if not is_verified:
            print("\n".join(log_lines))

    def log_verification_success(self, appimage_name: str, verification_type: str = "hash") -> None:
        """Log successful verification.

        Args:
            appimage_name: Name of the verified AppImage
            verification_type: Type of verification performed
        """
        message = (
            f"{STATUS_SUCCESS}{verification_type.title()} verification passed for {appimage_name}"
        )
        logging.info(f"Verification successful for {appimage_name}")
        print(message)

    def log_verification_failure(self, appimage_name: str, verification_type: str = "hash") -> None:
        """Log failed verification.

        Args:
            appimage_name: Name of the AppImage that failed verification
            verification_type: Type of verification that failed
        """
        message = (
            f"{STATUS_FAIL}{verification_type.title()} verification failed for {appimage_name}"
        )
        logging.error(f"Verification failed for {appimage_name}")
        print(message)

    def log_error(self, message: str, exception: Exception | None = None) -> None:
        """Log an error with optional exception details.

        Args:
            message: Error message to log
            exception: Optional exception that caused the error
        """
        if exception:
            logging.error(f"{message}: {exception}")
        else:
            logging.error(message)

    def log_warning(self, message: str) -> None:
        """Log a warning message.

        Args:
            message: Warning message to log
        """
        logging.warning(message)

    def log_info(self, message: str) -> None:
        """Log an informational message.

        Args:
            message: Informational message to log
        """
        logging.info(message)

    def log_debug(self, message: str) -> None:
        """Log a debug message.

        Args:
            message: Debug message to log
        """
        logging.debug(message)

    def print_status(self, message: str, success: bool = True) -> None:
        """Print a status message with appropriate indicator.

        Args:
            message: Status message to print
            success: Whether this is a success or failure status
        """
        status = STATUS_SUCCESS if success else STATUS_FAIL
        print(f"{status}{message}")
