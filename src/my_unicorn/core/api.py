"""Low-level GitHub API client for HTTP communication.

This module handles direct HTTP communication with the GitHub API,
including authentication, rate limiting, and retry logic.
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.config.validation import ConfigurationValidator
from my_unicorn.constants import (
    HTTP_NOT_FOUND,
    INCOMPATIBLE_PLATFORM_EXTENSIONS,
    INCOMPATIBLE_PLATFORM_PATTERNS,
    UNSTABLE_VERSION_KEYWORDS,
)
from my_unicorn.core.auth import GitHubAuthManager
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.logger import get_logger
from my_unicorn.types import ChecksumFileInfo
from my_unicorn.utils.asset_validation import (
    SPECIFIC_CHECKSUM_EXTENSIONS,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from my_unicorn.core.cache import ReleaseCacheManager

logger = get_logger(__name__)

# HTTP status codes with special handling in the retry loop
_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403


def create_api_timeout(base_seconds: int) -> aiohttp.ClientTimeout:
    """Create configured timeout for GitHub API requests.

    Timeout multipliers based on typical API response patterns:
    - sock_connect: 1x base - Initial connection should be fast
    - sock_read: 2x base - Reading may take longer for large responses
    - total: 3x base - Total budget includes potential retries

    Args:
        base_seconds: Base timeout from network configuration

    Returns:
        Configured ClientTimeout instance

    Example:
        >>> timeout = create_api_timeout(10)
        >>> timeout.total
        30.0

    """
    return aiohttp.ClientTimeout(
        total=base_seconds * 3,
        sock_read=base_seconds * 2,
        sock_connect=base_seconds,
    )


class ReleaseAPIClient:
    """Handles direct communication with GitHub API for release data.

    This class is typically created by ReleaseFetcher and receives its
    dependencies via constructor injection. It handles authentication,
    rate limiting, and retry logic for GitHub API calls.

    Usage:
        # Create with injected dependencies:
        auth = GitHubAuthManager.create_default()
        api_client = ReleaseAPIClient(
            owner="owner",
            repo="repo",
            session=session,
            auth_manager=auth,
        )

        # Typically created internally by ReleaseFetcher:
        fetcher = ReleaseFetcher(
            owner="owner",
            repo="repo",
            session=session,
            cache_manager=cache,
        )
        # fetcher.api_client is created automatically
    """

    def __init__(
        self,
        owner: str,
        repo: str,
        session: aiohttp.ClientSession,
        auth_manager: GitHubAuthManager,
        shared_api_task_id: str | None = None,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            owner: Repository owner
            repo: Repository name
            session: aiohttp session for making requests
            auth_manager: GitHub authentication manager
            shared_api_task_id: Optional shared API progress task ID
            progress_reporter: Optional progress reporter for tracking

        """
        self.owner = owner
        self.repo = repo
        self.session = session
        self.auth_manager = auth_manager
        self.shared_api_task_id = shared_api_task_id
        self.progress_reporter = progress_reporter or NullProgressReporter()

        # Load network config once at construction time rather than on
        # every API call to avoid repeated disk/parse overhead.
        _config = ConfigManager()
        _network_cfg = _config.load_global_config()["network"]
        self._retry_attempts: int = int(_network_cfg.get("retry_attempts", 3))
        self._timeout_seconds: int = int(
            _network_cfg.get("timeout_seconds", 10)
        )

        # Caches a confirmed branch name for the lifetime of this instance.
        self._default_branch_cache: str | None = None

    async def update_shared_progress(self, description: str) -> None:
        """Update shared API progress task.

        Args:
            description: Description to show for the current API request

        """
        if (
            not self.shared_api_task_id
            or not self.progress_reporter.is_active()
        ):
            return

        try:
            task_info = self.progress_reporter.get_task_info(
                self.shared_api_task_id
            )
            if task_info:
                new_completed = int(task_info.get("completed", 0)) + 1
                total_value = task_info.get("total")
                total = (
                    int(total_value)
                    if total_value and total_value > 0
                    else new_completed
                )
                await self.progress_reporter.update_task(
                    self.shared_api_task_id,
                    completed=float(new_completed),
                    description=(
                        f"🌐 {description} ({new_completed}/{total})"
                    ),
                )
        except Exception as e:
            # Progress updates are non-critical; log and continue.
            logger.debug("Failed to update shared progress task: %s", e)

    async def _wait_with_countdown(self, seconds: int, reason: str) -> None:
        """Sleep for ``seconds`` while showing a live countdown in the progress bar.

        Falls back to a plain ``asyncio.sleep`` when no progress reporter is
        active, so callers do not need to branch on this themselves.

        Args:
            seconds: Total seconds to wait.
            reason: Short label shown before the countdown (e.g. "Rate limit").

        """
        if self.shared_api_task_id and self.progress_reporter.is_active():
            for remaining in range(seconds, 0, -1):
                await self.update_shared_progress(
                    f"{reason} — resuming in {remaining}s"
                )
                await asyncio.sleep(1)
        else:
            await asyncio.sleep(seconds)

    @staticmethod
    def _parse_retry_after(headers: dict[str, str]) -> int | None:
        """Extract the wait duration from a Retry-After or x-ratelimit-reset header.

        GitHub may send either:
        - ``Retry-After: <seconds>``  (secondary rate limit)
        - ``x-ratelimit-reset: <unix timestamp>``  (primary rate limit)

        Args:
            headers: Response headers dict.

        Returns:
            Seconds to wait, or None if neither header is present or parseable.

        """
        # Prefer explicit Retry-After seconds
        retry_after = headers.get("Retry-After") or headers.get("retry-after")
        if retry_after:
            try:
                return max(1, int(retry_after))
            except ValueError:
                pass

        # Fall back to x-ratelimit-reset timestamp
        reset_ts = headers.get("x-ratelimit-reset")
        if reset_ts:
            try:
                wait = int(reset_ts) - int(time.time())
                return max(1, wait)
            except ValueError:
                pass

        return None

    async def _fetch_from_api(self, url: str, description: str) -> Any | None:
        """Fetch data from GitHub API with retry and rate-limit handling.

        Args:
            url: API URL to fetch
            description: Description for progress tracking

        Returns:
            Parsed JSON response, or None if the resource was not found (404).

        Raises:
            aiohttp.ClientResponseError: On 401 (bad token) immediately, or
                after all retry attempts for other HTTP errors.
            aiohttp.ClientError: After all retry attempts are exhausted for
                network-level failures.

        """
        # Check rate-limit before the first request.
        try:
            if self.auth_manager.should_wait_for_rate_limit():
                wait_time = self.auth_manager.get_wait_time()
                logger.warning(
                    "Rate limit low (remaining: %s). Waiting %ss.",
                    self.auth_manager.get_rate_limit_status().get("remaining"),
                    wait_time,
                )
                await self._wait_with_countdown(wait_time, "Rate limit")
        except Exception as e:
            # Rate-limit helpers failing must never block the request itself.
            logger.debug(
                "Rate-limit pre-check failed, proceeding anyway: %s", e
            )

        timeout = create_api_timeout(self._timeout_seconds)

        for attempt in range(1, self._retry_attempts + 1):
            # Refresh headers on every attempt — ensures the latest token is
            # always used (e.g. if the user ran `my-unicorn token --save`
            # and restarted mid-session, though unlikely for a CLI).
            headers = self.auth_manager.apply_auth({})

            try:
                async with self.session.get(
                    url=url, headers=headers, timeout=timeout
                ) as response:
                    if response.status == HTTP_NOT_FOUND:
                        return None

                    if response.status == _HTTP_UNAUTHORIZED:
                        # A static Bearer token cannot be refreshed at runtime.
                        # Retrying with the same invalid token is pointless, so
                        # fail immediately with an actionable message.
                        logger.error(
                            "❌ GitHub token is invalid or revoked (401). "
                            "Run 'my-unicorn token --save' to update it."
                        )
                        response.raise_for_status()  # raises ClientResponseError

                    if response.status == _HTTP_FORBIDDEN:
                        # May be a secondary rate limit with a Retry-After header.
                        retry_after = self._parse_retry_after(
                            dict(response.headers)
                        )
                        if retry_after:
                            logger.warning(
                                "403 secondary rate limit on attempt %d/%d "
                                "for %s. Sleeping %ss as instructed.",
                                attempt,
                                self._retry_attempts,
                                url,
                                retry_after,
                            )
                            await self._wait_with_countdown(
                                retry_after, "Secondary rate limit"
                            )
                            continue  # retry without consuming the backoff slot

                        # No Retry-After — treat as a hard failure.
                        response.raise_for_status()

                    # Raises aiohttp.ClientResponseError for other 4xx/5xx.
                    response.raise_for_status()

                    self.auth_manager.update_rate_limit_info(
                        dict(response.headers)
                    )

                    if (
                        self.shared_api_task_id
                        and self.progress_reporter.is_active()
                    ):
                        await self.update_shared_progress(description)

                    return await response.json()

            except aiohttp.ClientResponseError as e:
                # 401 already logged above; re-raise immediately, no retries.
                if e.status == _HTTP_UNAUTHORIZED:
                    raise

                logger.warning(
                    "Attempt %d/%d HTTP error for %s: %s",
                    attempt,
                    self._retry_attempts,
                    url,
                    e,
                )
                if attempt == self._retry_attempts:
                    logger.error(  # noqa: TRY400
                        "❌ API fetch failed after %d attempts: %s - %s",
                        self._retry_attempts,
                        url,
                        e,
                    )
                    raise

            except (aiohttp.ClientError, TimeoutError) as e:
                logger.warning(
                    "Attempt %d/%d network error for %s: %s",
                    attempt,
                    self._retry_attempts,
                    url,
                    e,
                )
                if attempt == self._retry_attempts:
                    logger.error(  # noqa: TRY400
                        "❌ API fetch failed after %d attempts: %s - %s",
                        self._retry_attempts,
                        url,
                        e,
                    )
                    raise

            except Exception as e:
                # Non-network/non-HTTP error: retrying is unlikely to help.
                logger.error(  # noqa: TRY400
                    "Unexpected error fetching %s: %s", url, e
                )
                raise

            backoff = 2**attempt
            logger.debug(
                "Backing off %ss before attempt %d/%d for %s",
                backoff,
                attempt + 1,
                self._retry_attempts,
                url,
            )
            await asyncio.sleep(backoff)

        # Unreachable: the loop always raises on the final attempt.
        # Explicit return satisfies static type checkers.
        return None  # pragma: no cover

    async def fetch_stable_release(self) -> dict[str, Any] | None:
        """Fetch the latest stable release.

        Returns:
            Release data dict or None if no stable release found.

        """
        url = (
            f"https://api.github.com/repos/{self.owner}/"
            f"{self.repo}/releases/latest"
        )
        data = await self._fetch_from_api(url, "Fetched stable release")

        if data is None:
            return None

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected response type for stable release: %s", type(data)
            )
            return None

        if data.get("prerelease", False):
            return None

        return data

    async def fetch_prerelease(self) -> dict[str, Any] | None:
        """Fetch the latest prerelease.

        Returns:
            Release data dict or None if no prerelease found.

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        data = await self._fetch_from_api(url, "Fetched prerelease")

        if data is None:
            return None

        if not isinstance(data, list):
            logger.warning(
                "Unexpected response type for prereleases: %s", type(data)
            )
            return None

        for release in data:
            if isinstance(release, dict) and release.get("prerelease", False):
                return release

        return None

    async def fetch_release_by_tag(self, tag: str) -> dict[str, Any] | None:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release data dict or None if not found.

        """
        url = (
            f"https://api.github.com/repos/{self.owner}/"
            f"{self.repo}/releases/tags/{tag}"
        )
        data = await self._fetch_from_api(url, f"Fetched release {tag}")

        if data is None:
            return None

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected response type for release tag %s: %s",
                tag,
                type(data),
            )
            return None

        return data

    async def fetch_default_branch(self) -> str:
        """Get the default branch name for the repository.

        The result is cached for the lifetime of this client instance
        to avoid repeated repo-info API calls.

        Returns:
            Default branch name (e.g., 'main', 'master').
            Falls back to 'main' if the repository is not found or the
            response is malformed.

        """
        if self._default_branch_cache is not None:
            return self._default_branch_cache

        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        data = await self._fetch_from_api(url, "Fetched default branch")

        if data is None:
            logger.warning(
                "Repository %s/%s not found; defaulting branch to 'main'.",
                self.owner,
                self.repo,
            )
            return "main"

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected response type for default branch: %s; "
                "defaulting to 'main'.",
                type(data),
            )
            return "main"

        # Only cache a real API-confirmed value. A fallback "main" from an
        # error path is not cached so a later successful call can correct it.
        branch = data.get("default_branch", "main")
        self._default_branch_cache = branch
        return branch


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
            msg = f"No stable release found for {self.owner}/{self.repo}"
            raise ValueError(msg)

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
            msg = f"No prerelease found for {self.owner}/{self.repo}"
            raise ValueError(msg)

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

        msg = f"No releases found for {self.owner}/{self.repo}"
        raise ValueError(msg)

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
            msg = f"Release {tag} not found for {self.owner}/{self.repo}"
            raise ValueError(msg)

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
                progress_reporter=self.progress_reporter,
            )
            return await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )
        except Exception as e:
            logger.error(  # noqa: TRY400
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
                progress_reporter=self.progress_reporter,
            )
            return await fetcher.fetch_specific_release(tag)
        except Exception:
            return None


