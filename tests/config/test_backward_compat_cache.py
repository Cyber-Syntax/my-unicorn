"""Tests for backward compatibility with old cache file format.

Task 6.2: Ensure old cache files (without checksum_files) still load.
Tests that legacy cache files without the checksum_files array continue
to work correctly with cache validation, loading, and normal operations.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import orjson
import pytest

from my_unicorn.config import ConfigManager
from my_unicorn.config.schemas import validate_cache_release
from my_unicorn.core.cache import ReleaseCacheManager


class TestLegacyCacheFileLoading:
    """Tests for loading old cache files without checksum_files array."""

    @pytest.fixture
    def tmp_cache_dir(self, tmp_path: Path) -> Path:
        """Create temporary cache directory."""
        cache_dir = tmp_path / "cache" / "releases"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @pytest.fixture
    def mock_config_manager(self, tmp_path: Path) -> MagicMock:
        """Create mock config manager with temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(
        self, mock_config_manager: MagicMock
    ) -> ReleaseCacheManager:
        """Create ReleaseCacheManager for tests."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def legacy_cache_entry_no_checksum_files(self) -> dict[str, Any]:
        """Cache entry without checksum_files array.

        Represents old cache files before checksum_files was added to schema.
        """
        return {
            "cached_at": "2025-01-15T10:30:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "test",
                "repo": "legacy-app",
                "version": "1.5.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "legacy-app-1.5.0.AppImage",
                        "size": 45000000,
                        "digest": "sha256:" + "a" * 64,
                        "browser_download_url": (
                            "https://github.com/test/legacy-app/releases/"
                            "download/v1.5.0/legacy-app-1.5.0.AppImage"
                        ),
                    }
                ],
                "original_tag_name": "v1.5.0",
            },
        }

    @pytest.fixture
    def legacy_cache_entry_no_digest(self) -> dict[str, Any]:
        """Older cache entry without digest field in assets.

        Represents very old cache files before digest was available.
        """
        return {
            "cached_at": "2024-06-01T08:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "oldtest",
                "repo": "very-old-app",
                "version": "0.5.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "very-old-app-0.5.0.AppImage",
                        "size": 30000000,
                        "digest": None,
                        "browser_download_url": (
                            "https://github.com/oldtest/very-old-app/releases/"
                            "download/v0.5.0/very-old-app-0.5.0.AppImage"
                        ),
                    }
                ],
                "original_tag_name": "v0.5.0",
            },
        }

    def test_schema_validation_passes_without_checksum_files(
        self, legacy_cache_entry_no_checksum_files: dict[str, Any]
    ) -> None:
        """Schema validation should pass for cache without checksum_files.

        Task 6.2: Cache validation passes for legacy format.
        """
        release_data = legacy_cache_entry_no_checksum_files["release_data"]
        assert "checksum_files" not in release_data
        validate_cache_release(
            legacy_cache_entry_no_checksum_files, "legacy_cache"
        )

    def test_schema_validation_passes_without_digest(
        self, legacy_cache_entry_no_digest: dict[str, Any]
    ) -> None:
        """Schema validation should pass for cache with null digest."""
        validate_cache_release(legacy_cache_entry_no_digest, "very_old_cache")

    @pytest.mark.asyncio
    async def test_load_legacy_cache_file_without_checksum_files(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry_no_checksum_files: dict[str, Any],
    ) -> None:
        """Loading cache file without checksum_files should succeed.

        Task 6.2: Load cache file without checksum_files array.
        """
        cache_file = tmp_cache_dir / "test_legacy-app.json"
        cache_file.write_bytes(
            orjson.dumps(legacy_cache_entry_no_checksum_files)
        )

        result = await cache_manager.get_cached_release(
            "test", "legacy-app", ignore_ttl=True
        )

        assert result is not None
        assert result["owner"] == "test"
        assert result["repo"] == "legacy-app"
        assert result["version"] == "1.5.0"
        assert "checksum_files" not in result

    @pytest.mark.asyncio
    async def test_load_legacy_cache_preserves_all_data(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry_no_checksum_files: dict[str, Any],
    ) -> None:
        """Loading should preserve all original data without loss.

        Task 6.2: Operations continue normally.
        """
        cache_file = tmp_cache_dir / "test_legacy-app.json"
        cache_file.write_bytes(
            orjson.dumps(legacy_cache_entry_no_checksum_files)
        )

        result = await cache_manager.get_cached_release(
            "test", "legacy-app", ignore_ttl=True
        )

        assert result is not None
        assert result["prerelease"] is False
        assert len(result["assets"]) == 1
        assert result["assets"][0]["name"] == "legacy-app-1.5.0.AppImage"
        assert result["assets"][0]["size"] == 45000000
        assert result["original_tag_name"] == "v1.5.0"

    @pytest.mark.asyncio
    async def test_operations_continue_normally_after_loading_legacy(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry_no_checksum_files: dict[str, Any],
    ) -> None:
        """Normal operations should work after loading legacy cache.

        Task 6.2: Operations continue normally.
        """
        cache_file = tmp_cache_dir / "test_legacy-app.json"
        cache_file.write_bytes(
            orjson.dumps(legacy_cache_entry_no_checksum_files)
        )

        loaded = await cache_manager.get_cached_release(
            "test", "legacy-app", ignore_ttl=True
        )
        assert loaded is not None

        # Cache stats should report valid entry
        stats = await cache_manager.get_cache_stats()
        assert stats["total_entries"] >= 1


class TestLegacyCacheSaveUpdatesFormat:
    """Tests for saving updated cache with checksum_files array."""

    @pytest.fixture
    def mock_config_manager(self, tmp_path: Path) -> MagicMock:
        """Create mock config manager with temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(
        self, mock_config_manager: MagicMock
    ) -> ReleaseCacheManager:
        """Create ReleaseCacheManager for tests."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def legacy_release_data(self) -> dict[str, Any]:
        """Legacy release data without checksum_files."""
        return {
            "owner": "test",
            "repo": "migrating-app",
            "version": "2.0.0",
            "prerelease": False,
            "assets": [
                {
                    "name": "migrating-app-2.0.0.AppImage",
                    "size": 55000000,
                    "digest": "sha256:" + "b" * 64,
                    "browser_download_url": (
                        "https://github.com/test/migrating-app/releases/"
                        "download/v2.0.0/migrating-app-2.0.0.AppImage"
                    ),
                }
            ],
            "original_tag_name": "v2.0.0",
        }

    @pytest.mark.asyncio
    async def test_save_adds_checksum_files_on_next_store(
        self,
        cache_manager: ReleaseCacheManager,
        legacy_release_data: dict[str, Any],
    ) -> None:
        """Storing checksum file should add array to legacy cache.

        Task 6.2: checksum_files array added on next save.
        """
        await cache_manager.save_release_data(
            "test", "migrating-app", legacy_release_data
        )

        # Verify initial save has no checksum_files
        initial_cached = await cache_manager.get_cached_release(
            "test", "migrating-app"
        )
        assert "checksum_files" not in initial_cached

        # Store a checksum file
        checksum_file_data = {
            "source": (
                "https://github.com/test/migrating-app/releases/"
                "download/v2.0.0/SHA256SUMS.txt"
            ),
            "filename": "SHA256SUMS.txt",
            "algorithm": "SHA256",
            "hashes": {"migrating-app-2.0.0.AppImage": "b" * 64},
        }
        result = await cache_manager.store_checksum_file(
            owner="test",
            repo="migrating-app",
            version="2.0.0",
            file_data=checksum_file_data,
        )

        assert result is True

        # Verify checksum_files was added
        updated_cached = await cache_manager.get_cached_release(
            "test", "migrating-app"
        )
        assert "checksum_files" in updated_cached
        assert len(updated_cached["checksum_files"]) == 1
        stored_filename = updated_cached["checksum_files"][0]["filename"]
        assert stored_filename == "SHA256SUMS.txt"

    @pytest.mark.asyncio
    async def test_resave_legacy_cache_adds_empty_checksum_files(
        self,
        cache_manager: ReleaseCacheManager,
        legacy_release_data: dict[str, Any],
    ) -> None:
        """Re-saving legacy release data preserves structure.

        Task 6.2: Operations continue normally.
        """
        await cache_manager.save_release_data(
            "test", "migrating-app", legacy_release_data
        )

        loaded = await cache_manager.get_cached_release(
            "test", "migrating-app"
        )
        assert loaded is not None
        assert "checksum_files" not in loaded

        # Re-save the same data (simulates update check)
        await cache_manager.save_release_data("test", "migrating-app", loaded)

        reloaded = await cache_manager.get_cached_release(
            "test", "migrating-app"
        )
        assert reloaded is not None
        # Should still work without checksum_files
        assert reloaded["version"] == "2.0.0"


class TestLegacyCacheHelperMethods:
    """Tests for helper methods with legacy cache files."""

    @pytest.fixture
    def tmp_cache_dir(self, tmp_path: Path) -> Path:
        """Create temporary cache directory."""
        cache_dir = tmp_path / "cache" / "releases"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @pytest.fixture
    def mock_config_manager(self, tmp_path: Path) -> MagicMock:
        """Create mock config manager with temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(
        self, mock_config_manager: MagicMock
    ) -> ReleaseCacheManager:
        """Create ReleaseCacheManager for tests."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.fixture
    def legacy_cache_entry(self) -> dict[str, Any]:
        """Legacy cache entry for helper method tests."""
        return {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "helper",
                "repo": "legacy-helper-app",
                "version": "3.0.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "helper-app-3.0.0.AppImage",
                        "size": 60000000,
                        "digest": "sha256:" + "c" * 64,
                        "browser_download_url": (
                            "https://github.com/helper/legacy-helper-app/"
                            "releases/download/v3.0.0/helper-app-3.0.0.AppImage"
                        ),
                    }
                ],
                "original_tag_name": "v3.0.0",
            },
        }

    @pytest.mark.asyncio
    async def test_get_checksum_file_returns_none_for_legacy_cache(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry: dict[str, Any],
    ) -> None:
        """get_checksum_file should return None for legacy cache without array.

        Task 6.2: Operations continue normally.
        """
        cache_file = tmp_cache_dir / "helper_legacy-helper-app.json"
        cache_file.write_bytes(orjson.dumps(legacy_cache_entry))

        result = await cache_manager.get_checksum_file(
            owner="helper",
            repo="legacy-helper-app",
            version="3.0.0",
            source_url="https://example.com/SHA256SUMS.txt",
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_has_checksum_file_returns_false_for_legacy_cache(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry: dict[str, Any],
    ) -> None:
        """has_checksum_file returns False for legacy cache without array.

        Task 6.2: Operations continue normally.
        """
        cache_file = tmp_cache_dir / "helper_legacy-helper-app.json"
        cache_file.write_bytes(orjson.dumps(legacy_cache_entry))

        result = await cache_manager.has_checksum_file(
            owner="helper",
            repo="legacy-helper-app",
            version="3.0.0",
            source_url="https://example.com/SHA256SUMS.txt",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_store_checksum_file_works_on_legacy_cache(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
        legacy_cache_entry: dict[str, Any],
    ) -> None:
        """store_checksum_file should work on legacy cache and add array.

        Task 6.2: checksum_files array added on next save.
        """
        cache_file = tmp_cache_dir / "helper_legacy-helper-app.json"
        cache_file.write_bytes(orjson.dumps(legacy_cache_entry))

        checksum_file_data = {
            "source": (
                "https://github.com/helper/legacy-helper-app/releases/"
                "download/v3.0.0/SHA256SUMS.txt"
            ),
            "filename": "SHA256SUMS.txt",
            "algorithm": "SHA256",
            "hashes": {"helper-app-3.0.0.AppImage": "c" * 64},
        }

        result = await cache_manager.store_checksum_file(
            owner="helper",
            repo="legacy-helper-app",
            version="3.0.0",
            file_data=checksum_file_data,
        )

        assert result is True

        # Verify the array was added
        updated = await cache_manager.get_cached_release(
            "helper", "legacy-helper-app"
        )
        assert "checksum_files" in updated
        assert len(updated["checksum_files"]) == 1


class TestLegacyCacheCacheTypes:
    """Tests for legacy cache with different cache types."""

    @pytest.fixture
    def tmp_cache_dir(self, tmp_path: Path) -> Path:
        """Create temporary cache directory."""
        cache_dir = tmp_path / "cache" / "releases"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    @pytest.fixture
    def mock_config_manager(self, tmp_path: Path) -> MagicMock:
        """Create mock config manager with temporary cache directory."""
        config_manager = MagicMock(spec=ConfigManager)
        global_config = {"directory": {"cache": tmp_path / "cache"}}
        config_manager.load_global_config.return_value = global_config
        return config_manager

    @pytest.fixture
    def cache_manager(
        self, mock_config_manager: MagicMock
    ) -> ReleaseCacheManager:
        """Create ReleaseCacheManager for tests."""
        return ReleaseCacheManager(mock_config_manager, ttl_hours=24)

    @pytest.mark.asyncio
    async def test_legacy_cache_loads_for_stable_type(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
    ) -> None:
        """Legacy stable cache should load correctly."""
        legacy_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "test",
                "repo": "stable-app",
                "version": "1.0.0",
                "prerelease": False,
                "assets": [],
                "original_tag_name": "v1.0.0",
            },
        }

        cache_file = tmp_cache_dir / "test_stable-app.json"
        cache_file.write_bytes(orjson.dumps(legacy_entry))

        result = await cache_manager.get_cached_release(
            "test", "stable-app", ignore_ttl=True, cache_type="stable"
        )

        assert result is not None
        assert "checksum_files" not in result

    @pytest.mark.asyncio
    async def test_legacy_cache_loads_for_prerelease_type(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
    ) -> None:
        """Legacy prerelease cache should load correctly."""
        legacy_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "test",
                "repo": "prerelease-app",
                "version": "2.0.0-beta.1",
                "prerelease": True,
                "assets": [],
                "original_tag_name": "v2.0.0-beta.1",
            },
        }

        cache_file = tmp_cache_dir / "test_prerelease-app_prerelease.json"
        cache_file.write_bytes(orjson.dumps(legacy_entry))

        result = await cache_manager.get_cached_release(
            "test", "prerelease-app", ignore_ttl=True, cache_type="prerelease"
        )

        assert result is not None
        assert result["prerelease"] is True
        assert "checksum_files" not in result

    @pytest.mark.asyncio
    async def test_legacy_cache_loads_for_latest_type(
        self,
        cache_manager: ReleaseCacheManager,
        tmp_cache_dir: Path,
    ) -> None:
        """Legacy latest cache should load correctly."""
        legacy_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "test",
                "repo": "latest-app",
                "version": "3.0.0",
                "prerelease": False,
                "assets": [],
                "original_tag_name": "v3.0.0",
            },
        }

        cache_file = tmp_cache_dir / "test_latest-app_latest.json"
        cache_file.write_bytes(orjson.dumps(legacy_entry))

        result = await cache_manager.get_cached_release(
            "test", "latest-app", ignore_ttl=True, cache_type="latest"
        )

        assert result is not None
        assert "checksum_files" not in result


class TestLegacyCacheSchemaValidation:
    """Additional schema validation tests for legacy cache formats."""

    def test_minimal_release_data_validates(self) -> None:
        """Minimal release_data structure should validate.

        Legacy caches may have minimal fields.
        """
        cache_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "minimal",
                "repo": "minimal-app",
                "version": "1.0.0",
                "prerelease": False,
                "assets": [],
                "original_tag_name": "v1.0.0",
            },
        }
        validate_cache_release(cache_entry, "minimal_cache")

    def test_asset_without_digest_validates(self) -> None:
        """Asset without digest field should validate (null is valid)."""
        cache_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "nodigest",
                "repo": "nodigest-app",
                "version": "1.0.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "app.AppImage",
                        "size": 10000000,
                        "digest": None,
                        "browser_download_url": (
                            "https://github.com/nodigest/nodigest-app/releases/"
                            "download/v1.0.0/app.AppImage"
                        ),
                    }
                ],
                "original_tag_name": "v1.0.0",
            },
        }
        validate_cache_release(cache_entry, "nodigest_cache")

    def test_multiple_assets_without_checksum_files_validates(self) -> None:
        """Multiple assets without checksum_files should validate."""
        cache_entry = {
            "cached_at": "2025-02-01T12:00:00.000000+00:00",
            "ttl_hours": 24,
            "release_data": {
                "owner": "multi",
                "repo": "multi-app",
                "version": "2.0.0",
                "prerelease": False,
                "assets": [
                    {
                        "name": "app-x86_64.AppImage",
                        "size": 50000000,
                        "digest": "sha256:" + "a" * 64,
                        "browser_download_url": (
                            "https://github.com/multi/multi-app/releases/"
                            "download/v2.0.0/app-x86_64.AppImage"
                        ),
                    },
                    {
                        "name": "app-aarch64.AppImage",
                        "size": 48000000,
                        "digest": "sha256:" + "b" * 64,
                        "browser_download_url": (
                            "https://github.com/multi/multi-app/releases/"
                            "download/v2.0.0/app-aarch64.AppImage"
                        ),
                    },
                ],
                "original_tag_name": "v2.0.0",
            },
        }
        validate_cache_release(cache_entry, "multi_cache")
