"""GitHub API client for fetching release information and assets.

This module handles communication with the GitHub API to fetch release
information, extract AppImage assets, and manage GitHub-specific operations.
"""

from typing import Any, TypedDict, cast
from urllib.parse import urlparse

import aiohttp

from .auth import GitHubAuthManager, auth_manager


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


class GitHubReleaseFetcher:
    """Fetches GitHub release information and extracts AppImage assets."""

    def __init__(self, owner: str, repo: str, session: aiohttp.ClientSession) -> None:
        """Initialize the GitHub release fetcher.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            session: aiohttp session for making requests

        """
        self.owner: str = owner
        self.repo: str = repo
        self.auth_manager: GitHubAuthManager = auth_manager
        self.api_url: str = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
        self.session = session

    def _normalize_version(self, tag_name: str) -> str:
        """Normalize version by stripping 'v' prefix.

        Args:
            tag_name: Version tag that may have 'v' prefix

        Returns:
            Version string without 'v' prefix

        """
        return tag_name.lstrip("v") if tag_name else ""

    async def fetch_latest_release(self) -> GitHubReleaseDetails:
        """Fetch the latest release information from GitHub API.

        Returns:
            Release details including assets

        Raises:
            aiohttp.ClientError: If the API request fails

        """
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=self.api_url, headers=headers) as response:
            response.raise_for_status()

            # Update rate limit information
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            data = await response.json()

            return GitHubReleaseDetails(
                owner=self.owner,
                repo=self.repo,
                version=self._normalize_version(data.get("tag_name", "")),
                prerelease=data.get("prerelease", False),
                assets=[
                    self.to_github_asset(asset)
                    for asset in data.get("assets", [])
                    if self.to_github_asset(asset) is not None
                ],
            )

    async def fetch_specific_release(self, tag: str) -> GitHubReleaseDetails:
        """Fetch a specific release by tag.

        Args:
            tag: Release tag to fetch

        Returns:
            Release details for the specified tag

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases/tags/{tag}"
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            response.raise_for_status()

            # Update rate limit information
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            data = await response.json()

            return GitHubReleaseDetails(
                owner=self.owner,
                repo=self.repo,
                version=self._normalize_version(data.get("tag_name", "")),
                prerelease=data.get("prerelease", False),
                assets=[
                    self.to_github_asset(asset)
                    for asset in data.get("assets", [])
                    if self.to_github_asset(asset) is not None
                ],
            )

    async def fetch_latest_prerelease(self) -> GitHubReleaseDetails:
        """Fetch the latest prerelease from GitHub API.

        This method is useful for apps like FreeTube that only provide prereleases.
        It fetches all releases and returns the most recent prerelease.

        Returns:
            Release details for the latest prerelease

        Raises:
            aiohttp.ClientError: If the API request fails
            ValueError: If no prerelease is found

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            response.raise_for_status()

            # Update rate limit information
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            data = await response.json()

            # Filter for prereleases only
            prereleases = [release for release in data if release.get("prerelease", False)]

            if not prereleases:
                raise ValueError(f"No prereleases found for {self.owner}/{self.repo}")

            # The releases are already sorted by published date (newest first)
            latest_prerelease = prereleases[0]

            return GitHubReleaseDetails(
                owner=self.owner,
                repo=self.repo,
                version=self._normalize_version(latest_prerelease.get("tag_name", "")),
                prerelease=latest_prerelease.get("prerelease", False),
                assets=[
                    self.to_github_asset(asset)
                    for asset in latest_prerelease.get("assets", [])
                    if self.to_github_asset(asset) is not None
                ],
            )

    async def fetch_latest_release_or_prerelease(
        self, prefer_prerelease: bool = False
    ) -> GitHubReleaseDetails:
        """Fetch the latest release or prerelease based on preference.

        This method provides flexibility for apps that may have both stable releases
        and prereleases, or apps that only provide one type.

        Args:
            prefer_prerelease: If True, prefer prereleases over stable releases.
                              If False, prefer stable releases over prereleases.

        Returns:
            Release details for the best matching release

        Raises:
            aiohttp.ClientError: If the API request fails
            ValueError: If no releases are found

        """
        url = f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        headers = GitHubAuthManager.apply_auth({})

        async with self.session.get(url=url, headers=headers) as response:
            response.raise_for_status()

            # Update rate limit information
            self.auth_manager.update_rate_limit_info(dict(response.headers))

            data = await response.json()

            if not data:
                raise ValueError(f"No releases found for {self.owner}/{self.repo}")

            # Separate stable releases and prereleases
            stable_releases = [
                release for release in data if not release.get("prerelease", False)
            ]
            prereleases = [release for release in data if release.get("prerelease", False)]

            # Choose based on preference and availability
            if prefer_prerelease:
                # Prefer prereleases, fallback to stable if no prereleases
                chosen_release = (
                    prereleases[0]
                    if prereleases
                    else (stable_releases[0] if stable_releases else None)
                )
            else:
                # Prefer stable releases, fallback to prereleases if no stable releases
                chosen_release = (
                    stable_releases[0]
                    if stable_releases
                    else (prereleases[0] if prereleases else None)
                )

            if not chosen_release:
                raise ValueError(f"No suitable releases found for {self.owner}/{self.repo}")

            return GitHubReleaseDetails(
                owner=self.owner,
                repo=self.repo,
                version=self._normalize_version(chosen_release.get("tag_name", "")),
                prerelease=chosen_release.get("prerelease", False),
                assets=[
                    self.to_github_asset(asset)
                    for asset in chosen_release.get("assets", [])
                    if self.to_github_asset(asset) is not None
                ],
            )

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
            if asset["name"].endswith(".AppImage"):
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
            asset for asset in release_data["assets"] if asset["name"].endswith(".AppImage")
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
            return await response.json()

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
    """Simplified GitHub API client for catalog-based installations."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize GitHub client.

        Args:
            session: aiohttp session for making requests

        """
        self.session = session

    async def get_latest_release(self, owner: str, repo: str) -> dict[str, Any] | None:
        """Get the latest release for a repository.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release data dictionary or None if not found

        """
        try:
            fetcher = GitHubReleaseFetcher(owner, repo, self.session)
            release_details = await fetcher.fetch_latest_release()

            # Convert to dictionary format expected by catalog strategy
            return {
                "tag_name": release_details["version"],
                "prerelease": release_details["prerelease"],
                "assets": release_details["assets"],
                "html_url": f"https://github.com/{owner}/{repo}/releases/tag/v{release_details['version']}",
            }
        except Exception:
            return None

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
            fetcher = GitHubReleaseFetcher(owner, repo, self.session)
            release_details = await fetcher.fetch_specific_release(tag)

            # Convert to dictionary format expected by catalog strategy
            return {
                "tag_name": release_details["version"],
                "prerelease": release_details["prerelease"],
                "assets": release_details["assets"],
                "html_url": f"https://github.com/{owner}/{repo}/releases/tag/{tag}",
            }
        except Exception:
            return None
