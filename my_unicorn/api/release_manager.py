"""Release Manager module.

This module handles fetching raw release data from the GitHub API.
"""

import logging
from typing import Any

from my_unicorn.auth_manager import GitHubAuthManager  # Ensure this import is correct

logger = logging.getLogger(__name__)


class ReleaseManager:
    """Handles fetching raw release data from GitHub."""

    def __init__(self, owner: str, repo: str):
        """Initialize the ReleaseManager.

        Args:
            owner: Repository owner/organization.
            repo: Repository name.

        """
        self.owner = owner
        self.repo = repo
        logger.debug("ReleaseManager initialized for %s/%s to fetch raw data.", owner, repo)

    def _fetch_all_releases_data(
        self, headers: dict[str, str] | None
    ) -> tuple[bool, dict[str, Any] | str]:
        """Fetch all releases and return the latest one's raw data."""
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        logger.debug("Fetching all releases from %s", api_url)
        response = GitHubAuthManager.make_authenticated_request(
            "GET",
            api_url,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:  # HTTP_OK
            releases = response.json()
            if not releases:
                logger.info(
                    "No releases found at all for %s/%s via _fetch_all_releases_data.",
                    self.owner,
                    self.repo,
                )
                return False, "No releases found (including pre-releases)"
            # The first release in the list is the most recent
            latest_release_data = releases[0]
            logger.debug(
                "Successfully fetched all releases, using the latest: %s",
                latest_release_data.get("tag_name"),
            )
            return True, latest_release_data
        # Rate limit handling is done by the caller (GitHubAPI) which can decide to refresh auth
        elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
            logger.warning(
                "GitHub API rate limit exceeded during _fetch_all_releases_data for %s/%s.",
                self.owner,
                self.repo,
            )
            return False, "GitHub API rate limit exceeded."  # Specific error for rate limit
        else:
            logger.error(
                "Failed to fetch all releases for %s/%s: %s - %s",
                self.owner,
                self.repo,
                response.status_code,
                response.text,
            )
            return False, "Failed to fetch all releases for %s/%s: %s - %s" % (
                self.owner,
                self.repo,
                response.status_code,
                response.text,
            )

    def get_latest_release_data(
        self, headers: dict[str, str] | None
    ) -> tuple[bool, dict[str, Any] | str]:
        """Get the latest stable release's raw data, or fallback to the latest pre-release.

        Args:
            headers: Authentication headers to be used for the request.

        Returns:
            tuple: (Success flag, Raw release JSON data or error message string)

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        logger.debug("Fetching latest stable release from %s", api_url)
        response = GitHubAuthManager.make_authenticated_request(
            "GET",
            api_url,
            headers=headers,
            timeout=30,
        )

        if response.status_code == 200:  # HTTP_OK
            release_data = response.json()
            logger.debug(
                "Successfully fetched latest stable release: %s", release_data.get("tag_name")
            )
            return True, release_data
        elif response.status_code == 404:  # HTTP_NOT_FOUND
            logger.info(
                "No stable release found for %s/%s via get_latest_release_data, "
                "falling back to fetching all releases.",
                self.owner,
                self.repo,
            )
            return self._fetch_all_releases_data(headers)
        # Rate limit handling is done by the caller (GitHubAPI)
        elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
            logger.warning(
                "GitHub API rate limit exceeded during get_latest_release_data for %s/%s.",
                self.owner,
                self.repo,
            )
            return False, "GitHub API rate limit exceeded."  # Specific error for rate limit
        else:
            logger.error(
                "Failed to fetch latest stable release for %s/%s: %s - %s",
                self.owner,
                self.repo,
                response.status_code,
                response.text,
            )
            return False, "Failed to fetch latest stable release for %s/%s: %s - %s" % (
                self.owner,
                self.repo,
                response.status_code,
                response.text,
            )

    def get_latest_beta_release_data(
        self, headers: dict[str, str] | None
    ) -> tuple[bool, dict[str, Any] | str]:
        """Get the latest beta/pre-release data directly (bypassing stable release check).

        This method fetches all releases and returns the latest one, which may be a beta.
        This is more efficient for repositories that primarily use beta releases.

        Args:
            headers: Authentication headers to be used for the request.

        Returns:
            tuple: (Success flag, Raw release JSON data or error message string)

        """
        logger.debug("Fetching latest beta release directly for %s/%s", self.owner, self.repo)
        return self._fetch_all_releases_data(headers)
