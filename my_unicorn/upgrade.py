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
import sys
from importlib.metadata import PackageNotFoundError, metadata
from typing import Any

import aiohttp
from packaging import version

from .config import ConfigManager, GlobalConfig
from .github_client import GitHubReleaseFetcher
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
        self.github_fetcher: GitHubReleaseFetcher = GitHubReleaseFetcher(
            owner=GITHUB_OWNER,
            repo=GITHUB_REPO,
            session=session,
        )

    def get_current_version(self) -> str:
        """Get the current installed version of my-unicorn.

        Returns:
            The current version string

        Raises:
            PackageNotFoundError: If the package is not found

        """
        try:
            package_metadata = metadata("my-unicorn")
            return package_metadata["Version"]
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
            release_data = (
                await self.github_fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=True, ignore_cache=refresh_cache
                )
            )

            logger.info(
                "Found latest release: %s",
                release_data.get("version", "unknown"),
            )

            # Convert to format compatible with old code
            return {
                "tag_name": f"v{release_data['version']}",
                "version": release_data["version"],
                "prerelease": release_data.get("prerelease", False),
                "assets": release_data.get("assets", []),
            }

        except aiohttp.ClientResponseError as e:
            if e.status == HTTP_FORBIDDEN:
                logger.error("GitHub API rate limit exceeded")
                print(
                    "".join(
                        [
                            "GitHub Rate limit exceeded. Please try again later ",
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
        """Update by doing a fresh git clone and running the installer.

        Returns:
            True if update was successful, False otherwise

        """
        repo_dir = self.global_config["directory"]["repo"]
        package_dir = self.global_config["directory"]["package"]
        source_dir = repo_dir / "source"
        installer = package_dir / "setup.sh"

        logger.debug("Starting upgrade to my-unicorn...")
        logger.debug("Repository directory: %s", repo_dir)
        logger.debug("Package directory: %s", package_dir)
        logger.debug("Source directory: %s", source_dir)
        logger.debug("Installer script: %s", installer)

        # Track progress with simple indicators
        download_task_id = None
        file_task_id = None
        install_task_id = None
        cleanup_task_id = None

        try:
            # Ensure repo directory exists
            repo_dir.mkdir(parents=True, exist_ok=True)

            # 1) Prepare fresh source tree
            if source_dir.exists():
                logger.info("Removing old source at %s", source_dir)
                logger.debug(
                    "Old source directory size: %s",
                    source_dir.stat().st_size
                    if source_dir.is_file()
                    else "directory",
                )
                shutil.rmtree(source_dir)
                logger.debug("Old source directory removed successfully")
            source_dir.mkdir(parents=True)
            logger.debug("Created fresh source directory: %s", source_dir)

            # 2) Clone into source_dir with simple progress tracking
            if self.progress:
                download_task_id = self.progress.start_task(
                    "repo_clone", "Cloning repository from GitHub..."
                )

            logger.info("Cloning repository to %s", source_dir)
            logger.debug(
                "Git clone command: git clone %s %s",
                f"{GITHUB_URL}.git",
                str(source_dir),
            )

            clone_process = await asyncio.create_subprocess_exec(
                "git",
                "clone",
                f"{GITHUB_URL}.git",
                str(source_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Simple progress updates during clone
            clone_task = asyncio.create_task(clone_process.wait())
            if self.progress and download_task_id:
                # Show progress during clone
                while not clone_task.done():
                    self.progress.update_task(download_task_id)
                    await asyncio.sleep(0.5)

            await clone_task

            logger.debug(
                "Git clone process completed with return code: %s",
                clone_process.returncode,
            )
            if clone_process.returncode == 0:
                logger.debug(
                    "Repository cloned successfully to %s", source_dir
                )
                # Check if source directory has expected content
                try:
                    source_contents = list(source_dir.iterdir())
                    logger.debug(
                        "Cloned repository contains %d items",
                        len(source_contents),
                    )
                    logger.debug(
                        "Repository structure: %s",
                        [item.name for item in source_contents],
                    )
                except Exception as e:
                    logger.debug(
                        "Could not list source directory contents: %s", e
                    )
            else:
                logger.debug("Git clone failed, will handle error")

            if self.progress and download_task_id:
                self.progress.finish_task(
                    download_task_id,
                    success=clone_process.returncode == 0,
                    final_description="Repository cloned successfully"
                    if clone_process.returncode == 0
                    else "Repository clone failed",
                )

            if clone_process.returncode != 0:
                logger.error(
                    "Git clone failed with return code %s",
                    clone_process.returncode,
                )
                print("❌ Failed to download repository")
                return False

            # 3) Copy files with simple progress tracking
            if self.progress:
                file_task_id = self.progress.start_task(
                    "file_operations", "Copying project files..."
                )

            logger.info("Copying code + scripts to %s", package_dir)
            logger.debug("Ensuring package directory exists: %s", package_dir)
            package_dir.mkdir(parents=True, exist_ok=True)
            logger.debug("Package directory created/verified")

            # Copy over the package code, scripts, and installation files
            files_to_copy = (
                "my_unicorn",
                "scripts",
                "pyproject.toml",
                "setup.sh",
            )
            for name in files_to_copy:
                src = source_dir / name
                dst = package_dir / name

                logger.debug("Processing file/directory: %s", name)
                logger.debug("Source: %s", src)
                logger.debug("Destination: %s", dst)

                if not src.exists():
                    logger.warning("Source file/directory not found: %s", src)
                    logger.debug("Skipping %s - source does not exist", name)
                    continue

                if self.progress and file_task_id:
                    self.progress.update_task(
                        file_task_id,
                        description=f"Copying {name}...",
                    )

                # Remove the old directory/file (but preserve venv and other dirs)
                if dst.exists():
                    logger.debug("Destination exists, removing old: %s", dst)
                    if dst.is_dir():
                        logger.debug("Removing old directory: %s", dst)
                        shutil.rmtree(dst)
                    else:
                        logger.debug("Removing old file: %s", dst)
                        dst.unlink()

                # Copy fresh
                if src.is_dir():
                    logger.debug(
                        "Copying directory tree from %s to %s", src, dst
                    )
                    _ = shutil.copytree(src, dst)
                    logger.debug("Directory copy completed for %s", name)
                else:
                    logger.debug("Copying file from %s to %s", src, dst)
                    _ = shutil.copy2(src, dst)
                    logger.debug("File copy completed for %s", name)

            if self.progress and file_task_id:
                self.progress.finish_task(
                    file_task_id,
                    success=True,
                    final_description="Files copied successfully",
                )

            # 4) Run installer with simple progress tracking
            if not installer.exists():
                logger.error("Installer script missing at %s", installer)
                print("❌ Installer script not found.")
                return False

            # Make installer executable
            logger.debug("Setting installer script permissions: %s", installer)
            installer.chmod(0o755)
            logger.debug("Installer script is now executable")

            if self.progress:
                install_task_id = self.progress.start_task(
                    "upgrade_installation",
                    "Running installer in UPDATE mode...",
                )

            logger.debug("Starting installer subprocess")
            logger.debug("Command: bash %s update", str(installer))
            logger.debug("Working directory: %s", str(package_dir))
            install_process = await asyncio.create_subprocess_exec(
                "bash",
                str(installer),
                "update",
                cwd=str(package_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
            logger.debug(
                "Installer subprocess started with PID: %s",
                install_process.pid,
            )

            # Stream output and update progress
            if install_process.stdout:
                while True:
                    line = await install_process.stdout.readline()
                    if not line:
                        break

                    line_str = line.decode().strip()

                    # Debug log all installer output for troubleshooting
                    logger.debug("Installer output: %s", line_str)

                    # Detailed logging for specific venv and installation operations
                    if "virtual environment" in line_str.lower():
                        logger.debug("VENV OPERATION: %s", line_str)
                    elif "pip install" in line_str.lower():
                        logger.debug("PIP INSTALL: %s", line_str)
                    elif "installing" in line_str.lower():
                        logger.debug("PACKAGE INSTALL: %s", line_str)
                    elif "creating" in line_str.lower():
                        logger.debug("CREATION STEP: %s", line_str)
                    elif "updating" in line_str.lower():
                        logger.debug("UPDATE STEP: %s", line_str)
                    elif "complete" in line_str.lower():
                        logger.debug("COMPLETION: %s", line_str)
                    elif "error" in line_str.lower():
                        logger.debug("ERROR OUTPUT: %s", line_str)
                    elif "warning" in line_str.lower():
                        logger.debug("WARNING OUTPUT: %s", line_str)

                    # Update progress indicator on key installer stages
                    if (
                        self.progress
                        and install_task_id
                        and any(
                            keyword in line_str.lower()
                            for keyword in [
                                "creating",
                                "installing",
                                "updating",
                                "complete",
                            ]
                        )
                    ):
                        self.progress.update_task(install_task_id)

            _ = await install_process.wait()

            logger.debug("Installer process completed")
            logger.debug("Installer exit code: %s", install_process.returncode)
            if install_process.returncode == 0:
                logger.debug("Installation successful")
            else:
                logger.debug(
                    "Installation failed with code: %s",
                    install_process.returncode,
                )

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
                    f"❌ Installer exited with code {install_process.returncode}"
                )
                return False

            # 5) Clean up source_dir with simple progress tracking
            if self.progress:
                cleanup_task_id = self.progress.start_task(
                    "cleanup", "Cleaning up temporary files..."
                )

            if source_dir.exists():
                logger.info("Cleaning up source directory")
                logger.debug("Removing source directory: %s", source_dir)
                try:
                    dir_size = sum(
                        f.stat().st_size
                        for f in source_dir.rglob("*")
                        if f.is_file()
                    )
                    logger.debug(
                        "Source directory size before cleanup: %d bytes",
                        dir_size,
                    )
                except Exception as e:
                    logger.debug(
                        "Could not calculate source directory size: %s", e
                    )
                shutil.rmtree(source_dir)
                logger.debug("Source directory cleanup completed")

            if self.progress and cleanup_task_id:
                self.progress.finish_task(
                    cleanup_task_id,
                    success=True,
                    final_description="Cleanup completed",
                )

            logger.debug("Self-update completed successfully")
            logger.debug(
                "All operations completed: clone, file copy, installation, cleanup"
            )
            return True

        except Exception as e:
            # Finish any pending progress tasks with error
            for task_id in [
                download_task_id,
                file_task_id,
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
        config_manager: Optional config manager, will create one if not provided
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
        package_metadata = metadata("my-unicorn")
        version_str = package_metadata["Version"]
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
