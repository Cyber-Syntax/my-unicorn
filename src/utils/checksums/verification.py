"""Verification functions for release description checksums.

This module provides functions to verify files using checksums from GitHub release descriptions and 
handles secure storage and validation of checksum data for AppImage integrity verification.
"""

import logging
import os
import tempfile
from pathlib import Path

from src.utils.checksums.extractor import ReleaseChecksumExtractor
from src.utils.checksums.storage import save_checksums_file

logger = logging.getLogger(__name__)


def get_repo_info_for_appimage(appimage_path: str | Path) -> dict[str, str]:
    """Get owner/repo information for an AppImage from app catalog.

    Attempts to extract repository information by matching the AppImage filename
    against entries in the app catalog.

    Args:
        appimage_path: Path to the AppImage file (str or Path)

    Returns:
        dict[str, str]: Dictionary with 'owner' and 'repo' keys if found, empty dict if not found
    """
    try:
        from src.app_catalog import APP_CATALOG

        app_id = Path(appimage_path).stem.split("-")[0].lower()
        logger.info(f"Trying to find repository info for app_id: {app_id}")

        # Check if this app_id matches any catalog entries
        for catalog_app_id, app_info in APP_CATALOG.items():
            if app_id == catalog_app_id.lower() or app_id == app_info.repo.lower():
                logger.info(f"Found matching app in catalog: {catalog_app_id}")
                return {"owner": app_info.owner, "repo": app_info.repo}

        logger.warning(f"No matching repository found for {app_id}")

    except Exception as e:
        logger.exception(f"Error finding repository info: {e}")

    return {}


def verify_with_release_checksums(
    owner: str, repo: str, appimage_path: str | Path, cleanup_on_failure: bool = False
) -> bool:
    """Verify an AppImage using checksums from GitHub release description.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_path: Path to the AppImage to verify
        cleanup_on_failure: Whether to remove the AppImage if verification fails

    Returns:
        True if verification succeeds, False otherwise

    """
    from src.verify import VerificationManager

    try:
        appimage_name = Path(appimage_path).name
        logger.info(f"Verifying {appimage_name} using checksums from {owner}/{repo}")

        # Extract checksums for the AppImage
        extractor = ReleaseChecksumExtractor(owner, repo)
        checksums = extractor.extract_checksums(appimage_name)

        if not checksums:
            logger.error("No checksums found in release description")
            return False

        # Create a temporary file for the checksums
        temp_dir = tempfile.gettempdir()
        sha_file = os.path.join(temp_dir, "SHA256SUMS.txt")
        save_checksums_file(checksums, sha_file)

        # Create verification manager
        verifier = VerificationManager(
            sha_name=sha_file,
            appimage_name=appimage_name,
            appimage_path=appimage_path,
            hash_type="sha256",
        )

        # Verify the AppImage
        return verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)

    except Exception as e:
        logger.exception(f"Error verifying with release checksums: {e}")
        return False


def handle_release_description_verification(
    appimage_path: str | Path,
    owner: str | None = None,
    repo: str | None = None,
    cleanup_on_failure: bool = False,
) -> bool:
    """Handle verification for apps that use release description for checksums.

    Verifies AppImage integrity using checksums stored in GitHub release descriptions.
    Can auto-detect repository information if not provided.

    Args:
        appimage_path: Path to the AppImage file to verify (str or Path)
        owner: Repository owner, auto-detected if None
        repo: Repository name, auto-detected if None
        cleanup_on_failure: Whether to remove the AppImage if verification fails

    Returns:
        bool: True if verification passed, False if failed or error occurred
    """
    try:
        appimage_name = Path(appimage_path).name

        # Auto-detect owner/repo if not provided
        if not owner or not repo:
            repo_info = get_repo_info_for_appimage(appimage_path)
            owner = repo_info.get("owner")
            repo = repo_info.get("repo")

            if not owner or not repo:
                logger.error(f"Could not determine owner/repo for {appimage_name}")
                return False

        logger.info(f"Verifying {appimage_name} using GitHub release description")
        return verify_with_release_checksums(
            owner=owner,
            repo=repo,
            appimage_path=appimage_path,
            cleanup_on_failure=cleanup_on_failure,
        )

    except Exception as e:
        logger.exception(f"Release description verification error: {e}")
        return False
