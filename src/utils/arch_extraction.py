#!/usr/bin/env python3
"""Architecture utilities for asset selection.

This module provides functions for extracting and identifying architecture information from 
filenames to ensure proper AppImage compatibility.
"""

import re

# Constants for architecture identification
ARCH_KEYWORDS = {
    "x86_64": ["x86_64", "amd64", "x86-64", "x64"],
    "aarch64": ["aarch64", "arm64", "armv8"],
    "armhf": ["armhf", "arm32", "armv7"],
    "i686": ["i686", "x86", "i386"],
}

ARCH_PATTERNS = [
    (r"(-arm64[^.]*\.appimage)$", "arm64"),
    (r"(-aarch64[^.]*\.appimage)$", "aarch64"),
    (r"(-amd64[^.]*\.appimage)$", "amd64"),
    (r"(-x86_64[^.]*\.appimage)$", "x86_64"),
    (r"(-x86[^.]*\.appimage)$", "x86"),
    (r"(-i686[^.]*\.appimage)$", "i686"),
    (r"(-i386[^.]*\.appimage)$", "i386"),
    (r"(-linux(?:64)?\.appimage)$", "linux"),
]

ALL_ARCH_MARKERS = [
    "arm64",
    "aarch64",
    "armhf",
    "arm32",
    "armv7",
    "armv8",
    "x86_64",
    "amd64",
    "x86-64",
    "x64",
    "i686",
    "x86",
    "i386",
]


def extract_arch_from_filename(filename: str) -> str | None:
    """Extract architecture keyword from an AppImage filename.
    Iterates through known architecture keywords and their markers.
    Uses regex to ensure the marker is a distinct word or segment in the filename.

    Args:
        filename: The AppImage filename to extract from

    Returns:
        str | None: The extracted canonical architecture keyword (e.g., "x86_64") or None
    """
    if not filename:
        return None

    lower_name = filename.lower()

    # Iterate through canonical keywords (x86_64, aarch64, etc.)
    # and their associated markers (amd64, x86-64, arm64, etc.)
    # The order in ARCH_KEYWORDS might matter if markers are ambiguous (e.g., "arm" vs "arm64")
    # More specific markers should ideally be checked first or be distinct enough.
    for canonical_arch, markers in ARCH_KEYWORDS.items():
        for marker in markers:
            # Regex to find the marker as a whole word or delimited by common separators.
            # This helps avoid matching "arm" in "alarm" or "x86" in "someapp-x8600.AppImage".
            # Pattern: (non-alphanumeric OR start of string) + marker + (non-alphanumeric OR end of string OR .appimage)
            # Using word boundaries \b might be too restrictive if markers are like "x86-64".
            # Using lookarounds for more precise matching:
            # (?<=^|[\W_]) ensures start of string or non-word char before.
            # (?=$|[\W_]|\.appimage) ensures end of string, non-word char, or .appimage after.
            # Simpler regex: look for marker surrounded by non-alphanumeric chars or start/end of string.
            # The re.escape(marker) is important if markers contain special regex characters.
            pattern = re.compile(
                rf"(?:^|[^a-zA-Z0-9])({re.escape(marker)})(?:$|[^a-zA-Z0-9])", re.IGNORECASE
            )
            if pattern.search(lower_name):
                return canonical_arch  # Return the canonical keyword

    return None  # No specific architecture keyword found


# The following functions are now effectively replaced or made redundant by the new extract_arch_from_filename.
# They are kept here but marked as deprecated to avoid breaking other parts of the codebase
# that might still be calling them directly, though they should be updated.


def extract_arch_keyword(filename: str) -> str:
    """
    DEPRECATED: Original function to extract architecture keyword.
    This function returned parts of the filename rather than a canonical keyword.
    Use extract_arch_from_filename for canonical keywords.
    """
    lower_name = filename.lower()
    # Original ARCH_PATTERNS were (regex_str_to_extract_part, label_that_was_ignored)
    # This logic is flawed as it returns a part of the filename.
    for pattern_str, _ in ARCH_PATTERNS:
        match = re.search(pattern_str, lower_name)
        if match:
            return match.group(1)
    return ".appimage"  # Fallback


def extract_arch_from_dash(filename: str) -> str | None:
    """
    DEPRECATED: Original function for more 'advanced' extraction.
    This function also returned parts of the filename.
    Use extract_arch_from_filename for canonical keywords.
    """
    lower_name = filename.lower()
    # This logic is complex and returns parts of the filename.
    for key in ["arm64", "aarch64", "amd64", "x86_64", "x86", "i686", "i386"]:  # Original keys
        if key in lower_name:
            pos = lower_name.find(key)
            if pos >= 0:
                dash_pos = lower_name.rfind("-", 0, pos)
                if dash_pos >= 0:
                    suffix = lower_name[dash_pos:]
                    if suffix.endswith(".appimage"):
                        suffix = suffix[:-9]
                    return f"{suffix}.appimage"  # Example: "-x86_64.appimage"
    # Fallback
    match = re.search(r"(-linux(?:64)?\.appimage)$", lower_name)
    if match:
        return match.group(1)
    return None


def is_compatible_with_architecture(filename: str, incompatible_archs: list[str]) -> bool:
    """Check if a filename is compatible with the current architecture."""
    lower_name = filename.lower()
    return not any(arch in lower_name for arch in incompatible_archs)


def is_generic_linux_build(filename: str) -> bool:
    """Check if a filename represents a generic Linux build."""
    lower_name = filename.lower()
    # Check if "linux" is in the name and no specific architecture markers are present.
    # This requires extract_arch_from_filename to be robust.
    # If extract_arch_from_filename returns None, and "linux" is in name, it might be generic.
    # However, ALL_ARCH_MARKERS might be too broad if not used with care.
    # A simpler check: if "linux" is present and extract_arch_from_filename(filename) is None.
    if "linux" in lower_name:
        if (
            extract_arch_from_filename(filename) is None
        ):  # Check if our function finds a specific arch
            return True
    return False
