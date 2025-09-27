"""Detection and prioritization strategies for verification."""

from __future__ import annotations

from typing import Any

from my_unicorn.github_client import ChecksumFileInfo, GitHubAsset, GitHubReleaseFetcher
from my_unicorn.logger import get_logger

logger = get_logger(__name__, enable_file_logging=True)


class VerificationDetectionService:
    """Service for detecting available verification methods."""

    def detect_available_methods(
        self,
        asset: dict[str, Any],
        config: dict[str, Any],
        assets: list[dict[str, Any]] | None = None,
        owner: str | None = None,
        repo: str | None = None,
        tag_name: str | None = None,
    ) -> tuple[bool, list[ChecksumFileInfo]]:
        """Detect available verification methods.

        Args:
            asset: GitHub asset information
            config: Verification configuration
            assets: All GitHub release assets (optional)
            owner: Repository owner (optional)
            repo: Repository name (optional)
            tag_name: Release tag name (optional)

        Returns:
            Tuple of (has_digest, checksum_files_list)

        """
        digest_value = asset.get("digest", "")
        has_digest = bool(digest_value and digest_value.strip())
        digest_requested = config.get("digest", False)

        # Log digest availability vs configuration
        if digest_requested and not has_digest:
            logger.warning(
                "⚠️  Digest verification requested but no digest available from GitHub API"
            )
            logger.debug("   📦 Asset digest field: '%s'", digest_value or "None")
        elif has_digest:
            logger.debug("✅ Digest available for verification: %s", digest_value[:16] + "...")

        # Check for manually configured checksum file
        manual_checksum_file = config.get("checksum_file")
        checksum_files = []

        if manual_checksum_file and manual_checksum_file.strip():
            # Use manually configured checksum file
            if owner and repo and tag_name:
                url = self._build_checksum_url(owner, repo, tag_name, manual_checksum_file)
                format_type = (
                    "yaml"
                    if manual_checksum_file.lower().endswith((".yml", ".yaml"))
                    else "traditional"
                )
                checksum_files.append(
                    ChecksumFileInfo(
                        filename=manual_checksum_file, url=url, format_type=format_type
                    )
                )
        elif assets and owner and repo and tag_name and not config.get("digest", False):
            # Auto-detect checksum files ONLY if digest verification is not explicitly enabled
            # This prevents interference with apps that are configured to use
            # digest verification
            logger.debug("🔍 Auto-detecting checksum files (digest not explicitly enabled)")
            try:
                # Convert assets to the format expected by GitHubReleaseFetcher
                github_assets: list[GitHubAsset] = []
                for asset_data in assets:
                    github_assets.append(
                        GitHubAsset(
                            name=asset_data.get("name", ""),
                            browser_download_url=asset_data.get("browser_download_url", ""),
                            size=asset_data.get("size", 0),
                            digest=asset_data.get("digest", ""),
                        )
                    )

                # Use GitHubReleaseFetcher to detect checksum files
                checksum_files = GitHubReleaseFetcher.detect_checksum_files(
                    github_assets, tag_name
                )
                logger.debug(
                    "🔍 Auto-detected %d checksum files from assets", len(checksum_files)
                )
            except Exception as e:  # Keep broad for backward compatibility
                logger.warning("Failed to auto-detect checksum files: %s", e)
        elif assets and config.get("digest", False):
            logger.debug("i  Skipping auto-detection: digest verification explicitly enabled")

        return has_digest, checksum_files

    def _build_checksum_url(
        self,
        owner: str,
        repo: str,
        tag_name: str,
        checksum_file: str,
    ) -> str:
        """Build URL for checksum file download.

        Args:
            owner: Repository owner
            repo: Repository name
            tag_name: Release tag name
            checksum_file: Checksum filename

        Returns:
            Complete checksum file URL

        """
        return (
            f"https://github.com/{owner}/{repo}/releases/download/{tag_name}/{checksum_file}"
        )


class ChecksumFilePrioritizationService:
    """Service for prioritizing checksum files for verification."""

    def prioritize_checksum_files(
        self,
        checksum_files: list[ChecksumFileInfo],
        target_filename: str,
    ) -> list[ChecksumFileInfo]:
        """Prioritize checksum files to try the most relevant one first.

        For a target file like 'app.AppImage', this will prioritize:
        1. Exact match: 'app.AppImage.DIGEST'
        2. Platform-specific: 'app.AppImage.sha256'
        3. Generic files: 'checksums.txt', etc.

        Args:
            checksum_files: List of detected checksum files
            target_filename: Name of the file being verified

        Returns:
            Reordered list with most relevant checksum files first

        """
        if not checksum_files:
            return checksum_files

        logger.debug(
            "🔍 Prioritizing %d checksum files for target: %s",
            len(checksum_files),
            target_filename,
        )

        def get_priority(checksum_file: ChecksumFileInfo) -> tuple[int, str]:
            """Get priority score for checksum file (lower = higher priority)."""
            filename = checksum_file.filename

            # Priority 1: Exact match (e.g., app.AppImage.DIGEST)
            digest_names = {f"{target_filename}.DIGEST", f"{target_filename}.digest"}
            if filename in digest_names:
                logger.debug("   📌 Priority 1 (exact .DIGEST): %s", filename)
                return (1, filename)

            # Priority 2: Platform-specific hash files (e.g., app.AppImage.sha256)
            target_extensions = [
                ".sha256",
                ".sha512",
                ".sha1",
                ".md5",
                ".sha256sum",
                ".sha512sum",
                ".sha1sum",
                ".md5sum",
            ]
            for ext in target_extensions:
                if filename == f"{target_filename}{ext}":
                    logger.debug("   📌 Priority 2 (platform-specific): %s", filename)
                    return (2, filename)

            # Priority 3: YAML files (usually most comprehensive)
            if checksum_file.format_type == "yaml":
                logger.debug("   📌 Priority 3 (YAML): %s", filename)
                return (3, filename)

            # Priority 4: Other .DIGEST files (might contain multiple files)
            if filename.lower().endswith((".digest",)):
                logger.debug("   📌 Priority 4 (other .DIGEST): %s", filename)
                return (4, filename)

            # Priority 5: Generic checksum files
            # Deprioritize experimental/beta/alpha versions by adding penalty
            penalty = 0
            lower_filename = filename.lower()
            experimental_variants = ["experimental", "beta", "alpha", "preview", "rc", "dev"]
            if any(variant in lower_filename for variant in experimental_variants):
                penalty = 10  # Push experimental versions to lower priority
                logger.debug("   📌 Priority 5 (generic + experimental penalty): %s", filename)
            else:
                logger.debug("   📌 Priority 5 (generic): %s", filename)
            return (5 + penalty, filename)

        # Sort by priority (lower number = higher priority)
        prioritized = sorted(checksum_files, key=get_priority)

        logger.debug("   📋 Final priority order:")
        for i, cf in enumerate(prioritized, 1):
            logger.debug("      %d. %s", i, cf.filename)

        return prioritized
