"""App selectors for install templates using Strategy pattern.

This module provides different strategies for selecting and resolving installation targets.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ...github_client import GitHubAsset, GitHubReleaseDetails
from ...logger import get_logger
from ...models import InstallationError, ValidationError

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CatalogInstallContext:
    """Context for catalog-based installation."""

    target: str
    app_name: str
    app_config: dict[str, Any]
    release_data: dict[str, Any]
    appimage_asset: GitHubAsset
    download_path: Path
    post_processing_task_id: str | None = None

    @property
    def verification_config(self) -> dict[str, Any]:
        """Get verification configuration from app config."""
        config = self.app_config.get("verification", {})
        return dict(config) if isinstance(config, dict) else {}


@dataclass(frozen=True, slots=True)
class URLInstallContext:
    """Context for URL-based installation."""

    target: str
    app_name: str
    owner: str
    repo_name: str
    release_data: GitHubReleaseDetails
    appimage_asset: GitHubAsset
    download_path: Path
    post_processing_task_id: str | None = None

    @property
    def verification_config(self) -> dict[str, Any]:
        """Get verification configuration (empty for URL installs)."""
        return {}


class AppSelector(Protocol):
    """Protocol for app selection strategies."""

    async def resolve_app_context(self, target: str, **kwargs: Any) -> Any:
        """Resolve target to installation context.

        Args:
            target: Installation target (app name or URL)
            **kwargs: Additional resolution options

        Returns:
            Installation context for the target

        """

    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are compatible with this selector.

        Args:
            targets: List of targets to validate

        Raises:
            ValidationError: If any target is invalid

        """


