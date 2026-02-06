"""Catalog-based application installation.

This module handles installation of applications directly from the catalog,
including configuration loading, GitHub repository validation, and AppImage
asset selection.
"""

from collections.abc import Callable
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.constants import ERROR_NO_APPIMAGE_ASSET, InstallSource
from my_unicorn.core.download import DownloadService
from my_unicorn.core.github import get_github_config
from my_unicorn.core.post_download import PostDownloadProcessor
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.error_formatters import build_install_error_result

logger = get_logger(__name__)


async def install_from_catalog(
    app_name: str,
    config_manager: ConfigManager,
    download_service: DownloadService,
    post_download_processor: PostDownloadProcessor,
    *,
    fetch_release_fn: Callable[..., Any],
    install_workflow_fn: Callable[..., Any],
    **options: Any,
) -> dict[str, Any]:
    """Install app from catalog.

    Args:
        app_name: Name of app in catalog
        config_manager: Configuration manager
        download_service: Service for downloading files
        post_download_processor: Processor for post-download operations
        fetch_release_fn: Callable to fetch release from GitHub
        install_workflow_fn: Callable to execute install workflow
        **options: Install options (verify_downloads, etc.)

    Returns:
        Installation result dictionary with 'success' key and error details
        if installation failed

    Raises:
        InstallationError: If app configuration is invalid or installation
            workflow fails
        ValueError: If no AppImage asset found in release
        aiohttp.ClientError: If GitHub API request fails

    """
    # Use injected functions
    _fetch_release = fetch_release_fn
    _install_workflow = install_workflow_fn

    logger.debug("Starting catalog install: app=%s", app_name)

    try:
        # Get app configuration (v2 format from catalog)
        app_config = config_manager.load_catalog(app_name)

        # Extract and validate GitHub configuration
        github_config = get_github_config(app_config)
        owner = github_config.owner
        repo = github_config.repo

        characteristic_suffix = (
            app_config.get("appimage", {})
            .get("naming", {})
            .get("architectures", [])
        )

        release = await _fetch_release(owner, repo)

        # Select best AppImage asset from compatible options
        asset = select_best_appimage_asset(
            release,
            preferred_suffixes=characteristic_suffix,
            installation_source=InstallSource.CATALOG,
        )
        # Asset is guaranteed non-None (raise_on_not_found=True by default)
        if asset is None:
            raise InstallError(
                ERROR_NO_APPIMAGE_ASSET,
                context={
                    "app_name": app_name,
                    "owner": owner,
                    "repo": repo,
                    "source": InstallSource.CATALOG,
                },
            )

        # Install workflow
        return await _install_workflow(
            app_name=app_name,
            asset=asset,
            release=release,
            app_config=app_config,  # type: ignore[arg-type]
            source=InstallSource.CATALOG,
            download_service=download_service,
            post_download_processor=post_download_processor,
            **options,
        )

    except InstallationError as error:
        logger.error("Failed to install %s: %s", app_name, error)
        return build_install_error_result(error, app_name, is_url=False)
    except (InstallError, VerificationError) as error:
        logger.error("Failed to install %s: %s", app_name, error)
        return build_install_error_result(error, app_name, is_url=False)
    except Exception as error:
        install_error = InstallError(
            str(error),
            context={
                "app_name": app_name,
                "source": InstallSource.CATALOG,
            },
            cause=error,
        )
        logger.error("Failed to install %s: %s", app_name, install_error)
        return build_install_error_result(
            install_error, app_name, is_url=False
        )


def build_url_install_config(
    app_name: str, owner: str, repo: str, prerelease: bool
) -> dict[str, Any]:
    """Build app config template for URL installations.

    Args:
        app_name: Application name
        owner: GitHub repository owner
        repo: GitHub repository name
        prerelease: Whether to include pre-releases

    Returns:
        App configuration dictionary in v2 format

    """
    return {
        "config_version": "2.0.0",
        "metadata": {
            "name": app_name,
            "display_name": app_name,
            "description": "",
        },
        "source": {
            "type": "github",
            "owner": owner,
            "repo": repo,
            "prerelease": prerelease,
        },
        "appimage": {
            "naming": {
                "template": "",
                "target_name": app_name,
                "architectures": ["amd64", "x86_64"],
            }
        },
        "verification": {
            "method": "digest",  # Will auto-detect checksum files
        },
        "icon": {
            "method": "extraction",
            "filename": "",
        },
    }
