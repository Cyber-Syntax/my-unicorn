#!/usr/bin/env python3
"""Path manipulation utilities for test framework.

This module provides consistent path construction for my-unicorn
configuration, apps, cache, and logs directories.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from pathlib import Path


def get_config_dir() -> Path:
    """Get my-unicorn config directory.

    Returns:
        Path to ~/.config/my-unicorn/
    """
    return Path.home() / ".config" / "my-unicorn"


def get_apps_dir() -> Path:
    """Get apps config directory.

    Returns:
        Path to ~/.config/my-unicorn/apps/
    """
    return get_config_dir() / "apps"


def get_cache_dir() -> Path:
    """Get cache directory.

    Returns:
        Path to ~/.config/my-unicorn/cache/releases/
    """
    return get_config_dir() / "cache" / "releases"


def get_log_dir() -> Path:
    """Get logs directory.

    Returns:
        Path to ~/.config/my-unicorn/logs/
    """
    return get_config_dir() / "logs"


def get_benchmark_dir() -> Path:
    """Get benchmark reports directory.

    Returns:
        Path to ./benchmark_reports/ (relative to test execution)
    """
    return Path("benchmark_reports")


def get_app_config_path(app_name: str) -> Path:
    """Get path to app config file.

    Args:
        app_name: Name of the app

    Returns:
        Path to ~/.config/my-unicorn/apps/{app_name}.json
    """
    return get_apps_dir() / f"{app_name}.json"


def get_cache_file_path(repo: str) -> Path:
    """Get path to cache file for repository.

    Args:
        repo: Repository in format "owner_repo" (e.g., "pbek_QOwnNotes")

    Returns:
        Path to ~/.config/my-unicorn/cache/releases/{repo}.json
    """
    return get_cache_dir() / f"{repo}.json"


def get_desktop_entry_path(app_name: str) -> Path:
    """Get path to desktop entry file.

    Args:
        app_name: Name of the app

    Returns:
        Path to ~/.local/share/applications/{app_name}.desktop
    """
    return (
        Path.home()
        / ".local"
        / "share"
        / "applications"
        / f"{app_name}.desktop"
    )


def get_backup_dir(app_name: str) -> Path:
    """Get path to app config backup directory.

    Args:
        app_name: Name of the app

    Returns:
        Path to ~/.config/my-unicorn/apps/backups/{app_name}/
    """
    return get_apps_dir() / "backups" / app_name


def get_global_config_path() -> Path:
    """Get path to global settings config file.

    Returns:
        Path to ~/.config/my-unicorn/settings.conf
    """
    return get_config_dir() / "settings.conf"


def get_catalog_dir() -> Path:
    """Get catalog directory from my-unicorn package.

    Returns:
        Path to src/my_unicorn/catalog/
    """
    # Navigate from scripts/tests/ to src/my_unicorn/catalog/
    return (
        Path(__file__).parent.parent.parent.parent
        / "src"
        / "my_unicorn"
        / "catalog"
    )
