#!/usr/bin/env python3
"""Application catalog module.

This module provides a catalog of supported applications that can be
installed directly by name, without requiring the user to enter URLs.
"""

import logging
import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.utils.icon_paths import ICON_PATHS

logger = logging.getLogger(__name__)


@dataclass
class AppInfo:
    """Information about an application in the catalog.

    Attributes:
        name: User-friendly display name
        description: Short description of the application
        owner: GitHub repository owner
        repo: GitHub repository name
        app_display_name: Unique identifier for the app (defaults to repo name)
        sha_name: SHA file name for verification (or "no_sha_file")
        hash_type: Hash type used for verification (e.g., "sha256", "sha512")
        category: Application category for filtering/grouping
        tags: List of tags associated with the application

    """

    name: str
    description: str
    owner: str
    repo: str
    app_display_name: Optional[str] = None
    sha_name: str = "no_sha_file"
    hash_type: str = "sha256"
    category: str = "Other"
    tags: List[str] = None

    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.tags is None:
            self.tags = []
        if self.app_display_name is None:
            self.app_display_name = self.repo


# Application catalog - mapping app_display_name (lowercase) to AppInfo
# The app_display_name is used for lookup and should be simple, like 'joplin', 'freetube', etc.
APP_CATALOG: Dict[str, AppInfo] = {
    "tagspaces": AppInfo(
        name="TagSpaces",
        description="A free and open-source personal data manager with tagging support",
        owner="tagspaces",
        repo="tagspaces",
        sha_name="SHA256SUMS.txt",
        hash_type="sha256",
        category="Productivity",
        tags=["file-manager", "tagging", "local-files"],
    ),
    "obsidian": AppInfo(
        name="Obsidian",
        description="A powerful knowledge base that works on local Markdown files",
        owner="obsidianmd",
        repo="obsidian-releases",
        app_display_name="obsidian",
        sha_name="SHA256SUMS.txt",
        hash_type="sha256",
        category="Productivity",
        tags=["markdown", "knowledge-base", "local-files"],
    ),
    "logseq": AppInfo(
        name="Logseq",
        description="A privacy-first, open-source knowledge base that works on local files (opt-out google telemetry, can be disabled)",
        owner="logseq",
        repo="logseq",
        sha_name="SHA256SUMS.txt",
        hash_type="sha256",
        category="Productivity",
        tags=["knowledge-base", "markdown", "privacy"],
    ),
    "joplin": AppInfo(
        name="Joplin",
        description="A note-taking and to-do application with synchronization capabilities",
        owner="laurent22",
        repo="joplin",
        sha_name="latest-linux.yml",
        hash_type="sha512",
        category="Productivity",
        tags=["notes", "markdown", "sync"],
    ),
    "freetube": AppInfo(
        name="FreeTube",
        description="An open source desktop YouTube player built with privacy in mind",
        owner="FreeTubeApp",
        repo="FreeTube",
        category="Media",
        tags=["video", "youtube", "privacy"],
    ),
    "zettlr": AppInfo(
        name="Zettlr",
        description="A markdown editor for writing academic texts and taking notes",
        owner="Zettlr",
        repo="Zettlr",
        sha_name="SHA256SUMS.txt",
        hash_type="sha256",
        category="Productivity",
        tags=["markdown", "academic", "notes"],
    ),
    "superproductivity": AppInfo(
        name="Super Productivity",
        description="To-do list & time tracker & kanban board & calendar all in one app",
        owner="johannesjo",
        repo="super-productivity",
        sha_name="latest-linux.yml",
        hash_type="sha512",
        category="Productivity",
        tags=["todo", "time-tracking", "productivity"],
    ),
    "appflowy": AppInfo(
        name="AppFlowy",
        description="Open-source alternative to Notion",
        owner="AppFlowy-IO",
        repo="AppFlowy",
        category="Productivity",
        tags=["notes", "organization", "notion-alternative"],
    ),
    "siyuan": AppInfo(
        name="SiYuan",
        description="A local-first personal knowledge management system (opt-out google telemetry, can be disabled)",
        owner="siyuan-note",
        repo="siyuan",
        sha_name="SHA256SUMS.txt",
        hash_type="sha256",
        category="Productivity",
        tags=["notes", "knowledge-base"],
    ),
    "standardnotes": AppInfo(
        name="Standard Notes",
        description="A simple and private notes app",
        owner="standardnotes",
        repo="app",
        app_display_name="standardnotes",  # Use this instead of repo for file names
        sha_name="SHA256SUMS",
        hash_type="sha256",
        category="Productivity",
        tags=["notes", "privacy", "encryption"],
    ),
    "qownnotes": AppInfo(
        name="QOwnNotes",
        description="Plain-text file notepad with markdown support and ownCloud & nextcloud and git integration",
        owner="pbek",
        repo="QOwnNotes",
        sha_name="QOwnNotes-x86_64-Qt6.AppImage.sha256sum",
        hash_type="sha256",
        category="Productivity",
        tags=["notes", "markdown", "owncloud"],
    ),
    "zen-browser": AppInfo(
        name="Zen Browser",
        description="A content-focused browser for distraction-free browsing",
        owner="zen-browser",
        repo="desktop",
        app_display_name="zen-browser",
        sha_name="extracted_checksum",  # Special marker to use release description for verification
        hash_type="sha256",
        category="Productivity",
        tags=["browser", "focus", "distraction-free", "privacy"],
    ),
    # Add more applications as needed
}


