"""Persistent cache service for GitHub release data.

This module provides a simple, efficient caching system for GitHub API
responses to eliminate duplicate API requests and improve performance for
frequent operations like update checks and widget scripts.

The cache stores complete GitHubReleaseDetails objects with TTL (Time To
Live) validation to ensure data freshness while minimizing API calls.
"""

import contextlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import orjson

from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger
from my_unicorn.types import CacheEntry
from my_unicorn.utils.datetime_utils import (
    get_current_datetime_local,
    get_current_datetime_local_iso,
)

logger = get_logger(__name__)


class ReleaseCacheManager:
    """Manages persistent caching of GitHub release data.

    This cache system:
    - Stores complete GitHubReleaseDetails in JSON files
    - Uses TTL-based validation (default: 24 hours)
    - Provides transparent fallback to API calls
    - Handles cache corruption gracefully
    - Uses atomic writes to prevent file corruption

    Usage:
        # Create explicitly:
        config = ConfigManager()
        cache = ReleaseCacheManager(config, ttl_hours=24)

        # Or via dependency injection:
        fetcher = GitHubReleaseFetcher(session, cache_manager=cache)

    Note:
        This class no longer uses a singleton pattern. Create instances
        explicitly or accept via dependency injection.
    """

    def __init__(
        self, config_manager: ConfigManager | None = None, ttl_hours: int = 24
    ):
        """Initialize the release cache manager.

        Args:
            config_manager: Configuration manager instance (optional)
            ttl_hours: Cache TTL in hours (default: 24)

        """
        self.config_manager = config_manager or ConfigManager()
        self.ttl_hours = ttl_hours

        # Get cache directory from configuration
        global_config = self.config_manager.load_global_config()
        self.cache_dir = global_config["directory"]["cache"] / "releases"

        # Ensure cache directory exists
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file_path(
        self, owner: str, repo: str, cache_type: str = "stable"
    ) -> Path:
        """Get cache file path for a specific repository.

        Args:
            owner: Repository owner
            repo: Repository name
            cache_type: Type of cache ("stable", "prerelease", "latest")

        Returns:
            Path to cache file

        """
        if cache_type == "stable":
            filename = f"{owner}_{repo}.json"
        else:
            filename = f"{owner}_{repo}_{cache_type}.json"
        return self.cache_dir / filename

    def _is_cache_fresh(self, cache_entry: CacheEntry) -> bool:
        """Check if cache entry is still fresh based on TTL.

        Args:
            cache_entry: Cache entry to validate

        Returns:
            True if cache is fresh, False if expired

        """
        try:
            cached_at = datetime.fromisoformat(cache_entry["cached_at"])
            ttl_hours = cache_entry.get("ttl_hours", self.ttl_hours)
            expiry = cached_at + timedelta(hours=ttl_hours)
            return get_current_datetime_local() < expiry
        except (ValueError, KeyError) as e:
            logger.debug("Invalid cache timestamp format: %s", e)
            return False

    async def get_cached_release(
        self,
        owner: str,
        repo: str,
        ignore_ttl: bool = False,
        cache_type: str = "stable",
    ) -> dict[str, Any] | None:
        """Get cached release data if available and fresh.

        Args:
            owner: Repository owner
            repo: Repository name
            ignore_ttl: If True, return cached data regardless of TTL
                       (for --refresh logic)
            cache_type: Type of cache ("stable", "prerelease", "latest")

        Returns:
            Cached release data or None if not available/expired

        """
        cache_file = self._get_cache_file_path(owner, repo, cache_type)

        if not cache_file.exists():
            logger.debug("No cache file found for %s/%s", owner, repo)
            return None

        try:
            # Read cache file
            cache_data = orjson.loads(cache_file.read_bytes())  # pylint: disable=no-member
            cache_entry = CacheEntry(cache_data)

            # Validate cache freshness
            if not ignore_ttl and not self._is_cache_fresh(cache_entry):
                logger.debug("Cache expired for %s/%s", owner, repo)
                return None

            logger.debug("Cache hit for %s/%s", owner, repo)
            return cache_entry["release_data"]

        except (ValueError, KeyError, TypeError) as e:
            # orjson raises ValueError for JSON errors
            logger.warning(
                "Cache file corrupted for %s/%s: %s", owner, repo, e
            )
            # Remove corrupted cache file
            with contextlib.suppress(OSError):
                cache_file.unlink()
            return None
        except Exception as e:
            logger.error(
                "Unexpected error reading cache for %s/%s: %s", owner, repo, e
            )
            return None

    async def save_release_data(
        self,
        owner: str,
        repo: str,
        release_data: dict[str, Any],
        cache_type: str = "stable",
    ) -> None:
        """Save release data to cache with current timestamp.

        Note: Expects release_data to already be filtered by ReleaseFetcher.
        This method no longer performs filtering to follow DRY principle.
        Filtering happens in github_client.py via Release.filter_for_platform()
        before the data is passed to this method.

        Uses atomic write operation to prevent file corruption.

        Args:
            owner: Repository owner
            repo: Repository name
            release_data: Pre-filtered release data to cache
            cache_type: Type of cache ("stable", "prerelease", "latest")

        """
        cache_file = self._get_cache_file_path(owner, repo, cache_type)

        try:
            # Create cache entry with current timestamp
            # Note: No filtering here - data is pre-filtered by ReleaseFetcher
            cache_entry = CacheEntry(
                {
                    "cached_at": get_current_datetime_local_iso(),
                    "ttl_hours": self.ttl_hours,
                    "release_data": release_data,
                }
            )

            # Use atomic write: write to temporary file, then rename
            temp_file = cache_file.with_suffix(".tmp")
            temp_file.write_bytes(
                orjson.dumps(  # pylint: disable=no-member
                    cache_entry,
                    option=orjson.OPT_INDENT_2 | orjson.OPT_UTC_Z,  # pylint: disable=no-member
                )
            )

            # Atomic move (rename is atomic on most filesystems)
            temp_file.replace(cache_file)

            logger.debug("Cached release data for %s/%s", owner, repo)

        except Exception as e:
            logger.error("Failed to save cache for %s/%s: %s", owner, repo, e)
            # Clean up temporary file if it exists
            with contextlib.suppress(OSError, UnboundLocalError):
                temp_file.unlink()

    async def clear_cache(
        self, owner: str | None = None, repo: str | None = None
    ) -> None:
        """Clear cache entries.

        Args:
            owner: If specified with repo, clear specific app cache
            repo: If specified with owner, clear specific app cache
            If both None, clear all cache entries

        """
        try:
            if owner and repo:
                # Clear specific app cache
                cache_file = self._get_cache_file_path(owner, repo)
                if cache_file.exists():
                    cache_file.unlink()
                    logger.debug("Cleared cache for %s/%s", owner, repo)
            else:
                # Clear all cache
                cache_files = list(self.cache_dir.glob("*.json"))
                for cache_file in cache_files:
                    cache_file.unlink()
                logger.debug("Cleared %d cache entries", len(cache_files))

        except Exception as e:
            logger.error("Failed to clear cache: %s", e)

    async def cleanup_expired_cache(self, max_age_days: int = 30) -> None:
        """Remove cache files older than specified days.

        Args:
            max_age_days: Maximum age in days for cache files

        """
        try:
            cutoff = get_current_datetime_local() - timedelta(
                days=max_age_days
            )
            removed_count = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_data = orjson.loads(cache_file.read_bytes())  # pylint: disable=no-member
                    cached_at = datetime.fromisoformat(cache_data["cached_at"])

                    if cached_at < cutoff:
                        cache_file.unlink()
                        removed_count += 1

                except Exception:
                    # Remove corrupted cache files
                    cache_file.unlink()
                    removed_count += 1

            if removed_count > 0:
                logger.info("Cleaned up %d old cache entries", removed_count)

        except Exception as e:
            logger.error("Failed to cleanup cache: %s", e)

    async def get_cache_stats(self) -> dict[str, int | str]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics

        """
        try:
            cache_files = list(self.cache_dir.glob("*.json"))
            total_files = len(cache_files)
            fresh_count = 0
            expired_count = 0
            corrupted_count = 0

            for cache_file in cache_files:
                try:
                    cache_data = orjson.loads(cache_file.read_bytes())  # pylint: disable=no-member
                    cache_entry = CacheEntry(cache_data)

                    if self._is_cache_fresh(cache_entry):
                        fresh_count += 1
                    else:
                        expired_count += 1

                except Exception:
                    corrupted_count += 1

            return {
                "total_entries": total_files,
                "fresh_entries": fresh_count,
                "expired_entries": expired_count,
                "corrupted_entries": corrupted_count,
                "cache_directory": str(self.cache_dir),
                "ttl_hours": self.ttl_hours,
            }

        except Exception as e:
            logger.error("Failed to get cache stats: %s", e)
            return {
                "total_entries": 0,
                "fresh_entries": 0,
                "expired_entries": 0,
                "corrupted_entries": 0,
                "cache_directory": str(self.cache_dir),
                "ttl_hours": self.ttl_hours,
                "error": str(e),
            }


def get_cache_manager(ttl_hours: int = 24) -> ReleaseCacheManager:
    """Create a new ReleaseCacheManager instance.

    .. deprecated::
        This function is deprecated. Create ReleaseCacheManager directly
        or accept it via dependency injection instead.

    Args:
        ttl_hours: Cache TTL in hours (default: 24)

    Returns:
        New ReleaseCacheManager instance

    """
    return ReleaseCacheManager(ttl_hours=ttl_hours)
