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
    # Default paths for all repositories (fallback)
    "default": [
        "assets/logo.png",
        "assets/icon.png",
        "assets/app-icon.png",
        "assets/icons/icon.png",
        "assets/icons/512x512.png",
        "assets/icons/256x256.png",
        "assets/icons/128x128.png",
        "icons/512x512.png",
        "icons/256x256.png",
        "icons/icon.svg",
        "resources/icons/512x512.png",
        "build/icons/512x512.png",
        "build/icons/256x256.png",
        "build/icon.png",
        "public/icon.png",
        "src/assets/icons/icon.png",
        "src/assets/icon.png",
    ],
    # Repository-specific configurations
    "super-productivity": ["src/assets/icons/favicon-192x192.png"],
    "joplin": ["Assets/LinuxIcons/256x256.png"],
    "freetube": ["_icons/icon.svg"],
    "appflowy": ["frontend/resources/flowy_icons/40x/app_logo.svg"],
    # Standard Notes with direct path to icon file
    "app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "icon.png",  # Save as icon.png
        "paths": [
            "packages/clipper/images/icon128.png",
            "packages/desktop/app/icon/Icon-256x256.png",
        ],
    },
    # Example with alternative owner/repo format
    "standardnotes/app": {
        "exact_path": "packages/clipper/images/icon128.png",
        "filename": "icon.png",
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
