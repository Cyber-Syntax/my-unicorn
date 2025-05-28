"""Application catalog module.

This module handles loading and managing application definitions from JSON files.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFINITIONS_PATH: Optional[Path] = None

@dataclass
class AppInfo:
    """Application information from definition file.

    Attributes:
        owner: Repository owner/organization
        repo: Repository name
        app_display_name: Display name for the application
        description: Description of the application
        category: Application category
        tags: List of tags describing the application
        hash_type: Type of hash used for verification (e.g., "sha256")
        appimage_name_template: Template for AppImage filename
        sha_name: Name of SHA file or "no_sha_file"
        preferred_characteristic_suffixes: List of characteristic suffixes in order of preference
        icon_info: Direct URL to icon file
        icon_file_name: Preferred filename for saving the icon
        icon_repo_path: Repository path to icon file (fallback if icon_info not available)
    """
    owner: str
    repo: str
    app_display_name: str
    description: str
    category: str
    tags: List[str]
    hash_type: str
    appimage_name_template: str
    sha_name: str
    preferred_characteristic_suffixes: List[str]
    icon_info: Optional[str]
    icon_file_name: Optional[str]
    icon_repo_path: Optional[str]

def initialize_definitions_path(path: Path) -> None:
    """Initialize the path to application definitions.

    Args:
        path: Path to directory containing JSON app definitions
    """
    global DEFINITIONS_PATH
    DEFINITIONS_PATH = path
    logger.info(f"Initialized app definitions path: {path}")

def get_all_apps() -> Dict[str, AppInfo]:
    """Get all available app definitions.

    Returns:
        Dict mapping lowercase repo names to AppInfo objects
    """
    if not DEFINITIONS_PATH:
        logger.error("App definitions path not initialized")
        return {}

    apps: Dict[str, AppInfo] = {}
    try:
        for json_file in DEFINITIONS_PATH.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    app_info = AppInfo(
                        owner=data["owner"],
                        repo=data["repo"],
                        app_display_name=data["app_display_name"],
                        description=data["description"],
                        category=data["category"],
                        tags=data["tags"],
                        hash_type=data["hash_type"],
                        appimage_name_template=data["appimage_name_template"],
                        sha_name=data["sha_name"],
                        preferred_characteristic_suffixes=data["preferred_characteristic_suffixes"],
                        icon_info=data.get("icon_info"),
                        icon_file_name=data.get("icon_file_name"),
                        icon_repo_path=data.get("icon_repo_path")
                    )
                    apps[app_info.repo.lower()] = app_info
            except Exception as e:
                logger.error(f"Error loading app definition from {json_file}: {e}")
                continue

    except Exception as e:
        logger.error(f"Error scanning app definitions directory: {e}")

    return apps

def load_app_definition(repo_name: str) -> Optional[AppInfo]:
    """Load application definition from JSON file.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        AppInfo object if found, None otherwise
    """
    if not DEFINITIONS_PATH:
        logger.error("App definitions path not initialized")
        return None

    # Convert repo name to lowercase for case-insensitive matching
    repo_name = repo_name.lower()

    # Handle owner/repo format
    if "/" in repo_name:
        repo_name = repo_name.split("/")[1]

    # Try to find and load the JSON file
    try:
        json_path = DEFINITIONS_PATH / f"{repo_name.capitalize()}.json"
        if not json_path.exists():
            json_path = DEFINITIONS_PATH / f"{repo_name}.json"
            if not json_path.exists():
                logger.debug(f"No app definition found for {repo_name}")
                return None

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Create AppInfo object from JSON data
        return AppInfo(
            owner=data["owner"],
            repo=data["repo"],
            app_display_name=data["app_display_name"],
            description=data["description"],
            category=data["category"],
            tags=data["tags"],
            hash_type=data["hash_type"],
            appimage_name_template=data["appimage_name_template"],
            sha_name=data["sha_name"],
            preferred_characteristic_suffixes=data["preferred_characteristic_suffixes"],
            icon_info=data.get("icon_info"),
            icon_file_name=data.get("icon_file_name"),
            icon_repo_path=data.get("icon_repo_path")
        )

    except Exception as e:
        logger.error(f"Error loading app definition for {repo_name}: {e}")
        return None

def get_app_display_name_for_owner_repo(owner: str, repo: str) -> str:
    """Get app display name for owner/repo combination.

    Args:
        owner: Repository owner/organization
        repo: Repository name

    Returns:
        Display name from app definition or repo name as fallback
    """
    app_info = load_app_definition(repo)
    return app_info.app_display_name if app_info else repo
