#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Icon path configuration module.

This module defines paths to icon files for various repositories.
Using a Python module instead of YAML allows for more complex configurations,
comments, and easier maintenance.
"""

# Dictionary mapping repository names (keys) to their icon configurations (values)
# Each configuration can be:
# 1. A list of paths to search in order of preference
# 2. A dictionary with additional options:
#    - 'paths': List of paths to search
#    - 'exact_path': Direct path to the icon file (highest priority)
#    - 'filename': Preferred filename to save the icon as (optional)
#    - 'size': Preferred icon size to download (optional)
#
# Repository names should be lowercase for case-insensitive matching
ICON_PATHS = {
    "super-productivity": {
        "exact_path": "src/assets/icons/favicon-192x192.png",
        "paths": ["src/assets/icons/favicon-192x192.png"],
        "filename": "superproductivity_icon.png",
    },
    "joplin": {
        "exact_path": "Assets/LinuxIcons/256x256.png",
        "paths": ["Assets/LinuxIcons/256x256.png"],
        "filename": "joplin_icon.png",
    },
    "freetube": {
        "exact_path": "_icons/icon.svg",
        "paths": ["_icons/icon.svg"],
        "filename": "freetube_icon.svg",
    },
    "appflowy": {
        "exact_path": "frontend/resources/flowy_icons/40x/app_logo.svg",
        "paths": ["frontend/resources/flowy_icons/40x/app_logo.svg"],
        "filename": "appflowy_icon.svg",
    },
    "siyuan-note/siyuan": {
        "exact_path": "app/src/assets/icon.png",
        "paths": ["app/src/assets/icon.png"],
        "filename": "siyuan_icon.png",
    },
    "Zettlr/Zettlr": {
        "exact_path": "resources/icons/png/512x512.png",
        "paths": ["resources/icons/png/512x512.png"],
        "filename": "zettlr_icon.png",
    },
    "app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "standardnotes_icon.png",
        "paths": [
            "packages/clipper/images/icon128.png",
            "packages/desktop/app/icon/Icon-256x256.png",
        ],
    },
    "standardnotes/app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "standardnotes_icon.png",
    },
    # Add more repository configurations as needed...
}


def get_icon_paths(repo_name: str):
    """
    Get icon paths configuration for a repository.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        dict or list: Icon paths configuration for the repository,
                     or default paths if not found
    """
    # Try with original case, then lowercase
    repo_config = ICON_PATHS.get(repo_name) or ICON_PATHS.get(repo_name.lower())

    # Also try with owner/repo format
    if not repo_config and "/" in repo_name:
        _, name = repo_name.split("/", 1)
        repo_config = ICON_PATHS.get(name) or ICON_PATHS.get(name.lower())

    # Fall back to default paths if no specific configuration found
    return repo_config or ICON_PATHS["default"]
