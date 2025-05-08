"""GitHub release description checksum extraction functionality.

This module provides capabilities to extract SHA256 checksums from GitHub
release descriptions for applications that store their checksums in the
release notes rather than as separate files.
"""

import logging
from pathlib import Path
from typing import List, Optional

from requests.exceptions import RequestException

from src.auth_manager import GitHubAuthManager
from src.utils.checksums.parser import parse_checksums_from_description

logger = logging.getLogger(__name__)


class ReleaseChecksumExtractor:
    """Extract and process checksums from GitHub release descriptions."""

    def __init__(self, owner: str, repo: str) -> None:
        """Initialize with GitHub repository information.

        Args:
            owner: Repository owner or organization name
            repo: Repository name

        """
        self.owner = owner
        self.repo = repo
        self.release_description: Optional[str] = None
        self._headers = GitHubAuthManager.get_auth_headers()

    def fetch_release_description(self) -> Optional[str]:
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

            if response.status_code != 200:
                logger.error(f"Failed to fetch release: {response.status_code} {response.text}")
                return None

            release_data = response.json()
            self.release_description = release_data.get("body", "")

            if not self.release_description:
                logger.warning("Empty release description")
                return None

            logger.info(
                f"Successfully fetched release description "
                f"({len(self.release_description)} characters)"
            )
            return self.release_description

        except RequestException as e:
            logger.error(f"Network error fetching release: {e}")
            raise

    def extract_checksums(self, target_filename: Optional[str] = None) -> List[str]:
        """Extract checksum lines from the release description.

        Args:
            target_filename: Optional filename to filter checksums for

        Returns:
            List of checksum lines in "hash filename" format

        Raises:
            ValueError: If no checksums found or description unavailable

        """
        if not self.release_description:
            self.release_description = self.fetch_release_description()

        if not self.release_description:
            raise ValueError("No release description available")

        checksums = parse_checksums_from_description(self.release_description)

        if not checksums:
            raise ValueError("No checksums found in release description")

        logger.debug(f"Found {len(checksums)} checksums in release description")

        # Filter checksums for specific target file if provided
        if target_filename and checksums:
            filename_lower = Path(target_filename).name.lower()
            filtered = [line for line in checksums if filename_lower in line.lower()]

            if filtered:
                logger.debug(f"Filtered to {len(filtered)} checksums for {target_filename}")
                return filtered
            else:
                logger.warning(f"No checksums found for {target_filename}, returning all")

        return checksums
