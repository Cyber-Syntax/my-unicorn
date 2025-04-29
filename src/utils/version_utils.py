#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Version utilities.

This module provides functions for parsing and comparing version strings.
"""

import re
import logging
from typing import Optional

# Configure module logger
logger = logging.getLogger(__name__)


def normalize_version_for_comparison(version: Optional[str]) -> str:
    """
    Normalize version string for consistent comparison.

    Args:
        version: Version string to normalize

    Returns:
        str: Normalized version string
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
        logger.debug(f"Normalized Standard Notes version format: {normalized}")

    return normalized


def extract_base_version(version: str) -> str:
    """
    Extract the base version number without beta/alpha suffixes.

    Args:
        version: Version string to extract from

    Returns:
        str: Base version number (e.g., "0.23.3" from "0.23.3-beta")
    """
    # Split on common version separators
    for separator in ["-", "+", "_"]:
        if separator in version:
            return version.split(separator)[0]

    return version


def extract_version(tag: str, is_beta: bool = False) -> Optional[str]:
    """
    Extract semantic version from tag string.

    Args:
        tag: Version tag to extract from
        is_beta: Whether this is a beta version

    Returns:
        str or None: Extracted version or None if not found
    """
    # Handle Standard Notes format: @standardnotes/desktop@3.195.13
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", tag)
    if std_notes_match:
        logger.debug(f"Extracted version from Standard Notes format: {std_notes_match.group(1)}")
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


def extract_version_from_filename(filename: str) -> Optional[str]:
    """
    Extract version from AppImage filename.

    Args:
        filename: AppImage filename

    Returns:
        str or None: Extracted version or None if not found
    """
    if not filename:
        return None

    # Handle Standard Notes format: @standardnotes/desktop@3.195.13
    std_notes_match = re.search(r"@standardnotes/desktop@(\d+\.\d+\.\d+)", filename)
    if std_notes_match:
        logger.debug(f"Extracted version from Standard Notes filename: {std_notes_match.group(1)}")
        return std_notes_match.group(1)

    # Handle Standard Notes AppImage format: app-3.195.13-x86_64.AppImage
    if filename.startswith("app-") and "standardnotes" in str(filename).lower():
        match = re.search(r"-(\d+\.\d+\.\d+)", filename)
        if match:
            logger.debug(f"Extracted version from Standard Notes AppImage: {match.group(1)}")
            return match.group(1)

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


def repo_uses_beta(repo_name: str) -> bool:
    """
    Determine if a repository typically uses beta/pre-releases.

    Args:
        repo_name: Repository name to check

    Returns:
        bool: True if the repository typically uses beta releases
    """
    # List of repos that are known to use beta releases
    beta_repos = ["FreeTube"]

    # Check if the repo is in the list
    if repo_name in beta_repos:
        logger.info(f"Repository {repo_name} is configured to use beta releases")
        return True

    return False
