"""Asset selection logic for GitHub releases."""

import re

from my_unicorn.core.github.models.asset import Asset
from my_unicorn.core.github.models.checksum import ChecksumFileInfo
from my_unicorn.core.github.models.constants import UNSTABLE_VERSION_KEYWORDS
from my_unicorn.core.github.models.release import Release
from my_unicorn.logger import get_logger
from my_unicorn.utils.asset_validation import (
    SPECIFIC_CHECKSUM_EXTENSIONS,
    get_checksum_file_format_type,
    is_appimage_file,
    is_checksum_file,
)

logger = get_logger(__name__)


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
        tag_name: str,
    ) -> list[ChecksumFileInfo]:
        """Detect checksum files in release assets.

        Filters to x86_64 Linux compatible checksum files only.
        Excludes ARM, macOS, and Windows checksums.

        Platform Exclusions:
            - ARM: latest-linux-arm.yml, *-arm64.AppImage.sha256
            - macOS: latest-mac.yml, *.dmg.DIGEST
            - Windows: latest-windows.yml, *.exe.sha256

        Args:
            assets: List of release assets
            tag_name: Release tag name

        Returns:
            List of detected checksum files (x86_64 Linux only)

        """
        checksum_files = []
        filtered_count = 0

        for asset in assets:
            if is_checksum_file(asset.name):
                # Apply platform compatibility filtering
                if AssetSelector.is_relevant_checksum(asset.name):
                    format_type = get_checksum_file_format_type(asset.name)
                    checksum_files.append(
                        ChecksumFileInfo(
                            filename=asset.name,
                            url=asset.browser_download_url,
                            format_type=format_type,
                        )
                    )
                else:
                    filtered_count += 1

        if filtered_count > 0:
            logger.debug(
                "Filtered %d non-x86_64 checksum files from %s",
                filtered_count,
                tag_name,
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
            # ARM-specific YAML files (e.g., latest-linux-arm.yml)
            r"(?i)latest.*arm.*\.ya?ml$",
            r"(?i)arm.*latest.*\.ya?ml$",
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
            ❌ "latest-linux-arm.yml" (ARM)
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
