"""GitHub Release Checksums Parsing Utilities.

This package provides pure utility functions for parsing and extracting SHA256 checksums
from GitHub release descriptions. All verification logic has been moved to the verification
module for proper separation of concerns.

Example usage:
    # Parse checksums from release description text
    from src.utils.checksums.parser import parse_checksums_from_description
    from src.utils.checksums.extractor import extract_checksums_from_text

    checksums = parse_checksums_from_description(description_text)
    filtered_checksums = extract_checksums_from_text(description_text, "app.AppImage")

    # Save checksums to file
    from src.utils.checksums.storage import save_checksums_file
    
    checksums_file = save_checksums_file(checksums, "/path/to/checksums.txt")

    # For verification workflows, use the verification module:
    from src.verification.release_desc_verifier import ReleaseDescVerifier
    
    # Auto-detect repository and verify
    success = ReleaseDescVerifier.verify_appimage_standalone("/path/to/app.AppImage")
    
    # Or with known repository info
    verifier = ReleaseDescVerifier("owner", "repo")
    success = verifier.verify_appimage("/path/to/app.AppImage")
"""

import logging

# Import core utility functionality (parsing and extraction only)
from src.utils.checksums.extractor import (
    extract_checksums_from_text,
    filter_checksums_by_filename,
    validate_checksum_format,
    extract_hash_and_filename,
)
from src.utils.checksums.parser import parse_checksums_from_description
from src.utils.checksums.storage import save_checksums_file

# Type annotations
ChecksumList = list[str]

logger = logging.getLogger(__name__)


# Backward compatibility functions with deprecation warnings
def extract_checksums(owner: str, repo: str, appimage_name: str | None) -> ChecksumList:
    """Extract checksums from GitHub release description.

    DEPRECATED: This function is deprecated. Use ReleaseDescVerifier from 
    src.verification.release_desc_verifier for verification workflows.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: AppImage filename to filter checksums for, or None

    Returns:
        list[str]: Checksum lines in "hash filename" format

    Raises:
        ValueError: If no checksums found
    """
    logger.warning(
        "extract_checksums() is deprecated. Use ReleaseDescVerifier from "
        "src.verification.release_desc_verifier instead."
    )
    
    # Import here to avoid circular dependencies
    from src.verification.release_desc_verifier import ReleaseDescVerifier
    
    verifier = ReleaseDescVerifier(owner=owner, repo=repo)
    checksums_file = verifier.extract_checksums_to_file(appimage_name)
    
    if not checksums_file:
        raise ValueError("Failed to extract checksums")
    
    # Read and return checksums from the file
    try:
        with open(checksums_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip()]
    except Exception as e:
        logger.error(f"Failed to read checksums file: {e}")
        raise ValueError("Failed to read extracted checksums")


def extract_checksums_to_file(
    owner: str, repo: str, appimage_name: str, output_path: str | None = None
) -> str | None:
    """Extract checksums for a specific AppImage from GitHub release.

    DEPRECATED: This function is deprecated. Use ReleaseDescVerifier from 
    src.verification.release_desc_verifier instead.

    Args:
        owner: Repository owner/organization
        repo: Repository name
        appimage_name: Name of the AppImage file to match
        output_path: Path for the output file, or None to use temp file

    Returns:
        str | None: Path to the created checksums file if successful, None if failed
    """
    logger.warning(
        "extract_checksums_to_file() is deprecated. Use ReleaseDescVerifier from "
        "src.verification.release_desc_verifier instead."
    )
    
    # Import here to avoid circular dependencies
    from src.verification.release_desc_verifier import ReleaseDescVerifier
    
    verifier = ReleaseDescVerifier(owner=owner, repo=repo)
    return verifier.extract_checksums_to_file(appimage_name, output_path)


# Legacy imports for backward compatibility (with deprecation warnings)
from src.utils.checksums.verification import (
    get_repo_info_for_appimage,
    verify_with_release_checksums,
    handle_release_description_verification,
)


# Export public API (only pure utilities, no verification functions)
__all__ = [
    # Core parsing and extraction utilities (pure functions)
    "extract_checksums_from_text",
    "filter_checksums_by_filename", 
    "validate_checksum_format",
    "extract_hash_and_filename",
    "parse_checksums_from_description",
    "save_checksums_file",
    # Type annotations
    "ChecksumList",
    # Deprecated backward compatibility functions
    "extract_checksums",
    "extract_checksums_to_file",
    "get_repo_info_for_appimage",
]