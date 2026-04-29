"""GitHub infrastructure - API client and release fetching."""

from my_unicorn.core.github.asset_selector import AssetSelector
from my_unicorn.core.github.client import ReleaseAPIClient
from my_unicorn.core.github.config_service import (
    GitHubConfig,
    extract_github_config,
    get_github_config,
)
from my_unicorn.core.github.models import Asset, Release
from my_unicorn.core.github.release_fetcher import GitHubClient, ReleaseFetcher

__all__ = [
    "Asset",
    "AssetSelector",
    "GitHubClient",
    "GitHubConfig",
    "Release",
    "ReleaseAPIClient",
    "ReleaseFetcher",
    "extract_github_config",
    "get_github_config",
]
