"""AppImage installation orchestration.

This module consolidates all installation logic:
  - InstallHandler       — public façade; entry point for callers
  - install_from_catalog — catalog-based install path
  - install_from_url     — GitHub URL-based install path
  - install_workflow     — shared core download + post-processing workflow
  - fetch_release        — thin GitHub API wrapper used by both paths
  - build_url_install_config — builds a v2-format config for URL installs
  - print_install_summary    — CLI output helpers
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

from my_unicorn.constants import (
    ERROR_NO_APPIMAGE_ASSET,
    ERROR_NO_RELEASE_FOUND,
    InstallSource,
)
from my_unicorn.core.api import Asset, GitHubClient, Release, get_github_config
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.post_download import (
    OperationType,
    PostDownloadContext,
    PostDownloadProcessor,
)
from my_unicorn.core.protocols.progress import (
    NullProgressReporter,
    ProgressReporter,
)
from my_unicorn.exceptions import (
    InstallationError,
    InstallError,
    VerificationError,
)
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import select_best_appimage_asset
from my_unicorn.utils.error_formatters import build_install_error_result
from my_unicorn.utils.github_utils import parse_github_url

if TYPE_CHECKING:
    from collections.abc import Callable

    import aiohttp

    from my_unicorn.config import ConfigManager


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# CLI display helpers
# ---------------------------------------------------------------------------


def _categorize_results(results: list[dict[str, Any]]) -> dict[str, list]:
    """Categorize installation results by status."""
    already_installed = [
        r for r in results if r.get("status") == "already_installed"
    ]
    newly_installed = [
        r
        for r in results
        if r.get("success", False) and r.get("status") != "already_installed"
    ]
    failed = [r for r in results if not r.get("success", False)]
    with_warnings = [r for r in newly_installed if r.get("warning")]

    return {
        "already_installed": already_installed,
        "newly_installed": newly_installed,
        "failed": failed,
        "with_warnings": with_warnings,
    }


def _print_all_already_installed(results: list[dict[str, Any]]) -> None:
    """Print message when all apps are already installed."""
    logger.info(
        "✅ All %s specified app(s) are already installed:", len(results)
    )
    for result in results:
        logger.info("   • %s", result.get("name", "Unknown"))


def _print_result_line(result: dict[str, Any]) -> None:
    """Print a single installation result line.

    Args:
        result (dict[str, Any]): The result of an installation attempt.

    Returns:
        None

    Prints:
        A formatted line showing the result of an installation attempt.
        %25s: right-aligns the string to 25 characters
        %-25s: left-aligns the string to 25 characters
    """
    app_name = result.get("name", "Unknown")

    if not result.get("success", False):
        logger.error("%-25s ❌ Installation failed", app_name)
        logger.error("%-25s    → %s", "", result.get("error", "Unknown error"))
        return

    if result.get("status") == "already_installed":
        logger.info("%-25s ℹ️  Already installed", app_name)
        return

    version = result.get("version", "")
    status_msg = f"✅ {version}" if version else "✅ Installed"
    logger.info("%-25s %s", app_name, status_msg)

    if result.get("warning"):
        logger.warning("%-25s    ⚠️  %s", "", result["warning"])


def _print_statistics(categories: dict[str, list]) -> None:
    """Print final installation statistics."""
    if categories["newly_installed"]:
        count = len(categories["newly_installed"])
        logger.info("🎉 Successfully installed %s app(s)", count)
    if categories["with_warnings"]:
        count = len(categories["with_warnings"])
        logger.warning("⚠️  %s app(s) installed with warnings", count)
    if categories["already_installed"]:
        count = len(categories["already_installed"])
        logger.info("ℹ️  %s app(s) already installed", count)
    if categories["failed"]:
        count = len(categories["failed"])
        logger.error("❌ %s app(s) failed to install", count)


def print_install_summary(results: list[dict[str, Any]]) -> None:
    """Print an installation summary to stdout."""
    if not results:
        logger.info("No installations completed")
        return

    categories = _categorize_results(results)

    if len(categories["already_installed"]) == len(results):
        _print_all_already_installed(results)
        return

    logger.info("📦 Installation Summary:")
    logger.info("-" * 50)

    for result in results:
        _print_result_line(result)

    _print_statistics(categories)


def display_no_targets_error() -> None:
    """Display error when no installation targets are specified."""
    logger.error("❌ No targets specified.")
    logger.info("💡 Use 'my-unicorn catalog' to see available catalog apps.")


# ---------------------------------------------------------------------------
# Core workflow helpers
# ---------------------------------------------------------------------------


async def fetch_release(
    github_client: GitHubClient,
    owner: str,
    repo: str,
) -> Release:
    """Fetch the latest release from GitHub.

    Args:
        github_client: Authenticated GitHub API client.
        owner: Repository owner.
        repo: Repository name.

    Returns:
        Release object whose assets are pre-filtered for x86_64 Linux.

    Raises:
        InstallError: If no release is found or the API call fails.

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
        raise
    except Exception as error:
        msg = f"Failed to fetch release for {owner}/{repo}"
        raise InstallError(
            msg,
            context={"owner": owner, "repo": repo},
            cause=error,
        ) from error


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

    Downloads the AppImage asset, then delegates verification, icon
    extraction, desktop entry creation, and config management to
    PostDownloadProcessor.

    Args:
        app_name: Human-readable application name.
        asset: GitHub release asset to download.
        release: Release metadata.
        app_config: v2-format application configuration dict.
        source: ``InstallSource.CATALOG`` or ``InstallSource.URL``.
        download_service: Service that performs the HTTP download.
        post_download_processor: Handles all post-download steps.
        **options:
            verify_downloads (bool): Run checksum verification. Default True.
            download_dir (Path): Where to save the downloaded file.

    Returns:
        Result dict with keys: success, target, name, path, source,
        version, verification, warning, icon, config, desktop.

    Raises:
        InstallationError: If post-download processing reports failure.
        InstallError: Wraps any unexpected exception with context.

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
        download_path = download_dir / asset.name
        logger.info("Downloading %s", app_name)
        downloaded_path = await download_service.download_appimage(
            asset, download_path
        )

        github_config = get_github_config(app_config)

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

        result = await post_download_processor.process(context)

        if not result.success:
            msg = result.error or "Post-download processing failed"
            raise InstallationError(msg)

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
        raise
    except Exception as error:
        raise InstallError(
            str(error),
            context={
                "app_name": app_name,
                "asset_name": asset.name,
                "source": source,
            },
            cause=error,
        ) from error


