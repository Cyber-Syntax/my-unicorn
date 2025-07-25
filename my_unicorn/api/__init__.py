"""API module for GitHub integration.

This module provides comprehensive GitHub API functionality including release management,
asset handling, checksum processing, and release description fetching.

Example usage:
    from my_unicorn.api import GitHubAPI, ReleaseDescriptionFetcher
    
    # Main GitHub API client
    api = GitHubAPI(owner="owner", repo="repo")
    release_data = api.get_latest_release()
    
    # Release description fetching
    fetcher = ReleaseDescriptionFetcher(owner="owner", repo="repo")
    description = fetcher.fetch_latest_release_description()
"""

# Core API functionality
from my_unicorn.api.github_api import GitHubAPI
from my_unicorn.api.release_manager import ReleaseManager
from my_unicorn.api.release_processor import ReleaseProcessor
from my_unicorn.api.release_description_fetcher import ReleaseDescriptionFetcher

# Asset data models
from my_unicorn.api.assets import (
    AppImageAsset,
    SHAAsset,
    ReleaseInfo,
)

# Asset and SHA management
from my_unicorn.api.sha_asset_finder import SHAAssetFinder
from my_unicorn.api.sha_manager import SHAManager

from my_unicorn.api.selector import AppImageSelector

__all__ = [
    # Core API classes
    "GitHubAPI",
    "ReleaseManager", 
    "ReleaseProcessor",
    "ReleaseDescriptionFetcher",
    "AppImageAsset",
    "SHAAsset", 
    "ReleaseInfo",
    # Asset management
    "SHAAssetFinder", 
    "SHAManager",
    # Utilities
    "AppImageSelector",
]