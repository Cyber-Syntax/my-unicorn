"""Persistent cache service for GitHub release data.

This module provides a simple, efficient caching system for GitHub API responses
to eliminate duplicate API requests and improve performance for frequent operations
like update checks and widget scripts.

The cache stores complete GitHubReleaseDetails objects with TTL (Time To Live)
validation to ensure data freshness while minimizing API calls.
"""

import contextlib
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, TypedDict

import orjson

from my_unicorn.config import ConfigManager
from my_unicorn.logger import get_logger
from my_unicorn.utils import is_appimage_file, is_checksum_file

logger = get_logger(__name__)


class CacheEntry(TypedDict):
    """Cache entry structure for storing release data."""

    cached_at: str  # ISO 8601 timestamp
    ttl_hours: int  # Cache TTL in hours
    release_data: dict[str, Any]  # GitHubReleaseDetails structure


class ReleaseCacheManager:
    """Manages persistent caching of GitHub release data.

    This cache system:
    - Stores complete GitHubReleaseDetails in JSON files
    - Uses TTL-based validation (default: 24 hours)
    - Provides transparent fallback to API calls
    - Handles cache corruption gracefully
    - Uses atomic writes to prevent file corruption
    """

    def __init__(self, config_manager: ConfigManager | None = None, ttl_hours: int = 24):
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

    def _is_checksum_file(self, filename: str) -> bool:
        """Check if filename is a checksum file for an AppImage.

        This method checks if the file is a checksum file AND if it's specifically
        a checksum for an AppImage file. This prevents keeping checksums for
        irrelevant files like tar.xz, zip, dmg, etc.

        Use the consolidated checksum file detection from utils.

        Args:
            filename: Name of the file to check

        Returns:
            True if the file is a checksum for an AppImage, False otherwise

        """
        return is_checksum_file(filename, require_appimage_base=True)

    def _is_appimage_file(self, filename: str) -> bool:
        """Check if filename is an AppImage file.

        Use the consolidated AppImage file detection from utils.

        Args:
            filename: Name of the file to check

        Returns:
            True if the file is an AppImage, False otherwise

        """
        return is_appimage_file(filename)

    def _filter_relevant_assets(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Filter assets to keep only AppImages and related checksum files.

        This reduces cache file size by removing irrelevant assets like:
        - Source code archives (.zip, .tar.gz)
        - Documentation files
        - Binary packages for other platforms
        - Other non-AppImage executables

        Args:
            assets: List of asset dictionaries from GitHub release

        Returns:
            Filtered list containing only AppImages and checksum files

        """
        relevant_assets = []

        for asset in assets:
            filename = asset.get("name", "")
            if not filename:
                continue

            # Keep AppImages
            if self._is_appimage_file(filename):
                relevant_assets.append(asset)
                logger.debug("Including AppImage: %s", filename)
                continue

            # Keep checksum files (only for AppImages)
            if self._is_checksum_file(filename):
                relevant_assets.append(asset)
                logger.debug("Including AppImage checksum file: %s", filename)
                continue

            # Log what we're filtering out for debugging
            logger.debug("Filtering out non-AppImage asset: %s", filename)

        # Count AppImages vs checksums for better logging
        appimage_count = sum(
            1 for asset in relevant_assets if self._is_appimage_file(asset.get("name", ""))
        )
        checksum_count = len(relevant_assets) - appimage_count

        logger.debug(
            "Asset filtering: %d -> %d assets (%d AppImages + %d AppImage checksums)",
            len(assets),
            len(relevant_assets),
            appimage_count,
            checksum_count,
        )

        return relevant_assets

    def _get_cache_file_path(self, owner: str, repo: str, cache_type: str = "stable") -> Path:
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
            return datetime.now(UTC) < expiry
        except (ValueError, KeyError) as e:
            logger.debug("Invalid cache timestamp format: %s", e)
            return False

    async def get_cached_release(
        self, owner: str, repo: str, ignore_ttl: bool = False, cache_type: str = "stable"
    ) -> dict[str, Any] | None:
        """Get cached release data if available and fresh.

        Args:
            owner: Repository owner
            repo: Repository name
            ignore_ttl: If True, return cached data regardless of TTL (for --refresh logic)
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
            logger.warning("Cache file corrupted for %s/%s: %s", owner, repo, e)
            # Remove corrupted cache file
            with contextlib.suppress(OSError):
                cache_file.unlink()
            return None
        except Exception as e:
            logger.error("Unexpected error reading cache for %s/%s: %s", owner, repo, e)
            return None

    async def save_release_data(
        self, owner: str, repo: str, release_data: dict[str, Any], cache_type: str = "stable"
    ) -> None:
        """Save release data to cache with current timestamp.

        Uses atomic write operation to prevent file corruption.

        Args:
            owner: Repository owner
            repo: Repository name
            release_data: Release data to cache
            cache_type: Type of cache ("stable", "prerelease", "latest")

        """
        cache_file = self._get_cache_file_path(owner, repo, cache_type)

        try:
            # Filter release data to keep only relevant assets (AppImages + checksums)
            filtered_release_data = release_data.copy()
            if "assets" in filtered_release_data:
                original_count = len(filtered_release_data["assets"])
                filtered_release_data["assets"] = self._filter_relevant_assets(
                    filtered_release_data["assets"]
                )
                logger.debug(
                    "Cache storage optimization: filtered assets from %d to %d for %s/%s",
                    original_count,
                    len(filtered_release_data["assets"]),
                    owner,
                    repo,
                )

            # Create cache entry with current timestamp
            cache_entry = CacheEntry(
                {
                    "cached_at": datetime.now(UTC).isoformat(),
                    "ttl_hours": self.ttl_hours,
                    "release_data": filtered_release_data,
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

    async def clear_cache(self, owner: str | None = None, repo: str | None = None) -> None:
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
                    logger.info("Cleared cache for %s/%s", owner, repo)
            else:
                # Clear all cache
                cache_files = list(self.cache_dir.glob("*.json"))
                for cache_file in cache_files:
                    cache_file.unlink()
                logger.info("Cleared %d cache entries", len(cache_files))

        except Exception as e:
            logger.error("Failed to clear cache: %s", e)

    async def cleanup_expired_cache(self, max_age_days: int = 30) -> None:
        """Remove cache files older than specified days.

        Args:
            max_age_days: Maximum age in days for cache files

        """
        try:
            cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
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


# Module-level cache manager instance
_cache_manager: ReleaseCacheManager | None = None


def get_cache_manager(ttl_hours: int = 24) -> ReleaseCacheManager:
    """Get the global cache manager instance.

    Args:
        ttl_hours: Cache TTL in hours (default: 24)

    Returns:
        ReleaseCacheManager instance

    """
    if _cache_manager is None:
        return ReleaseCacheManager(ttl_hours=ttl_hours)
    return _cache_manager
