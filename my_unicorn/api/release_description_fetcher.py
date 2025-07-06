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
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        logger.debug(f"Fetching release description from {api_url}")

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_release_description",
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error(f"Failed to fetch release: {response.status_code} {response.text}")
                return None

            release_data = response.json()
            description = release_data.get("body", "")

            if not description:
                logger.warning("Empty release description")
                return None

            logger.info(
                f"Successfully fetched release description "
                f"({len(description)} characters) for {self.owner}/{self.repo}"
            )
            return description

        except RequestException as e:
            logger.error(f"Network error fetching release description: {e}")
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
        logger.debug(f"Fetching release description for tag {tag} from {api_url}")

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_release_description_by_tag",
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error(
                    f"Failed to fetch release for tag {tag}: {response.status_code} {response.text}"
                )
                return None

            release_data = response.json()
            description = release_data.get("body", "")

            if not description:
                logger.warning(f"Empty release description for tag {tag}")
                return None

            logger.info(
                f"Successfully fetched release description for tag {tag} "
                f"({len(description)} characters) for {self.owner}/{self.repo}"
            )
            return description

        except RequestException as e:
            logger.error(f"Network error fetching release description for tag {tag}: {e}")
            raise

    def get_release_data(self) -> dict[str, Any] | None:
        """Get full release data including description and metadata.

        Returns:
            Complete release data dict or None if unavailable

        Raises:
            RequestException: If network request fails

        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        logger.debug(f"Fetching complete release data from {api_url}")

        try:
            response = GitHubAuthManager.make_authenticated_request(
                "GET",
                api_url,
                headers=self._headers,
                timeout=30,
                audit_action="fetch_release_data",
            )

            if response.status_code != 200:  # noqa: PLR2004
                logger.error(
                    f"Failed to fetch release data: {response.status_code} {response.text}"
                )
                return None

            release_data = response.json()
            logger.info(f"Successfully fetched release data for {self.owner}/{self.repo}")
            return release_data

        except RequestException as e:
            logger.error(f"Network error fetching release data: {e}")
            raise
