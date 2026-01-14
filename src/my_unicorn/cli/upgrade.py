"""my-unicorn cli upgrade module.

Handles self-updating the my-unicorn package using uv's tool management.
Disables caching for version checks to ensure latest version detection.

See docs/upgrade.md for detailed design rationale.
"""

import asyncio
import os
import shutil

import aiohttp
from packaging.version import InvalidVersion, Version

from my_unicorn import __version__
from my_unicorn.domain.version import normalize_version
from my_unicorn.infrastructure.github.release_fetcher import ReleaseFetcher
from my_unicorn.logger import get_logger

logger = get_logger(__name__)

GITHUB_OWNER = "Cyber-Syntax"
GITHUB_REPO = "my-unicorn"
GITHUB_URL = f"https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}"


def _detect_dev_installation() -> bool:
    """Detect if current installation is a development version.

    Checks if my-unicorn is installed as a local file path (dev) or from
    a git repository (production). Development installations use file:// URIs,
    while production installations use git+https:// URIs.

    Returns:
        True if development installation detected, False otherwise.
    """
    try:
        return asyncio.run(_run_uv_tool_list())
    except OSError as e:
        logger.debug("Could not detect installation type: %s", e)
        return False


async def _run_uv_tool_list() -> bool:
    """Run 'uv tool list --show-version-specifiers' and detect install type.

    Returns:
        True if my-unicorn is a dev installation (file://),
        False if production.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "uv",
            "tool",
            "list",
            "--show-version-specifiers",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await process.communicate()
        output = stdout.decode("utf-8", errors="ignore")

        for line in output.splitlines():
            if "my-unicorn" in line:
                return "file://" in line
        return False  # noqa: TRY300
    except OSError as e:
        logger.debug("Error running uv tool list: %s", e)
        return False


def perform_self_update() -> bool:
    """Update my-unicorn using uv tool install --upgrade from git.

    This ensures a reliable update from the official repository,
    regardless of how it was originally installed. Uses os.execvp to replace
    the current process, ensuring the upgrade completes properly.

    Returns:
        False if upgrade could not be started.
        Does not return on success (process replaced by execvp).

    Note:
        Users must restart their terminal after a successful upgrade to
        refresh the command cache and use the updated version.

    """
    logger.debug("Starting upgrade to my-unicorn...")
    logger.debug(
        "Executing: uv tool install --upgrade git+%s",
        GITHUB_URL,
    )

    uv_executable = shutil.which("uv") or "uv"

    try:
        # Use os.execvp to replace current process with uv install
        # This ensures the upgrade completes properly
        os.execvp(  # noqa: S606
            uv_executable,
            [
                uv_executable,
                "tool",
                "install",
                "--upgrade",
                f"git+{GITHUB_URL}",
            ],
        )
    except (OSError, FileNotFoundError) as e:
        logger.exception("Update failed")
        logger.info("❌ Update failed: %s", e)
        return False

    logger.error("Failed to execute uv upgrade")
    logger.info("❌ Failed to execute upgrade command")
    return False


def _is_candidate_newer(current_version: str, candidate_version: str) -> bool:
    """Return True if candidate version is newer than current.

    Parsing failures on the current version are treated as requiring an
    upgrade when the candidate parses successfully.
    """
    try:
        current = Version(normalize_version(current_version))
    except InvalidVersion:
        try:
            Version(normalize_version(candidate_version))
        except InvalidVersion:
            return candidate_version > current_version
        return True

    try:
        candidate = Version(normalize_version(candidate_version))
    except InvalidVersion:
        return False

    return candidate > current


# TODO: Update to fetch_latest_release() when stable releases are published
async def _fetch_latest_prerelease_version() -> str | None:
    """Fetch the latest prerelease version from GitHub (cache disabled)."""

    async with aiohttp.ClientSession() as session:
        fetcher = ReleaseFetcher(
            GITHUB_OWNER,
            GITHUB_REPO,
            session,
            use_cache=False,
        )
        try:
            release = await fetcher.fetch_latest_prerelease(ignore_cache=True)
        except (aiohttp.ClientError, TimeoutError) as exc:
            logger.warning(
                "Unable to fetch latest release for %s/%s: %s",
                GITHUB_OWNER,
                GITHUB_REPO,
                exc,
            )
            return None

    return release.version or release.original_tag_name


async def should_perform_self_update(
    current_version: str,
) -> tuple[bool, str | None]:
    """Determine if a newer release is available.

    Checks for dev installation first. Dev installations always upgrade to
    production. Otherwise, fetches latest version from GitHub API (cache
    disabled) to ensure accurate upgrade decisions.

    Returns:
        A tuple of (should_upgrade, latest_version) where:
        - should_upgrade: True if upgrade needed (dev install or newer version)
        - latest_version: The latest version string, or None if unavailable
    """
    is_dev_install = await _run_uv_tool_list()

    if is_dev_install:
        logger.info("🔧 Development installation detected")
        latest_version = await _fetch_latest_prerelease_version()
        return True, latest_version

    latest_version = await _fetch_latest_prerelease_version()

    if not latest_version:
        logger.warning(
            "Could not determine latest my-unicorn version; proceeding "
            "with upgrade.",
        )
        return True, None

    if not latest_version.strip():
        return True, None

    if not _is_candidate_newer(current_version, latest_version):
        return False, latest_version

    return True, latest_version


async def check_for_self_update() -> bool:
    """Check if a newer my-unicorn release is available (cache disabled).

    Returns:
        True if a newer version is available, False otherwise.
    """

    should_upgrade, _ = await should_perform_self_update(__version__)
    return should_upgrade


async def perform_self_update_async() -> bool:
    """Async wrapper for perform_self_update.

    Allows perform_self_update() to be called from async contexts.

    Returns:
        False if update could not be started.
        Does not return on success (process replaced by execvp).

    """
    return perform_self_update()
