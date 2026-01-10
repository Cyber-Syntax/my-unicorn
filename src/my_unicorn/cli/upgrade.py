"""my-unicorn cli upgrade module.

This module handles updating the my-unicorn package itself by using uv's
tool install with upgrade from the official GitHub repository.

Key Design Decisions:

1. **Cache Disabled for Version Checks**: The upgrade command intentionally
   disables caching for release fetches (use_cache=False, ignore_cache=True).
   This ensures users always check against the latest available version.
   Rationale:
   - CLI tools must use the latest version for security and reliability
   - Users expect fresh results when checking for updates
   - Cache TTL (24 hours default) could hide critical updates

2. **GitHub API Rate Limiting**: Rate limiting is acceptable for this use case.
   - Without token: 60 requests/hour (sufficient for manual checks)
   - With token (via keyring): 5000 requests/hour
   - Users run upgrades infrequently, so rate limits are not a concern

3. **Prerelease-Only Handling**: Currently fetches latest prerelease. When
   my-unicorn publishes stable releases, change fetch_latest_prerelease()
   to fetch_latest_release() in _fetch_latest_prerelease_version().
   See NOTE below for details.
"""

import asyncio
import os
import re
import shutil

import aiohttp
from packaging.version import InvalidVersion, Version

from my_unicorn import __version__
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


_PRERELEASE_MAP = {
    "alpha": "a",
    "beta": "b",
    "rc": "rc",
}

_PRERELEASE_RE = re.compile(
    r"""
    ^
    (?P<base>\d+\.\d+\.\d+)
    (?:-
        (?P<label>alpha|beta|rc)
        (?P<num>\d*)?
    )?
    $
    """,
    re.VERBOSE,
)


def normalize_version(v: str) -> str:
    """Normalize semver-like versions to PEP 440."""
    v = v.lstrip("v")

    match = _PRERELEASE_RE.match(v)
    if not match:
        return v

    base = match.group("base")
    label = match.group("label")
    num = match.group("num") or "0"

    if not label:
        return base

    pep_label = _PRERELEASE_MAP[label]
    return f"{base}{pep_label}{num}"


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
    except Exception as e:
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


# NOTE: Prerelease handling - update this when stable releases are published.
# Currently my-unicorn only publishes prerelease versions. When transitioning
# to stable releases, replace fetch_latest_prerelease() with
# fetch_latest_release() to prioritize stable versions over prereleases.
# This is a YAGNI decision - we'll implement stable release logic when it's
# actually needed.
async def _fetch_latest_prerelease_version() -> str | None:
    """Fetch the latest prerelease version from GitHub releases.

    Intentionally disables caching to always get fresh version data.
    Cache is disabled because:
    - Users need accurate version information for security and reliability
    - Upgrade decisions must be based on current available versions
    - Manual commands users run infrequently don't stress GitHub API limits
    """

    async with aiohttp.ClientSession() as session:
        # Cache is intentionally disabled here to ensure users always check
        # against the latest available version. This is safe because:
        # 1. GitHub API allows 60 requests/hour without auth token
        # 2. Users run upgrade checks infrequently
        # 3. Accuracy of version information is critical for CLI security
        fetcher = ReleaseFetcher(
            GITHUB_OWNER,
            GITHUB_REPO,
            session,
            use_cache=False,
        )
        try:
            release = await fetcher.fetch_latest_prerelease(ignore_cache=True)
        except Exception as exc:  # noqa: BLE001
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

    Checks if installation is dev-based first. If dev installation is detected,
    always upgrade to production (git repo version). Otherwise, fetches the
    latest version from GitHub API (cache disabled) to ensure accurate
    upgrade decisions.

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
    """Check if a newer my-unicorn release is available.

    Always queries GitHub API for fresh version data (cache disabled).

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
