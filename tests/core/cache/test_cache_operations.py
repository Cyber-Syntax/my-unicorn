"""Tests for cache operations in ReleaseCacheManager.

This module tests basic cache operations including initialization,
cache file path generation, freshness checks, retrieval, and saving.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import orjson
import pytest

from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.types import CacheEntry


class TestReleaseCacheManager:
    """Test suite for basic ReleaseCacheManager operations."""

    def test_init_creates_cache_directory(
        self, mock_config_manager: MagicMock, tmp_path: Path
    ) -> None:
        """Test cache manager creates cache directory on initialization."""
        ReleaseCacheManager(mock_config_manager)

        cache_dir = tmp_path / "cache" / "releases"
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_init_with_custom_ttl(
        self, mock_config_manager: MagicMock
    ) -> None:
        """Test initialization with custom TTL."""
        cache_manager = ReleaseCacheManager(mock_config_manager, ttl_hours=48)
        assert cache_manager.ttl_hours == 48

    def test_init_without_config_manager(self) -> None:
        """Test initialization without explicit config manager."""
        with patch("my_unicorn.core.cache.ConfigManager") as mock_config_class:
            mock_config = MagicMock()
            mock_config.load_global_config.return_value = {
                "directory": {"cache": Path("/tmp")}
            }
            mock_config_class.return_value = mock_config

            cache_manager = ReleaseCacheManager()
            assert cache_manager.config_manager == mock_config
            assert cache_manager.ttl_hours == 24

    def test_get_cache_file_path(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test cache file path generation."""
        # Test stable cache (default)
        path = cache_manager._get_cache_file_path("owner", "repo")
        assert path.name == "owner_repo.json"
        assert path.parent.name == "releases"

        # Test prerelease cache
        path = cache_manager._get_cache_file_path(
            "owner", "repo", "prerelease"
        )
        assert path.name == "owner_repo_prerelease.json"

        # Test latest cache
        path = cache_manager._get_cache_file_path("owner", "repo", "latest")
        assert path.name == "owner_repo_latest.json"

    def test_is_cache_fresh_valid_cache(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test cache freshness check with valid cache."""
        # Create cache entry that's 1 hour old (should be fresh for 24h TTL)
        cached_at = datetime.now(UTC) - timedelta(hours=1)
        cache_entry = CacheEntry(
            {
                "cached_at": cached_at.isoformat(),
                "ttl_hours": 24,
                "release_data": {},
            }
        )

        assert cache_manager._is_cache_fresh(cache_entry) is True

    def test_is_cache_fresh_expired_cache(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test cache freshness check with expired cache."""
        # Create cache entry that's 25 hours old (expired for 24h TTL)
        cached_at = datetime.now(UTC) - timedelta(hours=25)
        cache_entry = CacheEntry(
            {
                "cached_at": cached_at.isoformat(),
                "ttl_hours": 24,
                "release_data": {},
            }
        )

        assert cache_manager._is_cache_fresh(cache_entry) is False

    def test_is_cache_fresh_custom_ttl(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test cache freshness with custom TTL in cache entry."""
        # Create cache entry that's 10 hours old with 8h TTL (expired)
        cached_at = datetime.now(UTC) - timedelta(hours=10)
        cache_entry = CacheEntry(
            {
                "cached_at": cached_at.isoformat(),
                "ttl_hours": 8,  # Custom TTL that overrides manager's default
                "release_data": {},
            }
        )

        assert cache_manager._is_cache_fresh(cache_entry) is False

    def test_is_cache_fresh_invalid_timestamp(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test cache freshness with invalid timestamp."""
        cache_entry = CacheEntry(
            {
                "cached_at": "invalid-timestamp",
                "ttl_hours": 24,
                "release_data": {},
            }
        )

        assert cache_manager._is_cache_fresh(cache_entry) is False

    @pytest.mark.asyncio
    async def test_get_cached_release_no_file(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test getting cached release when no cache file exists."""
        result = await cache_manager.get_cached_release("owner", "repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_release_fresh_cache(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
        tmp_path: Path,
    ) -> None:
        """Test getting cached release with fresh cache."""
        # Create a fresh cache file
        cache_file = cache_manager._get_cache_file_path("owner", "repo")
        cache_entry = CacheEntry(
            {
                "cached_at": datetime.now(UTC).isoformat(),
                "ttl_hours": 24,
                "release_data": sample_release_data,
            }
        )

        cache_file.write_bytes(orjson.dumps(cache_entry))  # pylint: disable=no-member

        result = await cache_manager.get_cached_release("owner", "repo")
        assert result == sample_release_data

    @pytest.mark.asyncio
    async def test_get_cached_release_expired_cache(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
    ) -> None:
        """Test getting cached release with expired cache."""
        # Create an expired cache file
        cache_file = cache_manager._get_cache_file_path("owner", "repo")
        cached_at = datetime.now(UTC) - timedelta(
            hours=25
        )  # 25h old, expires after 24h
        cache_entry = CacheEntry(
            {
                "cached_at": cached_at.isoformat(),
                "ttl_hours": 24,
                "release_data": sample_release_data,
            }
        )

        cache_file.write_bytes(orjson.dumps(cache_entry))  # pylint: disable=no-member

        result = await cache_manager.get_cached_release("owner", "repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_release_ignore_ttl(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
    ) -> None:
        """Test getting cached release while ignoring TTL."""
        # Create an expired cache file
        cache_file = cache_manager._get_cache_file_path("owner", "repo")
        cached_at = datetime.now(UTC) - timedelta(hours=25)  # Expired
        cache_entry = CacheEntry(
            {
                "cached_at": cached_at.isoformat(),
                "ttl_hours": 24,
                "release_data": sample_release_data,
            }
        )

        cache_file.write_bytes(orjson.dumps(cache_entry))  # pylint: disable=no-member

        # Should return data even if expired when ignore_ttl=True
        result = await cache_manager.get_cached_release(
            "owner", "repo", ignore_ttl=True
        )
        assert result == sample_release_data

    @pytest.mark.asyncio
    async def test_get_cached_release_corrupted_file(
        self, cache_manager: ReleaseCacheManager
    ) -> None:
        """Test getting cached release with corrupted cache file."""
        cache_file = cache_manager._get_cache_file_path("owner", "repo")

        # Write invalid JSON
        cache_file.write_bytes(b"invalid json content")

        result = await cache_manager.get_cached_release("owner", "repo")
        assert result is None

        # Corrupted file should be removed
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_save_release_data(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
    ) -> None:
        """Test saving release data to cache."""
        await cache_manager.save_release_data(
            "owner", "repo", sample_release_data
        )

        cache_file = cache_manager._get_cache_file_path("owner", "repo")
        assert cache_file.exists()

        # Verify cache content
        cache_data = orjson.loads(cache_file.read_bytes())  # pylint: disable=no-member
        assert "cached_at" in cache_data
        assert "ttl_hours" in cache_data
        assert "release_data" in cache_data
        assert cache_data["ttl_hours"] == 24

        # Note: Filtering now happens in github_client.py before caching,
        # so we just verify the data is stored as-is
        saved_assets = cache_data["release_data"]["assets"]
        assert saved_assets == sample_release_data["assets"]

    @pytest.mark.asyncio
    async def test_save_release_data_different_cache_types(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
    ) -> None:
        """Test saving release data for different cache types."""
        # Save to different cache types
        await cache_manager.save_release_data(
            "owner", "repo", sample_release_data, "stable"
        )
        await cache_manager.save_release_data(
            "owner", "repo", sample_release_data, "prerelease"
        )
        await cache_manager.save_release_data(
            "owner", "repo", sample_release_data, "latest"
        )

        # Check that separate files were created
        stable_file = cache_manager._get_cache_file_path(
            "owner", "repo", "stable"
        )
        prerelease_file = cache_manager._get_cache_file_path(
            "owner", "repo", "prerelease"
        )
        latest_file = cache_manager._get_cache_file_path(
            "owner", "repo", "latest"
        )

        assert stable_file.exists()
        assert prerelease_file.exists()
        assert latest_file.exists()

    @pytest.mark.asyncio
    async def test_save_release_data_atomic_write(
        self,
        cache_manager: ReleaseCacheManager,
        sample_release_data: dict[str, Any],
    ) -> None:
        """Test that save_release_data uses atomic writes."""
        # Mock a write failure during the rename step
        original_replace = Path.replace

        def mock_replace(self: Path, target: Path) -> Path:
            if str(self).endswith(".tmp"):
                raise OSError("Simulated write failure")
            return original_replace(self, target)

        with patch.object(Path, "replace", mock_replace):
            # This should handle the error gracefully
            await cache_manager.save_release_data(
                "owner", "repo", sample_release_data
            )

            # Cache file should not exist due to failed write
            cache_file = cache_manager._get_cache_file_path("owner", "repo")
            assert not cache_file.exists()
