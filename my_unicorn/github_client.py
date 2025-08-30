"""GitHub API client for fetching release information and assets.

This module handles communication with the GitHub API to fetch release
information, extract AppImage assets, and manage GitHub-specific operations.
"""

import re
from dataclasses import dataclass
from typing import Any, TypedDict, cast
from urllib.parse import urlparse

import aiohttp

from .auth import GitHubAuthManager, auth_manager
from .logger import get_logger
from .services.cache import get_cache_manager
from .services.progress import get_progress_service
from .utils import extract_and_validate_version

logger = get_logger(__name__)


class GitHubAsset(TypedDict):
    name: str
    size: int
    digest: str
    browser_download_url: str


class GitHubReleaseDetails(TypedDict):
    owner: str
    repo: str
    version: str
    prerelease: bool
    assets: list[GitHubAsset]
    original_tag_name: str


@dataclass(slots=True, frozen=True)
class ChecksumFileInfo:
    """Information about detected checksum file."""

    filename: str
    url: str
    format_type: str  # 'yaml' or 'traditional'


class GitHubReleaseFetcher:
    """Fetches GitHub release information and extracts AppImage assets."""

    # Common checksum file patterns to look for in GitHub releases
    CHECKSUM_FILE_PATTERNS = [
        r"latest-.*\.yml$",
        r"latest-.*\.yaml$",
        r".*checksums?\.txt$",
        r".*checksums?\.yml$",
        r".*checksums?\.yaml$",
        r".*checksums?\.md5$",
        r".*checksums?\.sha1$",
        r".*checksums?\.sha256$",
        r".*checksums?\.sha512$",
        r"SHA\d+SUMS?(\.txt)?$",
        r"MD5SUMS?(\.txt)?$",
        r".*\.sum$",
        r".*\.hash$",
        r".*\.digest$",
        r".*\.DIGEST$",
        r".*appimage\.sha256$",
        r".*appimage\.sha512$",
    ]

    def __init__(
        self,
        owner: str,
        repo: str,
        session: aiohttp.ClientSession,
        shared_api_task_id: str | None = None,
        use_cache: bool = True,
    ) -> None:
        """Initialize the GitHub release fetcher.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            session: aiohttp session for making requests
            shared_api_task_id: Optional shared API progress task ID for consolidated progress
            use_cache: Whether to use persistent caching (default: True)

        """
        self.owner: str = owner
        self.repo: str = repo
        self.auth_manager: GitHubAuthManager = auth_manager
        self.api_url: str = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        self.session = session
        self.progress_service = get_progress_service()
        self.shared_api_task_id = shared_api_task_id
        self.use_cache = use_cache
        self.cache_manager = get_cache_manager() if use_cache else None

    def set_shared_api_task(self, task_id: str | None) -> None:
        """Set the shared API progress task ID.

        Args:
            task_id: Shared API progress task ID or None to disable

        """
        self.shared_api_task_id = task_id

    async def _update_shared_progress(self, description: str) -> None:
        """Update shared API progress task with ultra-simple approach.

        Shows current API request count as 100% (1/1, 2/2, 3/3, etc.)
        No prediction, no complex estimation - just real-time request counting.

        Args:
            description: Description to show for the current API request

        """
        if not self.shared_api_task_id or not self.progress_service.is_active():
            return

        try:
            # Get current progress info
            task_info = self.progress_service.get_task_info(self.shared_api_task_id)
            if task_info:
                new_completed = int(task_info.completed) + 1

                # Ultra-simple: total always equals completed (always shows 100%)
                await self.progress_service.update_task_total(
                    self.shared_api_task_id, float(new_completed)
                )
                await self.progress_service.update_task(
                    self.shared_api_task_id,
                    completed=float(new_completed),
                    description=f"🌐 {description} ({new_completed}/{new_completed})",
                )

                # Force immediate display refresh
                if hasattr(self.progress_service, "_refresh_live_display"):
                    self.progress_service._refresh_live_display()
        except Exception:
            # Don't let progress updates crash the main operation
            pass

    def _normalize_version(self, tag_name: str) -> str:
        """Normalize version by extracting and sanitizing version string.

        Handles various formats including package@version and v-prefixed versions.

        Args:
            tag_name: Version tag that may have 'v' prefix or package format

        Returns:
            Sanitized version string

        """
        if not tag_name:
            return ""

        # Use the comprehensive version extraction and validation
        normalized = extract_and_validate_version(tag_name)

        # Fall back to original logic if extraction fails
        if normalized is None:
            return tag_name.lstrip("v")

        return normalized

    @staticmethod
    def detect_checksum_files(
        assets: list[GitHubAsset],
        tag_name: str,
    ) -> list[ChecksumFileInfo]:
        """Detect checksum files in GitHub release assets.

        Args:
            assets: List of GitHub release assets
            tag_name: Release tag name

        Returns:
            List of detected checksum files with their info

        """
        checksum_files = []

        for asset in assets:
            asset_name = asset["name"]

            # Check if asset matches any checksum file pattern
            for pattern in GitHubReleaseFetcher.CHECKSUM_FILE_PATTERNS:
                if re.search(pattern, asset_name, re.IGNORECASE):
                    url = asset["browser_download_url"]

                    # Determine format type
                    format_type = (
                        "yaml"
                        if asset_name.lower().endswith((".yml", ".yaml"))
                        else "traditional"
                    )

                    checksum_files.append(
                        ChecksumFileInfo(filename=asset_name, url=url, format_type=format_type)
                    )
                    break

        # Prioritize YAML files (like latest-linux.yml) first as they're often more reliable
        checksum_files.sort(key=lambda x: (x.format_type != "yaml", x.filename))

        return checksum_files

    async def fetch_latest_release(self, ignore_cache: bool = False) -> GitHubReleaseDetails:
        """Fetch the latest release information from GitHub API.

        Args:
            ignore_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            Release details including assets

        Raises:
            aiohttp.ClientError: If the API request fails

        """
        # Check cache first (unless bypassed)
        if self.use_cache and self.cache_manager and not ignore_cache:
            cached_data = await self.cache_manager.get_cached_release(self.owner, self.repo)
            if cached_data:
                logger.debug("Using cached data for %s/%s", self.owner, self.repo)
                return cached_data

        # Fetch from API
        try:
            headers = GitHubAuthManager.apply_auth({})

            async with self.session.get(url=self.api_url, headers=headers) as response:
                response.raise_for_status()

                # Update rate limit information
                self.auth_manager.update_rate_limit_info(dict(response.headers))

                data = await response.json()

                # Update shared progress if available
                if self.shared_api_task_id and self.progress_service.is_active():
                    await self._update_shared_progress("Fetched ")

                release_details = GitHubReleaseDetails(
                    owner=self.owner,
                    repo=self.repo,
                    version=self._normalize_version(data.get("tag_name", "")),
                    prerelease=data.get("prerelease", False),
                    assets=[
                        asset_obj
                        for asset in data.get("assets", [])
                        if (asset_obj := self.to_github_asset(asset)) is not None
                    ],
                    original_tag_name=data.get("tag_name", ""),
                )

                # Save to cache for future use
                if self.use_cache and self.cache_manager:
                    await self.cache_manager.save_release_data(
                        self.owner, self.repo, release_details
                    )
                    logger.debug("Cached release data for %s/%s", self.owner, self.repo)

                return release_details

        except Exception:
            # Update shared progress with error if available
            if self.shared_api_task_id and self.progress_service.is_active():
                await self._update_shared_progress(
                    f"Failed to fetch release for {self.owner}/{self.repo}"
                )
            raise

    async def fetch_specific_release(self, tag: str) -> GitHubReleaseDetails:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release details for the specified tag

        """
        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
            headers = GitHubAuthManager.apply_auth({})

            async with self.session.get(url=url, headers=headers) as response:
                response.raise_for_status()

                # Update rate limit information
                self.auth_manager.update_rate_limit_info(dict(response.headers))

                data = await response.json()

                # Update shared progress if available
                if self.shared_api_task_id and self.progress_service.is_active():
                    await self._update_shared_progress(
                        f"Fetched release {tag} for {self.owner}/{self.repo}"
                    )

                return GitHubReleaseDetails(
                    owner=self.owner,
                    repo=self.repo,
                    version=self._normalize_version(data.get("tag_name", "")),
                    prerelease=data.get("prerelease", False),
                    assets=[
                        asset_obj
                        for asset in data.get("assets", [])
                        if (asset_obj := self.to_github_asset(asset)) is not None
                    ],
                    original_tag_name=data.get("tag_name", ""),
                )

        except Exception:
            # Update shared progress with error if available
            if self.shared_api_task_id and self.progress_service.is_active():
                await self._update_shared_progress(
                    f"Failed to fetch release {tag} for {self.owner}/{self.repo}"
                )
            raise

    async def fetch_latest_prerelease(self, ignore_cache: bool = False) -> GitHubReleaseDetails:
        """Fetch the latest prerelease from GitHub API.

        This method is useful for apps like FreeTube that only provide prereleases.
        It fetches all releases and returns the most recent prerelease.

        Args:
            ignore_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            Release details for the latest prerelease

        Raises:
            aiohttp.ClientError: If the API request fails
            ValueError: If no prerelease is found

        """
        # Check cache first (unless bypassed)
        if self.cache_manager and not ignore_cache:
            cached_data = await self.cache_manager.get_cached_release(
                self.owner, self.repo, cache_type="prerelease"
            )
            if cached_data:
                logger.debug("Using cached prerelease data for %s/%s", self.owner, self.repo)
                # Convert cached data back to GitHubReleaseDetails
                return GitHubReleaseDetails(
                    owner=cached_data["owner"],
                    repo=cached_data["repo"],
                    version=cached_data["version"],
                    prerelease=cached_data["prerelease"],
                    assets=cached_data["assets"],
                    original_tag_name=cached_data["original_tag_name"],
                )

        try:
            url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
            headers = GitHubAuthManager.apply_auth({})

            async with self.session.get(url=url, headers=headers) as response:
                response.raise_for_status()

                # Update rate limit information
                self.auth_manager.update_rate_limit_info(dict(response.headers))

                data = await response.json()

                # Update shared progress if available
                if self.shared_api_task_id and self.progress_service.is_active():
                    await self._update_shared_progress(
                        f"Fetched prereleases for {self.owner}/{self.repo}"
                    )

                # Filter for prereleases only
                prereleases = [release for release in data if release.get("prerelease", False)]

                if not prereleases:
                    raise ValueError(f"No prereleases found for {self.owner}/{self.repo}")

                # The releases are already sorted by published date (newest first)
                latest_prerelease = prereleases[0]

                release_details = GitHubReleaseDetails(
                    owner=self.owner,
                    repo=self.repo,
                    version=self._normalize_version(latest_prerelease.get("tag_name", "")),
                    prerelease=latest_prerelease.get("prerelease", False),
                    assets=[
                        asset_obj
                        for asset in latest_prerelease.get("assets", [])
                        if (asset_obj := self.to_github_asset(asset)) is not None
                    ],
                    original_tag_name=latest_prerelease.get("tag_name", ""),
                )

                # Cache the prerelease data
                if self.cache_manager:
                    await self.cache_manager.save_release_data(
                        self.owner, self.repo, dict(release_details), cache_type="prerelease"
                    )
                    logger.debug("Cached prerelease data for %s/%s", self.owner, self.repo)

                return release_details

        except Exception:
            # Update shared progress with error if available
            if self.shared_api_task_id and self.progress_service.is_active():
                await self._update_shared_progress(
                    f"Failed to fetch prereleases for {self.owner}/{self.repo}"
                )
            raise

    async def fetch_latest_release_or_prerelease(
        self, prefer_prerelease: bool = False, ignore_cache: bool = False
    ) -> GitHubReleaseDetails:
        """Fetch the latest release or prerelease based on preference.

        This method provides flexibility for apps that may have both stable releases
        and prereleases, or apps that only provide one type.

        Args:
            prefer_prerelease: If True, prefer prereleases over stable releases.
                              If False, prefer stable releases over prereleases.
            ignore_cache: If True, bypass cache and fetch fresh data from API

        Returns:
            Release details for the best matching release

        Raises:
            aiohttp.ClientError: If the API request fails
            ValueError: If no releases are found

        """
        # Try to use cached data first based on preference
        if prefer_prerelease:
            # First try prerelease cache, then stable cache as fallback
            try:
                return await self.fetch_latest_prerelease(ignore_cache=ignore_cache)
            except (ValueError, aiohttp.ClientResponseError):
                # No prereleases found, try stable release
                return await self.fetch_latest_release(ignore_cache=ignore_cache)
        else:
            # First try stable cache, then prerelease cache as fallback
            try:
                return await self.fetch_latest_release(ignore_cache=ignore_cache)
            except (ValueError, aiohttp.ClientResponseError):
                # No stable releases found, try prereleases
                return await self.fetch_latest_prerelease(ignore_cache=ignore_cache)

    def to_github_asset(self, asset: dict[str, Any]) -> GitHubAsset | None:
        """Convert GitHub API asset response to typed GitHubAsset.

        Args:
            asset: Raw asset data from GitHub API

        Returns:
            Typed GitHubAsset or None if conversion fails

        """
        try:
            name = asset.get("name", "")
            size = asset.get("size", 0)
            download_url = asset.get("browser_download_url", "")

            # GitHub API doesn't always provide digest, use empty string as default
            digest = asset.get("digest", "")

            if not name or not download_url:
                return None

            return GitHubAsset(
                name=cast(str, name),
                digest=cast(str, digest),
                size=cast(int, size),
                browser_download_url=cast(str, download_url),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def extract_appimage_asset(self, release_data: GitHubReleaseDetails) -> GitHubAsset | None:
        """Extract the first AppImage asset from release data.

        Args:
            release_data: Release details containing assets

        Returns:
            First AppImage asset found or None

        """
        for asset in release_data["assets"]:
            if asset["name"].endswith(".AppImage") or asset["name"].endswith(".appimage"):
                return asset
        return None

    def extract_appimage_assets(self, release_data: GitHubReleaseDetails) -> list[GitHubAsset]:
        """Extract all AppImage assets from release data.

        Args:
            release_data: Release details containing assets

        Returns:
            List of all AppImage assets found

        """
        return [
            asset
            for asset in release_data["assets"]
            if asset["name"].endswith(".AppImage") or asset["name"].endswith(".appimage")
        ]

    def select_best_appimage(
        self,
        release_data: GitHubReleaseDetails,
        preferred_suffixes: list[str] | None = None,
        installation_source: str = "catalog",
    ) -> GitHubAsset | None:
        """Select the best AppImage based on architecture, preferences, and installation source.

        This method prioritizes amd64/x86_64 architecture since that's what most users need.
        It automatically filters out ARM architectures (arm64, aarch64, armhf, etc.) to
        avoid complexity and focus on the most common use case.

        Selection strategy for catalog installs:
        1. Filter by preferred_suffixes if provided
        2. Filter out ARM architectures (arm64, aarch64, armhf, armv7, armv6)
        3. Among remaining candidates, prefer explicit x86_64/amd64 markers
        4. Fall back to first remaining candidate

        Selection strategy for URL installs:
        1. Filter out unstable versions (experimental, beta, alpha, etc.)
        2. Filter out ARM architectures (arm64, aarch64, armhf, armv7, armv6)
        3. Return first remaining stable candidate

        Args:
            release_data: Release details containing assets
            preferred_suffixes: List of preferred filename suffixes (e.g., ["x86_64", "linux"])
            installation_source: Installation source ("catalog" or "url")

        Returns:
            Best matching AppImage asset or None

        """
        appimages = self.extract_appimage_assets(release_data)

        if not appimages:
            return None

        if len(appimages) == 1:
            return appimages[0]

        # Apply different strategies based on installation source
        if installation_source == "url":
            # For URL installs: filter out unstable versions first
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
            stable_candidates = []
            for appimage in appimages:
                name_lower = appimage["name"].lower()
                if not any(keyword in name_lower for keyword in unstable_keywords):
                    stable_candidates.append(appimage)

            candidates = stable_candidates if stable_candidates else appimages
        else:
            # For catalog installs: use preferred_suffixes matching
            matched_appimages = []
            if preferred_suffixes:
                for suffix in preferred_suffixes:
                    for appimage in appimages:
                        if suffix.lower() in appimage["name"].lower():
                            matched_appimages.append(appimage)

            candidates = matched_appimages if matched_appimages else appimages

        # Filter out ARM architectures to prefer amd64 (most common)
        arm_keywords = ["arm64", "aarch64", "armhf", "armv7", "armv6"]
        amd64_candidates = []
        for appimage in candidates:
            name_lower = appimage["name"].lower()
            if not any(arm_keyword in name_lower for arm_keyword in arm_keywords):
                amd64_candidates.append(appimage)

        # If we have amd64 candidates, use those
        if amd64_candidates:
            candidates = amd64_candidates

        # For catalog installs, prefer explicit x86_64/amd64 markers
        if installation_source == "catalog":
            for appimage in candidates:
                name_lower = appimage["name"].lower()
                if "x86_64" in name_lower or "amd64" in name_lower:
                    return appimage

        # Fallback: return first candidate
        return candidates[0]

    async def check_rate_limit(self) -> dict[str, Any]:
        """Check current rate limit status.

        Returns:
            Rate limit information from GitHub API

        """
        url = "https://api.github.com/rate_limit"
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            response.raise_for_status()
            data = await response.json()
            return data

    @staticmethod
    def parse_repo_url(repo_url: str) -> tuple[str, str]:
        """Parse GitHub repository URL to extract owner and repo.

        Args:
            repo_url: GitHub repository URL or owner/repo format

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If URL format is invalid

        """
        # Handle owner/repo format
        if "/" in repo_url and not repo_url.startswith("http"):
            parts = repo_url.split("/")
            if len(parts) == 2:
                return parts[0], parts[1]

        # Handle full GitHub URLs
        if repo_url.startswith("http"):
            parsed = urlparse(repo_url)
            if parsed.hostname == "github.com":
                path_parts = parsed.path.strip("/").split("/")
                if len(path_parts) >= 2:
                    return path_parts[0], path_parts[1]

        raise ValueError(f"Invalid GitHub repository format: {repo_url}")

    async def get_default_branch(self) -> str:
        """Get the default branch name for the repository.

        Returns:
            Default branch name (e.g., 'main', 'master')

        Raises:
            aiohttp.ClientError: If the API request fails

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            response.raise_for_status()

            # Update rate limit information
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            data = await response.json()

            # Update shared progress if available
            if self.shared_api_task_id and self.progress_service.is_active():
                await self._update_shared_progress(
                    f"Fetched default branch for {self.owner}/{self.repo}"
                )

            return data.get("default_branch", "main")

    def build_icon_url(self, icon_path: str, branch: str | None = None) -> str:
        """Build GitHub raw URL for an icon file.

        Args:
            icon_path: Path to the icon file within the repository
            branch: Branch name (if None, will need to be fetched)

        Returns:
            Full GitHub raw URL for the icon

        """
        if branch is None:
            branch = "main"  # Default fallback

        # Clean the path - remove leading slash if present
        clean_path = icon_path.lstrip("/")

        return (
            f"https://raw.githubusercontent.com/{self.owner}/{self.repo}/{branch}/{clean_path}"
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
        # If path has a filename with extension, use it but rename to app_name
        import os

        filename = os.path.basename(icon_path)
        if "." in filename:
            extension = os.path.splitext(filename)[1]
            return f"{app_name}{extension}"
        else:
            # Default to .png if no extension detected
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

    async def get_latest_release(self, owner: str, repo: str) -> dict[str, Any] | None:
        """Get the latest release for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release data dictionary or None if not found

        """
        try:
            fetcher = GitHubReleaseFetcher(owner, repo, self.session, self.shared_api_task_id)
            release_details = await fetcher.fetch_latest_release_or_prerelease(
                prefer_prerelease=False
            )

            # Use original tag name from the release details, fallback to version-based tag
            original_tag_name = (
                release_details.get("original_tag_name") or f"v{release_details['version']}"
            )

            return {
                "tag_name": release_details["version"],
                "original_tag_name": original_tag_name,
                "prerelease": release_details["prerelease"],
                "assets": release_details["assets"],
                "html_url": f"https://github.com/{owner}/{repo}/releases/tag/{original_tag_name}",
            }

        except Exception as e:
            logger.error("Failed to fetch latest release for %s/%s: %s", owner, repo, e)
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
            fetcher = GitHubReleaseFetcher(owner, repo, self.session, self.shared_api_task_id)
            release_details = await fetcher.fetch_specific_release(tag)

            return {
                "tag_name": release_details["version"],
                "original_tag_name": tag,
                "prerelease": release_details["prerelease"],
                "assets": release_details["assets"],
                "html_url": f"https://github.com/{owner}/{repo}/releases/tag/{tag}",
            }
        except Exception:
            return None
