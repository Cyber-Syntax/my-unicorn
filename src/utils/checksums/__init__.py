"""GitHub Release Checksums Extraction and Verification.

This package provides functionality to extract and verify SHA256 checksums
from GitHub release descriptions for applications that store their checksums
in the release notes rather than as separate files.

Example usage:
    # Extract checksums for a specific AppImage and save to a file
    from src.utils.checksums import extract_checksums_to_file

    sha_file = extract_checksums_to_file(
        owner="zen-browser",
        repo="desktop",
        appimage_name="zen-x86_64.AppImage"
    )

    # Verify an AppImage using checksums from a release description
    from src.utils.checksums import verify_with_release_checksums

    success = verify_with_release_checksums(
        owner="zen-browser",
        repo="desktop",
        appimage_path="/path/to/zen-x86_64.AppImage"
    )
"""

import logging
import tempfile
from pathlib import Path
from typing import Any

# Import core functionality from modules
# Type annotations
ChecksumList = list[str]
from src.utils.checksums.extractor import ReleaseChecksumExtractor
from src.utils.checksums.parser import parse_checksums_from_description
from src.utils.checksums.storage import save_checksums_file
from src.utils.checksums.verification import (
    get_repo_info_for_appimage,
    handle_release_description_verification,
    verify_with_release_checksums,
)

logger = logging.getLogger(__name__)


# For backward compatibility with code using the old extract_checksums.py module
def extract_checksums(owner: str, repo: str, appimage_name: str | None) -> ChecksumList:
    """Extract checksums from GitHub release description.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: AppImage filename to filter checksums for, or None

    Returns:
        list[str]: Checksum lines in "hash filename" format

    Raises:
        ValueError: If no checksums found

    """
    logger.info(f"Extracting checksums for {owner}/{repo}")
    extractor = ReleaseChecksumExtractor(owner=owner, repo=repo)
    return extractor.extract_checksums(target_filename=appimage_name)


def extract_checksums_to_file(
    owner: str, repo: str, appimage_name: str , output_path: str | None = None
) -> str | None:
    """Extract checksums for a specific AppImage from GitHub release.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: Name of the AppImage file to match
        output_path: Path for the output file, or None to use temp file

    Returns:
        str | None: Path to the created checksums file if successful, None if failed
    """
    try:
        logger.info(f"Extracting checksums for {appimage_name} from {owner}/{repo}")
        extractor = ReleaseChecksumExtractor(owner=owner, repo=repo)

        # Extract checksums
        checksums = extractor.extract_checksums(target_filename=appimage_name)

        # Save to file
        return save_checksums_file(checksums, output_path)
    except Exception as e:
        logger.exception(f"Error extracting checksums: {e}")
        return None


# Export public API
__all__ = [
    "extract_checksums",
    "save_checksums_file",
    "verify_with_release_checksums",
    "extract_checksums_to_file",
    "handle_release_description_verification",
    "get_repo_info_for_appimage",
    "ReleaseChecksumExtractor",
    "parse_checksums_from_description",
]
