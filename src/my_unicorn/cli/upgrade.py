#!/usr/bin/python3
"""my-unicorn cli upgrade module.

This module handles updating the my-unicorn package itself by fetching
the latest release from GitHub and using uv's direct installation feature.

Currently using prereleases until stable releases are available.
"""

import os
import subprocess
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from typing import Any

import aiohttp
from packaging import version

from my_unicorn.config import ConfigManager, GlobalConfig
from my_unicorn.infrastructure.github import ReleaseFetcher
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


GITHUB_OWNER = "Cyber-Syntax"
GITHUB_REPO = "my-unicorn"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"
HTTP_FORBIDDEN = 403


def normalize_version_string(version_str: str) -> str:
    """Normalize a version string to Python's version format.

    Args:
        version_str: Version string (e.g., "v0.11.1-alpha", "0.11.1a0")

    Returns:
        Normalized version string

    """
    # Remove 'v' prefix if present
    clean = version_str.lstrip("v")

    # Try parsing first - if it works, use as-is
    try:
        version.parse(clean)
        return clean
    except Exception:
        # Fallback: minimal normalization only if needed
        return (
            clean.replace("-alpha.", "a")
            .replace("-alpha", "a0")
            .replace("-beta.", "b")
            .replace("-beta", "b0")
            .replace("-rc.", "rc")
            .replace("-rc", "rc0")
        )


