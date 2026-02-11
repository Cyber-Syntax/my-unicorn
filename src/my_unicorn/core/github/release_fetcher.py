"""High-level GitHub release fetching operations with caching.

This module orchestrates release fetching operations, managing cache
interactions and coordinating with the low-level HTTP client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.github.client import ReleaseAPIClient

if TYPE_CHECKING:
    import aiohttp

    from my_unicorn.core.cache import ReleaseCacheManager
from my_unicorn.core.github.models import Release
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


class ReleaseFetcher:
    """Orchestrates release fetching with caching support.

    This class uses dependency injection for the cache manager rather than
    accessing a global singleton. Create instances explicitly with an injected
    cache manager.

    Usage:
        # Create with injected cache manager:
        cache = ReleaseCacheManager(config_manager)
        fetcher = ReleaseFetcher(
            owner="owner",
            repo="repo",
            session=session,
            cache_manager=cache,
        )

        # Or without caching:
        fetcher = ReleaseFetcher(
            owner="owner",
            repo="repo",
            session=session,
            cache_manager=None,
        )
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        session: aiohttp.ClientSession,
        cache_manager: ReleaseCacheManager | None = None,
        auth_manager: GitHubAuthManager | None = None,
        shared_api_task_id: str | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize the release fetcher.

        Args:
            owner: Repository owner
            repo: Repository name
            session: aiohttp session for making requests
            cache_manager: Optional cache manager for release data
                          (None disables caching)
            auth_manager: Optional GitHub authentication manager
                         (creates default if not provided)
            shared_api_task_id: Optional shared API progress task ID
            progress_reporter: Optional progress reporter for tracking

        """
        self.owner = owner
        self.repo = repo
        self.cache_manager = cache_manager
        self.auth_manager = auth_manager or GitHubAuthManager.create_default()
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.api_client = ReleaseAPIClient(
            owner,
            repo,
            session,
            self.auth_manager,
            shared_api_task_id,
            progress_reporter=self.progress_reporter,
        )
        self.shared_api_task_id = shared_api_task_id
        self.session = session

    async def _get_from_cache(
        self, cache_type: str = "stable"
    ) -> Release | None:
        """Get release from cache.

        Args:
            cache_type: Cache type ('stable', 'prerelease', or default)

        Returns:
            Cached release or None

        """
        if not self.cache_manager:
            return None

        cached_data = await self.cache_manager.get_cached_release(
            self.owner, self.repo, cache_type=cache_type
        )

        if cached_data:
            logger.debug(
                "Using cached %s release data for %s/%s",
                cache_type,
                self.owner,
                self.repo,
            )
            return Release.from_dict(cached_data)

        return None

    async def _save_to_cache(
        self, release: Release, cache_type: str = "stable"
    ) -> None:
        """Save release to cache.

        Args:
            release: Release to cache
            cache_type: Cache type ('stable', 'prerelease', or default)

        """
        if not self.cache_manager:
            return

        await self.cache_manager.save_release_data(
            self.owner, self.repo, release.to_dict(), cache_type=cache_type
        )
        logger.debug(
            "Cached %s release data for %s/%s",
            cache_type,
            self.owner,
            self.repo,
        )

    async def fetch_latest_release(
        self, ignore_cache: bool = False
    ) -> Release:
        """Fetch the latest release (stable only).

        Args:
            ignore_cache: If True, bypass cache and fetch fresh data

        Returns:
            Latest release

        Raises:
            ValueError: If no release found

        """
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="stable")
            if cached:
                # Update shared progress even for cache hits
                if (
                    self.shared_api_task_id
                    and self.progress_reporter.is_active()
                ):
                    await self.api_client.update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        api_data = await self.api_client.fetch_stable_release()
        if api_data is None:
            raise ValueError(
                f"No stable release found for {self.owner}/{self.repo}"
            )

        release = Release.from_api_response(self.owner, self.repo, api_data)

        # Filter for platform compatibility before caching
        release = release.filter_for_platform()
        await self._save_to_cache(release, cache_type="stable")
        return release

    async def fetch_latest_prerelease(
        self, ignore_cache: bool = False
    ) -> Release:
        """Fetch the latest prerelease.

        Args:
            ignore_cache: If True, bypass cache and fetch fresh data

        Returns:
            Latest prerelease

        Raises:
            ValueError: If no prerelease found

        """
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="prerelease")
            if cached:
                # Update shared progress even for cache hits
                if (
                    self.shared_api_task_id
                    and self.progress_reporter.is_active()
                ):
                    await self.api_client.update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        api_data = await self.api_client.fetch_prerelease()
        if api_data is None:
            raise ValueError(
                f"No prerelease found for {self.owner}/{self.repo}"
            )

        release = Release.from_api_response(self.owner, self.repo, api_data)

        # Filter for platform compatibility before caching
        release = release.filter_for_platform()
        await self._save_to_cache(release, cache_type="prerelease")
        return release

    async def fetch_latest_release_or_prerelease(
        self, prefer_prerelease: bool = False, ignore_cache: bool = False
    ) -> Release:
        """Fetch the latest release or prerelease based on preference.

        Args:
            prefer_prerelease: If True, prefer prereleases over stable
            ignore_cache: If True, bypass cache and fetch fresh data

        Returns:
            Latest release matching preference

        Raises:
            ValueError: If no releases found

        """
        if prefer_prerelease:
            release = await self._try_prerelease_then_stable(ignore_cache)
        else:
            release = await self._try_stable_then_prerelease(ignore_cache)

        if release:
            return release

        if self.shared_api_task_id and self.progress_reporter.is_active():
            await self.api_client.update_shared_progress(
                f"No releases found for {self.owner}/{self.repo}"
            )

        raise ValueError(f"No releases found for {self.owner}/{self.repo}")

    async def _try_prerelease_then_stable(
        self, ignore_cache: bool
    ) -> Release | None:
        """Try to fetch prerelease first, then stable as fallback."""
        release = await self._fetch_prerelease_with_cache(ignore_cache)
        if release:
            return release
        return await self._fetch_stable_with_cache(ignore_cache)

    async def _try_stable_then_prerelease(
        self, ignore_cache: bool
    ) -> Release | None:
        """Try to fetch stable first, then prerelease as fallback."""
        release = await self._fetch_stable_with_cache(ignore_cache)
        if release:
            return release
        return await self._fetch_prerelease_with_cache(ignore_cache)

    async def _update_progress_for_cache_hit(self) -> None:
        """Update shared progress for cached release."""
        if (
            not self.shared_api_task_id
            or not self.progress_reporter.is_active()
        ):
            return
        await self.api_client.update_shared_progress(
            f"Retrieved {self.owner}/{self.repo} (cached)"
        )

    async def _fetch_stable_with_cache(
        self, ignore_cache: bool
    ) -> Release | None:
        """Fetch stable release with cache support."""
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="stable")
            if cached:
                await self._update_progress_for_cache_hit()
                return cached

        api_data = await self.api_client.fetch_stable_release()
        if api_data:
            release = Release.from_api_response(
                self.owner, self.repo, api_data
            )
            # Filter for platform compatibility before caching
            release = release.filter_for_platform()
            await self._save_to_cache(release, cache_type="stable")
            return release
        return None

    async def _fetch_prerelease_with_cache(
        self, ignore_cache: bool
    ) -> Release | None:
        """Fetch prerelease with cache support."""
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="prerelease")
            if cached:
                await self._update_progress_for_cache_hit()
                return cached

        api_data = await self.api_client.fetch_prerelease()
        if api_data:
            release = Release.from_api_response(
                self.owner, self.repo, api_data
            )
            # Filter for platform compatibility before caching
            release = release.filter_for_platform()
            await self._save_to_cache(release, cache_type="prerelease")
            return release
        return None

    async def fetch_specific_release(self, tag: str) -> Release:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release for the specified tag

        Raises:
            ValueError: If release not found

        """
        api_data = await self.api_client.fetch_release_by_tag(tag)
        if api_data is None:
            raise ValueError(
                f"Release {tag} not found for {self.owner}/{self.repo}"
            )
        return Release.from_api_response(self.owner, self.repo, api_data)

    async def get_default_branch(self) -> str:
        """Get the default branch name for the repository.

        Returns:
            Default branch name

        """
        return await self.api_client.fetch_default_branch()


