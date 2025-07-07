#!/usr/bin/env python3
"""Checksum handling utilities for different verification strategies.

This module provides functions to handle different checksum verification
strategies, including extracting checksums from GitHub release descriptions.
"""

import logging
import os
from pathlib import Path
from typing import Any

# Import from the new checksums package
from my_unicorn.utils.checksums import handle_release_description_verification
from my_unicorn.verify import VerificationManager

logger = logging.getLogger(__name__)


def verify_with_strategy(
    app_info: dict[str, Any], appimage_path: str, cleanup_on_failure: bool = False
) -> bool:
    """Verify an AppImage using the appropriate checksum strategy.

    This function determines the verification strategy based on the app_info
    and handles special cases like checksums in release descriptions.

    Args:
        app_info: Application information dictionary with verification details
        appimage_path: Path to the AppImage file to verify
        cleanup_on_failure: Whether to remove the AppImage if verification fails

    Returns:
        bool: True if verification passed, False otherwise

    """
    if not os.path.exists(appimage_path):
        logger.error("AppImage file not found: %s", appimage_path)
        return False

    # Get verification parameters
    checksum_file_name = app_info.get("checksum_file_name")
    checksum_file_download_url = app_info.get("checksum_file_download_url")
    checksum_hash_type = app_info.get("checksum_hash_type", "sha256")
    appimage_name = os.path.basename(appimage_path)

    # Handle special case for release description checksums
    if checksum_file_name == "extracted_checksum":
        logger.info("Using GitHub release description for verification of %s", appimage_name)

        # Get owner/repo from app_info if available
        owner = app_info.get("owner")
        repo = app_info.get("repo")

        # Use improved handle_release_description_verification which can auto-detect owner/repo
        return handle_release_description_verification(
            appimage_path=appimage_path,
            owner=owner,
            repo=repo,
            cleanup_on_failure=cleanup_on_failure,
        )

    # Standard verification using SHA file
    verifier = VerificationManager(
        checksum_file_name=checksum_file_name,
        checksum_file_download_url=checksum_file_download_url,
        appimage_name=appimage_name,
        appimage_path=appimage_path,
        checksum_hash_type=checksum_hash_type,
    )

    return verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)


def verify_downloaded_appimage(
    app_info: dict[str, Any], app_rename: str, downloads_dir: Path
) -> tuple[bool, str]:
    """Verify a downloaded AppImage based on app catalog information.

    This function handles the complete verification process including special
    cases like checksums from release descriptions.

    Args:
        app_info: Application information from the catalog
        app_rename: Display name of the application
        downloads_dir: Directory where the AppImage was downloaded

    Returns:
        tuple: (Success flag, AppImage path or error message)

    """
    try:
        # Find the downloaded AppImage file
        appimage_files = list(downloads_dir.glob(f"{app_rename}-*.AppImage"))
        if not appimage_files:
            logger.error("No AppImage found for %s in %s", app_rename, downloads_dir)
            return False, "No AppImage found for %s in %s" % (app_rename, downloads_dir)

        appimage_path = str(appimage_files[0])
        logger.info("Found AppImage to verify: %s", appimage_path)

        # Handle verification based on app_info
        success = verify_with_strategy(
            app_info=app_info, appimage_path=appimage_path, cleanup_on_failure=True
        )

        if success:
            logger.info("Successfully verified %s", os.path.basename(appimage_path))
            return True, appimage_path
        else:
            logger.error("Verification failed for %s", os.path.basename(appimage_path))
            return False, "Verification failed for %s" % os.path.basename(appimage_path)

    except Exception as e:
        logger.exception("Error during verification: %s", e)
        return False, "Error during verification: %s" % e