class AssetSelector:
    """Handles selection logic for choosing the best asset from a release."""

    @staticmethod
    def select_appimage_for_platform(
        release: Release,
        preferred_suffixes: list[str] | None = None,
        installation_source: str = "catalog",
    ) -> Asset | None:
        """Select the best AppImage based on architecture and preferences.

        Note: This method assumes the release has already been filtered
        by filter_for_platform() which removes ARM/Windows/macOS assets.
        Additional filtering here focuses on selecting the best variant
        when multiple compatible AppImages exist.

        Selection strategy for catalog installs:
        1. Filter by preferred_suffixes if provided
        2. Prefer explicit x86_64/amd64 markers
        3. Fall back to first remaining candidate

        Selection strategy for URL installs:
        1. Filter out unstable versions (beta, alpha, etc.)
        2. Prefer explicit x86_64/amd64 markers
        3. Return first remaining stable candidate

        Args:
            release: Release to select from (should be pre-filtered)
            preferred_suffixes: List of preferred filename suffixes
            installation_source: Installation source ("catalog" or "url")

        Returns:
            Best matching AppImage asset or None

        """
        appimages = release.get_appimages()

        if not appimages:
            return None

        if len(appimages) == 1:
            return appimages[0]

        # Apply different strategies based on installation source
        if installation_source == "url":
            # For URL installs, filter out unstable versions
            candidates = AssetSelector._filter_unstable_versions(appimages)
        elif preferred_suffixes:
            # For catalog installs with suffixes, filter by them
            candidates = [
                app
                for suffix in preferred_suffixes
                for app in appimages
                if suffix.lower() in app.name.lower()
            ]
            if not candidates:
                candidates = appimages
        else:
            candidates = appimages

        # Prefer explicit x86_64/amd64 markers when available
        explicit_match = AssetSelector._find_explicit_amd64(candidates)
        if explicit_match:
            return explicit_match

        # Fallback: return first candidate
        return candidates[0] if candidates else appimages[0]

    @staticmethod
    def _filter_unstable_versions(appimages: list[Asset]) -> list[Asset]:
        """Filter out unstable version keywords."""
        stable = [
            app
            for app in appimages
            if not any(
                kw in app.name.lower() for kw in UNSTABLE_VERSION_KEYWORDS
            )
        ]
        return stable or appimages

    @staticmethod
    def _find_explicit_amd64(appimages: list[Asset]) -> Asset | None:
        """Find asset with explicit amd64/x86_64 marker."""
        for app in appimages:
            name_lower = app.name.lower()
            if "x86_64" in name_lower or "amd64" in name_lower:
                return app
        return None

    @staticmethod
    def detect_checksum_files(
        assets: list[Asset],
        tag_name: str,
    ) -> list[ChecksumFileInfo]:
        """Detect checksum files in release assets.

        Filters to x86_64 Linux compatible checksum files only.
        Excludes ARM, macOS, and Windows checksums.

        Platform Exclusions:
            - ARM: latest-linux-arm.yml, *-arm64.AppImage.sha256
            - macOS: latest-mac.yml, *.dmg.DIGEST
            - Windows: latest-windows.yml, *.exe.sha256

        Args:
            assets: List of release assets
            tag_name: Release tag name

        Returns:
            List of detected checksum files (x86_64 Linux only)

        """
        checksum_files = []
        filtered_count = 0

        for asset in assets:
            if is_checksum_file(asset.name):
                # Apply platform compatibility filtering
                if AssetSelector.is_relevant_checksum(asset.name):
                    format_type = get_checksum_file_format_type(asset.name)
                    checksum_files.append(
                        ChecksumFileInfo(
                            filename=asset.name,
                            url=asset.browser_download_url,
                            format_type=format_type,
                        )
                    )
                else:
                    filtered_count += 1

        if filtered_count > 0:
            logger.debug(
                "Filtered %d non-x86_64 checksum files from %s",
                filtered_count,
                tag_name,
            )

        # Prioritize YAML files first as they're often more reliable
        checksum_files.sort(
            key=lambda x: (x.format_type != "yaml", x.filename)
        )

        return checksum_files

    @staticmethod
    def is_platform_compatible(filename: str) -> bool:
        """Check if file is compatible with Linux x86_64 platform.

        Excludes:
        - Windows files (.msi, .exe, Win64, Windows patterns)
        - macOS files (.dmg, .pkg, mac/darwin patterns)
        - ARM architectures (arm64, aarch64, armv7l, armhf, armv6)
        - Source archives (tar.gz, tar.xz with -src- pattern)
        - Experimental builds

        Args:
            filename: Filename to check

        Returns:
            True if file is compatible with Linux x86_64, False otherwise

        """
        if not filename:
            return False

        filename_lower = filename.lower()

        for pattern in INCOMPATIBLE_PLATFORM_PATTERNS:
            if re.search(pattern, filename):
                return False

        return not filename_lower.endswith(INCOMPATIBLE_PLATFORM_EXTENSIONS)

    @staticmethod
    def is_relevant_checksum(filename: str) -> bool:
        """Check if checksum file is platform-compatible.

        Handles two types of checksum files:
        1. AppImage-specific: "app.AppImage.sha256sum" - requires valid base
        2. Standalone: "SHA256SUMS.txt", "latest-linux.yml" - needs platform
           compatibility

        Examples:
            ✅ "QOwnNotes-x86_64.AppImage.sha256sum" (AppImage-specific)
            ✅ "KeePassXC-2.7.10-x86_64.AppImage.DIGEST" (AppImage-specific)
            ✅ "Joplin-3.4.12.AppImage.sha512" (AppImage-specific)
            ✅ "SHA256SUMS.txt" (standalone)
            ✅ "latest-linux.yml" (standalone)
            ✅ "SHA256SUMS" (standalone)
            ❌ "KeePassXC-2.7.10-Win64.msi.DIGEST" (Windows)
            ❌ "Obsidian-1.9.14-arm64.AppImage.sha256" (ARM)
            ❌ "latest-linux-arm.yml" (ARM)
            ❌ "latest-mac-arm64.yml" (macOS)

        Args:
            filename: Checksum filename to check

        Returns:
            True if checksum is platform-compatible, False otherwise

        """
        if not filename:
            return False

        # Must be a checksum file
        if not is_checksum_file(filename):
            return False

        # First check if file itself is platform-compatible
        if not AssetSelector.is_platform_compatible(filename):
            return False

        return AssetSelector._validate_checksum_type(filename)

    @staticmethod
    def _validate_checksum_type(filename: str) -> bool:
        """Validate checksum type (AppImage-specific vs standalone).

        Args:
            filename: Checksum filename to validate

        Returns:
            True if valid checksum type, False otherwise

        """
        filename_lower = filename.lower()

        # Check if this is an AppImage-specific checksum file
        # These have format: <appimage_name>.<checksum_ext>
        base_name = filename
        is_appimage_specific = False

        # Check specific checksum extensions (these require AppImage base)
        for ext in SPECIFIC_CHECKSUM_EXTENSIONS:
            if filename_lower.endswith(ext):
                base_name = filename[: -len(ext)]
                is_appimage_specific = True
                break

        # Also handle pattern-based checksums (e.g., .sha256, .sha512)
        if not is_appimage_specific:
            checksum_suffixes = [
                ".sha256",
                ".sha512",
                ".sha1",
                ".md5",
            ]
            for suffix in checksum_suffixes:
                if filename_lower.endswith(suffix):
                    base_name = filename[: -len(suffix)]
                    # Only consider AppImage-specific if base ends with
                    # .AppImage
                    if is_appimage_file(base_name):
                        is_appimage_specific = True
                    break

        # For AppImage-specific checksums, validate the base AppImage
        if is_appimage_specific:
            if not is_appimage_file(base_name):
                return False
            # Base must be platform-compatible (not Windows, macOS, ARM)
            return AssetSelector.is_platform_compatible(base_name)

        # For standalone checksum files (like SHA256SUMS.txt, latest-linux.yml)
        # we already validated platform compatibility above, so accept them
        return True

    @staticmethod
    def filter_for_cache(assets: list[Asset]) -> list[Asset]:
        """Filter assets to cache-worthy subset (x86_64 AppImages + checksums).

        This is the main entry point for cache filtering. It keeps only:
        - Linux x86_64 AppImages (excludes Windows, macOS, ARM builds)
        - Checksum files for compatible AppImages

        This method should be called before caching release data to avoid
        storing irrelevant assets.

        Args:
            assets: List of all release assets

        Returns:
            Filtered list of platform-compatible assets

        """
        filtered = []

        for asset in assets:
            filename = asset.name

            # Keep platform-compatible AppImages
            if is_appimage_file(filename):
                if AssetSelector.is_platform_compatible(filename):
                    filtered.append(asset)
                    logger.debug(
                        "Including platform-compatible AppImage: %s", filename
                    )
                else:
                    logger.debug(
                        "Filtering out non-compatible AppImage: %s", filename
                    )
                continue

            # Keep relevant checksum files
            if AssetSelector.is_relevant_checksum(filename):
                filtered.append(asset)
                logger.debug("Including relevant checksum file: %s", filename)
            else:
                logger.debug("Filtering out asset: %s", filename)

        return filtered


