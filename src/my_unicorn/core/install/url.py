"""URL-based application installation.

This module handles installation of applications from GitHub URLs, including
URL parsing and validation, release fetching, and AppImage asset selection.
"""

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import ERROR_NO_APPIMAGE_ASSET, InstallSource
from my_unicorn.core.download import DownloadService
from my_unicorn.core.github import (
    GitHubClient,
    get_github_config,
    parse_github_url,
)
from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.exceptions import InstallError, VerificationError
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.error_formatters import build_install_error_result

from .catalog import build_url_install_config

if TYPE_CHECKING:
    from my_unicorn.core.github import Asset, Release

logger = get_logger(__name__)


async def validate_and_fetch_release(
    owner: str,
    repo: str,
    *,
    fetch_release_fn: Callable[..., Any],
) -> tuple["Release", "Asset"]:
    """Validate GitHub identifiers and fetch release with AppImage.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        fetch_release_fn: Callable to fetch release from GitHub

    Returns:
        Tuple of (release, appimage_asset)

    Raises:
        ValueError: If GitHub identifiers are invalid or no AppImage found
        aiohttp.ClientError: If GitHub API request fails

    """
    # Use injected function
    _fetch_release = fetch_release_fn

    # Validate GitHub identifiers for security
    config = {"source": {"owner": owner, "repo": repo}}
    get_github_config(config)  # Validates identifiers

    # Fetch latest release (already filtered for x86_64 Linux)
    release = await _fetch_release(owner, repo)

    # Select best AppImage (filters unstable versions for URLs)
    asset = select_best_appimage_asset(
        release, installation_source=InstallSource.URL
    )
    # Asset is guaranteed non-None (raise_on_not_found=True by default)
    if asset is None:
        raise InstallError(
            ERROR_NO_APPIMAGE_ASSET,
            context={
                "owner": owner,
                "repo": repo,
                "source": InstallSource.URL,
            },
        )

    return release, asset


async def install_from_url(
    github_url: str,
    download_service: DownloadService,
    github_client: GitHubClient,
    post_download_processor: PostDownloadProcessor,
    *,
    fetch_release_fn: Callable[..., Any],
    install_workflow_fn: Callable[..., Any],
    **options: Any,
) -> dict[str, Any]:
    """Install app from GitHub URL.

    Args:
        github_url: GitHub repository URL
        download_service: Service for downloading files
        github_client: GitHub API client
        post_download_processor: Processor for post-download operations
        fetch_release_fn: Callable to fetch release from GitHub
        install_workflow_fn: Callable to execute install workflow
        **options: Install options

    Returns:
        Installation result dictionary with 'success' key and error details
        if installation failed

    Raises:
        InstallationError: If URL is invalid or installation workflow fails
        ValueError: If no AppImage asset found in release or URL parsing
            fails
        aiohttp.ClientError: If GitHub API request fails

    """
    # Use injected functions
    _fetch_release = fetch_release_fn
    _install_workflow = install_workflow_fn

    logger.debug("Starting URL install: url=%s", github_url)

    try:
        # Parse GitHub URL
        url_info = parse_github_url(github_url)
        owner = url_info["owner"]
        repo = url_info["repo"]
        app_name = url_info.get("app_name") or repo
        prerelease = url_info.get("prerelease", False)

        logger.debug(
            "Parsed GitHub URL: owner=%s, repo=%s, app_name=%s",
            owner,
            repo,
            app_name,
        )

        # Validate and fetch release with AppImage
        release, asset = await validate_and_fetch_release(
            owner, repo, fetch_release_fn=_fetch_release
        )

        # Build app config template for URL install
        app_config = build_url_install_config(
            app_name, owner, repo, prerelease
        )

        # Execute install workflow
        return await _install_workflow(
            app_name=app_name,
            asset=asset,
            release=release,
            app_config=app_config,
            source=InstallSource.URL,
            download_service=download_service,
            post_download_processor=post_download_processor,
            **options,
        )

    except (InstallError, VerificationError) as error:
        logger.error("Failed to install from URL %s: %s", github_url, error)
        return build_install_error_result(error, github_url, is_url=True)
    except Exception as error:
        install_error = InstallError(
            str(error),
            context={"url": github_url, "source": InstallSource.URL},
            cause=error,
        )
        logger.error(
            "Failed to install from URL %s: %s", github_url, install_error
        )
        return build_install_error_result(
            install_error, github_url, is_url=True
        )
