"""API module for GitHub integration.

This module provides comprehensive GitHub API functionality including release management,
asset handling, checksum processing, and release description fetching.

Example usage:
    from src.api import GitHubAPI, ReleaseDescriptionFetcher
    
    # Main GitHub API client
    api = GitHubAPI(owner="owner", repo="repo")
    release_data = api.get_latest_release()
    
    # Release description fetching
    fetcher = ReleaseDescriptionFetcher(owner="owner", repo="repo")
    description = fetcher.fetch_latest_release_description()
"""

# Core API functionality
from src.api.github_api import GitHubAPI
from src.api.release_manager import ReleaseManager
from src.api.release_processor import ReleaseProcessor
from src.api.release_description_fetcher import ReleaseDescriptionFetcher

# Asset data models
from src.api.assets import (
    ReleaseAsset,
    AppImageAsset,
    SHAAsset,
    ArchitectureInfo,
    ReleaseInfo,
)

# Asset and SHA management
from src.api.sha_asset_finder import SHAAssetFinder
from src.api.sha_manager import SHAManager

from src.api.selector import AppImageSelector

__all__ = [
    # Core API classes
    "GitHubAPI",
    "ReleaseManager", 
    "ReleaseProcessor",
    "ReleaseDescriptionFetcher",
    # Asset data models
    "ReleaseAsset",
    "AppImageAsset",
    "SHAAsset", 
    "ArchitectureInfo",
    "ReleaseInfo",
    # Asset management
    "SHAAssetFinder", 
    "SHAManager",
    # Utilities
    "AppImageSelector",
]