"""Tests for checksum file helper methods in ReleaseCacheManager.

This module tests the store_checksum_file, get_checksum_file, and
has_checksum_file methods that enable targeted operations on cached
checksum file data.
"""

from typing import Any

import pytest


class TestChecksumFileHelperMethods:
    """Tests for checksum file helper methods in ReleaseCacheManager.

    These tests verify the store_checksum_file, get_checksum_file, and
    has_checksum_file methods that enable targeted operations on cached
    checksum file data.
    """

    @pytest.fixture
    def base_release_data(self) -> dict[str, object]:
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
    def checksum_file_data(self) -> dict[str, str | dict[str, str]]:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any, checksum_file_data: dict[str, Any]
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any, base_release_data: dict[str, Any]
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any, base_release_data: dict[str, Any]
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any, base_release_data: dict[str, Any]
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self, cache_manager: Any
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
        self,
        cache_manager: Any,
        base_release_data: dict[str, Any],
        checksum_file_data: dict[str, Any],
    ) -> None:
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
