"""Utility functions for my-unicorn AppImage installer.

This module provides common utility functions used across the application
including path operations, string manipulation, and validation helpers.
"""

import re
from pathlib import Path


def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename for safe filesystem use."""
    # Remove invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*]', "", filename)

    # Remove control characters
    sanitized = "".join(char for char in sanitized if ord(char) >= 32)

    # Limit length
    if len(sanitized) > 255:
        name, ext = Path(sanitized).stem, Path(sanitized).suffix
        max_name_len = 255 - len(ext)
        sanitized = name[:max_name_len] + ext

    return sanitized.strip()


BYTES_PER_UNIT = 1024.0


def format_bytes(size: float) -> str:
    """Format byte size in human readable format (e.g., '1.5 MB')."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < BYTES_PER_UNIT:
            return f"{size:.1f} {unit}"
        size /= BYTES_PER_UNIT
    return f"{size:.1f} PB"


def extract_version_from_package_string(package_string: str) -> str | None:
    """Extract version from package string (e.g., 'pkg@1.2.3' -> '1.2.3')."""
    if not package_string:
        return None

    # Handle package@version format
    if "@" in package_string:
        # Split by @ and take the last part (version)
        parts = package_string.split("@")
        if len(parts) >= 2:
            version_part = parts[-1]
            # Clean up the version part
            version_part = version_part.strip()
            if version_part:
                return sanitize_version_string(version_part)

    # Handle direct version strings
    return sanitize_version_string(package_string)


def sanitize_version_string(version: str) -> str:
    """Remove invalid characters and prefixes from version string."""
    if not version:
        return ""

    # Remove common prefixes
    version = version.lstrip("v")

    # Remove any remaining @ symbols that might be present
    version = version.replace("@", "")

    # Remove quotes and other problematic characters for JSON
    version = version.strip("\"'")

    # Remove any trailing/leading whitespace
    version = version.strip()

    return version


def validate_version_string(version: str) -> bool:
    """Check if version string matches semantic version pattern."""
    if not version:
        return False

    # The version should already be sanitized, but ensure no prefixes
    version = version.lstrip("v")

    # Check semantic version pattern (major.minor.patch with optional pre-release)
    pattern = r"^\d+(\.\d+)*(-[a-zA-Z0-9.-]+)?$"
    return bool(re.match(pattern, version))


def extract_and_validate_version(package_string: str) -> str | None:
    """Extract and validate version from package string.

    Combines extraction, sanitization, and validation in one function.

    Args:
        package_string: Package string that may contain version

    Returns:
        Valid version string or None if extraction/validation fails

    """
    extracted_version = extract_version_from_package_string(package_string)
    if extracted_version and validate_version_string(extracted_version):
        return extracted_version
    return None


def create_desktop_entry_name(app_name: str) -> str:
    """Create desktop entry filename from app name (e.g., 'app.desktop')."""
    # Normalize to lowercase and clean up the name
    name = app_name.lower().strip()

    # Remove special characters except alphanumeric, hyphens, and underscores
    name = re.sub(r"[^\w-]", "", name)

    # Replace multiple consecutive hyphens/underscores with single hyphen
    name = re.sub(r"[-_]+", "-", name)

    # Remove leading/trailing hyphens
    name = name.strip("-")

    # Ensure we have a valid name
    if not name:
        name = "appimage"

    return f"{name}.desktop"


# Checksum File Pattern Matching

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


def is_checksum_file(filename: str, require_appimage_base: bool = False) -> bool:
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
    """Check if filename ends with .AppImage."""
    return filename.lower().endswith(".appimage")


def get_checksum_file_format_type(filename: str) -> str:
    """Return 'yaml' or 'traditional' based on file extension."""
    if filename.lower().endswith((".yml", ".yaml")):
        return "yaml"
    return "traditional"
