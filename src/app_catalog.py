#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Application catalog module.

This module provides a catalog of supported applications that can be
installed directly by name, without requiring the user to enter URLs.
"""

import logging
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
        sha_name: SHA file name for verification (or "no_sha_file")
        hash_type: Hash type used for verification (e.g., "sha256", "sha512")
        category: Application category for filtering/grouping
        tags: List of tags associated with the application
    """

    name: str
    description: str
    owner: str
    repo: str
    sha_name: str = "no_sha_file"
    hash_type: str = "sha256"
    category: str = "Other"
    tags: List[str] = None

    def __post_init__(self):
        """Initialize default values for optional fields."""
        if self.tags is None:
            self.tags = []


# Application catalog - mapping app_id (lowercase) to AppInfo
# The app_id is used for lookup and should be simple, like 'joplin', 'freetube', etc.
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
        sha_name="QOwnNotes-x86_64.AppImage.sha256sum",
        hash_type="sha256",
        category="Productivity",
        tags=["notes", "markdown", "owncloud"],
    ),
    # Add more applications as needed
}


def get_app_info(app_id: str) -> Optional[AppInfo]:
    """Get information about an application by its ID.

    Args:
        app_id: The application identifier (case-insensitive)

    Returns:
        AppInfo object if found, None otherwise
    """
    return APP_CATALOG.get(app_id.lower())


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

    for app_id, app_info in APP_CATALOG.items():
        repo_key = f"{app_info.owner}/{app_info.repo}".lower()
        repo_only_key = app_info.repo.lower()

        if repo_key not in ICON_PATHS and repo_only_key not in ICON_PATHS:
            missing_icons.append((app_id, repo_key))

    if missing_icons:
        logger.warning(f"Missing icon paths for {len(missing_icons)} apps:")
        for app_id, repo_key in missing_icons:
            logger.warning(f"  - {app_id} ({repo_key})")
