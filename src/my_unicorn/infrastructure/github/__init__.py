"""GitHub infrastructure - API client and release fetching."""

from my_unicorn.infrastructure.github.client import ReleaseAPIClient
from my_unicorn.infrastructure.github.models import (
    Asset,
    AssetSelector,
    ChecksumFileInfo,
    Release,
)
from my_unicorn.infrastructure.github.operations import (
    extract_github_config,
    parse_github_url,
)
from my_unicorn.infrastructure.github.release_fetcher import (
    GitHubClient,
    ReleaseFetcher,
)

__all__ = [
    "Asset",
    "AssetSelector",
    "ChecksumFileInfo",
    "GitHubClient",
    "Release",
    "ReleaseAPIClient",
    "ReleaseFetcher",
    "extract_github_config",
    "parse_github_url",
]