class CatalogAppSelector:
    """Resolves apps from catalog."""

    def __init__(self, catalog_manager: Any, github_client: Any) -> None:
        """Initialize catalog app selector.

        Args:
            catalog_manager: Catalog manager for app lookup
            github_client: GitHub client for API access

        """
        self.catalog_manager = catalog_manager
        self.github_client = github_client

    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are valid catalog app names."""
        available_apps = self.catalog_manager.get_available_apps()

        for target in targets:
            if target not in available_apps:
                raise ValidationError(
                    f"Application '{target}' not found in catalog. "
                    f"Available apps: {', '.join(sorted(available_apps.keys()))}"
                )

    async def resolve_app_context(self, target: str, **kwargs: Any) -> CatalogInstallContext:
        """Resolve catalog app to installation context."""
        logger.info("🚀 Resolving catalog app: %s", target)

        # Get app configuration from catalog
        app_config = self.catalog_manager.get_app_config(target)
        if not app_config:
            raise InstallationError(f"App configuration not found: {target}")

        # Get release configuration
        release_config = self._get_release_config(app_config)

        # Fetch release data from GitHub
        logger.info("📡 Fetching release data for %s", target)
        release_data = await self._fetch_release_data(release_config)

        # Find AppImage asset
        characteristic_suffix = app_config.get("appimage", {}).get("characteristic_suffix", [])
        appimage_asset = await self._select_appimage_asset(
            release_config, release_data, characteristic_suffix, target
        )

        # Setup download path
        download_dir = kwargs.get("download_dir", Path.cwd())
        filename = self._get_filename_from_url(appimage_asset["browser_download_url"])
        download_path = download_dir / filename

        # Create post-processing task if progress is enabled
        post_processing_task_id = await self._create_post_processing_task(target, **kwargs)

        return CatalogInstallContext(
            target=target,
            app_name=target,
            app_config=app_config,
            release_data=release_data,
            appimage_asset=appimage_asset,
            download_path=download_path,
            post_processing_task_id=post_processing_task_id,
        )

    def _get_release_config(self, app_config: dict[str, Any]) -> dict[str, Any]:
        """Get release configuration from app config."""
        return {
            "owner": app_config.get("owner"),
            "repo": app_config.get("repo"),
            "tag": app_config.get("tag"),
        }

    async def _fetch_release_data(self, release_config: dict[str, Any]) -> dict[str, Any]:
        """Fetch release data from GitHub."""
        from ...github_client import GitHubReleaseFetcher

        owner = release_config.get("owner")
        repo = release_config.get("repo")

        if not isinstance(owner, str) or not isinstance(repo, str):
            raise InstallationError(f"Invalid owner/repo in release config: {release_config}")

        # Get shared API task from github_client for progress tracking
        shared_api_task_id = getattr(self.github_client, "shared_api_task_id", None)
        fetcher = GitHubReleaseFetcher(
            owner, repo, self.github_client.session, shared_api_task_id
        )

        return await fetcher.fetch_latest_release_or_prerelease(prefer_prerelease=False)

    async def _select_appimage_asset(
        self,
        release_config: dict[str, Any],
        release_data: dict[str, Any],
        characteristic_suffix: list[str],
        app_name: str,
    ) -> GitHubAsset:
        """Select best AppImage asset from release."""
        from ...github_client import GitHubReleaseFetcher

        owner = release_config.get("owner")
        repo = release_config.get("repo")

        if not isinstance(owner, str) or not isinstance(repo, str):
            raise InstallationError(f"Invalid owner/repo in release config for {app_name}")

        shared_api_task_id = getattr(self.github_client, "shared_api_task_id", None)
        fetcher = GitHubReleaseFetcher(
            owner, repo, self.github_client.session, shared_api_task_id
        )

        appimage_asset = fetcher.select_best_appimage(release_data, characteristic_suffix)
        if not appimage_asset:
            raise InstallationError(
                f"No AppImage found for {app_name} with "
                f"characteristic_suffix: {characteristic_suffix}"
            )

        return appimage_asset

    def _get_filename_from_url(self, url: str) -> str:
        """Extract filename from download URL."""
        return url.split("/")[-1]

    async def _create_post_processing_task(self, app_name: str, **kwargs: Any) -> str | None:
        """Create post-processing progress task if enabled."""
        if not kwargs.get("show_progress", False):
            return None

        # Check if we have access to progress service through github_client or other means
        progress_service = None
        if hasattr(self.github_client, "download_service"):
            download_service = self.github_client.download_service
            if hasattr(download_service, "progress_service"):
                progress_service = download_service.progress_service

        if progress_service and progress_service.is_active():
            return await progress_service.create_post_processing_task(app_name)

        return None


class URLAppSelector:
    """Resolves apps from GitHub URLs."""

    def __init__(self, github_client: Any) -> None:
        """Initialize URL app selector.

        Args:
            github_client: GitHub client for API access

        """
        self.github_client = github_client

    def validate_targets(self, targets: list[str]) -> None:
        """Validate that targets are valid GitHub repository URLs."""
        for target in targets:
            if not target.startswith("https://github.com/"):
                raise ValidationError(f"Invalid GitHub URL format: {target}")

            # Basic URL structure validation
            parts = target.replace("https://github.com/", "").split("/")
            if len(parts) < 2:
                raise ValidationError(f"Invalid GitHub URL format: {target}")

    async def resolve_app_context(self, target: str, **kwargs: Any) -> URLInstallContext:
        """Resolve GitHub URL to installation context."""
        logger.info("🚀 Resolving GitHub URL: %s", target)

        # Parse owner/repo from URL
        owner, repo_name, release_data, appimage_asset = await self._parse_and_fetch_release(
            target
        )

        # Generate app name from repo
        app_name = repo_name.lower()

        # Setup download path
        download_dir = kwargs.get("download_dir", Path.cwd())
        filename = self._get_filename_from_url(appimage_asset["browser_download_url"])
        download_path = download_dir / filename

        # Create post-processing task if progress is enabled
        post_processing_task_id = await self._create_post_processing_task(app_name, **kwargs)

        return URLInstallContext(
            target=target,
            app_name=app_name,
            owner=owner,
            repo_name=repo_name,
            release_data=release_data,
            appimage_asset=appimage_asset,
            download_path=download_path,
            post_processing_task_id=post_processing_task_id,
        )

    async def _parse_and_fetch_release(
        self, repo_url: str
    ) -> tuple[str, str, GitHubReleaseDetails, GitHubAsset]:
        """Parse URL and fetch release data with best AppImage asset."""
        # Parse owner/repo from URL
        parts = repo_url.replace("https://github.com/", "").split("/")
        if len(parts) < 2:
            raise ValueError(f"Invalid GitHub URL format: {repo_url}")

        owner, repo_name = parts[0], parts[1]

        # Use GitHubReleaseFetcher for both fetching and asset selection
        from ...github_client import GitHubReleaseFetcher

        shared_api_task_id = getattr(self.github_client, "shared_api_task_id", None)
        fetcher = GitHubReleaseFetcher(
            owner, repo_name, self.github_client.session, shared_api_task_id
        )

        # Fetch latest release
        try:
            release_data = await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )
            logger.info(
                "Found %s release for %s/%s: %s",
                "prerelease" if release_data.get("prerelease") else "release",
                owner,
                repo_name,
                release_data.get("version", "unknown"),
            )
        except Exception as error:
            logger.error("Failed to fetch releases for %s/%s: %s", owner, repo_name, error)
            raise InstallationError(
                f"No releases found for {owner}/{repo_name}: {error}"
            ) from error

        if not release_data:
            raise InstallationError(f"No releases found for {owner}/{repo_name}")

        appimage_asset = fetcher.select_best_appimage(release_data, installation_source="url")
        if not appimage_asset:
            raise InstallationError(f"No AppImage found in {owner}/{repo_name} releases")

        return owner, repo_name, release_data, appimage_asset

    def _get_filename_from_url(self, url: str) -> str:
        """Extract filename from download URL."""
        return url.split("/")[-1]

    async def _create_post_processing_task(self, app_name: str, **kwargs: Any) -> str | None:
        """Create post-processing progress task if enabled."""
        if not kwargs.get("show_progress", False):
            return None

        # Check if we have access to progress service through github_client
        progress_service = None
        if hasattr(self.github_client, "download_service"):
            download_service = self.github_client.download_service
            if hasattr(download_service, "progress_service"):
                progress_service = download_service.progress_service

        if progress_service and progress_service.is_active():
            return await progress_service.create_post_processing_task(app_name)

        return None
