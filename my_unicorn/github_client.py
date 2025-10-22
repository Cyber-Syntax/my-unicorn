"""GitHub API client for fetching release information and assets.

This module handles communication with the GitHub API to fetch release
information, extract AppImage assets, and manage GitHub-specific operations.

Refactored to use dataclasses and improved separation of concerns.
"""

import os
from dataclasses import dataclass
from typing import Any

import aiohttp

from .auth import GitHubAuthManager, auth_manager
from .logger import get_logger
from .services.cache import get_cache_manager
from .services.progress import get_progress_service
from .utils import (
    extract_and_validate_version,
    get_checksum_file_format_type,
    is_checksum_file,
)

logger = get_logger(__name__)

# Constants
HTTP_NOT_FOUND = 404


@dataclass(slots=True, frozen=True)
class ChecksumFileInfo:
    """Information about detected checksum file."""

    filename: str
    url: str
    format_type: str  # 'yaml' or 'traditional'


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
    def from_api_response(cls, asset_data: dict[str, Any]) -> "Asset | None":
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
        name_lower = self.name.lower()
        return name_lower.endswith(".appimage")


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
    ) -> "Release":
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
    def from_dict(cls, data: dict[str, Any]) -> "Release":
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


class AssetSelector:
    """Handles selection logic for choosing the best asset from a release."""

    @staticmethod
    def find_all_appimages(release: Release) -> list[Asset]:
        """Find all AppImage assets in a release.

        Args:
            release: Release to search

        Returns:
            List of all AppImage assets

        """
        return release.get_appimages()

    @staticmethod
    def find_first_appimage(release: Release) -> Asset | None:
        """Find the first AppImage asset in a release.

        Args:
            release: Release to search

        Returns:
            First AppImage asset or None if no AppImages found

        """
        appimages = AssetSelector.find_all_appimages(release)
        return appimages[0] if appimages else None

    @staticmethod
    def select_appimage_for_platform(
        release: Release,
        preferred_suffixes: list[str] | None = None,
        installation_source: str = "catalog",
    ) -> Asset | None:
        """Select the best AppImage based on architecture and preferences.

        This method prioritizes amd64/x86_64 architecture.
        It automatically filters out ARM architectures.

        Selection strategy for catalog installs:
        1. Filter by preferred_suffixes if provided
        2. Filter out ARM architectures
        3. Prefer explicit x86_64/amd64 markers
        4. Fall back to first remaining candidate

        Selection strategy for URL installs:
        1. Filter out unstable versions
        2. Filter out ARM architectures
        3. Return first remaining stable candidate

        Args:
            release: Release to select from
            preferred_suffixes: List of preferred filename suffixes
            installation_source: Installation source ("catalog" or "url")

        Returns:
            Best matching AppImage asset or None

        """
        appimages = AssetSelector.find_all_appimages(release)

        if not appimages:
            return None

        if len(appimages) == 1:
            return appimages[0]

        # Apply different strategies based on installation source
        candidates = AssetSelector._filter_by_source(
            appimages, installation_source, preferred_suffixes
        )

        # Filter out ARM architectures to prefer amd64
        candidates = AssetSelector._filter_arm_architectures(candidates)

        # For catalog installs, prefer explicit x86_64/amd64 markers
        if installation_source == "catalog":
            explicit_match = AssetSelector._find_explicit_amd64(candidates)
            if explicit_match:
                return explicit_match

        # Fallback: return first candidate
        return candidates[0]

    @staticmethod
    def _filter_by_source(
        appimages: list[Asset],
        installation_source: str,
        preferred_suffixes: list[str] | None,
    ) -> list[Asset]:
        """Filter assets based on installation source."""
        if installation_source == "url":
            return AssetSelector._filter_unstable_versions(appimages)
        return AssetSelector._filter_by_preferred_suffixes(
            appimages, preferred_suffixes
        )

    @staticmethod
    def _filter_unstable_versions(appimages: list[Asset]) -> list[Asset]:
        """Filter out unstable version keywords."""
        unstable_keywords = [
            "experimental",
            "beta",
            "alpha",
            "rc",
            "pre",
            "dev",
            "test",
            "nightly",
        ]
        stable = [
            app
            for app in appimages
            if not any(kw in app.name.lower() for kw in unstable_keywords)
        ]
        return stable if stable else appimages

    @staticmethod
    def _filter_by_preferred_suffixes(
        appimages: list[Asset], preferred_suffixes: list[str] | None
    ) -> list[Asset]:
        """Filter assets by preferred suffixes."""
        if not preferred_suffixes:
            return appimages

        matched = [
            app
            for suffix in preferred_suffixes
            for app in appimages
            if suffix.lower() in app.name.lower()
        ]
        return matched if matched else appimages

    @staticmethod
    def _filter_arm_architectures(appimages: list[Asset]) -> list[Asset]:
        """Filter out ARM architecture assets."""
        arm_keywords = ["arm64", "aarch64", "armhf", "armv7", "armv6"]
        amd64 = [
            app
            for app in appimages
            if not any(kw in app.name.lower() for kw in arm_keywords)
        ]
        return amd64 if amd64 else appimages

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
        assets: list[Asset], tag_name: str
    ) -> list[ChecksumFileInfo]:
        """Detect checksum files in release assets.

        Args:
            assets: List of release assets
            tag_name: Release tag name

        Returns:
            List of detected checksum files with their info

        """
        checksum_files = []

        for asset in assets:
            if is_checksum_file(asset.name):
                format_type = get_checksum_file_format_type(asset.name)
                checksum_files.append(
                    ChecksumFileInfo(
                        filename=asset.name,
                        url=asset.browser_download_url,
                        format_type=format_type,
                    )
                )

        # Prioritize YAML files first as they're often more reliable
        checksum_files.sort(
            key=lambda x: (x.format_type != "yaml", x.filename)
        )

        return checksum_files


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
                await self.progress_service.update_task_total(
                    self.shared_api_task_id, float(new_completed)
                )
                await self.progress_service.update_task(
                    self.shared_api_task_id,
                    completed=float(new_completed),
                    description=(
                        f"🌐 {description} ({new_completed}/{new_completed})"
                    ),
                )

                if hasattr(self.progress_service, "_refresh_live_display"):
                    self.progress_service._refresh_live_display()
        except Exception:
            pass

    async def _fetch_from_api(
        self, url: str, description: str
    ) -> dict[str, Any] | None:
        """Fetch data from GitHub API.

        Args:
            url: API URL to fetch
            description: Description for progress tracking

        Returns:
            API response data or None if not found

        """
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            if response.status == HTTP_NOT_FOUND:
                return None

            response.raise_for_status()
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            if self.shared_api_task_id and self.progress_service.is_active():
                await self._update_shared_progress(description)

            return await response.json()

    async def fetch_stable_release(self) -> Release | None:
        """Fetch the latest stable release.

        Returns:
            Release instance or None if no stable release found

        """
        url = (
            f"https://api.github.com/repos/{self.owner}/"
            f"{self.repo}/releases/latest"
        )
        data = await self._fetch_from_api(url, "Fetched stable release")

        if data is None:
            return None

        if data.get("prerelease", False):
            return None

        return Release.from_api_response(self.owner, self.repo, data)

    async def fetch_prerelease(self) -> Release | None:
        """Fetch the latest prerelease.

        Returns:
            Release instance or None if no prerelease found

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        data = await self._fetch_from_api(url, "Fetched prerelease")

        if data is None:
            return None

        for release in data:
            if release.get("prerelease", False):
                return Release.from_api_response(
                    self.owner, self.repo, release
                )

        return None

    async def fetch_release_by_tag(self, tag: str) -> Release | None:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release instance or None if not found

        """
        url = (
            f"https://api.github.com/repos/{self.owner}/"
            f"{self.repo}/releases/tags/{tag}"
        )
        data = await self._fetch_from_api(url, f"Fetched release {tag}")

        if data is None:
            return None

        return Release.from_api_response(self.owner, self.repo, data)

    async def fetch_default_branch(self) -> str:
        """Get the default branch name for the repository.

        Returns:
            Default branch name (e.g., 'main', 'master')

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        data = await self._fetch_from_api(url, "Fetched default branch")

        if data is None:
            return "main"

        return data.get("default_branch", "main")


class ReleaseFetcher:
    """Orchestrates release fetching with caching support."""

    def __init__(
        self,
        owner: str,
        repo: str,
        session: aiohttp.ClientSession,
        shared_api_task_id: str | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize the release fetcher.

        Args:
            owner: Repository owner
            repo: Repository name
            session: aiohttp session for making requests
            shared_api_task_id: Optional shared API progress task ID
            use_cache: Whether to use persistent caching

        """
        self.owner = owner
        self.repo = repo
        self.use_cache = use_cache
        self.cache_manager = get_cache_manager() if use_cache else None
        self.api_client = ReleaseAPIClient(
            owner, repo, session, auth_manager, shared_api_task_id
        )
        self.progress_service = get_progress_service()
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
                return cached

        release = await self.api_client.fetch_stable_release()
        if release is None:
            raise ValueError(
                f"No stable release found for {self.owner}/{self.repo}"
            )

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
                return cached

        release = await self.api_client.fetch_prerelease()
        if release is None:
            raise ValueError(
                f"No prerelease found for {self.owner}/{self.repo}"
            )

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

        if self.shared_api_task_id and self.progress_service.is_active():
            await self.api_client._update_shared_progress(
                f"No releases found for {self.owner}/{self.repo}"
            )

        raise ValueError(f"No releases found for {self.owner}/{self.repo}")

    async def _try_prerelease_then_stable(
        self, ignore_cache: bool
    ) -> Release | None:
        """Try to fetch prerelease first, then stable as fallback."""
        # Try prerelease
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="prerelease")
            if cached:
                return cached

        release = await self.api_client.fetch_prerelease()
        if release:
            await self._save_to_cache(release, cache_type="prerelease")
            return release

        # Fallback to stable
        return await self._fetch_stable_with_cache(ignore_cache)

    async def _try_stable_then_prerelease(
        self, ignore_cache: bool
    ) -> Release | None:
        """Try to fetch stable first, then prerelease as fallback."""
        # Try stable
        release = await self._fetch_stable_with_cache(ignore_cache)
        if release:
            return release

        # Fallback to prerelease
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="prerelease")
            if cached:
                return cached

        release = await self.api_client.fetch_prerelease()
        if release:
            await self._save_to_cache(release, cache_type="prerelease")
            return release

        return None

    async def _fetch_stable_with_cache(
        self, ignore_cache: bool
    ) -> Release | None:
        """Fetch stable release with cache support."""
        if not ignore_cache:
            cached = await self._get_from_cache(cache_type="stable")
            if cached:
                return cached

        release = await self.api_client.fetch_stable_release()
        if release:
            await self._save_to_cache(release, cache_type="stable")
        return release

    async def fetch_specific_release(self, tag: str) -> Release:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release for the specified tag

        Raises:
            ValueError: If release not found

        """
        release = await self.api_client.fetch_release_by_tag(tag)
        if release is None:
            raise ValueError(
                f"Release {tag} not found for {self.owner}/{self.repo}"
            )
        return release

    async def get_default_branch(self) -> str:
        """Get the default branch name for the repository.

        Returns:
            Default branch name

        """
        return await self.api_client.fetch_default_branch()

    @staticmethod
    def build_icon_url(
        owner: str, repo: str, icon_path: str, branch: str | None = None
    ) -> str:
        """Build GitHub raw URL for an icon file.

        Args:
            owner: Repository owner
            repo: Repository name
            icon_path: Path to the icon file within the repository
            branch: Branch name (defaults to 'main')

        Returns:
            Full GitHub raw URL for the icon

        """
        if branch is None:
            branch = "main"

        clean_path = icon_path.lstrip("/")
        return (
            f"https://raw.githubusercontent.com/{owner}/"
            f"{repo}/{branch}/{clean_path}"
        )

    @staticmethod
    def extract_icon_filename(icon_path: str, app_name: str) -> str:
        """Extract or generate icon filename from path.

        Args:
            icon_path: Path to the icon file
            app_name: Name of the application

        Returns:
            Appropriate filename for the icon

        """
        filename = os.path.basename(icon_path)
        if "." in filename:
            extension = os.path.splitext(filename)[1]
            return f"{app_name}{extension}"
        return f"{app_name}.png"


class GitHubClient:
    """High-level GitHub client for release operations."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize GitHub client.

        Args:
            session: aiohttp session for making requests

        """
        self.session = session
        self.progress_service = get_progress_service()
        self.shared_api_task_id: str | None = None

    def set_shared_api_task(self, task_id: str | None) -> None:
        """Set the shared API progress task ID.

        Args:
            task_id: Shared API progress task ID or None to disable

        """
        self.shared_api_task_id = task_id

    async def get_latest_release(
        self, owner: str, repo: str
    ) -> dict[str, Any] | None:
        """Get the latest release for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release data dictionary or None if not found

        """
        try:
            fetcher = ReleaseFetcher(
                owner, repo, self.session, self.shared_api_task_id
            )
            release = await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )

            original_tag_name = (
                release.original_tag_name or f"v{release.version}"
            )

            return {
                "tag_name": release.version,
                "original_tag_name": original_tag_name,
                "prerelease": release.prerelease,
                "assets": [
                    {
                        "name": asset.name,
                        "size": asset.size,
                        "digest": asset.digest,
                        "browser_download_url": asset.browser_download_url,
                    }
                    for asset in release.assets
                ],
                "html_url": (
                    f"https://github.com/{owner}/{repo}/"
                    f"releases/tag/{original_tag_name}"
                ),
            }
        except Exception as e:
            logger.error(
                "Failed to fetch latest release for %s/%s: %s",
                owner,
                repo,
                e,
            )
            raise

    async def get_release_by_tag(
        self, owner: str, repo: str, tag: str
    ) -> dict[str, Any] | None:
        """Get a specific release by tag.

        Args:
            owner: Repository owner
            repo: Repository name
            tag: Release tag

        Returns:
            Release data dictionary or None if not found

        """
        try:
            fetcher = ReleaseFetcher(
                owner, repo, self.session, self.shared_api_task_id
            )
            release = await fetcher.fetch_specific_release(tag)

            return {
                "tag_name": release.version,
                "original_tag_name": tag,
                "prerelease": release.prerelease,
                "assets": [
                    {
                        "name": asset.name,
                        "size": asset.size,
                        "digest": asset.digest,
                        "browser_download_url": asset.browser_download_url,
                    }
                    for asset in release.assets
                ],
                "html_url": (
                    f"https://github.com/{owner}/{repo}/releases/tag/{tag}"
                ),
            }
        except Exception:
            return None
