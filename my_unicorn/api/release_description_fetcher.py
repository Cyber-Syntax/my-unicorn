"""Release description fetching functionality for GitHub API.

This module provides functionality to fetch release descriptions from GitHub repositories
for applications that store checksums in their release notes rather than as separate files.
"""

import logging
from typing import Any

from requests.exceptions import RequestException

from my_unicorn.auth_manager import GitHubAuthManager

logger = logging.getLogger(__name__)


class ReleaseDescriptionFetcher:
    """Handles fetching release descriptions from GitHub repositories."""

    def __init__(self, owner: str, repo: str) -> None:
        """Initialize with GitHub repository information.

        Args:
            owner: Repository owner or organization name
            repo: Repository name

        """
        self.owner = owner
        self.repo = repo
        self._headers = GitHubAuthManager.get_auth_headers()

    def fetch_latest_release_description(self) -> str | None:
        """Fetch the latest release description from GitHub API.

        Returns:
            The release description text or None if unavailable

        Raises:
            RequestException: If network request fails

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}" + "/releases/latest"
        logger.debug("Fetching release description from %s", api_url)

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error("Failed to fetch release: %s %s", response.status_code, response.text)
                return None

            release_data = response.json()
            description = release_data.get("body", "")

            if not description:
                logger.warning("Empty release description")
                return None

            logger.info(
                "Successfully fetched release description (%d characters) for %s/%s",
                len(description),
                self.owner,
                self.repo,
            )
            return description

        except RequestException as e:
            logger.error("Network error fetching release description: %s", e)
            raise

    def fetch_release_description_by_tag(self, tag: str) -> str | None:
        """Fetch release description for a specific tag.

        Args:
            tag: The release tag to fetch

        Returns:
            The release description text or None if unavailable

        Raises:
            RequestException: If network request fails

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        logger.debug("Fetching release description for tag %s from %s", tag, api_url)

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error(
                    "Failed to fetch release for tag %s: %s %s",
                    tag,
                    response.status_code,
                    response.text,
                )
                return None

            release_data = response.json()
            description = release_data.get("body", "")

            if not description:
                logger.warning("Empty release description for tag %s", tag)
                return None

            logger.info(
                "Successfully fetched release description for tag %s (%d characters) for %s/%s",
                tag,
                len(description),
                self.owner,
                self.repo,
            )
            return description

        except RequestException as e:
            logger.error("Network error fetching release description for tag %s: %s", tag, e)
            raise

    def get_release_data(self) -> dict[str, Any] | None:
        """Get full release data including description and metadata.

        Returns:
            Complete release data dict or None if unavailable

        Raises:
            RequestException: If network request fails

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}" + "/releases/latest"
        logger.debug("Fetching complete release data from %s", api_url)

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error(
                    "Failed to fetch release data: %s %s", response.status_code, response.text
                )
                return None

            release_data = response.json()
            logger.info("Successfully fetched release data for %s/%s", self.owner, self.repo)
            return release_data

        except RequestException as e:
            logger.error("Network error fetching release data: %s", e)
            raise
