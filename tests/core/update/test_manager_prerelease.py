"""Tests for prerelease fallback logic in UpdateManager._fetch_release_data.

This module tests edge cases and fallback behavior when handling
prerelease versions and fallback to stable releases.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest

from my_unicorn.core.github import Release
from my_unicorn.core.update.manager import UpdateManager


class TestFetchReleaseDataPrereleaseLogic:
    """Test cases for prerelease fallback logic in _fetch_release_data."""

    @pytest.fixture
    def update_manager(self) -> UpdateManager:
        """Create UpdateManager instance with mocked dependencies.

        Returns:
            UpdateManager with all external dependencies mocked.

        """
        with (
            patch("my_unicorn.core.update.manager.ConfigManager"),
            patch("my_unicorn.core.update.manager.GitHubAuthManager"),
            patch("my_unicorn.core.update.manager.FileOperations"),
            patch("my_unicorn.core.update.manager.BackupService"),
            patch("my_unicorn.core.update.manager.ReleaseCacheManager"),
        ):
            # Create a minimal config manager mock
            mock_config = MagicMock()
            mock_config.load_global_config.return_value = {
                "max_concurrent_downloads": 3,
                "directory": {
                    "storage": Path("/test/storage"),
                    "download": Path("/test/download"),
                    "backup": Path("/test/backup"),
                    "icon": Path("/test/icon"),
                    "cache": Path("/test/cache"),
                },
            }
            with patch(
                "my_unicorn.core.update.manager.ConfigManager"
            ) as mock_config_cls:
                mock_config_cls.return_value = mock_config
                return UpdateManager()

    def _create_mock_release(self, version: str, prerelease: bool) -> Release:
        """Create a mock Release object.

        Args:
            version: Version string for the release.
            prerelease: Whether this is a prerelease.

        Returns:
            Mock Release object.

        """
        return Release(
            owner="owner",
            repo="repo",
            version=version,
            prerelease=prerelease,
            assets=[],
            original_tag_name=f"v{version}",
        )

    @pytest.mark.asyncio
    async def test_fetch_release_data_prerelease_fallback_to_stable(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify fallback from prerelease to stable release.

        This test verifies that when fetch_latest_prerelease raises a
        ValueError indicating no prereleases found, the manager falls back
        to fetching the latest stable release instead:

        1. fetch_latest_prerelease() is called first
        2. It raises ValueError with "No prereleases found"
        3. fetch_latest_release_or_prerelease() is called with
           prefer_prerelease=False
        4. Returns stable release data

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        stable_release = self._create_mock_release("1.0.0", prerelease=False)

        with patch(
            "my_unicorn.core.update.manager.ReleaseFetcher"
        ) as mock_fetcher_cls:
            mock_fetcher = AsyncMock()
            mock_fetcher_cls.return_value = mock_fetcher

            # Configure mocks for prerelease fallback flow
            mock_fetcher.fetch_latest_prerelease.side_effect = ValueError(
                "No prereleases found for owner/repo"
            )
            mock_fetcher.fetch_latest_release_or_prerelease.return_value = (
                stable_release
            )

            # Call _fetch_release_data with prerelease=True
            result = await update_manager._fetch_release_data(
                owner="owner",
                repo="repo",
                should_use_prerelease=True,
                session=mock_session,
                refresh_cache=False,
            )

            # Verify both methods were called in correct order
            mock_fetcher.fetch_latest_prerelease.assert_called_once_with(
                ignore_cache=False
            )
            mock_fetcher.fetch_latest_release_or_prerelease.assert_called_once_with(
                prefer_prerelease=False, ignore_cache=False
            )

            # Verify stable release is returned
            assert result == stable_release
            assert result.version == "1.0.0"
            assert result.prerelease is False

    @pytest.mark.asyncio
    async def test_fetch_release_data_prerelease_only_stable_available(
        self, update_manager: UpdateManager
    ) -> None:
        """Test successful fallback when only stable releases exist.

        This test verifies edge case where no prerelease versions exist
        for an application. The manager should:

        1. Attempt to fetch prerelease (fails with ValueError)
        2. Fall back to stable release (succeeds)
        3. Return stable release without errors

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        stable_release = self._create_mock_release("2.0.0", prerelease=False)

        with patch(
            "my_unicorn.core.update.manager.ReleaseFetcher"
        ) as mock_fetcher_cls:
            mock_fetcher = AsyncMock()
            mock_fetcher_cls.return_value = mock_fetcher

            # Simulate no prerelease versions available
            mock_fetcher.fetch_latest_prerelease.side_effect = ValueError(
                "No prereleases found for owner/repo"
            )
            mock_fetcher.fetch_latest_release_or_prerelease.return_value = (
                stable_release
            )

            result = await update_manager._fetch_release_data(
                owner="owner",
                repo="repo",
                should_use_prerelease=True,
                session=mock_session,
                refresh_cache=False,
            )

            # Verify result is valid stable release
            assert result.version == "2.0.0"
            assert result.prerelease is False
            assert result.owner == "owner"
            assert result.repo == "repo"

    @pytest.mark.asyncio
    async def test_fetch_release_data_prerelease_different_error_reraises(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify that non-prerelease errors are re-raised.

        This test ensures that when fetch_latest_prerelease fails with an
        error other than "No prereleases found", the error is propagated
        instead of attempting fallback to stable releases.

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)

        with patch(
            "my_unicorn.core.update.manager.ReleaseFetcher"
        ) as mock_fetcher_cls:
            mock_fetcher = AsyncMock()
            mock_fetcher_cls.return_value = mock_fetcher

            # Configure to raise a different ValueError
            unexpected_error = ValueError("API rate limit exceeded")
            mock_fetcher.fetch_latest_prerelease.side_effect = unexpected_error

            # Verify the error is re-raised
            with pytest.raises(ValueError, match="API rate limit exceeded"):
                await update_manager._fetch_release_data(
                    owner="owner",
                    repo="repo",
                    should_use_prerelease=True,
                    session=mock_session,
                    refresh_cache=False,
                )

            # Verify fetch_latest_release_or_prerelease was NOT called
            mock_fetcher.fetch_latest_release_or_prerelease.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_release_data_stable_no_fallback(
        self, update_manager: UpdateManager
    ) -> None:
        """Verify no fallback when should_use_prerelease=False.

        This test confirms that when should_use_prerelease is False, the
        method directly fetches stable releases without attempting to fetch
        and fall back from prerelease versions.

        """
        mock_session = AsyncMock(spec=aiohttp.ClientSession)
        stable_release = self._create_mock_release("1.5.0", prerelease=False)

        with patch(
            "my_unicorn.core.update.manager.ReleaseFetcher"
        ) as mock_fetcher_cls:
            mock_fetcher = AsyncMock()
            mock_fetcher_cls.return_value = mock_fetcher
            mock_fetcher.fetch_latest_release_or_prerelease.return_value = (
                stable_release
            )

            result = await update_manager._fetch_release_data(
                owner="owner",
                repo="repo",
                should_use_prerelease=False,
                session=mock_session,
                refresh_cache=False,
            )

            # Verify fetch_latest_prerelease was NOT called
            mock_fetcher.fetch_latest_prerelease.assert_not_called()

            # Verify fetch_latest_release_or_prerelease was called once
            mock_fetcher.fetch_latest_release_or_prerelease.assert_called_once_with(
                prefer_prerelease=False, ignore_cache=False
            )

            # Verify stable release returned
            assert result == stable_release
            assert result.version == "1.5.0"
