"""GitHub API client for fetching release information and assets.

This module handles communication with the GitHub API to fetch release
information, extract AppImage assets, and manage GitHub-specific operations.

Refactored to use dataclasses and improved separation of concerns.
"""

import asyncio
import os
import re
from dataclasses import dataclass, replace
from typing import Any

import aiohttp

from my_unicorn.config import config_manager

from .auth import GitHubAuthManager, auth_manager
from .cache import get_cache_manager
from .logger import get_logger
from .progress import get_progress_service
from .utils import (
    SPECIFIC_CHECKSUM_EXTENSIONS,
    extract_and_validate_version,
    get_checksum_file_format_type,
    is_appimage_file,
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

    def filter_for_platform(self) -> "Release":
        """Return new Release with only platform-relevant assets.

        Filters assets to include only:
        - Linux x86_64 AppImages (excludes Windows, macOS, ARM)
        - Checksum files for compatible AppImages

        This method uses AssetSelector.filter_for_cache() for consistent
        filtering across the application.

        Returns:
            New Release instance with filtered assets

        """
        filtered_assets = AssetSelector.filter_for_cache(self.assets)
        return replace(self, assets=filtered_assets)


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

        Note: This method assumes the release has already been filtered
        by filter_for_platform() which removes ARM/Windows/macOS assets.
        Additional filtering here focuses on selecting the best variant
        when multiple compatible AppImages exist.

        Selection strategy for catalog installs:
        1. Filter by preferred_suffixes if provided
        2. Prefer explicit x86_64/amd64 markers
        3. Fall back to first remaining candidate

        Selection strategy for URL installs:
        1. Filter out unstable versions (beta, alpha, etc.)
        2. Prefer explicit x86_64/amd64 markers
        3. Return first remaining stable candidate

        Args:
            release: Release to select from (should be pre-filtered)
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
        if installation_source == "url":
            # For URL installs, filter out unstable versions
            candidates = AssetSelector._filter_unstable_versions(appimages)
        elif preferred_suffixes:
            # For catalog installs with suffixes, filter by them
            candidates = AssetSelector._filter_by_preferred_suffixes(
                appimages, preferred_suffixes
            )
        else:
            candidates = appimages

        # Prefer explicit x86_64/amd64 markers when available
        explicit_match = AssetSelector._find_explicit_amd64(candidates)
        if explicit_match:
            return explicit_match

        # Fallback: return first candidate
        return candidates[0] if candidates else appimages[0]

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

    @staticmethod
    def is_platform_compatible(filename: str) -> bool:
        """Check if file is compatible with Linux x86_64 platform.

        Excludes:
        - Windows files (.msi, .exe, Win64, Windows patterns)
        - macOS files (.dmg, .pkg, mac/darwin patterns)
        - ARM architectures (arm64, aarch64, armv7l, armhf, armv6)
        - Source archives (tar.gz, tar.xz with -src- pattern)
        - Experimental builds

        Args:
            filename: Filename to check

        Returns:
            True if file is compatible with Linux x86_64, False otherwise

        """
        if not filename:
            return False

        filename_lower = filename.lower()

        # Check all incompatible patterns
        incompatible_patterns = [
            # Windows patterns
            r"(?i)win(32|64)",
            r"(?i)windows",
            r"(?i)legacy.*win",
            r"(?i)portable.*win",
            # macOS patterns (but not "macro")
            r"(?i)mac(?!ro)",
            r"(?i)darwin",
            r"(?i)osx",
            r"(?i)apple",
            # macOS-specific YAML files
            r"(?i)latest.*mac.*\.ya?ml$",
            r"(?i)mac.*latest.*\.ya?ml$",
            # ARM architecture patterns
            r"(?i)arm64",
            r"(?i)aarch64",
            r"(?i)armv7l?",
            r"(?i)armhf",
            r"(?i)armv6",
            # Source archive patterns
            r"(?i)[-_.]src[-_.]",
            r"(?i)[-_.]source[-_.]",
            # Experimental/unstable patterns
            r"(?i)experimental",
            r"(?i)qt6.*experimental",
        ]

        # Check if any pattern matches
        for pattern in incompatible_patterns:
            if re.search(pattern, filename):
                return False

        # Check incompatible extensions
        incompatible_exts = (".msi", ".exe", ".dmg", ".pkg")
        return not filename_lower.endswith(incompatible_exts)

    @staticmethod
    def is_relevant_checksum(filename: str) -> bool:
        """Check if checksum file is for a platform-compatible AppImage.

        Examples:
            ✅ "QOwnNotes-x86_64.AppImage.sha256sum"
            ✅ "KeePassXC-2.7.10-x86_64.AppImage.DIGEST"
            ✅ "Joplin-3.4.12.AppImage.sha512"
            ❌ "KeePassXC-2.7.10-Win64.msi.DIGEST" (Windows)
            ❌ "Obsidian-1.9.14-arm64.AppImage.sha256" (ARM)
            ❌ "latest-mac-arm64.yml" (macOS)

        Args:
            filename: Checksum filename to check

        Returns:
            True if checksum is for a compatible AppImage, False otherwise

        """
        if not filename:
            return False

        # Must be a checksum file
        if not is_checksum_file(filename):
            return False

        filename_lower = filename.lower()

        # Extract base filename (remove checksum extension)
        base_name = filename
        for ext in SPECIFIC_CHECKSUM_EXTENSIONS:
            if filename_lower.endswith(ext):
                base_name = filename[: -len(ext)]
                break

        # Also handle pattern-based checksums (e.g., .sha256, .sha512)
        if base_name == filename:
            # Try removing common checksum suffixes
            checksum_suffixes = [
                ".sha256",
                ".sha512",
                ".sha1",
                ".md5",
            ]
            for suffix in checksum_suffixes:
                if filename_lower.endswith(suffix):
                    base_name = filename[: -len(suffix)]
                    break

        # Base must be an AppImage
        if not is_appimage_file(base_name):
            return False

        # Base must be platform-compatible (not Windows, macOS, ARM)
        return AssetSelector.is_platform_compatible(base_name)

    @staticmethod
    def filter_for_cache(assets: list[Asset]) -> list[Asset]:
        """Filter assets to cache-worthy subset (x86_64 AppImages + checksums).

        This is the main entry point for cache filtering. It keeps only:
        - Linux x86_64 AppImages (excludes Windows, macOS, ARM builds)
        - Checksum files for compatible AppImages

        This method should be called before caching release data to avoid
        storing irrelevant assets.

        Args:
            assets: List of all release assets

        Returns:
            Filtered list of platform-compatible assets

        """
        filtered = []

        for asset in assets:
            filename = asset.name

            # Keep platform-compatible AppImages
            if is_appimage_file(filename):
                if AssetSelector.is_platform_compatible(filename):
                    filtered.append(asset)
                    logger.debug(
                        "Including platform-compatible AppImage: %s", filename
                    )
                else:
                    logger.debug(
                        "Filtering out non-compatible AppImage: %s", filename
                    )
                continue

            # Keep relevant checksum files
            if AssetSelector.is_relevant_checksum(filename):
                filtered.append(asset)
                logger.debug("Including relevant checksum file: %s", filename)
            else:
                logger.debug("Filtering out asset: %s", filename)

        return filtered


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
        headers = GitHubAuthManager.apply_auth({})

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

        # Allow AttributeError for non-dict responses (tests expect this)
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
                # release is a dict from the filtered list; cast for the call
                return Release.from_api_response(
                    self.owner,
                    self.repo,
                    __import__("typing").cast(dict, release),
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

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected API response type for release by tag %s: %s",
                tag,
                type(data),
            )
            return None

        # data should be a dict here; pass through to constructor
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

        if not isinstance(data, dict):
            logger.warning(
                "Unexpected API response for default branch: %s", type(data)
            )
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
                # Update shared progress even for cache hits
                if (
                    self.shared_api_task_id
                    and self.progress_service
                    and self.progress_service.is_active()
                ):
                    await self.api_client._update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        release = await self.api_client.fetch_stable_release()
        if release is None:
            raise ValueError(
                f"No stable release found for {self.owner}/{self.repo}"
            )

        # Filter for platform compatibility before caching
        release = release.filter_for_platform()
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
                # Update shared progress even for cache hits
                if (
                    self.shared_api_task_id
                    and self.progress_service
                    and self.progress_service.is_active()
                ):
                    await self.api_client._update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        release = await self.api_client.fetch_prerelease()
        if release is None:
            raise ValueError(
                f"No prerelease found for {self.owner}/{self.repo}"
            )

        # Filter for platform compatibility before caching
        release = release.filter_for_platform()
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
                # Update shared progress for cached prerelease
                if (
                    self.shared_api_task_id
                    and self.progress_service
                    and self.progress_service.is_active()
                ):
                    await self.api_client._update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        release = await self.api_client.fetch_prerelease()
        if release:
            # Filter for platform compatibility before caching
            release = release.filter_for_platform()
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
                # Update shared progress for cached prerelease
                if (
                    self.shared_api_task_id
                    and self.progress_service
                    and self.progress_service.is_active()
                ):
                    await self.api_client._update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        release = await self.api_client.fetch_prerelease()
        if release:
            # Filter for platform compatibility before caching
            release = release.filter_for_platform()
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
                # Update shared progress for cached stable release
                if (
                    self.shared_api_task_id
                    and self.progress_service
                    and self.progress_service.is_active()
                ):
                    await self.api_client._update_shared_progress(
                        f"Retrieved {self.owner}/{self.repo} (cached)"
                    )
                return cached

        release = await self.api_client.fetch_stable_release()
        if release:
            # Filter for platform compatibility before caching
            release = release.filter_for_platform()
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