def get_app_info(app_display_name: str) -> Optional[AppInfo]:
    """Get information about an application by its ID.

    Args:
        app_display_name: The application identifier (case-insensitive)

    Returns:
        AppInfo object if found, None otherwise

    """
    return APP_CATALOG.get(app_display_name.lower())


def find_app_by_owner_repo(owner: str, repo: str) -> Optional[AppInfo]:
    """Find an application in the catalog by owner and repo.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        AppInfo object if found, None otherwise

    """
    # Convert to lowercase for case-insensitive comparison
    owner_lower = owner.lower()
    repo_lower = repo.lower()

    # Search through the catalog for a matching app
    for app in APP_CATALOG.values():
        if app.owner.lower() == owner_lower and app.repo.lower() == repo_lower:
            return app

    # No match found
    return None


def get_app_display_name_for_owner_repo(owner: str, repo: str) -> str:
    """Get the app_display_name for a given owner/repo combination.

    This helps ensure we always use the correct app_display_name from
    the catalog for naming purposes, even when only owner/repo is available.

    Args:
        owner: Repository owner
        repo: Repository name

    Returns:
        The app_display_name from the catalog if found, otherwise defaults to repo name

    """
    app_info = find_app_by_owner_repo(owner, repo)
    if app_info and app_info.app_display_name:
        logger.debug(
            f"Found app_display_name '{app_info.app_display_name}' in catalog for {owner}/{repo}"
        )
        return app_info.app_display_name

    # Default to repo name if not found in catalog
    logger.debug(f"No app_display_name found in catalog for {owner}/{repo}, using repo name")
    return repo


def get_all_apps() -> List[AppInfo]:
    """Get a list of all applications in the catalog.

    Returns:
        List of AppInfo objects

    """
    return list(APP_CATALOG.values())


def get_apps_by_category(category: str) -> List[AppInfo]:
    """Get applications filtered by category.

    Args:
        category: Category name to filter by

    Returns:
        List of AppInfo objects in the specified category

    """
    return [app for app in APP_CATALOG.values() if app.category.lower() == category.lower()]


def get_apps_by_tag(tag: str) -> List[AppInfo]:
    """Get applications filtered by tag.

    Args:
        tag: Tag to filter by

    Returns:
        List of AppInfo objects with the specified tag

    """
    return [
        app
        for app in APP_CATALOG.values()
        if app.tags and tag.lower() in [t.lower() for t in app.tags]
    ]


def search_apps(query: str) -> List[AppInfo]:
    """Search for applications by name, description, or tags.

    Args:
        query: Search query string

    Returns:
        List of matching AppInfo objects

    """
    query = query.lower()
    results = []

    for app in APP_CATALOG.values():
        if (
            query in app.name.lower()
            or query in app.description.lower()
            or (app.tags and any(query in tag.lower() for tag in app.tags))
        ):
            results.append(app)

    return results


def get_categories() -> List[str]:
    """Get a list of all categories in the catalog.

    Returns:
        List of category names

    """
    return sorted({app.category for app in APP_CATALOG.values()})


def sync_with_icon_paths():
    """Ensure all apps in the catalog have corresponding entries in ICON_PATHS.

    This is a utility function for development/maintenance.
    """
    missing_icons = []

    for app_display_name, app_info in APP_CATALOG.items():
        repo_key = f"{app_info.owner}/{app_info.repo}".lower()
        repo_only_key = app_info.repo.lower()

        if repo_key not in ICON_PATHS and repo_only_key not in ICON_PATHS:
            missing_icons.append((app_display_name, repo_key))

    if missing_icons:
        logger.warning(f"Missing icon paths for {len(missing_icons)} apps:")
        for app_display_name, repo_key in missing_icons:
            logger.warning(f"  - {app_display_name} ({repo_key})")


def find_app_by_name_in_filename(filename: str) -> Optional[AppInfo]:
    """Find app information based on the AppImage filename.

    This function tries to match the filename with entries in the app catalog,
    which is particularly useful when verifying AppImages with extracted checksums.

    Args:
        filename: The AppImage filename (with or without path)

    Returns:
        AppInfo object if found, None otherwise

    """
    if not filename:
        logger.error("Empty filename provided to find_app_by_name_in_filename")
        return None

    # Extract just the basename without path
    basename = os.path.basename(filename).lower()
    logger.debug(f"Looking for app match for filename: {basename}")

    # Extract the first part before hyphen (likely the app name)
    name_part = basename.split("-")[0].lower()

    # First, direct match against app_display_name in the catalog
    for app_id, app_info in APP_CATALOG.items():
        if app_id.lower() == name_part:
            logger.debug(f"Found direct app_id match: {app_id}")
            return app_info

        # Check if app_display_name matches the first part of the filename
        if hasattr(app_info, "app_display_name") and app_info.app_display_name:
            if app_info.app_display_name.lower() == name_part:
                logger.debug(f"Found display name match: {app_info.app_display_name}")
                return app_info

        # Check if repo name matches the first part of the filename
        if app_info.repo.lower() == name_part:
            logger.debug(f"Found repo name match: {app_info.repo}")
            return app_info

    # Special hard-coded fallbacks for known cases
    if "zen" in basename.lower():
        logger.info("Detected Zen Browser AppImage")
        return APP_CATALOG.get("zen-browser")

    logger.warning(f"Could not find app information for filename: {basename}")
    return None
