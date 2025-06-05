"""Application catalog module.

This module handles loading and managing application definitions from JSON files.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Constants
MIN_WORD_LENGTH = 2

# Module-level variable to store the path to app definitions
_definitions_path: Path | None = None


@dataclass
class AppInfo:
    """Application information from definition file.

    Attributes:
        owner: Repository owner/organization
        repo: Repository name
        app_rename: Display name for the application
        description: Description of the application
        category: Application category
        tags: List of tags describing the application
        appimage_name_template: Template for AppImage filename
        preferred_characteristic_suffixes: List of characteristic suffixes in order of preference
        skip_verification: Whether to skip hash verification for this app
        use_asset_digest: Whether to use GitHub's asset digest for verification instead of SHA files
        use_github_release_desc: Whether to use GitHub release description for checksum extraction
        beta: Whether this app should prefer beta/pre-release versions
        hash_type: Type of hash used for verification (e.g., "sha256") - optional if skip_verification is True
        sha_name: Name of SHA file - optional if skip_verification or use_asset_digest is True
        icon_info: Direct URL to icon file
        icon_file_name: Preferred filename for saving the icon
        icon_repo_path: Repository path to icon file (fallback if icon_info not available)

    """

    owner: str
    repo: str
    app_rename: str
    description: str
    category: str
    tags: list[str]
    appimage_name_template: str
    preferred_characteristic_suffixes: list[str]
    skip_verification: bool = False
    use_asset_digest: bool = False
    use_github_release_desc: bool = False
    beta: bool = False
    hash_type: str | None = None
    sha_name: str | None = None
    icon_info: str | None = None
    icon_file_name: str | None = None
    icon_repo_path: str | None = None


def initialize_definitions_path(path: Path) -> None:
    """Initialize the path to application definitions.

    Args:
        path: Path to directory containing JSON app definitions

    """
    # Use globals() to avoid global statement
    globals()["_definitions_path"] = path
    logger.info("Initialized app definitions path: %s", path)


def get_all_apps() -> dict[str, AppInfo]:
    """Get all available app definitions.

    Returns:
        Dict mapping lowercase repo names to AppInfo objects

    """
    if not _definitions_path:
        logger.error("App definitions path not initialized")
        return {}

    apps: dict[str, AppInfo] = {}
    try:
        for json_file in _definitions_path.glob("*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    app_info = AppInfo(
                        owner=data["owner"],
                        repo=data["repo"],
                        app_rename=data["app_rename"],
                        description=data["description"],
                        category=data["category"],
                        tags=data["tags"],
                        appimage_name_template=data["appimage_name_template"],
                        preferred_characteristic_suffixes=data["preferred_characteristic_suffixes"],
                        skip_verification=data.get("skip_verification", False),
                        use_asset_digest=data.get("use_asset_digest", False),
                        use_github_release_desc=data.get("use_github_release_desc", False),
                        beta=data.get("beta", False),
                        hash_type=data.get("hash_type"),
                        sha_name=data.get("sha_name"),
                        icon_info=data.get("icon_info"),
                        icon_file_name=data.get("icon_file_name"),
                        icon_repo_path=data.get("icon_repo_path"),
                    )
                    apps[app_info.repo.lower()] = app_info
            except (KeyError, json.JSONDecodeError) as e:
                logger.error("Error loading app definition from %s: %s", json_file, e)
                continue

    except OSError as e:
        logger.error("Error scanning app definitions directory: %s", e)

    return apps


def find_app_by_owner_repo(owner: str, repo: str) -> AppInfo | None:
    """Find app definition by exact owner/repo match.

    Args:
        owner: Repository owner/organization
        repo: Repository name

    Returns:
        AppInfo object if found, None otherwise

    """
    all_apps = get_all_apps()

    for app_info in all_apps.values():
        if app_info.owner.lower() == owner.lower() and app_info.repo.lower() == repo.lower():
            return app_info

    return None


def load_app_definition(repo_name: str) -> AppInfo | None:
    """Load application definition from JSON file.

    Args:
        repo_name: Repository name (case-insensitive)

    Returns:
        AppInfo object if found, None otherwise

    """
    if not _definitions_path:
        logger.error("App definitions path not initialized")
        return None

    # Convert repo name to lowercase for case-insensitive matching
    repo_name = repo_name.lower()

    # Handle owner/repo format
    if "/" in repo_name:
        repo_name = repo_name.split("/")[1]

    # Try to find and load the JSON file
    try:
        json_path = _definitions_path / f"{repo_name.capitalize()}.json"
        if not json_path.exists():
            json_path = _definitions_path / f"{repo_name}.json"
            if not json_path.exists():
                logger.debug("No app definition found for %s", repo_name)
                return None

        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        # Create AppInfo object from JSON data
        return AppInfo(
            owner=data["owner"],
            repo=data["repo"],
            app_rename=data["app_rename"],
            description=data["description"],
            category=data["category"],
            tags=data["tags"],
            appimage_name_template=data["appimage_name_template"],
            preferred_characteristic_suffixes=data["preferred_characteristic_suffixes"],
            skip_verification=data.get("skip_verification", False),
            use_asset_digest=data.get("use_asset_digest", False),
            use_github_release_desc=data.get("use_github_release_desc", False),
            beta=data.get("beta", False),
            hash_type=data.get("hash_type"),
            sha_name=data.get("sha_name"),
            icon_info=data.get("icon_info"),
            icon_file_name=data.get("icon_file_name"),
            icon_repo_path=data.get("icon_repo_path"),
        )

    except (OSError, KeyError, json.JSONDecodeError) as e:
        logger.error("Error loading app definition for %s: %s", repo_name, e)
        return None


def get_app_rename_for_owner_repo(repo: str) -> str:
    """Get app display name for repo.

    Args:
        repo: Repository name

    Returns:
        Display name from app definition or repo name as fallback

    """
    app_info = load_app_definition(repo)
    return app_info.app_rename if app_info else repo


def _try_direct_repo_match(name_part: str, all_apps: dict[str, AppInfo]) -> AppInfo | None:
    """Try to find direct repository name match."""
    for _repo_name, app_info in all_apps.items():
        if app_info.repo.lower() == name_part:
            return app_info
    return None


def _try_display_name_match(name_part: str, all_apps: dict[str, AppInfo]) -> AppInfo | None:
    """Try to find app display name match."""
    for _repo_name, app_info in all_apps.items():
        display_name_normalized = app_info.app_rename.lower().replace(" ", "").replace("-", "")
        name_part_normalized = name_part.replace(" ", "").replace("-", "")

        if display_name_normalized == name_part_normalized:
            return app_info
    return None


def _try_repo_substring_match(basename: str, all_apps: dict[str, AppInfo]) -> AppInfo | None:
    """Try to find repository substring match."""
    for _repo_name, app_info in all_apps.items():
        if app_info.repo.lower() in basename:
            return app_info
    return None


def _try_display_name_substring_match(
    basename: str, all_apps: dict[str, AppInfo]
) -> AppInfo | None:
    """Try to find display name substring match."""
    for _repo_name, app_info in all_apps.items():
        display_name_parts = app_info.app_rename.lower().split()
        if any(part in basename for part in display_name_parts if len(part) > MIN_WORD_LENGTH):
            return app_info
    return None


def _try_special_case_match(basename: str) -> AppInfo | None:
    """Try to find special case pattern match."""
    special_cases = {
        "zen": "zen-browser",
        "freetube": "freetube",
        "obsidian": "obsidian",
        "joplin": "joplin",
    }

    for pattern, repo_name in special_cases.items():
        if pattern in basename.lower():
            app_info = load_app_definition(repo_name)
            if app_info:
                return app_info
    return None


def find_app_by_name_in_filename(filename: str) -> AppInfo | None:
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

    # Remove .AppImage extension and convert to lowercase for matching
    base_filename = filename.lower()
    if base_filename.endswith(".appimage"):
        base_filename = base_filename.removesuffix(".appimage")

    # Extract just the basename without path
    basename = Path(base_filename).name
    logger.debug("Looking for app match for filename: %s", basename)

    # Get all apps from the JSON-based catalog
    all_apps = get_all_apps()
    if not all_apps:
        logger.warning("No apps found in catalog")
        return None

    # Extract the first part before hyphen or version number (likely the app name)
    name_part = basename.split("-")[0].lower()

    # Define matching strategies in order of preference
    matching_strategies = [
        ("direct repo match", lambda: _try_direct_repo_match(name_part, all_apps)),
        ("display name match", lambda: _try_display_name_match(name_part, all_apps)),
        ("repo substring match", lambda: _try_repo_substring_match(basename, all_apps)),
        (
            "display name substring match",
            lambda: _try_display_name_substring_match(basename, all_apps),
        ),
        ("special case match", lambda: _try_special_case_match(basename)),
    ]

    # Try each strategy until one succeeds
    for strategy_name, strategy_func in matching_strategies:
        result = strategy_func()
        if result:
            logger.info("Found %s for '%s': %s", strategy_name, filename, result.repo)
            return result

    logger.warning("No app catalog match found for filename: %s", filename)
    return None
