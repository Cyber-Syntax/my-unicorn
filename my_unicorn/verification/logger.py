"""Logging and user feedback for AppImage verification.

This module provides structured logging and user feedback functionality
for verification operations, including status messages and comparison results.
"""

import gettext
import logging

_ = gettext.gettext

# Status indicators
STATUS_SUCCESS = "✓ "  # Unicode check mark
STATUS_FAIL = "✗ "  # Unicode cross mark


class VerificationLogger:
    """Handles logging and user feedback for verification operations."""

    def __init__(self) -> None:
        """Initialize the verification logger."""
        pass

    def log_verification_start(self, appimage_name: str, checksum_hash_type: str) -> None:
        """Log the start of verification process.

        Args:
            appimage_name: Name of the AppImage being verified
            checksum_hash_type: Type of hash being used for verification
        """
        logging.info("Starting verification of %s using %s", appimage_name, checksum_hash_type)

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
        checksum_hash_type: str,
        actual_hash: str,
        expected_hash: str,
        is_verified: bool,
    ) -> None:
        """Log hash comparison results with detailed information.

        Args:
            appimage_name: Name of the AppImage file
            checksum_hash_type: Hash algorithm used
            actual_hash: Calculated hash value
            expected_hash: Expected hash value
            is_verified: Whether verification passed
        """
        status = STATUS_SUCCESS if is_verified else STATUS_FAIL
        status_text = _("VERIFIED") if is_verified else _("VERIFICATION FAILED")

        log_lines = [
            f"{status}{status_text}",
            _("File: {name}").format(name=appimage_name or "Unknown"),
            _("Algorithm: {type}").format(type=checksum_hash_type.upper()),
            _("Expected: {hash}").format(hash=expected_hash),
            _("Actual:   {hash}").format(hash=actual_hash),
            "----------------------------------------",
        ]

        # Always log the verification results
        logging.info("\n".join(log_lines))

        # Only print to console if verification failed
        if not is_verified:
            print("\n".join(log_lines))

    def log_error(self, message: str, exception: Exception | None = None) -> None:
        """Log an error with optional exception details.

        Args:
            message: Error message to log
            exception: Optional exception that caused the error
        """
        if exception:
            logging.error("%s: %s", message, exception)
        else:
            logging.error(message)

    def log_info(self, message: str) -> None:
        """Log an informational message.

        Args:
            message: Informational message to log
        """
        logging.info(message)