class SelfUpdater:
    """Handles self-updating of the my-unicorn package."""

    def __init__(
        self,
        config_manager: ConfigManager,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the self-updater.

        Args:
            config_manager: Configuration manager instance
            session: aiohttp client session for API requests

        """
        self.config_manager: ConfigManager = config_manager
        self.global_config: GlobalConfig = config_manager.load_global_config()
        self.session: aiohttp.ClientSession = session
        self.github_fetcher: ReleaseFetcher = ReleaseFetcher(
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
            session=session,
        )
        self._uv_available: bool = self._check_uv_available()

    def _check_uv_available(self) -> bool:
        """Check if UV is available in the system.

        Returns:
            True if UV is installed and available, False otherwise

        """
        try:
            result = subprocess.run(
                ["uv", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                logger.debug("UV is available: %s", result.stdout.strip())
                return True
            logger.debug("UV command failed: %s", result.stderr.strip())
            return False
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("UV is not available in PATH")
            return False

    def get_current_version(self) -> str:
        """Get the current installed version of my-unicorn.

        Returns:
            The current version string

        Raises:
            PackageNotFoundError: If the package is not found

        """
        try:
            return get_version("my-unicorn")
        except PackageNotFoundError:
            logger.error("Package 'my-unicorn' not found")
            raise

    async def get_latest_release(
        self, refresh_cache: bool = False
    ) -> dict[str, Any] | None:
        """Get the latest release information from GitHub API.

        Args:
            refresh_cache: Whether to bypass cache and fetch fresh data

        Returns:
            Release information or None if failed

        """
        try:
            logger.info("Fetching latest release from GitHub...")
            # Using prerelease until stable versions are published
            release_data = (
                await self.github_fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=True, ignore_cache=refresh_cache
                )
            )

            logger.info(
                "Found latest release: %s",
                release_data.version,
            )

            # Convert to format compatible with old code
            return {
                "tag_name": f"v{release_data.version}",
                "version": release_data.version,
                "prerelease": release_data.prerelease,
                "assets": [
                    {
                        "name": asset.name,
                        "size": asset.size,
                        "browser_download_url": asset.browser_download_url,
                        "digest": asset.digest or "",
                    }
                    for asset in release_data.assets
                ],
            }

        except aiohttp.ClientResponseError as e:
            if e.status == HTTP_FORBIDDEN:
                logger.exception("GitHub API rate limit exceeded")
                logger.info(
                    "GitHub Rate limit exceeded. Please try again later."
                )
            else:
                logger.exception(
                    "GitHub API error: %s - %s", e.status, e.message
                )
                logger.info("GitHub API error. Please check your connection.")
            return None
        except Exception:
            logger.exception("Unexpected error fetching release")
            logger.info(
                "Error connecting to GitHub. Please check your connection."
            )
            return None

    async def check_for_update(self, refresh_cache: bool = False) -> bool:
        """Check if a new release is available from the GitHub repo.

        Args:
            refresh_cache: Whether to bypass cache and fetch fresh data

        Returns:
            True if update is available, False otherwise

        """
        logger.info("Checking for updates...")

        # Get latest release info
        latest_release = await self.get_latest_release(refresh_cache)
        if not latest_release:
            return False

        latest_version_tag = latest_release.get("tag_name")
        if not isinstance(latest_version_tag, str):
            latest_version_tag = None
        if not latest_version_tag:
            logger.error("Malformed release data - no tag_name found")
            logger.info(
                "Malformed release data! Reinstall manually or open an issue on GitHub for help!"
            )
            return False

        # Get current version
        try:
            current_version_str = self.get_current_version()
            logger.debug("Current version string: %s", current_version_str)
            logger.debug(
                "Latest version tag from GitHub: %s", latest_version_tag
            )

            # Normalize both versions for proper comparison
            current_normalized = normalize_version_string(
                current_version_str.split("+")[0]  # Remove git info
            )
            latest_normalized = normalize_version_string(latest_version_tag)

            logger.debug("Normalized current: %s", current_normalized)
            logger.debug("Normalized latest: %s", latest_normalized)

            # Use packaging library for proper version comparison
            current_version_obj = version.parse(current_normalized)
            latest_version_obj = version.parse(latest_normalized)

            logger.debug("Version comparison objects:")
            logger.debug("  Current: %s", current_version_obj)
            logger.debug("  Latest: %s", latest_version_obj)

            if latest_version_obj > current_version_obj:
                logger.debug("Update available: latest > current")
                return True

            if latest_version_obj == current_version_obj:
                logger.debug("No update needed: versions are equal")
                return False

            logger.debug("No update needed: current > latest (dev version?)")
            return False

        except (PackageNotFoundError, Exception):
            logger.exception("Error checking version")
            logger.info("Error checking version. Please try again.")
            return False

    async def perform_update(self) -> bool:
        """Update using UV's direct GitHub installation.

        This uses uv's modern tool installation from GitHub which:
        - Fetches the latest version directly from GitHub
        - Resolves and installs dependencies automatically
        - No need for local repository cloning
        - Follows best practices used by ruff, uv, and other modern
          CLI tools

        Returns:
            False if upgrade could not be started.
            Does not return on success (process replaced by execvp).

        """
        logger.debug("Starting upgrade to my-unicorn...")
        logger.debug("UV available: %s", self._uv_available)

        # Check UV availability first
        if not self._uv_available:
            logger.error("UV is required for upgrading my-unicorn")
            logger.info("❌ UV is required for upgrading my-unicorn")
            logger.info(
                "Install UV first: curl -LsSf https://astral.sh/uv/install.sh | sh"
            )
            return False

        try:
            logger.info("⚡ Upgrading my-unicorn...")
            logger.info("Executing: uv tool upgrade my-unicorn")

            # Close session before replacing process
            await self.session.close()

            # Use os.execvp to replace current process with uv upgrade
            # This ensures the upgrade completes properly and is the
            # recommended approach for self-upgrading CLI tools
            os.execvp(
                "uv",
                ["uv", "tool", "upgrade", "my-unicorn"],
            )

            # Note: Code after execvp won't execute if successful
            # If we reach here, execvp failed
            logger.error("Failed to execute uv upgrade")
            logger.info("❌ Failed to execute upgrade command")
            return False

        except Exception as e:
            logger.exception("Update failed")
            logger.info("❌ Update failed: %s", e)
            return False


async def get_self_updater(
    config_manager: ConfigManager | None = None,
) -> SelfUpdater:
    """Get a SelfUpdater instance with proper session management.

    Args:
        config_manager: Optional config manager, will create one if not
            provided

    Returns:
        Configured SelfUpdater instance

    """
    if config_manager is None:
        from my_unicorn.config import config_manager as default_config_manager

        config_manager = default_config_manager

    # Use a timeout for GitHub API requests driven by configuration
    try:
        global_conf = config_manager.load_global_config()
        network_cfg = global_conf.get("network", {})
        timeout_seconds = int(network_cfg.get("timeout_seconds", 10))
    except Exception:
        # Fall back to a sensible default if config lookup fails
        timeout_seconds = 10

    # Map configured base seconds to aiohttp timeouts (keeps previous defaults)
    timeout = aiohttp.ClientTimeout(
        total=timeout_seconds * 3,
        sock_read=timeout_seconds * 2,
        sock_connect=timeout_seconds,
    )
    session = aiohttp.ClientSession(timeout=timeout)

    return SelfUpdater(config_manager, session)


async def check_for_self_update(refresh_cache: bool = False) -> bool:
    """Check for self-updates.

    Args:
        refresh_cache: Whether to bypass cache and fetch fresh data

    Returns:
        True if update is available, False otherwise

    """
    updater = await get_self_updater()
    try:
        return await updater.check_for_update(refresh_cache)
    finally:
        await updater.session.close()


async def perform_self_update(refresh_cache: bool = False) -> bool:
    """Perform self-update.

    Args:
        refresh_cache: Whether to bypass cache and fetch fresh data

    Returns:
        True if update was successful, False otherwise

    """
    updater = await get_self_updater()
    try:
        # First check if update is available
        if await updater.check_for_update(refresh_cache):
            return await updater.perform_update()
        return False
    finally:
        await updater.session.close()
