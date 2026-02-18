"""Tests for checksum file persistence in ReleaseCacheManager.

This module tests checksum_files array persistence for managing cached
checksum data in ReleaseCacheManager.
"""

from typing import Any

import orjson
import pytest


class TestChecksumFilesPersistence:
    """Tests for checksum_files array persistence in cache.

    These tests verify that checksum_file data discovered during verification
    can be properly persisted to and restored from the cache. This enables
    reuse of checksum data without re-downloading checksum files.
    """

    @pytest.fixture
    def sample_checksum_files(self) -> list[dict[str, str | dict[str, str]]]:
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
    def release_data_with_checksum_files(
        self, sample_checksum_files: list[dict[str, str | dict[str, str]]]
    ) -> dict[str, object]:
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
    def release_data_without_checksum_files(self) -> dict[str, object]:
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
        self,
        cache_manager: Any,
        release_data_with_checksum_files: dict[str, Any],
    ) -> None:
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
        self,
        cache_manager: Any,
        release_data_with_checksum_files: dict[str, Any],
    ) -> None:
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
        self,
        cache_manager: Any,
        release_data_without_checksum_files: dict[str, Any],
    ) -> None:
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
    async def test_checksum_files_with_multiple_entries(
        self, cache_manager: Any
    ) -> None:
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
        self,
        cache_manager: Any,
        release_data_with_checksum_files: dict[str, Any],
    ) -> None:
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