class GitHubClient:
    """High-level GitHub client for release operations.

    Uses dependency injection for cache management. Create instances with an
    injected cache_manager for caching support, or leave as None to disable
    caching.

    Usage:
        # With caching:
        cache = ReleaseCacheManager(config_manager)
        client = GitHubClient(session, cache_manager=cache)

        # Without caching:
        client = GitHubClient(session, cache_manager=None)
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth_manager: GitHubAuthManager | None = None,
        cache_manager: ReleaseCacheManager | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize GitHub client.

        Args:
            session: aiohttp session for making requests
            auth_manager: Optional GitHub authentication manager
                         (creates default if not provided)
            cache_manager: Optional cache manager for release data
                          (None disables caching)
            progress_reporter: Optional progress reporter for tracking

        """
        self.session = session
        self.auth_manager = auth_manager or GitHubAuthManager.create_default()
        self.cache_manager = cache_manager
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.shared_api_task_id: str | None = None

    def set_shared_api_task(self, task_id: str | None) -> None:
        """Set the shared API progress task ID.

        Args:
            task_id: Shared API progress task ID or None to disable

        """
        self.shared_api_task_id = task_id

    async def get_latest_release(
        self, owner: str, repo: str
    ) -> Release | None:
        """Get the latest release for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release object or None if not found

        """
        try:
            fetcher = ReleaseFetcher(
                owner=owner,
                repo=repo,
                session=self.session,
                cache_manager=self.cache_manager,
                auth_manager=self.auth_manager,
                shared_api_task_id=self.shared_api_task_id,
            )
            return await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )
        except Exception as e:
            logger.error(
                "Failed to fetch latest release for %s/%s: %s",
                owner,
                repo,
                e,
            )
            return None

    async def get_release_by_tag(
        self, owner: str, repo: str, tag: str
    ) -> Release | None:
        """Get a specific release by tag.

        Args:
            owner: Repository owner
            repo: Repository name
            tag: Release tag

        Returns:
            Release object or None if not found

        """
        try:
            fetcher = ReleaseFetcher(
                owner=owner,
                repo=repo,
                session=self.session,
                cache_manager=self.cache_manager,
                auth_manager=self.auth_manager,
                shared_api_task_id=self.shared_api_task_id,
            )
            return await fetcher.fetch_specific_release(tag)
        except Exception:
            return None
