"""Release Manager module.

This module handles fetching raw release data from the GitHub API.
"""

import logging
from typing import Any, Dict, Tuple, Union

from src.auth_manager import GitHubAuthManager  # Ensure this import is correct

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
        logger.debug(f"ReleaseManager initialized for {owner}/{repo} to fetch raw data.")

    def _fetch_all_releases_data(self, headers: Dict) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Fetch all releases and return the latest one's raw data."""
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        logger.debug(f"Fetching all releases from {api_url}")
        response = GitHubAuthManager.make_authenticated_request(
            "GET",
            api_url,
            headers=headers,
            timeout=30,
            audit_action="fetch_all_releases_for_fallback",
        )

        if response.status_code == 200:  # HTTP_OK
            releases = response.json()
            if not releases:
                logger.info(
                    f"No releases found at all for {self.owner}/{self.repo} via _fetch_all_releases_data."
                )
                return False, "No releases found (including pre-releases)"
            # The first release in the list is the most recent
            latest_release_data = releases[0]
            logger.debug(
                f"Successfully fetched all releases, using the latest: {latest_release_data.get('tag_name')}"
            )
            return True, latest_release_data
        # Rate limit handling is done by the caller (GitHubAPI) which can decide to refresh auth
        elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
            logger.warning(
                f"GitHub API rate limit exceeded during _fetch_all_releases_data for {self.owner}/{self.repo}."
            )
            return False, "GitHub API rate limit exceeded."  # Specific error for rate limit
        else:
            error_msg = (
                f"Failed to fetch all releases for {self.owner}/{self.repo}: "
                f"{response.status_code} - {response.text}"
            )
            logger.error(error_msg)
            return False, error_msg

    def get_latest_release_data(self, headers: Dict) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Get the latest stable release's raw data, or fallback to the latest pre-release.

        Args:
            headers: Authentication headers to be used for the request.

        Returns:
            tuple: (Success flag, Raw release JSON data or error message string)
        """
        api_url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/latest"
        logger.debug(f"Fetching latest stable release from {api_url}")
        response = GitHubAuthManager.make_authenticated_request(
            "GET",
            api_url,
            headers=headers,
            timeout=30,
            audit_action="fetch_latest_stable_release_raw",
        )

        if response.status_code == 200:  # HTTP_OK
            release_data = response.json()
            logger.debug(
                f"Successfully fetched latest stable release: {release_data.get('tag_name')}"
            )
            return True, release_data
        elif response.status_code == 404:  # HTTP_NOT_FOUND
            logger.info(
                f"No stable release found for {self.owner}/{self.repo} via get_latest_release_data, "
                f"falling back to fetching all releases."
            )
            return self._fetch_all_releases_data(headers)
        # Rate limit handling is done by the caller (GitHubAPI)
        elif response.status_code == 403 and "rate limit exceeded" in response.text.lower():
            logger.warning(
                f"GitHub API rate limit exceeded during get_latest_release_data for {self.owner}/{self.repo}."
            )
            return False, "GitHub API rate limit exceeded."  # Specific error for rate limit
        else:
            error_msg = (
                f"Failed to fetch latest stable release for {self.owner}/{self.repo}: "
                f"{response.status_code} - {response.text}"
            )
            logger.error(error_msg)
            return False, error_msg

    def get_latest_beta_release_data(
        self, headers: Dict
    ) -> Tuple[bool, Union[Dict[str, Any], str]]:
        """Get the latest beta/pre-release data directly (bypassing stable release check).

        This method fetches all releases and returns the latest one, which may be a beta.
        This is more efficient for repositories that primarily use beta releases.

        Args:
            headers: Authentication headers to be used for the request.

        Returns:
            tuple: (Success flag, Raw release JSON data or error message string)
        """
        logger.debug(f"Fetching latest beta release directly for {self.owner}/{self.repo}")
        return self._fetch_all_releases_data(headers)
