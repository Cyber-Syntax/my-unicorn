"""Asset validation utilities for checking file types.

This module provides shared file type validation functions used across
multiple modules for detecting AppImage and checksum files.

These are cross-layer utilities used by:
- infrastructure/github/models.py: Filtering release assets
- infrastructure/cache.py: Managing cached releases
- domain/types.py: Asset properties
- infrastructure/icon.py: File type detection
"""

import re

# Comprehensive checksum file patterns consolidated from github_client.py and cache.py
CHECKSUM_FILE_PATTERNS = [
    r"latest-.*\.yml$",
    r"latest-.*\.yaml$",
    r".*checksums?\.txt$",
    r".*checksums?\.yml$",
    r".*checksums?\.yaml$",
    r".*checksums?\.md5$",
    r".*checksums?\.sha1$",
    r".*checksums?\.sha256$",
    r".*checksums?\.sha512$",
    r"SHA\d+SUMS?(\.txt)?$",
    r"MD5SUMS?(\.txt)?$",
    r".*\.sum$",
    r".*\.hash$",
    r".*\.digest$",
    r".*\.DIGEST$",
    r".*appimage\.sha256$",
    r".*appimage\.sha512$",
]

# Specific checksum file extensions that require base file checking
SPECIFIC_CHECKSUM_EXTENSIONS = [
    ".sha256sum",
    ".sha512sum",
    ".sha1sum",
    ".md5sum",
    ".digest",
    ".sum",
    ".hash",
]


def is_checksum_file(
    filename: str, require_appimage_base: bool = False
) -> bool:
    """Check if filename is a checksum file.

    Args:
        filename: Name of the file to check
        require_appimage_base: If True, for specific extensions, only return True
                             if the base file (without checksum extension) is an AppImage

    Returns:
        True if the file is a checksum file

    """
    if not filename:
        return False

    filename_lower = filename.lower()

    # Check general checksum patterns first (these are always considered checksum files)
    for pattern in CHECKSUM_FILE_PATTERNS:
        if re.match(pattern, filename_lower, re.IGNORECASE):
            return True

    # Check specific checksum extensions
    for extension in SPECIFIC_CHECKSUM_EXTENSIONS:
        if filename_lower.endswith(extension):
            if not require_appimage_base:
                return True

            # Extract the base filename by removing the checksum extension
            base_filename = filename_lower[: -len(extension)]
            return is_appimage_file(base_filename)

    return False


def is_appimage_file(filename: str) -> bool:
    """Check if filename ends with .AppImage.

    Args:
        filename: Name of the file to check

    Returns:
        True if the file is an AppImage

    """
    return filename.lower().endswith(".appimage")


def get_checksum_file_format_type(filename: str) -> str:
    """Return 'yaml' or 'traditional' based on file extension.

    Args:
        filename: Name of the checksum file

    Returns:
        'yaml' for YAML-formatted checksums, 'traditional' otherwise

    """
    if filename.lower().endswith((".yml", ".yaml")):
        return "yaml"
    return "traditional"
