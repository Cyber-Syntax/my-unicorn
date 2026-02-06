"""Core installation workflow logic.

This module contains the shared workflow execution logic for both catalog
and URL-based installations, including asset downloading, verification,
icon extraction, and configuration management.
"""

from pathlib import Path
from typing import Any

from my_unicorn.constants import ERROR_NO_RELEASE_FOUND
from my_unicorn.core.download import DownloadService
from my_unicorn.core.github import (
    Asset,
    GitHubClient,
    Release,
    get_github_config,
)
from my_unicorn.core.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


async def install_workflow(
    app_name: str,
    asset: Asset,
    release: Release,
    app_config: dict[str, Any],
    source: str,
    download_service: DownloadService,
    post_download_processor: PostDownloadProcessor,
    **options: Any,
) -> dict[str, Any]:
    """Core install workflow shared by catalog and URL installs.

    This workflow handles downloading the AppImage asset, verifying it,
    extracting icons, and creating desktop entries.

    Args:
        app_name: Name of the application
        asset: GitHub asset to download
        release: Release information
        app_config: App configuration
        source: Install source (InstallSource.CATALOG or InstallSource.URL)
        download_service: Service for downloading files
        post_download_processor: Processor for post-download operations
        **options: Install options (verify_downloads, download_dir)

    Returns:
        Installation result dictionary with verification, icon, config,
        and desktop entry results

    Raises:
        InstallationError: If verification fails or installation step fails
        OSError: If file operations fail (permissions, disk space)
        aiohttp.ClientError: If download fails

    """
    verify = options.get("verify_downloads", True)
    download_dir = options.get("download_dir", Path.cwd())

    logger.debug(
        "Install workflow: app=%s, verify=%s, source=%s",
        app_name,
        verify,
        source,
    )

    try:
        # 1. Download
        download_path = download_dir / asset.name
        logger.info("Downloading %s", app_name)
        downloaded_path = await download_service.download_appimage(
            asset, download_path
        )

        # 2. Use PostDownloadProcessor for all post-download operations
        github_config = get_github_config(app_config)

        # Create processing context
        context = PostDownloadContext(
            app_name=app_name,
            downloaded_path=downloaded_path,
            asset=asset,
            release=release,
            app_config=app_config,
            catalog_entry=None,
            operation_type=OperationType.INSTALL,
            owner=github_config.owner,
            repo=github_config.repo,
            verify_downloads=verify,
            source=source,
        )

        # Process download
        result = await post_download_processor.process(context)

        if not result.success:
            msg = result.error or "Post-download processing failed"
            raise InstallationError(msg)

        # Build result dictionary
        return {
            "success": True,
            "target": app_name,
            "name": app_name,
            "path": str(result.install_path),
            "source": source,
            "version": release.version,
            "verification": result.verification_result,
            "warning": (
                result.verification_result.get("warning")
                if result.verification_result
                else None
            ),
            "icon": result.icon_result,
            "config": result.config_result,
            "desktop": result.desktop_result,
        }

    except (InstallError, VerificationError):
        # Domain exceptions already have context, re-raise as-is
        raise
    except Exception as error:
        # Wrap unexpected exceptions in InstallError with context
        raise InstallError(
            str(error),
            context={
                "app_name": app_name,
                "asset_name": asset.name,
                "source": source,
            },
            cause=error,
        ) from error


async def fetch_release(
    github_client: GitHubClient, owner: str, repo: str
) -> Release:
    """Fetch release data from GitHub.

    Args:
        github_client: GitHub API client
        owner: GitHub repository owner
        repo: GitHub repository name

    Returns:
        Release object with assets

    Raises:
        InstallError: If no release found or fetch fails

    """
    try:
        release = await github_client.get_latest_release(owner, repo)
        if not release:
            msg = ERROR_NO_RELEASE_FOUND.format(owner=owner, repo=repo)
            raise InstallError(
                msg,
                context={"owner": owner, "repo": repo},
            )
        return release
    except InstallError:
        # Re-raise domain exceptions as-is
        raise
    except Exception as error:
        msg = f"Failed to fetch release for {owner}/{repo}"
        raise InstallError(
            msg,
            context={"owner": owner, "repo": repo},
            cause=error,
        ) from error
