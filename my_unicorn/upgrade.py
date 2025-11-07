#!/usr/bin/python3
"""my-unicorn cli upgrade module.

This module handles updating the my-unicorn package itself by fetching
the latest release from GitHub, cloning the repository, and running
the installer script in update mode.

TODO: Switch to stable releases only when we publish stable versions
Currently using prereleases until stable releases are available.
"""

import asyncio
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as get_version
from typing import Any

import aiohttp
from packaging import version

from .config import ConfigManager, GlobalConfig
from .github_client import ReleaseFetcher
from .logger import get_logger


class SimpleProgress:
    """Simple progress indicator using rotating slash characters."""

    def __init__(self) -> None:
        """Initialize the simple progress indicator."""
        self.indicators = ["/", "-", "\\", "|"]
        self.current = 0
        self.active_tasks: dict[str, str] = {}

    def start_task(self, name: str, description: str) -> str:
        """Start a new progress task.

        Args:
            name: Task name/identifier
            description: Task description to display

        Returns:
            Task ID for updating the task

        """
        task_id = f"task_{len(self.active_tasks)}"
        self.active_tasks[task_id] = description
        print(f"⚡ {description}")
        return task_id

    def update_task(
        self, task_id: str, description: str | None = None
    ) -> None:
        """Update a task's progress indicator.

        Args:
            task_id: Task identifier
            description: Optional new description

        """
        if task_id in self.active_tasks:
            if description:
                self.active_tasks[task_id] = description
            indicator = self.indicators[self.current % len(self.indicators)]
            print(
                f"\r{indicator} {self.active_tasks[task_id]}",
                end="",
                flush=True,
            )
            self.current += 1

    def finish_task(
        self,
        task_id: str,
        success: bool = True,
        final_description: str | None = None,
    ) -> None:
        """Finish a task.

        Args:
            task_id: Task identifier
            success: Whether the task completed successfully
            final_description: Optional final description

        """
        if task_id in self.active_tasks:
            status = "✅" if success else "❌"
            desc = final_description or self.active_tasks[task_id]
            print(f"\r{status} {desc}")
            del self.active_tasks[task_id]


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
    clean_version = version_str.lstrip("v")

    # Convert GitHub-style version tags to Python version format
    replacements = {
        "-alpha": "a0",
        "-alpha.": "a",
        "-beta": "b0",
        "-beta.": "b",
        "-rc": "rc0",
        "-rc.": "rc",
    }

    for old, new in replacements.items():
        if old in clean_version:
            clean_version = clean_version.replace(old, new)
            break

    return clean_version


