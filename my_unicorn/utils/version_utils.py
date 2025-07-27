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
        version: Version string to normalize, or None.

    Returns:
        A normalized version string. Returns an empty string if input is None.

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


def extract_version(tag: str) -> str | None:
    """Extract semantic version from tag string.

    Handles:
    - Semantic versions (X.Y.Z)
    - Standard Notes format (@standardnotes/desktop@X.Y.Z)
    - Versions with prefixes/suffixes (v1.2.3, 4.5.6-beta, etc.)

    Args:
        tag: Tag string to extract version from.

    Returns:
        The extracted semantic version, or None if no valid version found.

    """
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", tag)
    if std_notes_match:
        return std_notes_match.group(1)

    clean_tag = tag.lstrip("vV").replace("-stable", "")
    clean_tag = re.sub(r"-beta(\.\d+)?", "", clean_tag)

    version_match = re.search(r"\d+\.\d+\.\d+(?:\.\d+)?", clean_tag)
    if version_match:
        return version_match.group(0)

    alt_match = re.search(r"(\d+(?:\.\d+)+)", clean_tag)
    return alt_match.group(1) if alt_match else None


def handle_standard_notes_version(filename: str) -> str | None:
    """Extract version from Standard Notes filename format.

    Args:
        filename: Filename to extract from.

    Returns:
        Extracted version string, or None if not matched.

    """
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", filename)
    if std_notes_match:
        logger.debug(
            "Extracted version from Standard Notes filename: %s", std_notes_match.group(1)
        )
        return std_notes_match.group(1)

    if filename.startswith("app-") and "standardnotes" in filename.lower():
        match = re.search(r"-(\d+\.\d+\.\d+)", filename)
        if match:
            logger.debug("Extracted version from Standard Notes AppImage: %s", match.group(1))
            return match.group(1)

    return None


def extract_version_from_filename(filename: str) -> str | None:
    """Extract version from a typical AppImage filename.

    Args:
        filename: The AppImage filename.

    Returns:
        Extracted semantic version string, or None if no match found.

    """
    if not filename:
        return None

    if filename.startswith("app-") and "standardnotes" in filename.lower():
        return handle_standard_notes_version(filename)

    version_match = re.search(r"(\d+\.\d+\.\d+)(?!-)", filename)
    if version_match:
        return version_match.group(1)

    parts = filename.split("-")
    for part in parts:
        if re.fullmatch(r"\d+\.\d+\.\d+", part):
            return part

    for part in parts:
        if re.match(r"^\d+\.\d+\.\d+", part) and not re.match(r"^x\d+_\d+$", part):
            version = extract_version(part)
            if version and re.fullmatch(r"\d+\.\d+\.\d+", version):
                return version

    version_match = re.search(r"\d+\.\d+\.\d+", filename)
    return version_match.group(0) if version_match else None


def handle_zen_browser_version(
    raw_tag: str,
    normalized_version: str,
    owner: str,
    repo: str,
) -> str:
    """Handle zen-browser's special version format (e.g., 1.2.3b).

    Args:
        raw_tag: Original tag name from GitHub.
        normalized_version: Version string previously extracted.
        owner: GitHub repo owner.
        repo: GitHub repo name.

    Returns:
        Final normalized version string (possibly with letter suffix).

    """
    if owner == "zen-browser" and repo == "desktop":
        zen_tag_pattern = re.compile(r"^v?(\d+\.\d+\.\d+)([a-zA-Z])$")
        match = zen_tag_pattern.match(raw_tag)
        if match:
            version_base, letter_suffix = match.groups()
            potential_zen_version = f"{version_base}{letter_suffix}"
            if normalized_version != potential_zen_version:
                logger.info(
                    f"zen-browser: using version format {potential_zen_version} instead of {normalized_version} from tag {raw_tag}"
                )
                return potential_zen_version
    return normalized_version
