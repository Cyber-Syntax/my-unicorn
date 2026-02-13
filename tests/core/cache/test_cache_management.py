"""Tests for cache management operations in ReleaseCacheManager.

This module tests cache management operations including clearing,
cleanup, and statistics gathering.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import patch

import orjson
import pytest

from my_unicorn.types import CacheEntry


class TestReleaseCacheManager:
    """Test suite for ReleaseCacheManager cache management operations."""

    @pytest.mark.asyncio
    async def test_clear_cache_specific_app(
        self, cache_manager: Any, sample_release_data: Any
    ) -> None:
        """Test clearing cache for a specific app."""
        # Create cache file
        await cache_manager.save_release_data(
            "owner", "repo", sample_release_data
        )
        cache_file = cache_manager._get_cache_file_path("owner", "repo")
        assert cache_file.exists()

        # Clear specific app cache
        await cache_manager.clear_cache("owner", "repo")
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_clear_cache_all(
        self, cache_manager: Any, sample_release_data: Any
    ) -> None:
        """Test clearing all cache entries."""
        # Create multiple cache files
        await cache_manager.save_release_data(
            "owner1", "repo1", sample_release_data
        )
        await cache_manager.save_release_data(
            "owner2", "repo2", sample_release_data
        )

        cache_file1 = cache_manager._get_cache_file_path("owner1", "repo1")
        cache_file2 = cache_manager._get_cache_file_path("owner2", "repo2")

        assert cache_file1.exists()
        assert cache_file2.exists()

        # Clear all cache
        await cache_manager.clear_cache()

        assert not cache_file1.exists()
        assert not cache_file2.exists()

    @pytest.mark.asyncio
    async def test_clear_cache_error_handling(
        self, cache_manager: Any
    ) -> None:
        """Test error handling in cache clearing."""
        # Mock an error during file deletion
        with patch(
            "pathlib.Path.unlink", side_effect=OSError("Permission denied")
        ):
            # Should not raise exception
            await cache_manager.clear_cache("owner", "repo")

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(
        self, cache_manager: Any, sample_release_data: Any
    ) -> None:
        """Test cleanup of expired cache entries."""
        # Create fresh cache
        await cache_manager.save_release_data(
            "owner1", "repo1", sample_release_data
        )

        # Create old cache by manually setting timestamp
        old_cache_file = cache_manager._get_cache_file_path("owner2", "repo2")
        old_timestamp = datetime.now(UTC) - timedelta(days=35)
        old_cache_entry = CacheEntry(
            {
                "cached_at": old_timestamp.isoformat(),
                "ttl_hours": 24,
                "release_data": sample_release_data,
            }
        )
        old_cache_file.write_bytes(orjson.dumps(old_cache_entry))  # pylint: disable=no-member

        fresh_cache_file = cache_manager._get_cache_file_path(
            "owner1", "repo1"
        )

        # Both files should exist initially
        assert fresh_cache_file.exists()
        assert old_cache_file.exists()

        # Cleanup with 30-day threshold
        await cache_manager.cleanup_expired_cache(max_age_days=30)

        # Only fresh file should remain
        assert fresh_cache_file.exists()
        assert not old_cache_file.exists()

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache_corrupted_files(
        self, cache_manager: Any
    ) -> None:
        """Test cleanup removes corrupted cache files."""
        # Create corrupted cache file
        corrupted_file = cache_manager.cache_dir / "corrupted.json"
        corrupted_file.write_bytes(b"invalid json")

        assert corrupted_file.exists()

        await cache_manager.cleanup_expired_cache()

        # Corrupted file should be removed
        assert not corrupted_file.exists()

    @pytest.mark.asyncio
    async def test_get_cache_stats(
        self, cache_manager: Any, sample_release_data: Any
    ) -> None:
        """Test getting cache statistics."""
        # Create fresh cache
        await cache_manager.save_release_data(
            "owner1", "repo1", sample_release_data
        )

        # Create expired cache
        expired_file = cache_manager._get_cache_file_path("owner2", "repo2")
        old_timestamp = datetime.now(UTC) - timedelta(hours=25)  # Expired
        expired_entry = CacheEntry(
            {
                "cached_at": old_timestamp.isoformat(),
                "ttl_hours": 24,
                "release_data": sample_release_data,
            }
        )
        expired_file.write_bytes(orjson.dumps(expired_entry))  # pylint: disable=no-member

        # Create corrupted cache
        corrupted_file = cache_manager.cache_dir / "corrupted.json"
        corrupted_file.write_bytes(b"invalid json")

        stats = await cache_manager.get_cache_stats()

        assert stats["total_entries"] == 3
        assert stats["fresh_entries"] == 1
        assert stats["expired_entries"] == 1
        assert stats["corrupted_entries"] == 1
        assert stats["ttl_hours"] == 24
        assert "cache_directory" in stats

    @pytest.mark.asyncio
    async def test_get_cache_stats_error_handling(
        self, cache_manager: Any
    ) -> None:
        """Test cache stats error handling."""
        # Mock the glob method at the module level where it's called
        with patch("pathlib.Path.glob", side_effect=OSError("Access denied")):
            stats = await cache_manager.get_cache_stats()

            assert stats["total_entries"] == 0
            assert stats["fresh_entries"] == 0
            assert stats["expired_entries"] == 0
            assert stats["corrupted_entries"] == 0
            assert "error" in stats

    @pytest.mark.asyncio
    async def test_cache_with_different_cache_types(
        self, cache_manager: Any, sample_release_data: Any
    ) -> None:
        """Test caching and retrieval with different cache types."""
        # Test all cache types
        cache_types = ["stable", "prerelease", "latest"]

        # Note: Filtering now happens in github_client.py before caching,
        # so we just verify the data is stored and retrieved as-is
        for cache_type in cache_types:
            # Save data for each cache type
            await cache_manager.save_release_data(
                "owner", "repo", sample_release_data, cache_type
            )

            # Retrieve data for each cache type - should match original data
            result = await cache_manager.get_cached_release(
                "owner", "repo", cache_type=cache_type
            )
            assert result == sample_release_data
