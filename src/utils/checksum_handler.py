#!/usr/bin/env python3
"""Checksum handling utilities for different verification strategies.

This module provides functions to handle different checksum verification
strategies, including extracting checksums from GitHub release descriptions.
"""

import logging
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from src.utils.extract_hash import handle_release_description_verification
from src.verify import VerificationManager

logger = logging.getLogger(__name__)


def verify_with_strategy(
    app_info: Dict[str, Any], appimage_path: str, cleanup_on_failure: bool = False
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
        logger.error(f"AppImage file not found: {appimage_path}")
        return False

    # Get verification parameters
    sha_name = app_info.get("sha_name")
    sha_url = app_info.get("sha_url")
    hash_type = app_info.get("hash_type", "sha256")
    appimage_name = os.path.basename(appimage_path)

    # Handle special case for release description checksums
    if sha_name == "extracted_checksum":
        logger.info(f"Using GitHub release description for verification of {appimage_name}")

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
        sha_name=sha_name,
        sha_url=sha_url,
        appimage_name=appimage_name,
        appimage_path=appimage_path,
        hash_type=hash_type,
    )

    return verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)


def verify_downloaded_appimage(
    app_info: Dict[str, Any], app_display_name: str, downloads_dir: Path
) -> Tuple[bool, str]:
    """Verify a downloaded AppImage based on app catalog information.

    This function handles the complete verification process including special
    cases like checksums from release descriptions.

    Args:
        app_info: Application information from the catalog
        app_display_name: Display name of the application
        downloads_dir: Directory where the AppImage was downloaded

    Returns:
        tuple: (Success flag, AppImage path or error message)

    """
    try:
        # Find the downloaded AppImage file
        appimage_files = list(downloads_dir.glob(f"{app_display_name}-*.AppImage"))
        if not appimage_files:
            error_msg = f"No AppImage found for {app_display_name} in {downloads_dir}"
            logger.error(error_msg)
            return False, error_msg

        appimage_path = str(appimage_files[0])
        logger.info(f"Found AppImage to verify: {appimage_path}")

        # Handle verification based on app_info
        success = verify_with_strategy(
            app_info=app_info, appimage_path=appimage_path, cleanup_on_failure=True
        )

        if success:
            logger.info(f"Successfully verified {os.path.basename(appimage_path)}")
            return True, appimage_path
        else:
            error_msg = f"Verification failed for {os.path.basename(appimage_path)}"
            logger.error(error_msg)
            return False, error_msg

    except Exception as e:
        error_msg = f"Error during verification: {e}"
        logger.exception(error_msg)
        return False, error_msg