def extract_and_validate_version(package_string: str) -> str | None:
    """Extract and validate version from package string.

    Combines extraction, sanitization, and validation in one function.
    Used by GitHub models to normalize version strings from release data.

    Args:
        package_string: Package string that may contain version

    Returns:
        Valid version string or None if extraction/validation fails

    """
    if not package_string:
        return None

    # Handle package@version format
    if "@" in package_string:
        parts = package_string.split("@")
        if len(parts) < 2:
            return None
        version = parts[-1].strip()
        if not version:
            return None
    else:
        version = package_string

    # Sanitize version
    version = version.lstrip("v").replace("@", "").strip("\"'").strip()
    if not version:
        return None

    # Validate version
    pattern = r"^\d+(\.\d+)*(-[a-zA-Z0-9.-]+)?$"
    if re.match(pattern, version):
        return version
    return None


@dataclass(slots=True, frozen=True)
class Asset:
    """Represents a GitHub release asset.

    Attributes:
        name: Asset filename
        size: Asset size in bytes
        digest: Asset digest/hash (may be empty)
        browser_download_url: Direct download URL for the asset

    """

    name: str
    size: int
    digest: str
    browser_download_url: str

    @classmethod
    def from_api_response(cls, asset_data: dict[str, Any]) -> Asset | None:
        """Create Asset from GitHub API response data.

        Args:
            asset_data: Raw asset data from GitHub API

        Returns:
            Asset instance or None if required fields are missing

        """
        try:
            name = asset_data.get("name", "")
            size = asset_data.get("size", 0)
            download_url = asset_data.get("browser_download_url", "")
            digest = asset_data.get("digest", "")

            if not name or not download_url:
                return None

            return cls(
                name=name,
                size=int(size),
                digest=digest,
                browser_download_url=download_url,
            )
        except (KeyError, TypeError, ValueError):
            return None

    def is_appimage(self) -> bool:
        """Check if this asset is an AppImage file.

        Returns:
            True if asset is an AppImage, False otherwise

        """
        return is_appimage_file(self.name)


