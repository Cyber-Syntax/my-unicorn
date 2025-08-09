#!/usr/bin/python3
"""Self-update functionality for my-unicorn package from GitHub.

This module handles updating the my-unicorn package itself by fetching
the latest release from GitHub, cloning the repository, and running
the installer script in update mode.
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
        branch_type: str = "stable",
    ) -> None:
        """Initialize the self-updater.

        Args:
            config_manager: Configuration manager instance
            session: aiohttp client session for API requests
            branch_type: Type of branch to update from ("stable" or "dev")

        """
        self.config_manager: ConfigManager = config_manager
        self.global_config: GlobalConfig = config_manager.load_global_config()
        self.session: aiohttp.ClientSession = session
        self.branch_type: str = branch_type
        self.github_fetcher: GitHubReleaseFetcher = GitHubReleaseFetcher(
            owner=GITHUB_OWNER, repo=GITHUB_REPO, session=session
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

    async def get_latest_release(self) -> dict[str, Any] | None:
        """Get the latest release information from GitHub API.

        Returns:
            Release information or None if failed

        """
        try:
            if self.branch_type == "stable":
                logger.info("Fetching latest stable release from GitHub...")
                release_data = await self.github_fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=False  # Prefer stable releases for stable branch
                )
            else:  # dev branch
                logger.info("Fetching latest prerelease from GitHub...")
                release_data = await self.github_fetcher.fetch_latest_release_or_prerelease(
                    prefer_prerelease=True  # Prefer prereleases for dev branch
                )

            logger.info("Found latest release: %s", release_data.get("version", "unknown"))

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
                    "GitHub Rate limit exceeded. Please try again later within 1 hour "
                    + "or use different network/VPN."
                )
            else:
                logger.error("GitHub API error: %s", e)
                print(f"GitHub API error: {e}")
            return None
        except Exception as e:
            logger.error("Unexpected error fetching release: %s", e)
            print(f"Error connecting to GitHub: {e}")
            return None

    async def check_for_update(self) -> bool:
        """Check if a new release is available from the GitHub repo.

        Returns:
            True if update is available, False otherwise

        """
        branch_desc = "stable" if self.branch_type == "stable" else "development"
        logger.info("Checking for updates on %s branch...", branch_desc)

        # Get latest release info
        latest_release = await self.get_latest_release()
        if not latest_release:
            return False

        latest_version_tag = latest_release.get("tag_name")
        if not isinstance(latest_version_tag, str):
            latest_version_tag = None
        if not latest_version_tag:
            logger.error("Malformed release data - no tag_name found")
            print(
                "Malformed release data! Reinstall manually or "
                + "open an issue on GitHub for help!"
            )
            return False

        # Get current version
        try:
            current_version_str = self.get_current_version()

            # Normalize both versions for proper comparison
            current_normalized = normalize_version_string(
                current_version_str.split("+")[0]  # Remove git info
            )
            latest_normalized = normalize_version_string(latest_version_tag)

            branch_desc = "stable" if self.branch_type == "stable" else "development"
            print(f"Current version: {current_version_str}")
            print(f"Latest version ({branch_desc}): {latest_version_tag}")

            logger.debug("Normalized current: %s", current_normalized)
            logger.debug("Normalized latest: %s", latest_normalized)

            # Use packaging library for proper version comparison
            current_version_obj = version.parse(current_normalized)
            latest_version_obj = version.parse(latest_normalized)

            if latest_version_obj > current_version_obj:
                print("🆕 Updates are available!")
                print(
                    "Note: Your previous custom settings might be preserved, but please "
                    + "backup important data."
                )
                return True
            elif latest_version_obj == current_version_obj:
                print("✅ my-unicorn is up to date")
                return False
            else:
                print("💻 You are using a development version")
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
        installer = package_dir / "my-unicorn-installer.sh"

        try:
            # Ensure repo directory exists
            repo_dir.mkdir(parents=True, exist_ok=True)

            # 1) Prepare fresh source tree
            if source_dir.exists():
                logger.info("Removing old source at %s", source_dir)
                shutil.rmtree(source_dir)
            source_dir.mkdir(parents=True)

            # 2) Determine branch to clone
            if self.branch_type == "stable":
                branch_name = await self.github_fetcher.get_default_branch()
                logger.info("Using stable branch: %s", branch_name)
                print(f"📥 Downloading latest stable version from {branch_name} branch...")
                clone_args = [
                    "git",
                    "clone",
                    "-b",
                    branch_name,
                    f"{GITHUB_URL}.git",
                    str(source_dir),
                ]
            else:
                # For dev branch, try common development branch names
                dev_branches = ["develop", "dev", "development", "unstable"]
                branch_name = None

                # Try to find an existing dev branch
                for branch in dev_branches:
                    try:
                        check_process = await asyncio.create_subprocess_exec(
                            "git",
                            "ls-remote",
                            "--heads",
                            f"{GITHUB_URL}.git",
                            branch,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, _ = await check_process.communicate()
                        if check_process.returncode == 0 and stdout.strip():
                            branch_name = branch
                            break
                    except Exception:
                        continue

                if not branch_name:
                    # Fallback to default branch for dev if no dev branch found
                    branch_name = await self.github_fetcher.get_default_branch()
                    logger.warning(
                        "No development branch found, using default branch: %s", branch_name
                    )

                logger.info("Using development branch: %s", branch_name)
                print(
                    f"📥 Downloading latest development version from {branch_name} branch..."
                )
                clone_args = [
                    "git",
                    "clone",
                    "-b",
                    branch_name,
                    f"{GITHUB_URL}.git",
                    str(source_dir),
                ]

            # 3) Clone into source_dir
            clone_process = await asyncio.create_subprocess_exec(
                *clone_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            _ = await clone_process.wait()

            if clone_process.returncode != 0:
                logger.error("Git clone failed with return code %s", clone_process.returncode)
                logger.error("Git clone failed")
                print("❌ Failed to download repository")
                return False

            # 3) Copy over only the package code and scripts
            logger.info("Copying code + scripts to %s", package_dir)
            package_dir.mkdir(parents=True, exist_ok=True)

            # Copy over the package code, scripts, and installation files
            for name in ("my_unicorn", "scripts", "pyproject.toml", "my-unicorn-installer.sh"):
                src = source_dir / name
                dst = package_dir / name

                if not src.exists():
                    logger.warning("Source file/directory not found: %s", src)
                    continue

                # Remove the old directory/file (but preserve venv and other dirs)
                if dst.exists():
                    if dst.is_dir():
                        shutil.rmtree(dst)
                    else:
                        dst.unlink()

                # Copy fresh
                _ = shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)

            # 4) Make installer executable and invoke it in update mode
            if not installer.exists():
                logger.error("Installer script missing at %s", installer)
                print("❌ Installer script not found.")
                return False

            # Make installer executable
            installer.chmod(0o755)

            print("🚀 Running installer in UPDATE mode…")

            install_process = await asyncio.create_subprocess_exec(
                "bash",
                str(installer),
                "update",
                cwd=str(package_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

            # Stream output in real-time
            if install_process.stdout:
                while True:
                    line = await install_process.stdout.readline()
                    if not line:
                        break
                    print(line.decode().strip())

            _ = await install_process.wait()

            if install_process.returncode != 0:
                print(f"❌ Installer exited with code {install_process.returncode}")
                return False

            # 5) Clean up source_dir
            if source_dir.exists():
                shutil.rmtree(source_dir)

            print("✅ Update successful!")
            return True

        except Exception as e:
            logger.exception("Update failed: %s", e)
            print(f"❌ Update failed: {e}")
            return False


async def get_self_updater(
    config_manager: ConfigManager | None = None, branch_type: str = "stable"
) -> SelfUpdater:
    """Get a SelfUpdater instance with proper session management.

    Args:
        config_manager: Optional config manager, will create one if not provided
        branch_type: Type of branch to update from ("stable" or "dev")

    Returns:
        Configured SelfUpdater instance

    """
    if config_manager is None:
        from .config import config_manager as default_config_manager

        config_manager = default_config_manager

    # Use a timeout for GitHub API requests
    timeout = aiohttp.ClientTimeout(total=30)
    session = aiohttp.ClientSession(timeout=timeout)

    return SelfUpdater(config_manager, session, branch_type)


async def check_for_self_update(branch_type: str = "stable") -> bool:
    """Check for self-updates.

    Args:
        branch_type: Type of branch to check ("stable" or "dev")

    Returns:
        True if update is available, False otherwise

    """
    updater = await get_self_updater(branch_type=branch_type)
    try:
        return await updater.check_for_update()
    finally:
        await updater.session.close()


async def perform_self_update(branch_type: str = "stable") -> bool:
    """Perform self-update.

    Args:
        branch_type: Type of branch to update from ("stable" or "dev")

    Returns:
        True if update was successful, False otherwise

    """
    updater = await get_self_updater(branch_type=branch_type)
    try:
        # First check if update is available
        if await updater.check_for_update():
            return await updater.perform_update()
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
async def main_check(branch_type: str = "stable") -> None:
    """Check for updates (CLI compatibility)."""
    _ = await check_for_self_update(branch_type)


async def main_update(branch_type: str = "stable") -> None:
    """Perform updates (CLI compatibility)."""
    if await check_for_self_update(branch_type):
        _ = await perform_self_update(branch_type)


if __name__ == "__main__":
    # Simple CLI for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        asyncio.run(main_check())
    elif len(sys.argv) > 1 and sys.argv[1] == "--update":
        asyncio.run(main_update())
    else:
        display_current_version()
