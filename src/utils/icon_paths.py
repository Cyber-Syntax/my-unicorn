#!/usr/bin/env python3
"""Icon path configuration module.

This module defines exact paths to icon files for various repositories.
Using a Python module instead of YAML allows for better documentation
and easier maintenance.

Examples:
    >>> from src.utils.icon_paths import get_icon_path
    >>> path = get_icon_path("joplin")
    >>> print(path)
    'Assets/LinuxIcons/256x256.png'
"""

from typing import Any, Dict, Optional

__all__ = ["ICON_PATHS", "get_icon_path"]

# Dictionary mapping repository names (keys) to their icon configurations (values)
# Each configuration contains:
#    - 'exact_path': Direct path to the icon file
#    - 'filename': Preferred filename to save the icon as
#
# Repository names are stored in lowercase for case-insensitive matching
ICON_PATHS: Dict[str, Dict[str, str]] = {
    "super-productivity": {
        "exact_path": "src/assets/icons/favicon-192x192.png",
        "filename": "superproductivity_icon.png",
    },
    "joplin": {
        "exact_path": "Assets/LinuxIcons/256x256.png",
        "filename": "joplin_icon.png",
    },
    "freetube": {
        "exact_path": "_icons/icon.svg",
        "filename": "freetube_icon.svg",
    },
    "appflowy": {
        "exact_path": "frontend/resources/flowy_icons/40x/app_logo.svg",
        "filename": "appflowy_icon.svg",
    },
    "siyuan-note/siyuan": {
        "exact_path": "app/src/assets/icon.png",
        "filename": "siyuan_icon.png",
    },
    "zettlr": {
        "exact_path": "resources/icons/png/512x512.png",
        "filename": "zettlr_icon.png",
    },
    "app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "standardnotes_icon.png",
    },
    "standardnotes/app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "standardnotes_icon.png",
    },
    "pbek/qownnotes": {
        "exact_path": "icons/icon.png",
        "filename": "qownnotes_icon.png",
    },
    # Add more repository configurations as needed...
}


def get_icon_path(repo_name: str) -> Optional[str]:
    """Get the exact icon path for a repository.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        str or None: Exact path to the icon file or None if not configured
    """
    if not repo_name:
        return None

    # Normalize to lowercase for lookup
    repo_lower = repo_name.lower()

    # Direct lookup
    if repo_lower in ICON_PATHS:
        return ICON_PATHS[repo_lower].get("exact_path")

    # Handle owner/repo format
    if "/" in repo_lower:
        # Try with just the repo part (after the slash)
        _, name = repo_lower.split("/", 1)
        if name in ICON_PATHS:
            return ICON_PATHS[name].get("exact_path")

    # If repo_name doesn't have a slash, check if any key with a slash ends with this repo
    else:
        for key in ICON_PATHS:
            if "/" in key and key.split("/", 1)[1] == repo_lower:
                return ICON_PATHS[key].get("exact_path")

    return None


def get_icon_filename(repo_name: str) -> Optional[str]:
    """Get the preferred filename for saving an icon.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        str or None: Preferred filename or None if not configured
    """
    if not repo_name:
        return None

    # Normalize to lowercase for lookup
    repo_lower = repo_name.lower()

    # Direct lookup
    if repo_lower in ICON_PATHS:
        return ICON_PATHS[repo_lower].get("filename")

    # Handle owner/repo format
    if "/" in repo_lower:
        # Try with just the repo part
        _, name = repo_lower.split("/", 1)
        if name in ICON_PATHS:
            return ICON_PATHS[name].get("filename")

    # If repo_name doesn't have a slash, check if any key with a slash ends with this repo
    else:
        for key in ICON_PATHS:
            if "/" in key and key.split("/", 1)[1] == repo_lower:
                return ICON_PATHS[key].get("filename")

    return None


# For backwards compatibility
def get_icon_paths(repo_name: str) -> Optional[Dict[str, Any]]:
    """Legacy function for backwards compatibility with existing tests and code.

    This function recreates the old dictionary format that tests expect.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        Dict or None: Icon configuration for the repository in the old format
    """
    if not repo_name:
        return None

    # Normalize to lowercase for lookup
    repo_lower = repo_name.lower()

    # Try direct lookup first
    if repo_lower in ICON_PATHS:
        # Create a copy of the config and ensure it has a paths key
        config = ICON_PATHS[repo_lower].copy()
        if "paths" not in config:
            config["paths"] = []
        return config

    # Handle owner/repo format
    if "/" in repo_lower:
        # Try with just the repo part
        _, name = repo_lower.split("/", 1)
        if name in ICON_PATHS:
            config = ICON_PATHS[name].copy()
            if "paths" not in config:
                config["paths"] = []
            return config

    # If repo_name doesn't have a slash, check if any key with a slash ends with this repo
    else:
        for key in ICON_PATHS:
            if "/" in key and key.split("/", 1)[1] == repo_lower:
                config = ICON_PATHS[key].copy()
                if "paths" not in config:
                    config["paths"] = []
                return config

    return None