class SelfUpdater:
    """Handles self-updating of the my-unicorn package."""

    def __init__(
        self,
        config_manager: ConfigManager,
        session: aiohttp.ClientSession,
        simple_progress: bool = True,
    ) -> None:
        """Initialize the self-updater.

        Args:
            config_manager: Configuration manager instance
            session: aiohttp client session for API requests
            simple_progress: Whether to use simple progress indicators

        """
        self.config_manager: ConfigManager = config_manager
        self.global_config: GlobalConfig = config_manager.load_global_config()
        self.session: aiohttp.ClientSession = session
        self.progress = SimpleProgress() if simple_progress else None
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
                timeout=5,
            )
            available = result.returncode == 0
            if available:
                logger.debug("UV is available: %s", result.stdout.strip())
            return available
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
            version_str = get_version("my-unicorn")
            # Handle None return in Python 3.13+ for uninstalled packages
            if version_str is None:
                logger.error("Package 'my-unicorn' not found")
                raise PackageNotFoundError("my-unicorn")
            return version_str
        except PackageNotFoundError:
            logger.error("Package 'my-unicorn' not found")
            raise

    def get_formatted_version(self) -> str:
        """Get formatted version for better readability.

        Returns:
            Formatted version string

        """
        try:
            version_str = self.get_current_version()
            # Handle version with git info
            if "+" in version_str:
                numbered_version, git_version = version_str.split("+", 1)
                return f"{numbered_version} (git: {git_version})"
            return version_str
        except PackageNotFoundError:
            return "Package not found"

    def display_version_info(self) -> None:
        """Display the current version of my-unicorn."""
        print("my-unicorn version: ", end="")
        try:
            print(self.get_formatted_version())
        except Exception as e:
            logger.exception("Failed to get version: %s", e)
            print(f"Error: {e}")

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
            # TODO: Change to prefer_prerelease=False when we have stable releases
            # would be better to have variable in settings.conf for user choice
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
                logger.error("GitHub API rate limit exceeded")
                print(
                    "".join(
                        [
                            "GitHub Rate limit exceeded. Please try "
                            "again later ",
                            "within 1 hour or use different network/VPN.",
                        ]
                    )
                )
            else:
                logger.error("GitHub API error: %s", e)
                print(f"GitHub API error: {e}")
            return None
        except Exception as e:
            logger.error("Unexpected error fetching release: %s", e)
            print(f"Error connecting to GitHub: {e}")
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
            print(
                "".join(
                    [
                        "Malformed release data! Reinstall manually or ",
                        "open an issue on GitHub for help!",
                    ]
                )
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
            elif latest_version_obj == current_version_obj:
                logger.debug("No update needed: versions are equal")
                return False
            else:
                logger.debug(
                    "No update needed: current > latest (dev version?)"
                )
                return False

        except (PackageNotFoundError, Exception) as e:
            logger.error("Error checking version: %s", e)
            print(f"Error: {e}")
            return False

    async def perform_update(self) -> bool:
        """Update by cloning repo and running setup.sh install.

        Simplified approach that delegates all
        installation logic to setup.sh, eliminating code duplication.

        Returns:
            True if update was successful, False otherwise

        """
        repo_dir = self.global_config["directory"]["repo"]
        installer_script = repo_dir / "setup.sh"

        logger.debug("Starting upgrade to my-unicorn...")
        logger.debug("Repository directory: %s", repo_dir)
        logger.debug("UV available: %s", self._uv_available)

        # Inform user about UV usage
        if self._uv_available:
            logger.info("UV detected - will use UV for faster installation")
        else:
            logger.info(
                "Using pip for installation (install UV for faster updates)"
            )

        # Track progress
        download_task_id = None
        install_task_id = None
        cleanup_task_id = None

        try:
            # 1) Prepare fresh repo directory
            if repo_dir.exists():
                logger.info("Removing old repo at %s", repo_dir)
                shutil.rmtree(repo_dir)
                logger.debug("Old repo directory removed successfully")

            repo_dir.mkdir(parents=True)
            logger.debug("Created fresh repo directory: %s", repo_dir)

            # 2) Clone repository
            if self.progress:
                download_task_id = self.progress.start_task(
                    "repo_clone", "Cloning repository from GitHub..."
                )

            logger.info("Cloning repository to %s", repo_dir)
            clone_process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                f"{GITHUB_URL}.git",
                str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Progress updates during clone
            clone_task = asyncio.create_task(clone_process.wait())
            if self.progress and download_task_id:
                while not clone_task.done():
                    self.progress.update_task(download_task_id)
                    await asyncio.sleep(0.5)

            await clone_task

            if self.progress and download_task_id:
                self.progress.finish_task(
                    download_task_id,
                    success=clone_process.returncode == 0,
                    final_description="Repository cloned successfully"
                    if clone_process.returncode == 0
                    else "Repository clone failed",
                )

            if clone_process.returncode != 0:
                logger.error("Git clone failed")
                print("❌ Failed to download repository")
                return False

            # 3) Run setup.sh install from the cloned repo
            if not installer_script.exists():
                logger.error(
                    "Installer script missing at %s", installer_script
                )
                print("❌ Installer script not found.")
                return False

            logger.debug("Making installer executable: %s", installer_script)
            installer_script.chmod(0o755)

            if self.progress:
                install_msg = (
                    "Running installation with UV..."
                    if self._uv_available
                    else "Running installation with pip..."
                )
                install_task_id = self.progress.start_task(
                    "upgrade_installation",
                    install_msg,
                )

            logger.info("Executing: bash %s install", installer_script)
            install_process = await asyncio.create_subprocess_exec(
                "bash",
                str(installer_script),
                "install",
                cwd=str(repo_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream output with progress updates
            if install_process.stdout:
                while True:
                    line = await install_process.stdout.readline()
                    if not line:
                        break
                    line_str = line.decode().strip()
                    logger.debug("Installer output: %s", line_str)

                    if (
                        self.progress
                        and install_task_id
                        and any(
                            kw in line_str.lower()
                            for kw in [
                                "creating",
                                "installing",
                                "updating",
                                "complete",
                            ]
                        )
                    ):
                        self.progress.update_task(install_task_id)

            await install_process.wait()
            logger.debug("Installer exit code: %s", install_process.returncode)

            if self.progress and install_task_id:
                self.progress.finish_task(
                    install_task_id,
                    success=install_process.returncode == 0,
                    final_description="Installation completed successfully"
                    if install_process.returncode == 0
                    else "Installation failed",
                )

            if install_process.returncode != 0:
                print(
                    f"❌ Installer exited with code "
                    f"{install_process.returncode}"
                )
                return False

            # 4) Clean up cloned repository
            if self.progress:
                cleanup_task_id = self.progress.start_task(
                    "cleanup", "Cleaning up temporary files..."
                )

            if repo_dir.exists():
                logger.info("Cleaning up repo directory")
                shutil.rmtree(repo_dir)
                logger.debug("Repo directory cleanup completed")

            if self.progress and cleanup_task_id:
                self.progress.finish_task(
                    cleanup_task_id,
                    success=True,
                    final_description="Cleanup completed",
                )

            logger.info("Self-update completed successfully")
            return True

        except Exception as e:
            # Finish any pending progress tasks
            for task_id in [
                download_task_id,
                install_task_id,
                cleanup_task_id,
            ]:
                if self.progress and task_id:
                    self.progress.finish_task(task_id, success=False)

            logger.exception("Update failed: %s", e)
            print(f"❌ Update failed: {e}")
            return False


async def get_self_updater(
    config_manager: ConfigManager | None = None,
    simple_progress: bool = True,
) -> SelfUpdater:
    """Get a SelfUpdater instance with proper session management.

    Args:
        config_manager: Optional config manager, will create one if not
            provided
        simple_progress: Whether to use simple progress indicators

    Returns:
        Configured SelfUpdater instance

    """
    if config_manager is None:
        from .config import config_manager as default_config_manager

        config_manager = default_config_manager

    # Use a timeout for GitHub API requests
    timeout = aiohttp.ClientTimeout(total=30)
    session = aiohttp.ClientSession(timeout=timeout)

    return SelfUpdater(config_manager, session, simple_progress)


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
        else:
            return False
    finally:
        await updater.session.close()


def display_current_version() -> None:
    """Display the current version synchronously (for CLI compatibility)."""
    try:
        version_str = get_version("my-unicorn")
        # Handle None return in Python 3.13+ for uninstalled packages
        if version_str is None:
            print("Version information not available")
            return
        # Handle version with git info
        if "+" in version_str:
            numbered_version, git_version = version_str.split("+", 1)
            formatted_version = f"{numbered_version} (git: {git_version})"
        else:
            formatted_version = version_str
        print(f"my-unicorn version: {formatted_version}")
    except PackageNotFoundError:
        print("my-unicorn version: Package not found")
    except Exception as e:
        logger.exception("Failed to display version: %s", e)
        print(f"Error: {e}")


# Legacy compatibility functions for CLI usage
async def main_check() -> None:
    """Check for updates (CLI compatibility)."""
    _ = await check_for_self_update()


async def main_update() -> None:
    """Perform updates (CLI compatibility)."""
    if await check_for_self_update():
        _ = await perform_self_update()


if __name__ == "__main__":
    # Simple CLI for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        asyncio.run(main_check())
    elif len(sys.argv) > 1 and sys.argv[1] == "--update":
        asyncio.run(main_update())
    else:
        display_current_version()