# ---------------------------------------------------------------------------
# Config builder (used by the URL install path)
# ---------------------------------------------------------------------------


def build_url_install_config(
    app_name: str,
    owner: str,
    repo: str,
    prerelease: bool,
) -> dict[str, Any]:
    """Build a v2-format app-config dict for URL-based installations.

    Args:
        app_name: Application name (usually the repo name).
        owner: GitHub repository owner.
        repo: GitHub repository name.
        prerelease: Whether pre-release versions are acceptable.

    Returns:
        Minimal v2 app-config suitable for passing to install_workflow.

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
            "method": "digest",
        },
        "icon": {
            "method": "extraction",
            "filename": "",
        },
    }


# ---------------------------------------------------------------------------
# Catalog install path
# ---------------------------------------------------------------------------


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
    """Install an app from the catalog.

    Args:
        app_name: Catalog entry name.
        config_manager: Reads catalog and global config from disk.
        download_service: Performs the HTTP download.
        post_download_processor: Runs all post-download steps.
        fetch_release_fn: Async callable ``(owner, repo) -> Release``.
        install_workflow_fn: Async callable that runs the core workflow.
        **options: Forwarded to install_workflow_fn (e.g. verify_downloads).

    Returns:
        Result dict (see install_workflow for key descriptions).

    """

    def _raise_no_asset() -> None:
        raise InstallError(
            ERROR_NO_APPIMAGE_ASSET,
            context={
                "app_name": app_name,
                "owner": owner,
                "repo": repo,
                "source": InstallSource.CATALOG,
            },
        )

    logger.debug("Starting catalog install: app=%s", app_name)

    try:
        app_config = config_manager.load_catalog(app_name)

        github_config = get_github_config(app_config)
        owner = github_config.owner
        repo = github_config.repo

        characteristic_suffix = (
            app_config.get("appimage", {})
            .get("naming", {})
            .get("architectures", [])
        )

        release = await fetch_release_fn(owner, repo)

        asset = select_best_appimage_asset(
            release,
            preferred_suffixes=characteristic_suffix,
            installation_source=InstallSource.CATALOG,
        )
        if asset is None:
            _raise_no_asset()

        return await install_workflow_fn(
            app_name=app_name,
            asset=asset,
            release=release,
            app_config=app_config,
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
            context={"app_name": app_name, "source": InstallSource.CATALOG},
            cause=error,
        )
        logger.error("Failed to install %s: %s", app_name, install_error)
        return build_install_error_result(
            install_error, app_name, is_url=False
        )


# ---------------------------------------------------------------------------
# URL install path
# ---------------------------------------------------------------------------
#


def validate_github_identifiers(owner: str, repo: str) -> None:
    """Validate GitHub owner and repo strings before any API call.

    Delegates to ``get_github_config`` which runs
    ``ConfigurationValidator.validate_app_config`` internally.  Raising
    early here prevents malformed or malicious identifiers from ever
    reaching the network layer.

    Args:
        owner: GitHub repository owner or organisation name.
        repo: GitHub repository name.

    Raises:
        ValueError: If either identifier fails security validation.

    Example:
        >>> validate_github_identifiers("Cyber-Syntax", "my-unicorn")  # ok
        >>> validate_github_identifiers("bad/../owner", "repo")        # raises

    """
    get_github_config({"source": {"owner": owner, "repo": repo}})


async def validate_and_fetch_release(
    owner: str,
    repo: str,
    *,
    fetch_release_fn: Callable[..., Any],
) -> tuple[Release, Asset]:
    """Validate GitHub identifiers, fetch the release, and pick an AppImage.

    Args:
        owner: Repository owner (validated for security before use).
        repo: Repository name.
        fetch_release_fn: Async callable ``(owner, repo) -> Release``.

    Returns:
        ``(release, appimage_asset)`` tuple.

    Raises:
        InstallError: If no compatible AppImage is found.

    """
    # Security check: reject bad identifiers before touching the network.
    validate_github_identifiers(owner, repo)

    release = await fetch_release_fn(owner, repo)

    asset = select_best_appimage_asset(
        release, installation_source=InstallSource.URL
    )
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
    post_download_processor: PostDownloadProcessor,
    *,
    fetch_release_fn: Callable[..., Any],
    install_workflow_fn: Callable[..., Any],
    **options: Any,
) -> dict[str, Any]:
    """Install an app from a GitHub URL.

    Args:
        github_url: Full GitHub repository URL.
        download_service: Performs the HTTP download.
        github_client: GitHub API client (used for URL-level validation).
        post_download_processor: Runs all post-download steps.
        fetch_release_fn: Async callable ``(owner, repo) -> Release``.
        install_workflow_fn: Async callable that runs the core workflow.
        **options: Forwarded to install_workflow_fn.

    Returns:
        Result dict (see install_workflow for key descriptions).

    """
    logger.debug("Starting URL install: url=%s", github_url)

    try:
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

        release, asset = await validate_and_fetch_release(
            owner, repo, fetch_release_fn=fetch_release_fn
        )

        app_config = build_url_install_config(
            app_name, owner, repo, prerelease
        )

        return await install_workflow_fn(
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


# ---------------------------------------------------------------------------
# Public facade
# ---------------------------------------------------------------------------


class InstallHandler:
    """Handles AppImage installation orchestration from catalog or URL sources.

    This is the primary entry point for callers.  Internal logic is split
    into module-level functions so each piece can be tested independently,
    and InstallHandler wires them together while owning the service objects.

    Attributes:
        download_service: Service for downloading AppImage files.
        storage_service: Service for file storage operations.
        config_manager: Configuration manager for app settings.
        github_client: GitHub API client for release fetching.
        progress_reporter: Progress reporter for tracking installation steps.
        post_download_processor: Processor for post-download workflow.

    Thread Safety:
        Each install operation should use a separate InstallHandler instance
        for isolated progress tracking. The download service manages its own
        internal progress state.

    Example:
        >>> container = ServiceContainer(config, progress)
        >>> handler = container.create_install_handler()
        >>> result = await handler.install_from_catalog("firefox")
        >>> if result["success"]:
        ...     logger.info(f"Installed to {result['path']}")

    """

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        post_download_processor: PostDownloadProcessor,
        progress_reporter: ProgressReporter | None = None,
    ) -> None:
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client
        self.progress_reporter = progress_reporter or NullProgressReporter()
        self.post_download_processor = post_download_processor

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create_default(
        cls,
        session: aiohttp.ClientSession,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        install_dir: Path,
        progress_reporter: ProgressReporter | None = None,
    ) -> InstallHandler:
        """Create an InstallHandler with sensible default dependencies.

        Args:
            session: Active aiohttp session used for all downloads.
            config_manager: Loaded configuration manager.
            github_client: Authenticated GitHub client.
            install_dir: Directory where AppImages will be stored.
            progress_reporter: Optional UI progress reporter.

        Returns:
            Fully configured InstallHandler.

        """
        download_service = DownloadService(session, progress_reporter)
        storage_service = FileOperations(install_dir)
        post_download_processor = PostDownloadProcessor(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            progress_reporter=progress_reporter,
        )
        return cls(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
            post_download_processor=post_download_processor,
            progress_reporter=progress_reporter,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def install_from_catalog(
        self,
        app_name: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install an app from the catalog.

        Args:
            app_name: Catalog entry name.
            **options: Forwarded to the core workflow (verify_downloads, etc.).

        Returns:
            Result dict with ``success`` key and error details on failure.

        """
        return await install_from_catalog(
            app_name=app_name,
            config_manager=self.config_manager,
            download_service=self.download_service,
            post_download_processor=self.post_download_processor,
            fetch_release_fn=self._fetch_release,
            install_workflow_fn=self._install_workflow,
            **options,
        )

    async def install_from_url(
        self,
        github_url: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install an app from a GitHub URL.

        Args:
            github_url: Full GitHub repository URL.
            **options: Forwarded to the core workflow.

        Returns:
            Result dict with ``success`` key and error details on failure.

        """
        return await install_from_url(
            github_url=github_url,
            download_service=self.download_service,
            github_client=self.github_client,
            post_download_processor=self.post_download_processor,
            fetch_release_fn=self._fetch_release,
            install_workflow_fn=self._install_workflow,
            **options,
        )

    async def install_multiple(
        self,
        catalog_apps: list[str],
        url_apps: list[str],
        **options: Any,
    ) -> list[dict[str, Any]]:
        """Install multiple apps concurrently.

        Failures are captured per-app and returned as error result dicts
        rather than raising, so a single failure does not abort the batch.

        Args:
            catalog_apps: Catalog entry names to install.
            url_apps: GitHub URLs to install from.
            **options: Forwarded to each individual install call.
                concurrent (int): Max simultaneous downloads.

        Returns:
            List of result dicts, one per app/URL.

        """
        global_config = self.config_manager.load_global_config()
        concurrent = options.get(
            "concurrent",
            global_config["max_concurrent_downloads"],
        )
        semaphore = asyncio.Semaphore(int(concurrent))

        async def install_one(app_or_url: str, is_url: bool) -> dict[str, Any]:
            async with semaphore:
                try:
                    if is_url:
                        return await self.install_from_url(
                            app_or_url, **options
                        )
                    return await self.install_from_catalog(
                        app_or_url, **options
                    )
                except InstallationError as error:
                    logger.error(
                        "Installation error for %s: %s", app_or_url, error
                    )
                    return build_install_error_result(
                        error, app_or_url, is_url
                    )
                except (InstallError, VerificationError) as error:
                    logger.error(
                        "Domain error installing %s: %s", app_or_url, error
                    )
                    return build_install_error_result(
                        error, app_or_url, is_url
                    )
                except Exception as error:
                    source = (
                        InstallSource.URL if is_url else InstallSource.CATALOG
                    )
                    install_error = InstallError(
                        str(error),
                        context={"target": app_or_url, "source": source},
                        cause=error,
                    )
                    logger.error(
                        "Unexpected error installing %s: %s",
                        app_or_url,
                        install_error,
                    )
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": str(install_error),
                        "source": source,
                    }

        tasks = [install_one(app, is_url=False) for app in catalog_apps]
        tasks += [install_one(url, is_url=True) for url in url_apps]
        return await asyncio.gather(*tasks)

    # ------------------------------------------------------------------
    # Private helpers (kept so tests can mock _fetch_release /
    # _install_workflow at the instance level)
    # ------------------------------------------------------------------

    async def _fetch_release(self, owner: str, repo: str) -> Release:
        """Thin wrapper around the module-level fetch_release."""
        return await fetch_release(self.github_client, owner, repo)

    async def _install_workflow(
        self,
        app_name: str,
        asset: Any,
        release: Any,
        app_config: dict[str, Any],
        source: str,
        download_service: DownloadService | None = None,
        post_download_processor: Any | None = None,
        **options: Any,
    ) -> dict[str, Any]:
        """Thin wrapper around the module-level install_workflow."""
        return await install_workflow(
            app_name=app_name,
            asset=asset,
            release=release,
            app_config=app_config,
            source=source,
            download_service=download_service or self.download_service,
            post_download_processor=(
                post_download_processor or self.post_download_processor
            ),
            **options,
        )
