#!/usr/bin/python3
"""Update my_unicorn package from GitHub by cloning the repository."""

import logging
import os
import shutil
import subprocess
import sys
from importlib.metadata import PackageNotFoundError, metadata
from pathlib import Path

import requests
from packaging import version
from requests import exceptions

# Constants
GITHUB = "https://github.com/Cyber-Syntax/my-unicorn"
GITHUB_API_RELEASES_URL = "https://api.github.com/repos/Cyber-Syntax/my-unicorn/releases"
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
INSTALL_DIR = XDG_DATA_HOME / "my-unicorn"

logger = logging.getLogger(__name__)


def normalize_version_string(version_str: str) -> str:
    """Normalize a version string to Python's version format.

    Args:
        version_str: Version string (e.g., "v0.11.1-alpha", "0.11.1a0")

    Returns:
        str: Normalized version string

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


def get_current_version() -> str:
    """Get the current installed version of my-unicorn.

    Returns:
        str: The current version string

    Raises:
        PackageNotFoundError: If the package is not found

    """
    try:
        package_metadata = metadata("my-unicorn")
        return package_metadata["Version"]
    except PackageNotFoundError:
        logger.error("Package 'my-unicorn' not found")
        raise


def get_formatted_version() -> str:
    """Get formatted version for better readability.

    Returns:
        str: Formatted version string

    """
    try:
        version_str = get_current_version()
        # Handle version with git info
        if "+" in version_str:
            numbered_version, git_version = version_str.split("+", 1)
            return f"{numbered_version} (git: {git_version})"
        return version_str
    except PackageNotFoundError:
        return "Package not found"


def display_current_version() -> None:
    """Display the current version of my-unicorn."""
    print("my-unicorn version: ", end="")
    try:
        print(get_formatted_version())
    except Exception as e:
        logger.exception("Failed to get version: %s", e)
        print(f"Error: {e}")


# NOTE: This need to be changed when we switch to a stable release
def get_latest_release_info() -> dict | None:
    """Get the latest release information from GitHub API.

    Since this project uses pre-releases (alpha/beta), we get all releases
    and return the most recent one.

    Returns:
        dict | None: Release information or None if failed

    """
    try:
        logger.info("Fetching releases from GitHub API...")
        response = requests.get(GITHUB_API_RELEASES_URL, timeout=10)

        if response.status_code == 200:
            releases = response.json()

            if not releases:
                logger.error("No releases found")
                print("No releases found in the repository.")
                return None

            if not isinstance(releases, list):
                logger.error("Invalid response format - expected list of releases")
                print("Invalid response format from GitHub API.")
                return None

            # Return the first release (most recent)
            latest_release = releases[0]
            logger.info("Found latest release: %s", latest_release.get("tag_name", "unknown"))
            return latest_release

        elif response.status_code == 403:
            response_data = response.json() if response.content else {}
            message = response_data.get("message", "")
            if "rate limit exceeded" in message.lower():
                logger.error("GitHub API rate limit exceeded")
                print(
                    "GitHub Rate limit exceeded. Please try again later within 1 hour or use different network/VPN."
                )
            else:
                logger.error("GitHub API error: %s", message)
                print(f"GitHub API error: {message}")
        else:
            logger.error("Unexpected status code: %s", response.status_code)
            print(f"Unexpected status code: {response.status_code}")

        return None

    except (
        exceptions.ConnectionError,
        exceptions.Timeout,
        exceptions.RequestException,
        exceptions.HTTPError,
    ) as e:
        logger.error("Error connecting to GitHub API: %s", e)
        print("Error connecting to server!")
        return None
    except Exception as e:
        logger.error("Unexpected error: %s", e)
        print(f"Unexpected error: {e}")
        return None


def check_for_update() -> bool:
    """Check if a new release is available from the GitHub repo.

    Returns:
        bool: True if update is available, False otherwise

    """
    logger.info("Checking for updates...")

    # Get latest release info
    latest_release = get_latest_release_info()
    if not latest_release:
        return False

    latest_version_tag = latest_release.get("tag_name")
    if not latest_version_tag:
        logger.error("Malformed release data - no tag_name found")
        print("Malformed release data! Reinstall manually or open an issue on GitHub for help!")
        return False

    # Get current version
    try:
        current_version_str = get_current_version()

        # Normalize both versions for proper comparison
        current_normalized = normalize_version_string(
            current_version_str.split("+")[0]
        )  # Remove git info
        latest_normalized = normalize_version_string(latest_version_tag)

        print(f"Current version: {current_version_str}")
        print(f"Latest version: {latest_version_tag}")

        logger.debug("Normalized current: %s", current_normalized)
        logger.debug("Normalized latest: %s", latest_normalized)

        # Use packaging library for proper version comparison
        try:
            current_version_obj = version.parse(current_normalized)
            latest_version_obj = version.parse(latest_normalized)

            if latest_version_obj > current_version_obj:
                print("🆕 Updates are available!")
                print(
                    "Note: Your previous custom settings might be preserved, but please backup important data."
                )
                return True
            elif latest_version_obj == current_version_obj:
                print("✅ my-unicorn is up to date")
                return False
            else:
                print("ℹ️  You are using a development version")
                return False

        except Exception as e:
            logger.error("Error parsing versions: %s", e)
            print(f"Error comparing versions: {e}")
            return False

    except PackageNotFoundError:
        logger.error("Current package not found")
        print("Error: my-unicorn package not found. Please reinstall.")
        return False


def perform_update() -> bool:
    """Update by doing a fresh git clone into INSTALL_DIR/source,
    copying only the package and scripts over, then invoking
    the installer script in update mode.
    """
    source_dir = INSTALL_DIR / "source"
    installer = INSTALL_DIR / "my-unicorn-installer.sh"

    try:
        # 1) Prepare fresh source tree
        if source_dir.exists():
            logger.info("Removing old source at %s", source_dir)
            shutil.rmtree(source_dir)
        source_dir.mkdir(parents=True)

        # 2) Clone into source_dir
        logger.info("Cloning into %s", source_dir)
        subprocess.run(["git", "clone", f"{GITHUB}.git", str(source_dir)], check=True)

        # 3) Copy over only the package code and scripts
        logger.info("Copying code + scripts into %s", INSTALL_DIR)
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)

        # Copy over the package code, scripts, and pyproject.toml, my-unicorn-installer.sh
        for name in ("my_unicorn", "scripts", "pyproject.toml", "my-unicorn-installer.sh"):
            src = source_dir / name
            dst = INSTALL_DIR / name

            # Remove the old directory (but keep venv/)
            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()

            # Copy fresh
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        # 4) Invoke the installer in update mode
        if not installer.exists():
            logger.error("Installer script missing at %s", installer)
            print("❌ Installer script not found.")
            return False

        print("🚀 Running installer in UPDATE mode…")
        result = subprocess.run(
            ["bash", str(installer), "update"],
            cwd=str(INSTALL_DIR),
            check=False,
        )

        if result.returncode != 0:
            print(f"❌ Installer exited with {result.returncode}")
            return False

        # 5) Clean up source_dir
        shutil.rmtree(source_dir)
        print("✅ Update successful!")
        return True

    except Exception as e:
        logger.exception("Update failed: %s", e)
        print(f"❌ Update failed: {e}")
        return False


if __name__ == "__main__":
    # Simple CLI for testing
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        check_for_update()
    elif len(sys.argv) > 1 and sys.argv[1] == "--update":
        if check_for_update():
            perform_update()
    else:
        display_current_version()
