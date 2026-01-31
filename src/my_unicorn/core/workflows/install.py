"""Install handler for AppImage installations.

This handler consolidates all installation logic, replacing the complex
template method pattern with a simpler, more maintainable approach.
"""

import asyncio
from pathlib import Path
from typing import Any

import aiohttp

from my_unicorn.config import ConfigManager
from my_unicorn.core.download import DownloadService
from my_unicorn.core.file_ops import FileOperations
from my_unicorn.core.github import (
    Asset,
    GitHubClient,
    Release,
    parse_github_url,
)
from my_unicorn.core.verification import VerificationService
from my_unicorn.core.workflows.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.exceptions import InstallationError
from my_unicorn.logger import get_logger
from my_unicorn.ui.display import ProgressDisplay
from my_unicorn.utils.appimage_utils import (
    select_best_appimage_asset,
    verify_appimage_download,
)
from my_unicorn.utils.config_builders import create_app_config_v2
from my_unicorn.utils.error_formatters import build_install_error_result
from my_unicorn.utils.validation import validate_github_identifier

logger = get_logger(__name__)


class InstallHandler:
    """Handles installation orchestration."""

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: ConfigManager,
        github_client: GitHubClient,
    ) -> None:
        """Initialize install handler.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            github_client: GitHub API client

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client

    @classmethod
    def create_default(
        cls,
        session: aiohttp.ClientSession,
        config_manager: ConfigManager,
        github_client: GitHubClient,
        install_dir: Path,
        progress_service: ProgressDisplay | None = None,
    ) -> "InstallHandler":
        """Create InstallHandler with default dependencies.

        Factory method for simplified instantiation with sensible defaults.

        Args:
            session: HTTP session for downloads
            config_manager: Configuration manager
            github_client: GitHub client
            install_dir: Installation directory
            progress_service: Optional progress service

        Returns:
            Configured InstallHandler instance

        """
        download_service = DownloadService(session, progress_service)
        storage_service = FileOperations(install_dir)

        return cls(
            download_service=download_service,
            storage_service=storage_service,
            config_manager=config_manager,
            github_client=github_client,
        )

    async def install_from_catalog(
        self,
        app_name: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install app from catalog.

        Args:
            app_name: Name of app in catalog
            **options: Install options (verify_downloads, etc.)

        Returns:
            Installation result dictionary

        """
        logger.debug("Starting catalog install: app=%s", app_name)

        try:
            # Get app configuration (v2 format from catalog)
            app_config = self.config_manager.load_catalog(app_name)

            # Extract source info from v2 config
            source_config = app_config.get("source", {})
            owner = source_config.get("owner", "")
            repo = source_config.get("repo", "")

            # Validate GitHub identifiers for security
            try:
                validate_github_identifier(owner, "GitHub owner")
                validate_github_identifier(repo, "GitHub repo")
            except ValueError as e:
                msg = f"Invalid GitHub configuration in catalog: {e}"
                raise InstallationError(msg, target=app_name)

            characteristic_suffix = (
                app_config.get("appimage", {})
                .get("naming", {})
                .get("architectures", [])
            )

            release = await self._fetch_release(owner, repo)

            # Select best AppImage asset from compatible options
            asset = select_best_appimage_asset(
                release,
                preferred_suffixes=characteristic_suffix,
                installation_source="catalog",
            )
            # Asset is guaranteed non-None (raise_on_not_found=True by default)
            if asset is None:
                msg = "No suitable AppImage asset found"
                raise ValueError(msg)

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release=release,
                app_config=app_config,  # type: ignore[arg-type]
                source="catalog",
                **options,
            )

        except InstallationError as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return build_install_error_result(error, app_name, is_url=False)
        except Exception as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return build_install_error_result(error, app_name, is_url=False)

    async def install_from_url(
        self,
        github_url: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install app from GitHub URL.

        Args:
            github_url: GitHub repository URL
            **options: Install options

        Returns:
            Installation result dictionary

        """
        logger.debug("Starting URL install: url=%s", github_url)

        try:
            # Parse GitHub URL
            url_info = parse_github_url(github_url)
            owner = url_info["owner"]
            repo = url_info["repo"]
            app_name = url_info.get("app_name") or repo
            prerelease = url_info.get("prerelease", False)

            # Validate GitHub identifiers for security
            try:
                validate_github_identifier(owner, "GitHub owner")
                validate_github_identifier(repo, "GitHub repo")
            except ValueError as e:
                msg = f"Invalid GitHub URL: {e}"
                raise InstallationError(msg, target=github_url)

            logger.debug(
                "Parsed GitHub URL: owner=%s, repo=%s, app_name=%s",
                owner,
                repo,
                app_name,
            )

            # Fetch latest release (already filtered for x86_64 Linux)
            release = await self._fetch_release(owner, repo)

            # Select best AppImage (filters unstable versions for URLs)
            asset = select_best_appimage_asset(
                release, installation_source="url"
            )
            # Asset is guaranteed non-None (raise_on_not_found=True by default)
            if asset is None:
                msg = "No suitable AppImage asset found"
                raise ValueError(msg)

            # Create v2 format app config template for URL installs
            # Note: verification method will auto-detect checksums
            app_config = {
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

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,  # type: ignore[arg-type]
                release=release,
                app_config=app_config,
                source="url",
                **options,
            )

        except Exception as error:
            logger.error(
                "Failed to install from URL %s: %s", github_url, error
            )
            return build_install_error_result(error, github_url, is_url=True)

    async def install_multiple(
        self,
        catalog_apps: list[str],
        url_apps: list[str],
        **options: Any,
    ) -> list[dict[str, Any]]:
        """Install multiple apps with concurrency control.

        Args:
            catalog_apps: List of catalog app names
            url_apps: List of GitHub URLs
            **options: Install options

        Returns:
            List of installation results

        """
        concurrent = options.get("concurrent", 3)
        semaphore = asyncio.Semaphore(concurrent)

        async def install_one(app_or_url: str, is_url: bool) -> dict[str, Any]:
            """Install a single app with semaphore control."""
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
                except Exception as error:
                    logger.error(
                        "Unexpected error installing %s: %s", app_or_url, error
                    )
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": f"Installation failed: {error}",
                        "source": "url" if is_url else "catalog",
                    }

        # Create tasks
        tasks = []
        for app in catalog_apps:
            tasks.append(install_one(app, is_url=False))
        for url in url_apps:
            tasks.append(install_one(url, is_url=True))

        return await asyncio.gather(*tasks)

    @staticmethod
    def separate_targets_impl(
        config_manager: ConfigManager, targets: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        This is a helper on the service so CLI code can reuse the
        same logic easily (and tests can target the behavior).

        Args:
            config_manager: Configuration manager instance
            targets: List of mixed targets (URLs or catalog names)

        Returns:
            (url_targets, catalog_targets)

        Raises:
            InstallationError: If unknown targets are present

        """
        from my_unicorn.exceptions import InstallationError

        url_targets: list[str] = []
        catalog_targets: list[str] = []
        unknown_targets: list[str] = []

        available_apps = set(config_manager.list_catalog_apps())

        for target in targets:
            if target.startswith("https://github.com/"):
                url_targets.append(target)
            elif target in available_apps:
                catalog_targets.append(target)
            else:
                unknown_targets.append(target)

        if unknown_targets:
            unknown_list = ", ".join(unknown_targets)
            msg = (
                f"Unknown applications or invalid URLs: {unknown_list}. "
                "Use 'my-unicorn catalog --available' to see available apps."
            )
            raise InstallationError(msg)

        return url_targets, catalog_targets

    @staticmethod
    async def check_apps_needing_work_impl(
        config_manager: ConfigManager,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """Check which apps actually need installation work.

        Args:
            config_manager: Configuration manager instance
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            install_options: Installation options

        Returns:
            (urls_needing_work, catalog_needing_work, already_installed)

        """
        # Default behavior: all URLs need work
        urls_needing_work: list[str] = list(url_targets)
        catalog_needing_work: list[str] = []
        already_installed: list[str] = []

        for app_name in catalog_targets:
            try:
                # Check if app exists in catalog
                try:
                    config_manager.load_catalog(app_name)
                except (FileNotFoundError, ValueError):
                    catalog_needing_work.append(app_name)
                    continue

                if not install_options.get("force", False):
                    # Check if app is already installed
                    try:
                        installed_config = config_manager.load_app_config(
                            app_name
                        )
                        installed_path = Path(
                            installed_config.get("installed_path", "")
                        )
                        if installed_path.exists():
                            already_installed.append(app_name)
                            continue
                    except (FileNotFoundError, KeyError):
                        # Not installed, needs work
                        pass

                catalog_needing_work.append(app_name)
            except Exception:
                # If we can't determine the status, assume it needs work
                catalog_needing_work.append(app_name)

        return urls_needing_work, catalog_needing_work, already_installed

    async def _install_workflow(
        self,
        app_name: str,
        asset: Asset,
        release: Release,
        app_config: dict[str, Any],
        source: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Core install workflow shared by catalog and URL installs.

        Args:
            app_name: Name of the application
            asset: GitHub asset to download
            release: Release information
            app_config: App configuration
            source: Install source ("catalog" or "url")
            **options: Install options

        Returns:
            Installation result dictionary

        """
        # Get options
        verify = options.get("verify_downloads", True)
        download_dir = options.get("download_dir", Path.cwd())

        logger.debug(
            "Install workflow: app=%s, verify=%s, source=%s",
            app_name,
            verify,
            source,
        )

        # Ensure task ids are always defined even if an early exception is
        # raised (such as during download). This prevents UnboundLocalError
        # in the exception handler that attempts to finish progress tasks.
        verification_task_id = None
        installation_task_id = None

        try:
            # 1. Download
            download_path = download_dir / asset.name
            logger.info("Downloading %s", app_name)
            downloaded_path = await self.download_service.download_appimage(
                asset, download_path
            )
            progress_service = getattr(
                self.download_service, "progress_service", None
            )
            if progress_service:
                (
                    verification_task_id,
                    installation_task_id,
                ) = await progress_service.create_installation_workflow(
                    app_name, with_verification=verify
                )

            # 2. Verify
            verify_result = None
            if verify:
                logger.info("Verifying %s", app_name)

                # Create verification service
                verification_service = VerificationService(
                    download_service=self.download_service,
                    progress_service=getattr(
                        self.download_service, "progress_service", None
                    ),
                )

                verify_result = await verify_appimage_download(
                    file_path=downloaded_path,
                    asset=asset,
                    release=release,
                    app_name=app_name,
                    verification_service=verification_service,
                    verification_config=app_config.get("verification"),
                    owner=app_config.get("owner", ""),
                    repo=app_config.get("repo", ""),
                    progress_task_id=verification_task_id,
                )
                if not verify_result["passed"]:
                    error_msg = verify_result.get("error", "Unknown error")
                    msg = f"Verification failed: {error_msg}"
                    raise InstallationError(msg)
            logger.info("Installing %s", app_name)
            # Move file to install directory first
            moved_path = self.storage_service.move_to_install_dir(
                downloaded_path
            )
            # Then rename according to configuration
            install_path = rename_appimage(
                appimage_path=moved_path,
                app_name=app_name,
                app_config=app_config,
                catalog_entry=None,
                storage_service=self.storage_service,
            )
            logger.debug("Installed to path: %s", install_path)

            # 4. Extract icon
            logger.info("Extracting icon for %s", app_name)
            # Get icon directory from config
            global_config = self.config_manager.load_global_config()
            icon_dir = Path(global_config["directory"]["icon"])

            icon_result = await setup_appimage_icon(
                appimage_path=install_path,
                app_name=app_name,
                icon_dir=icon_dir,
                app_config=app_config,
                catalog_entry=None,
            )

            # 5. Create configuration
            logger.info("Creating config for %s", app_name)
            config_result = create_app_config_v2(
                app_name=app_name,
                app_path=install_path,
                app_config=app_config,
                release=release,
                verify_result=verify_result,
                icon_result=icon_result,
                source=source,
                config_manager=self.config_manager,
            )

            # 6. Create desktop entry
            logger.info("Creating desktop entry for %s", app_name)
            desktop_result = create_desktop_entry(
                appimage_path=install_path,
                app_name=app_name,
                icon_result=icon_result,
                config_manager=self.config_manager,
            )

            # Success!
            logger.info("Successfully installed %s", app_name)

            # Mark installation task as complete
            if installation_task_id and progress_service:
                await progress_service.finish_task(
                    installation_task_id, success=True
                )

            return {
                "success": True,
                "target": app_name,
                "name": app_name,
                "path": str(install_path),
                "source": source,
                "version": release.version,
                "verification": verify_result,
                # Pass warning through if present
                "warning": (
                    verify_result.get("warning") if verify_result else None
                ),
                "icon": icon_result,
                "config": config_result,
                "desktop": desktop_result,
            }

        except Exception as error:
            logger.error(
                "Installation workflow failed for %s: %s", app_name, error
            )

            # Mark installation task as failed
            if installation_task_id and progress_service:
                error_msg = str(error)
                await progress_service.finish_task(
                    installation_task_id, success=False, description=error_msg
                )

            raise

    async def _fetch_release(self, owner: str, repo: str) -> Release:
        """Fetch release data from GitHub."""
        try:
            release = await self.github_client.get_latest_release(owner, repo)
            if not release:
                msg = f"No release found for {owner}/{repo}"
                raise InstallationError(msg)
            return release  # type: ignore[return-value]
        except Exception as error:
            logger.error(
                "Failed to fetch release for %s/%s: %s", owner, repo, error
            )
            raise
