"""Release description verification for GitHub repositories.

This module provides functionality to extract checksums from GitHub release descriptions
and delegate verification to the existing verification infrastructure. It acts as a bridge
between API fetching and the core verification system.
"""

import logging
from pathlib import Path

from src.api.release_description_fetcher import ReleaseDescriptionFetcher
from src.utils.checksums.parser import parse_checksums_from_description
from src.utils.checksums.storage import save_checksums_file
from src.verification.manager import VerificationManager

logger = logging.getLogger(__name__)


class ReleaseDescVerifier:
    """Extracts checksums from GitHub release descriptions and delegates verification."""

    def __init__(self, owner: str, repo: str) -> None:
        """Initialize the release description verifier.

        Args:
            owner: Repository owner or organization name
            repo: Repository name

        """
        self.owner = owner
        self.repo = repo
        self.fetcher = ReleaseDescriptionFetcher(owner, repo)

    def verify_appimage(
        self,
        appimage_path: str | Path,
        appimage_name: str | None = None,
        cleanup_on_failure: bool = False
    ) -> bool:
        """Verify an AppImage using checksums from GitHub release description.

        This method extracts checksums from the release description, creates a temporary
        SHA file, and delegates the actual verification to VerificationManager.

        Args:
            appimage_path: Path to the AppImage file to verify
            appimage_name: Optional specific AppImage filename to filter checksums for
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            True if verification succeeds, False otherwise

        """
        try:
            appimage_path = Path(appimage_path)
            actual_appimage_name = appimage_name or appimage_path.name

            logger.info(
                f"Starting release description verification for {actual_appimage_name} "
                f"from {self.owner}/{self.repo}"
            )

            # Extract checksums to temporary file
            temp_sha_file = self.extract_checksums_to_file(actual_appimage_name)
            if not temp_sha_file:
                logger.error("Failed to extract checksums from release description")
                return False

            # Delegate to existing verification infrastructure
            verifier = VerificationManager(
                checksum_file_name=temp_sha_file,
                appimage_name=actual_appimage_name,
                appimage_path=str(appimage_path),
                checksum_hash_type="sha256"  # Release descriptions typically use SHA256
            )

            return verifier.verify_appimage(cleanup_on_failure=cleanup_on_failure)

        except Exception as e:
            logger.exception(f"Error during release description verification: {e}")
            return False

    def extract_checksums_to_file(
        self,
        appimage_name: str | None = None,
        output_path: str | None = None
    ) -> str | None:
        """Extract checksums from release description and save to file.

        Args:
            appimage_name: Optional AppImage filename to filter checksums for
            output_path: Optional path for output file, uses temp file if None

        Returns:
            Path to the created checksums file if successful, None if failed

        """
        try:
            logger.debug(f"Extracting checksums from {self.owner}/{self.repo}")

            # Fetch release description
            description = self.fetcher.fetch_latest_release_description()
            if not description:
                logger.error("Failed to fetch release description")
                return None

            # Parse checksums from description
            checksums = parse_checksums_from_description(description)
            if not checksums:
                logger.error("No checksums found in release description")
                return None

            # Filter for specific AppImage if requested
            if appimage_name:
                target_checksums = self._filter_checksums_for_target(checksums, appimage_name)
                if target_checksums:
                    checksums = target_checksums
                else:
                    logger.warning(f"No checksums found for {appimage_name}, using all checksums")

            # Save to file
            return save_checksums_file(checksums, output_path)

        except Exception as e:
            logger.exception(f"Error extracting checksums to file: {e}")
            return None

    def _filter_checksums_for_target(
        self, checksums: list[str], target_filename: str
    ) -> list[str]:
        """Filter checksums for a specific target filename.

        Args:
            checksums: List of checksum lines
            target_filename: Target filename to filter for

        Returns:
            Filtered list of checksum lines

        """
        if not target_filename:
            return checksums

        filename_lower = Path(target_filename).name.lower()
        filtered = [line for line in checksums if filename_lower in line.lower()]

        if filtered:
            logger.debug(f"Filtered to {len(filtered)} checksums for {target_filename}")
            return filtered
        else:
            logger.warning(f"No checksums found for {target_filename}")
            return []

    @staticmethod
    def get_repo_info_for_appimage(appimage_path: str | Path) -> dict[str, str]:
        """Get owner/repo information for an AppImage from app catalog.

        Args:
            appimage_path: Path to the AppImage file (str or Path)

        Returns:
            Dictionary with 'owner' and 'repo' keys if found, empty dict if not found

        """
        try:
            from src.catalog import find_app_by_name_in_filename

            appimage_filename = Path(appimage_path).name
            logger.debug(f"Looking up repository info for filename: {appimage_filename}")

            app_info = find_app_by_name_in_filename(appimage_filename)
            if app_info:
                logger.debug(f"Found matching app in catalog: {app_info.owner}/{app_info.repo}")
                return {"owner": app_info.owner, "repo": app_info.repo}

            logger.warning(f"No matching repository found for {appimage_filename}")

        except Exception as e:
            logger.exception(f"Error finding repository info: {e}")

        return {}

    @staticmethod
    def validate_repo_info(repo_info: dict[str, str]) -> bool:
        """Validate that repository information contains required fields.

        Args:
            repo_info: Dictionary with repository information

        Returns:
            True if repo_info contains both 'owner' and 'repo' keys with values

        """
        return bool(
            repo_info
            and repo_info.get("owner")
            and repo_info.get("repo")
        )

    @classmethod
    def create_from_appimage_path(
        cls, appimage_path: str | Path
    ) -> "ReleaseDescVerifier | None":
        """Create a ReleaseDescVerifier by auto-detecting repository info from AppImage path.

        Args:
            appimage_path: Path to the AppImage file

        Returns:
            ReleaseDescVerifier instance if repository info found, None otherwise

        """
        repo_info = cls.get_repo_info_for_appimage(appimage_path)
        if not cls.validate_repo_info(repo_info):
            logger.error(f"Could not determine repository info for {appimage_path}")
            return None

        logger.info(
            f"Auto-detected repository: {repo_info['owner']}/{repo_info['repo']}"
        )
        return cls(owner=repo_info["owner"], repo=repo_info["repo"])

    @classmethod
    def verify_appimage_standalone(
        cls,
        appimage_path: str | Path,
        owner: str | None = None,
        repo: str | None = None,
        cleanup_on_failure: bool = False,
    ) -> bool:
        """Standalone verification method for AppImages using release description checksums.

        This is the main entry point for verifying AppImages when you may not have
        repository information readily available.

        Args:
            appimage_path: Path to the AppImage file to verify
            owner: Repository owner, auto-detected if None
            repo: Repository name, auto-detected if None
            cleanup_on_failure: Whether to remove the AppImage if verification fails

        Returns:
            True if verification passed, False if failed or error occurred

        """
        try:
            appimage_name = Path(appimage_path).name

            # Auto-detect owner/repo if not provided
            if not owner or not repo:
                repo_info = cls.get_repo_info_for_appimage(appimage_path)
                owner = repo_info.get("owner")
                repo = repo_info.get("repo")

                if not owner or not repo:
                    logger.error(f"Could not determine owner/repo for {appimage_name}")
                    return False

            logger.info(
                f"Verifying {appimage_name} using GitHub release description from {owner}/{repo}"
            )

            # Create verifier and verify
            verifier = cls(owner=owner, repo=repo)
            return verifier.verify_appimage(
                appimage_path=appimage_path,
                cleanup_on_failure=cleanup_on_failure,
            )

        except Exception as e:
            logger.exception(f"Release description verification error: {e}")
            return False