@dataclass(slots=True, frozen=True)
class Release:
    """Represents a GitHub release with its metadata and assets.

    Attributes:
        owner: Repository owner
        repo: Repository name
        version: Normalized version string
        prerelease: Whether this is a prerelease
        assets: List of release assets
        original_tag_name: Original tag name from GitHub

    """

    owner: str
    repo: str
    version: str
    prerelease: bool
    assets: list[Asset]
    original_tag_name: str

    @classmethod
    def from_api_response(
        cls, owner: str, repo: str, api_data: dict[str, Any]
    ) -> Release:
        """Create Release from GitHub API response data.

        Args:
            owner: Repository owner
            repo: Repository name
            api_data: Raw release data from GitHub API

        Returns:
            Release instance

        """

        tag_name = api_data.get("tag_name", "")
        version = cls._normalize_version(tag_name)
        prerelease = api_data.get("prerelease", False)

        # Convert assets
        assets = []
        for asset_data in api_data.get("assets", []):
            asset = Asset.from_api_response(asset_data)
            if asset:
                assets.append(asset)

        return cls(
            owner=owner,
            repo=repo,
            version=version,
            prerelease=prerelease,
            assets=assets,
            original_tag_name=tag_name,
        )

    @staticmethod
    def _normalize_version(tag_name: str) -> str:
        """Normalize version by extracting and sanitizing version string.

        Args:
            tag_name: Version tag that may have 'v' prefix or package format

        Returns:
            Sanitized version string

        """
        if not tag_name:
            return ""

        normalized = extract_and_validate_version(tag_name)
        if normalized is None:
            return tag_name.lstrip("v")

        return normalized

    def to_dict(self) -> dict[str, Any]:
        """Convert Release to dictionary for caching.

        Returns:
            Dictionary representation suitable for JSON serialization

        """
        return {
            "owner": self.owner,
            "repo": self.repo,
            "version": self.version,
            "prerelease": self.prerelease,
            "assets": [
                {
                    "name": asset.name,
                    "size": asset.size,
                    "digest": asset.digest,
                    "browser_download_url": asset.browser_download_url,
                }
                for asset in self.assets
            ],
            "original_tag_name": self.original_tag_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Release:
        """Create Release from dictionary (e.g., from cache).

        Args:
            data: Dictionary representation of a release

        Returns:
            Release instance

        """

        assets = [
            Asset(
                name=a["name"],
                size=a["size"],
                digest=a.get("digest", ""),
                browser_download_url=a["browser_download_url"],
            )
            for a in data.get("assets", [])
        ]

        return cls(
            owner=data["owner"],
            repo=data["repo"],
            version=data["version"],
            prerelease=data["prerelease"],
            assets=assets,
            original_tag_name=data["original_tag_name"],
        )

    def get_appimages(self) -> list[Asset]:
        """Get all AppImage assets from this release.

        Returns:
            List of AppImage assets

        """
        return [asset for asset in self.assets if asset.is_appimage()]

    def filter_for_platform(self) -> Release:
        """Return new Release with only platform-relevant assets.

        Filters assets to include only:
        - Linux x86_64 AppImages (excludes Windows, macOS, ARM)
        - Checksum files for compatible AppImages

        This method uses AssetSelector.filter_for_cache() for consistent
        filtering across the application.

        Returns:
            New Release instance with filtered assets

        """

        filtered_assets = AssetSelector.filter_for_cache(self.assets)
        return replace(self, assets=filtered_assets)


@dataclass(frozen=True)
class GitHubConfig:
    """Validated GitHub repository configuration.

    This dataclass represents a validated GitHub configuration
    extracted from application configuration.

    Attributes:
        owner: GitHub repository owner/organization
        repo: GitHub repository name
        prerelease: Whether to use prerelease versions

    """

    owner: str
    repo: str
    prerelease: bool = False


def get_github_config(app_config: Mapping[str, Any]) -> GitHubConfig:
    """Extract and validate GitHub configuration from app config.

    This function consolidates the pattern of extracting GitHub config
    and validating it for security, eliminating duplicate code across
    install and update workflows.

    Args:
        app_config: Application configuration mapping

    Returns:
        GitHubConfig: Validated configuration object

    Raises:
        ValueError: If GitHub identifiers are invalid or missing

    Examples:
        >>> config = {
        ...     "source": {
        ...         "owner": "AppFlowy-IO",
        ...         "repo": "AppFlowy",
        ...         "prerelease": False
        ...     }
        ... }
        >>> github_config = get_github_config(config)
        >>> github_config.owner
        'AppFlowy-IO'

    """
    ConfigurationValidator.validate_app_config(app_config)
    owner, repo, prerelease = extract_github_config(app_config)
    return GitHubConfig(owner=owner, repo=repo, prerelease=prerelease)


def extract_github_config(
    effective_config: Mapping[str, Any],
) -> tuple[str, str, bool]:
    """Extract GitHub repository configuration from effective config.

    Args:
        effective_config: Effective app configuration mapping

    Returns:
        Tuple containing:
            - owner: Repository owner
            - repo: Repository name
            - prerelease: Whether to use prereleases

    Examples:
        >>> config = {
        ...     "source": {
        ...         "owner": "AppFlowy-IO",
        ...         "repo": "AppFlowy",
        ...         "prerelease": False
        ...     }
        ... }
        >>> extract_github_config(config)
        ('AppFlowy-IO', 'AppFlowy', False)

    """
    source_config = effective_config.get("source", {})
    owner = source_config.get("owner", "unknown")
    repo = source_config.get("repo", "unknown")
    prerelease = source_config.get("prerelease", False)

    return owner, repo, prerelease
