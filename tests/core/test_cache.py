"""Tests for cache service functionality.

This module contains comprehensive tests for the ReleaseCacheManager class
which provides persistent caching of GitHub release data with TTL validation.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import orjson
import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.types import CacheEntry


class TestReleaseCacheManager:
    """Test suite for ReleaseCacheManager."""

    @pytest.fixture
    def mock_config_manager(self, tmp_path):
        """Create a mock config manager with a temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        tmp_path / "cache" / "releases"
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(self, mock_config_manager):
        """Create a ReleaseCacheManager instance for testing."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def sample_release_data(self):
        """Sample release data for testing."""
        return {
            "tag_name": "v1.0.0",
            "name": "Test Release",
            "published_at": "2025-08-30T12:00:00Z",
            "assets": [
                {
                    "name": "test.AppImage",
                    "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/test.AppImage",
                    "size": 12345678,
                },
                {
                    "name": "test.AppImage.sha256",
                    "browser_download_url": "https://github.com/test/test/releases/download/v1.0.0/test.AppImage.sha256",
                    "size": 64,
                },
                {
                    "name": "source.tar.gz",  # Should be filtered out
                    "browser_download_url": "https://github.com/test/test/archive/v1.0.0.tar.gz",
                    "size": 98765,
                },
            ],
        }

    def test_init_creates_cache_directory(self, mock_config_manager, tmp_path):
        """Test cache manager creates cache directory on initialization."""
        ReleaseCacheManager(mock_config_manager)

        cache_dir = tmp_path / "cache" / "releases"
        assert cache_dir.exists()
        assert cache_dir.is_dir()

    def test_init_with_custom_ttl(self, mock_config_manager):
        """Test initialization with custom TTL."""
        cache_manager = ReleaseCacheManager(mock_config_manager, ttl_hours=48)
        assert cache_manager.ttl_hours == 48

    def test_init_without_config_manager(self):
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

    # NOTE: _is_appimage_file, _is_checksum_file, and _filter_relevant_assets
    # have been removed from ReleaseCacheManager as filtering now happens
    # in github_client.py via Release.filter_for_platform() before caching.
    # These tests are no longer needed as the cache manager no longer
    # performs filtering (DRY principle).

    def test_get_cache_file_path(self, cache_manager):
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

    def test_is_cache_fresh_valid_cache(self, cache_manager):
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

    def test_is_cache_fresh_expired_cache(self, cache_manager):
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

    def test_is_cache_fresh_custom_ttl(self, cache_manager):
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

    def test_is_cache_fresh_invalid_timestamp(self, cache_manager):
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
    async def test_get_cached_release_no_file(self, cache_manager):
        """Test getting cached release when no cache file exists."""
        result = await cache_manager.get_cached_release("owner", "repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cached_release_fresh_cache(
        self, cache_manager, sample_release_data, tmp_path
    ):
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
        self, cache_manager, sample_release_data
    ):
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
        self, cache_manager, sample_release_data
    ):
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
    async def test_get_cached_release_corrupted_file(self, cache_manager):
        """Test getting cached release with corrupted cache file."""
        cache_file = cache_manager._get_cache_file_path("owner", "repo")

        # Write invalid JSON
        cache_file.write_bytes(b"invalid json content")

        result = await cache_manager.get_cached_release("owner", "repo")
        assert result is None

        # Corrupted file should be removed
        assert not cache_file.exists()

    @pytest.mark.asyncio
    async def test_save_release_data(self, cache_manager, sample_release_data):
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
        self, cache_manager, sample_release_data
    ):
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
        self, cache_manager, sample_release_data
    ):
        """Test that save_release_data uses atomic writes."""
        # Mock a write failure during the rename step
        original_replace = Path.replace

        def mock_replace(self, target):
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

    @pytest.mark.asyncio
    async def test_clear_cache_specific_app(
        self, cache_manager, sample_release_data
    ):
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
    async def test_clear_cache_all(self, cache_manager, sample_release_data):
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
    async def test_clear_cache_error_handling(self, cache_manager):
        """Test error handling in cache clearing."""
        # Mock an error during file deletion
        with patch(
            "pathlib.Path.unlink", side_effect=OSError("Permission denied")
        ):
            # Should not raise exception
            await cache_manager.clear_cache("owner", "repo")

    @pytest.mark.asyncio
    async def test_cleanup_expired_cache(
        self, cache_manager, sample_release_data
    ):
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
    async def test_cleanup_expired_cache_corrupted_files(self, cache_manager):
        """Test cleanup removes corrupted cache files."""
        # Create corrupted cache file
        corrupted_file = cache_manager.cache_dir / "corrupted.json"
        corrupted_file.write_bytes(b"invalid json")

        assert corrupted_file.exists()

        await cache_manager.cleanup_expired_cache()

        # Corrupted file should be removed
        assert not corrupted_file.exists()

    @pytest.mark.asyncio
    async def test_get_cache_stats(self, cache_manager, sample_release_data):
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
    async def test_get_cache_stats_error_handling(self, cache_manager):
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
        self, cache_manager, sample_release_data
    ):
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


class TestChecksumFilesPersistence:
    """Tests for checksum_files array persistence in cache.

    These tests verify that checksum_file data discovered during verification
    can be properly persisted to and restored from the cache. This enables
    reuse of checksum data without re-downloading checksum files.
    """

    @pytest.fixture
    def mock_config_manager(self, tmp_path):
        """Create a mock config manager with a temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(self, mock_config_manager):
        """Create a ReleaseCacheManager instance for testing."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def sample_checksum_files(self):
        """Sample checksum_files array for testing."""
        return [
            {
                "source": "https://github.com/test/app/releases/download/v1.0.0/SHA256SUMS.txt",
                "filename": "SHA256SUMS.txt",
                "algorithm": "SHA256",
                "hashes": {
                    "app-1.0.0-x86_64.AppImage": "a" * 64,
                    "app-1.0.0-aarch64.AppImage": "b" * 64,
                },
            }
        ]

    @pytest.fixture
    def release_data_with_checksum_files(self, sample_checksum_files):
        """Release data containing checksum_files array."""
        return {
            "owner": "test",
            "repo": "app",
            "version": "1.0.0",
            "prerelease": False,
            "assets": [
                {
                    "name": "app-1.0.0-x86_64.AppImage",
                    "size": 50000000,
                    "digest": "sha256:" + "a" * 64,
                    "browser_download_url": "https://github.com/test/app/releases/download/v1.0.0/app-1.0.0-x86_64.AppImage",
                }
            ],
            "original_tag_name": "v1.0.0",
            "checksum_files": sample_checksum_files,
        }

    @pytest.fixture
    def release_data_without_checksum_files(self):
        """Legacy release data without checksum_files array."""
        return {
            "owner": "test",
            "repo": "legacy-app",
            "version": "0.9.0",
            "prerelease": False,
            "assets": [
                {
                    "name": "legacy-app-0.9.0.AppImage",
                    "size": 40000000,
                    "digest": None,
                    "browser_download_url": "https://github.com/test/legacy-app/releases/download/v0.9.0/legacy-app-0.9.0.AppImage",
                }
            ],
            "original_tag_name": "v0.9.0",
        }

    @pytest.mark.asyncio
    async def test_save_release_data_with_checksum_files(
        self, cache_manager, release_data_with_checksum_files
    ):
        """Verify checksum_files array is persisted to cache JSON."""
        await cache_manager.save_release_data(
            "test", "app", release_data_with_checksum_files
        )

        cache_file = cache_manager._get_cache_file_path("test", "app")
        assert cache_file.exists()

        cache_data = orjson.loads(cache_file.read_bytes())
        saved_release = cache_data["release_data"]

        assert "checksum_files" in saved_release
        assert len(saved_release["checksum_files"]) == 1
        checksum_entry = saved_release["checksum_files"][0]
        assert checksum_entry["filename"] == "SHA256SUMS.txt"
        assert checksum_entry["algorithm"] == "SHA256"
        assert "app-1.0.0-x86_64.AppImage" in checksum_entry["hashes"]

    @pytest.mark.asyncio
    async def test_load_release_data_with_checksum_files(
        self, cache_manager, release_data_with_checksum_files
    ):
        """Verify checksum_files array is restored from cache JSON."""
        await cache_manager.save_release_data(
            "test", "app", release_data_with_checksum_files
        )

        result = await cache_manager.get_cached_release("test", "app")

        assert result is not None
        assert "checksum_files" in result
        expected = release_data_with_checksum_files["checksum_files"]
        assert result["checksum_files"] == expected

    @pytest.mark.asyncio
    async def test_backward_compatible_cache_without_checksum_files(
        self, cache_manager, release_data_without_checksum_files
    ):
        """Verify old cache entries without checksum_files load correctly."""
        await cache_manager.save_release_data(
            "test", "legacy-app", release_data_without_checksum_files
        )

        result = await cache_manager.get_cached_release("test", "legacy-app")

        assert result is not None
        assert result["owner"] == "test"
        assert result["repo"] == "legacy-app"
        assert "checksum_files" not in result

    @pytest.mark.asyncio
    async def test_checksum_files_with_multiple_entries(self, cache_manager):
        """Verify multiple checksum_files from different sources persist."""
        release_data = {
            "owner": "multi",
            "repo": "checksums",
            "version": "2.0.0",
            "prerelease": False,
            "assets": [
                {
                    "name": "app-2.0.0.AppImage",
                    "size": 60000000,
                    "digest": "sha512:" + "c" * 128,
                    "browser_download_url": "https://github.com/multi/checksums/releases/download/v2.0.0/app-2.0.0.AppImage",
                }
            ],
            "original_tag_name": "v2.0.0",
            "checksum_files": [
                {
                    "source": "https://github.com/multi/checksums/releases/download/v2.0.0/SHA256SUMS",
                    "filename": "SHA256SUMS",
                    "algorithm": "SHA256",
                    "hashes": {"app-2.0.0.AppImage": "d" * 64},
                },
                {
                    "source": "https://github.com/multi/checksums/releases/download/v2.0.0/SHA512SUMS",
                    "filename": "SHA512SUMS",
                    "algorithm": "SHA512",
                    "hashes": {"app-2.0.0.AppImage": "e" * 128},
                },
            ],
        }

        await cache_manager.save_release_data(
            "multi", "checksums", release_data
        )
        result = await cache_manager.get_cached_release("multi", "checksums")

        assert result is not None
        assert len(result["checksum_files"]) == 2
        assert result["checksum_files"][0]["algorithm"] == "SHA256"
        assert result["checksum_files"][1]["algorithm"] == "SHA512"

    @pytest.mark.asyncio
    async def test_checksum_files_preserved_across_cache_types(
        self, cache_manager, release_data_with_checksum_files
    ):
        """Verify checksum_files persist correctly for all cache types."""
        cache_types = ["stable", "prerelease", "latest"]

        for cache_type in cache_types:
            await cache_manager.save_release_data(
                "test", "app", release_data_with_checksum_files, cache_type
            )

            result = await cache_manager.get_cached_release(
                "test", "app", cache_type=cache_type
            )

            msg = f"Cache type {cache_type} should return data"
            assert result is not None, msg
            assert "checksum_files" in result
            assert len(result["checksum_files"]) == 1


class TestChecksumFileHelperMethods:
    """Tests for checksum file helper methods in ReleaseCacheManager.

    These tests verify the store_checksum_file, get_checksum_file, and
    has_checksum_file methods that enable targeted operations on cached
    checksum file data.
    """

    @pytest.fixture
    def mock_config_manager(self, tmp_path):
        """Create a mock config manager with a temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(self, mock_config_manager):
        """Create a ReleaseCacheManager instance for testing."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def base_release_data(self):
        """Base release data without checksum_files."""
        return {
            "owner": "test",
            "repo": "helper-app",
            "version": "2.0.0",
            "prerelease": False,
            "assets": [
                {
                    "name": "helper-app-2.0.0.AppImage",
                    "size": 55000000,
                    "digest": "sha256:" + "f" * 64,
                    "browser_download_url": "https://github.com/test/helper-app/releases/download/v2.0.0/helper-app-2.0.0.AppImage",
                }
            ],
            "original_tag_name": "v2.0.0",
        }

    @pytest.fixture
    def checksum_file_data(self):
        """Sample checksum file data for testing."""
        return {
            "source": "https://github.com/test/helper-app/releases/download/v2.0.0/SHA256SUMS.txt",
            "filename": "SHA256SUMS.txt",
            "algorithm": "SHA256",
            "hashes": {
                "helper-app-2.0.0.AppImage": "f" * 64,
            },
        }

    @pytest.mark.asyncio
    async def test_store_checksum_file_adds_to_cache(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify store_checksum_file adds checksum file to existing cache."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        result = await cache_manager.store_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            file_data=checksum_file_data,
        )

        assert result is True

        cached = await cache_manager.get_cached_release("test", "helper-app")
        assert cached is not None
        assert "checksum_files" in cached
        assert len(cached["checksum_files"]) == 1
        assert cached["checksum_files"][0]["filename"] == "SHA256SUMS.txt"

    @pytest.mark.asyncio
    async def test_store_checksum_file_returns_false_when_no_cache(
        self, cache_manager, checksum_file_data
    ):
        """Verify store_checksum_file returns False when no cache exists."""
        result = await cache_manager.store_checksum_file(
            owner="nonexistent",
            repo="app",
            version="1.0.0",
            file_data=checksum_file_data,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_store_checksum_file_returns_false_on_version_mismatch(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify store_checksum_file returns False on version mismatch."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        result = await cache_manager.store_checksum_file(
            owner="test",
            repo="helper-app",
            version="3.0.0",
            file_data=checksum_file_data,
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_store_checksum_file_updates_existing_entry(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify store_checksum_file updates entry with same source URL."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        await cache_manager.store_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            file_data=checksum_file_data,
        )

        updated_data = {
            **checksum_file_data,
            "hashes": {"helper-app-2.0.0.AppImage": "g" * 64},
        }
        result = await cache_manager.store_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            file_data=updated_data,
        )

        assert result is True

        cached = await cache_manager.get_cached_release("test", "helper-app")
        assert len(cached["checksum_files"]) == 1
        checksum_entry = cached["checksum_files"][0]
        stored_hash = checksum_entry["hashes"]["helper-app-2.0.0.AppImage"]
        assert stored_hash == "g" * 64

    @pytest.mark.asyncio
    async def test_store_checksum_file_adds_multiple_files(
        self, cache_manager, base_release_data
    ):
        """Verify store_checksum_file can add multiple checksum files."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        sha256_data = {
            "source": "https://github.com/test/helper-app/releases/download/v2.0.0/SHA256SUMS",
            "filename": "SHA256SUMS",
            "algorithm": "SHA256",
            "hashes": {"helper-app-2.0.0.AppImage": "a" * 64},
        }
        sha512_data = {
            "source": "https://github.com/test/helper-app/releases/download/v2.0.0/SHA512SUMS",
            "filename": "SHA512SUMS",
            "algorithm": "SHA512",
            "hashes": {"helper-app-2.0.0.AppImage": "b" * 128},
        }

        await cache_manager.store_checksum_file(
            "test", "helper-app", "2.0.0", sha256_data
        )
        await cache_manager.store_checksum_file(
            "test", "helper-app", "2.0.0", sha512_data
        )

        cached = await cache_manager.get_cached_release("test", "helper-app")
        assert len(cached["checksum_files"]) == 2

    @pytest.mark.asyncio
    async def test_get_checksum_file_returns_matching_entry(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify get_checksum_file retrieves correct checksum file."""
        release_with_checksum = {
            **base_release_data,
            "checksum_files": [checksum_file_data],
        }
        await cache_manager.save_release_data(
            "test", "helper-app", release_with_checksum
        )

        result = await cache_manager.get_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            source_url=checksum_file_data["source"],
        )

        assert result is not None
        assert result["filename"] == "SHA256SUMS.txt"
        assert result["algorithm"] == "SHA256"

    @pytest.mark.asyncio
    async def test_get_checksum_file_returns_none_when_not_found(
        self, cache_manager, base_release_data
    ):
        """Verify get_checksum_file returns None when source not found."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        result = await cache_manager.get_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            source_url="https://nonexistent.com/file.txt",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checksum_file_returns_none_on_version_mismatch(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify get_checksum_file returns None on version mismatch."""
        release_with_checksum = {
            **base_release_data,
            "checksum_files": [checksum_file_data],
        }
        await cache_manager.save_release_data(
            "test", "helper-app", release_with_checksum
        )

        result = await cache_manager.get_checksum_file(
            owner="test",
            repo="helper-app",
            version="3.0.0",
            source_url=checksum_file_data["source"],
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_checksum_file_returns_none_when_no_cache(
        self, cache_manager
    ):
        """Verify get_checksum_file returns None when no cache exists."""
        result = await cache_manager.get_checksum_file(
            owner="nonexistent",
            repo="app",
            version="1.0.0",
            source_url="https://example.com/checksums.txt",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_has_checksum_file_returns_true_when_exists(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify has_checksum_file returns True when file exists."""
        release_with_checksum = {
            **base_release_data,
            "checksum_files": [checksum_file_data],
        }
        await cache_manager.save_release_data(
            "test", "helper-app", release_with_checksum
        )

        result = await cache_manager.has_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            source_url=checksum_file_data["source"],
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_has_checksum_file_returns_false_when_not_exists(
        self, cache_manager, base_release_data
    ):
        """Verify has_checksum_file returns False when file not found."""
        await cache_manager.save_release_data(
            "test", "helper-app", base_release_data
        )

        result = await cache_manager.has_checksum_file(
            owner="test",
            repo="helper-app",
            version="2.0.0",
            source_url="https://nonexistent.com/checksums.txt",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_has_checksum_file_returns_false_on_version_mismatch(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify has_checksum_file returns False on version mismatch."""
        release_with_checksum = {
            **base_release_data,
            "checksum_files": [checksum_file_data],
        }
        await cache_manager.save_release_data(
            "test", "helper-app", release_with_checksum
        )

        result = await cache_manager.has_checksum_file(
            owner="test",
            repo="helper-app",
            version="3.0.0",
            source_url=checksum_file_data["source"],
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_has_checksum_file_returns_false_when_no_cache(
        self, cache_manager
    ):
        """Verify has_checksum_file returns False when no cache exists."""
        result = await cache_manager.has_checksum_file(
            owner="nonexistent",
            repo="app",
            version="1.0.0",
            source_url="https://example.com/checksums.txt",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_store_checksum_file_with_different_cache_types(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify store_checksum_file works with different cache types."""
        for cache_type in ["stable", "prerelease", "latest"]:
            await cache_manager.save_release_data(
                "test", "helper-app", base_release_data, cache_type
            )

            result = await cache_manager.store_checksum_file(
                owner="test",
                repo="helper-app",
                version="2.0.0",
                file_data=checksum_file_data,
                cache_type=cache_type,
            )

            assert result is True, f"Failed for cache_type={cache_type}"

            cached = await cache_manager.get_cached_release(
                "test", "helper-app", cache_type=cache_type
            )
            assert "checksum_files" in cached

    @pytest.mark.asyncio
    async def test_get_checksum_file_with_different_cache_types(
        self, cache_manager, base_release_data, checksum_file_data
    ):
        """Verify get_checksum_file works with different cache types."""
        for cache_type in ["stable", "prerelease", "latest"]:
            release_with_checksum = {
                **base_release_data,
                "checksum_files": [checksum_file_data],
            }
            await cache_manager.save_release_data(
                "test", "helper-app", release_with_checksum, cache_type
            )

            result = await cache_manager.get_checksum_file(
                owner="test",
                repo="helper-app",
                version="2.0.0",
                source_url=checksum_file_data["source"],
                cache_type=cache_type,
            )

            msg = f"Failed for cache_type={cache_type}"
            assert result is not None, msg
            assert result["filename"] == "SHA256SUMS.txt"
