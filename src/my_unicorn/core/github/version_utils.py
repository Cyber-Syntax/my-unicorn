"""GitHub version extraction and validation utilities.

This module provides functions for extracting and validating version strings
from GitHub package/release information.
"""

import re


def extract_and_validate_version(package_string: str) -> str | None:
    """Extract and validate version from package string.

    Combines extraction, sanitization, and validation in one function.
    Used by GitHub models to normalize version strings from release data.

    Args:
        package_string: Package string that may contain version

    Returns:
        Valid version string or None if extraction/validation fails

    """
    if not package_string:
        return None

    # Handle package@version format
    if "@" in package_string:
        parts = package_string.split("@")
        if len(parts) < 2:
            return None
        version = parts[-1].strip()
        if not version:
            return None
    else:
        version = package_string

    # Sanitize version
    version = version.lstrip("v").replace("@", "").strip("\"'").strip()
    if not version:
        return None

    # Validate version
    pattern = r"^\d+(\.\d+)*(-[a-zA-Z0-9.-]+)?$"
    if re.match(pattern, version):
        return version
    return None
