#!/usr/bin/env python3
"""Version utilities.

This module provides functions for parsing, comparing, and validating version strings
used in AppImage releases. It handles different version formats and normalizes them
for consistent comparison.
"""

import logging
import re

logger = logging.getLogger(__name__)


def normalize_version_for_comparison(version: str | None) -> str:
    """Normalize version string for consistent comparison.

    Strips version prefixes like 'v' and standardizes special formats like
    Standard Notes versioning scheme for consistent comparison.

    Args:
        version: Version string to normalize, or None

    Returns:
        str: Normalized version string, empty string if input is None

    """
    if not version:
        return ""

    # Convert to lowercase for case-insensitive comparison
    normalized = version.lower()

    # Remove 'v' prefix if present
    if normalized.startswith("v"):
        normalized = normalized[1:]

    # Handle Standard Notes format: @standardnotes/desktop@3.195.13
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", normalized)
    if std_notes_match:
        normalized = std_notes_match.group(1)
        logger.debug("Normalized Standard Notes version format: %s", normalized)

    return normalized


def extract_version(tag: str, is_beta: bool = False) -> str | None:
    """Extract semantic version from tag string.

    Handles various version formats including:
    - Standard semantic versions (X.Y.Z)
    - Standard Notes format (@standardnotes/desktop@X.Y.Z)
    - Beta versions with suffixes

    Args:
        tag: Version tag to extract from
        is_beta: Whether this is a beta version

    Returns:
        str | None: Extracted version string if found, None if no version found

    """
    # Handle Standard Notes format: @standardnotes/desktop@3.195.13
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", tag)
    if std_notes_match:
        logger.debug(
            "Extracted version from Standard Notes format: %s", std_notes_match.group(1)
        )
        return std_notes_match.group(1)

    # Clean common prefixes/suffixes
    clean_tag = tag.lstrip("vV").replace("-stable", "")

    # For beta versions, remove beta suffix before matching
    if "-beta" in clean_tag:
        # Remove beta suffix including any additional components (like beta.1)
        clean_tag = re.sub(r"-beta(\.\d+)?", "", clean_tag)

    # Match semantic version pattern
    version_match = re.search(r"\d+\.\d+\.\d+(?:\.\d+)*", clean_tag)
    if version_match:
        return version_match.group(0)

    # Try alternative patterns if standard semantic version not found
    alt_match = re.search(r"(\d+[\w\.]+)", clean_tag)
    return alt_match.group(1) if alt_match else None


def handle_standard_notes_version(filename: str) -> str | None:
    """Extract version from Standard Notes tag."""
    # Handle Standard Notes format: @standardnotes/desktop@3.195.13
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", filename)
    if std_notes_match:
        logger.debug(
            "Extracted version from Standard Notes filename: %s", std_notes_match.group(1)
        )
        return std_notes_match.group(1)

    # Handle Standard Notes AppImage format: app-3.195.13-x86_64.AppImage
    if filename.startswith("app-") and "standardnotes" in str(filename).lower():
        match = re.search(r"-(\d+\.\d+\.\d+)", filename)
        if match:
            logger.debug("Extracted version from Standard Notes AppImage: %s", match.group(1))
            return match.group(1)


def extract_version_from_filename(filename: str) -> str | None:
    """Extract version from AppImage filename.

    Args:
        filename: AppImage filename

    Returns:
        str | None: Extracted version string if found, None if not found

    """
    if not filename:
        return None

    # Handle standard notes
    if filename.startswith("app-") and "standardnotes" in str(filename).lower():
        handle_standard_notes_version(filename)

    # First try a direct match for semantic version pattern
    version_match = re.search(r"(\d+\.\d+\.\d+)(?!-)", filename)
    if version_match:
        return version_match.group(1)

    # Try to find version in filename segments
    parts = filename.split("-")
    for part in parts:
        # Check if this part has a semantic version pattern
        if re.match(r"^\d+\.\d+\.\d+$", part):
            return part

    # If no direct match, try more general pattern but avoid architecture like x86_64
    for part in parts:
        if re.match(r"^\d+\.\d+\.\d+", part) and not re.match(r"^x\d+_\d+$", part):
            version = extract_version(part, False)
            if version and re.match(r"^\d+\.\d+\.\d+$", version):
                return version

    # Final fallback to regex search
    version_match = re.search(r"\d+\.\d+\.\d+", filename)

    return version_match.group(0) if version_match else None

def handle_zen_browser_version(
    raw_tag: str, normalized_version: str, owner: str, repo: str
) -> str:
    """Handle zen-browser's special version format (X.Y.Z[letter])."""
    if owner == "zen-browser" and repo == "desktop":
        import re

        zen_tag_pattern = re.compile(r"^v?(\d+\.\d+\.\d+)([a-zA-Z])$")
        match = zen_tag_pattern.match(raw_tag)
        if match:
            version_base, letter_suffix = match.group(1), match.group(2)
            potential_zen_version = f"{version_base}{letter_suffix}"
            if normalized_version != potential_zen_version:
                logger.info(
                    f"zen-browser: using version format {potential_zen_version} instead of {normalized_version} from tag {raw_tag}"
                )
                return potential_zen_version
    return normalized_version