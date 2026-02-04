"""GitHub domain models for releases and assets.

This module contains data classes representing GitHub releases and assets.
"""

import re
from dataclasses import dataclass, replace
from typing import Any

from my_unicorn.core.github.version_utils import extract_and_validate_version
from my_unicorn.logger import get_logger
from my_unicorn.utils.asset_validation import (
    SPECIFIC_CHECKSUM_EXTENSIONS,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
)

logger = get_logger(__name__)

# Constants
UNSTABLE_VERSION_KEYWORDS = (
    "experimental",
    "beta",
    "alpha",
    "rc",
    "pre",
    "dev",
    "test",
    "nightly",
)


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
        return is_appimage_file(self.name)


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
        appimages = release.get_appimages()

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
            candidates = [
                app
                for suffix in preferred_suffixes
                for app in appimages
                if suffix.lower() in app.name.lower()
            ]
            if not candidates:
                candidates = appimages
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
        stable = [
            app
            for app in appimages
            if not any(
                kw in app.name.lower() for kw in UNSTABLE_VERSION_KEYWORDS
            )
        ]
        return stable if stable else appimages

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
        assets: list[Asset],
        tag_name: str,  # noqa: ARG004
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
        """Check if checksum file is platform-compatible.

        Handles two types of checksum files:
        1. AppImage-specific: "app.AppImage.sha256sum" - requires valid base
        2. Standalone: "SHA256SUMS.txt", "latest-linux.yml" - needs platform
           compatibility

        Examples:
            ✅ "QOwnNotes-x86_64.AppImage.sha256sum" (AppImage-specific)
            ✅ "KeePassXC-2.7.10-x86_64.AppImage.DIGEST" (AppImage-specific)
            ✅ "Joplin-3.4.12.AppImage.sha512" (AppImage-specific)
            ✅ "SHA256SUMS.txt" (standalone)
            ✅ "latest-linux.yml" (standalone)
            ✅ "SHA256SUMS" (standalone)
            ❌ "KeePassXC-2.7.10-Win64.msi.DIGEST" (Windows)
            ❌ "Obsidian-1.9.14-arm64.AppImage.sha256" (ARM)
            ❌ "latest-mac-arm64.yml" (macOS)

        Args:
            filename: Checksum filename to check

        Returns:
            True if checksum is platform-compatible, False otherwise

        """
        if not filename:
            return False

        # Must be a checksum file
        if not is_checksum_file(filename):
            return False

        # First check if file itself is platform-compatible
        if not AssetSelector.is_platform_compatible(filename):
            return False

        return AssetSelector._validate_checksum_type(filename)

    @staticmethod
    def _validate_checksum_type(filename: str) -> bool:
        """Validate checksum type (AppImage-specific vs standalone).

        Args:
            filename: Checksum filename to validate

        Returns:
            True if valid checksum type, False otherwise

        """
        filename_lower = filename.lower()

        # Check if this is an AppImage-specific checksum file
        # These have format: <appimage_name>.<checksum_ext>
        base_name = filename
        is_appimage_specific = False

        # Check specific checksum extensions (these require AppImage base)
        for ext in SPECIFIC_CHECKSUM_EXTENSIONS:
            if filename_lower.endswith(ext):
                base_name = filename[: -len(ext)]
                is_appimage_specific = True
                break

        # Also handle pattern-based checksums (e.g., .sha256, .sha512)
        if not is_appimage_specific:
            checksum_suffixes = [
                ".sha256",
                ".sha512",
                ".sha1",
                ".md5",
            ]
            for suffix in checksum_suffixes:
                if filename_lower.endswith(suffix):
                    base_name = filename[: -len(suffix)]
                    # Only consider AppImage-specific if base ends with
                    # .AppImage
                    if is_appimage_file(base_name):
                        is_appimage_specific = True
                    break

        # For AppImage-specific checksums, validate the base AppImage
        if is_appimage_specific:
            if not is_appimage_file(base_name):
                return False
            # Base must be platform-compatible (not Windows, macOS, ARM)
            return AssetSelector.is_platform_compatible(base_name)

        # For standalone checksum files (like SHA256SUMS.txt, latest-linux.yml)
        # we already validated platform compatibility above, so accept them
        return True

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
