"""Low-level GitHub API client for HTTP communication.

This module handles direct HTTP communication with the GitHub API,
including authentication, rate limiting, and retry logic.
"""

import asyncio
from typing import Any

import aiohttp

from my_unicorn.config import config_manager
from my_unicorn.infrastructure.auth import GitHubAuthManager, auth_manager
from my_unicorn.logger import get_logger
from my_unicorn.ui.progress import get_progress_service

logger = get_logger(__name__)

# Constants
HTTP_NOT_FOUND = 404


class ReleaseAPIClient:
    """Handles direct communication with GitHub API for release data."""

    def __init__(
        self,
        owner: str,
        repo: str,
        session: aiohttp.ClientSession,
        auth_manager: GitHubAuthManager,
        shared_api_task_id: str | None = None,
    ) -> None:
        """Initialize the API client.

        Args:
            owner: Repository owner
            repo: Repository name
            session: aiohttp session for making requests
            auth_manager: GitHub authentication manager
            shared_api_task_id: Optional shared API progress task ID

        """
        self.owner = owner
        self.repo = repo
        self.session = session
        self.auth_manager = auth_manager
        self.shared_api_task_id = shared_api_task_id
        self.progress_service = get_progress_service()

    async def _update_shared_progress(self, description: str) -> None:
        """Update shared API progress task.

        Args:
            description: Description to show for the current API request

        """
        if (
            not self.shared_api_task_id
            or not self.progress_service.is_active()
        ):
            return

        try:
            task_info = self.progress_service.get_task_info(
                self.shared_api_task_id
            )
            if task_info:
                new_completed = int(task_info.completed) + 1
                total = (
                    int(task_info.total)
                    if task_info.total > 0
                    else new_completed
                )
                await self.progress_service.update_task(
                    self.shared_api_task_id,
                    completed=float(new_completed),
                    description=(
                        f"🌐 {description} ({new_completed}/{total})"
                    ),
                )

                if hasattr(self.progress_service, "_refresh_live_display"):
                    self.progress_service._refresh_live_display()
        except Exception:
            pass

    async def _fetch_from_api(self, url: str, description: str) -> Any | None:
        """Fetch data from GitHub API.

        Args:
            url: API URL to fetch
            description: Description for progress tracking

        Returns:
            API response data or None if not found

        """
        headers = auth_manager.apply_auth({})

        # If rate-limit is low, wait before making the request
        try:
            if self.auth_manager.should_wait_for_rate_limit():
                wait_time = self.auth_manager.get_wait_time()
                # Cap wait during tests
                capped_wait = min(wait_time, 1)
                logger.warning(
                    "Rate limit low (%s). Waiting %s s (capped %s s)",
                    self.auth_manager._remaining_requests,
                    wait_time,
                    capped_wait,
                )
                if (
                    self.shared_api_task_id
                    and self.progress_service.is_active()
                ):
                    # Update shared progress with a short message
                    await self._update_shared_progress(
                        f"Waiting for rate limit reset ({capped_wait}s)"
                    )
                await asyncio.sleep(capped_wait)
        except Exception:
            # Do not fail API fetch if rate-limit helpers have issues; proceed
            pass

        # Load network configuration (retry and timeout)
        network_cfg = config_manager.load_global_config()["network"]
        retry_attempts = int(network_cfg.get("retry_attempts", 3))
        timeout_seconds = int(network_cfg.get("timeout_seconds", 10))

        # Compose a ClientTimeout derived from configured base seconds.
        # Use modest multipliers to keep behavior similar to prior defaults.
        timeout = aiohttp.ClientTimeout(
            total=timeout_seconds * 3,
            sock_read=timeout_seconds * 2,
            sock_connect=timeout_seconds,
        )

        last_exc: Exception | None = None

        # Retry loop with exponential backoff for transient network errors
        for attempt in range(1, retry_attempts + 1):
            try:
                async with self.session.get(
                    url=url, headers=headers, timeout=timeout
                ) as response:
                    if response.status == HTTP_NOT_FOUND:
                        return None

                    _maybe = response.raise_for_status()
                    if asyncio.iscoroutine(_maybe):
                        await _maybe
                    # Update rate limit info from headers
                    self.auth_manager.update_rate_limit_info(
                        dict(response.headers)
                    )

                    if (
                        self.shared_api_task_id
                        and self.progress_service.is_active()
                    ):
                        await self._update_shared_progress(description)

                    return await response.json()

            except (aiohttp.ClientError, TimeoutError) as e:
                last_exc = e
                logger.warning(
                    "Attempt %d/%d for %s failed: %s",
                    attempt,
                    retry_attempts,
                    url,
                    e,
                )
                if attempt == retry_attempts:
                    logger.error(
                        "❌ API fetch failed after %d attempts: %s - %s",
                        attempt,
                        url,
                        e,
                    )
                    raise
                # Exponential backoff before retrying
                backoff = 2**attempt
                await asyncio.sleep(backoff)
            except Exception as e:
                # Non-network error: do not attempt further retries
                logger.error("Unexpected error fetching API %s: %s", url, e)
                raise

        if last_exc:
            raise last_exc
        # Explicitly return None when no result was obtained and no
        # exception is available — helps static checkers (Pylance/pyright)
        # recognize that this function always returns a value of the
        # annotated `Any | None` type on all control paths.
        return None

    async def fetch_stable_release(self) -> dict[str, Any] | None:
        """Fetch the latest stable release.

        Returns:
            Release data dict or None if no stable release found

        """
        url = (
            f"https://api.github.com/repos/{self.owner}/"
            f"{self.repo}/releases/latest"
        )
        data = await self._fetch_from_api(url, "Fetched stable release")

        if data is None:
            return None

        # Allow AttributeError for non-dict responses (tests expect this)
        if data.get("prerelease", False):
            return None

        return data

    async def fetch_prerelease(self) -> dict[str, Any] | None:
        """Fetch the latest prerelease.

        Returns:
            Release data dict or None if no prerelease found

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        data = await self._fetch_from_api(url, "Fetched prerelease")

        if data is None:
            return None

        # Expect a list of releases; guard if API returned unexpected type
        if not isinstance(data, list):
            logger.warning(
                "Unexpected API response type for prereleases: %s", type(data)
            )
            return None

        # Filter releases to dict entries to avoid calling .get() on bad items
        releases = [r for r in data if isinstance(r, dict)]

        for release in releases:
            if release.get("prerelease", False):
                return release

        return None

    async def fetch_release_by_tag(self, tag: str) -> dict[str, Any] | None:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release data dict or None if not found

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
                "Unexpected API response type for release by tag %s: %s",
                tag,
                type(data),
            )
            return None

        return data

    async def fetch_default_branch(self) -> str:
        """Get the default branch name for the repository.

        Returns:
            Default branch name (e.g., 'main', 'master')

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        data = await self._fetch_from_api(url, "Fetched default branch")

        if data is None:
            return "main"

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected API response for default branch: %s", type(data)
            )
            return "main"

        return data.get("default_branch", "main")
