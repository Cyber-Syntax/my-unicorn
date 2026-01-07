"""Install handler for AppImage installations.

This handler consolidates all installation logic, replacing the complex
template method pattern with a simpler, more maintainable approach.
"""

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from my_unicorn.download import DownloadService
from my_unicorn.exceptions import InstallationError
from my_unicorn.file_ops import FileOperations
from my_unicorn.github_client import Asset, GitHubClient, Release
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_setup import (
    create_desktop_entry,
    rename_appimage,
    setup_appimage_icon,
)
from my_unicorn.utils.asset_selection import select_best_appimage_asset
from my_unicorn.utils.github_ops import parse_github_url
from my_unicorn.utils.verification import verify_appimage_download
from my_unicorn.verification import VerificationService

logger = get_logger(__name__)


class InstallHandler:
    """Handles installation orchestration."""

    def __init__(
        self,
        download_service: DownloadService,
        storage_service: FileOperations,
        config_manager: Any,
        github_client: GitHubClient,
        catalog_manager: Any,
    ) -> None:
        """Initialize install handler.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            github_client: GitHub API client
            catalog_manager: Catalog manager for app configs

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client
        self.catalog_manager = catalog_manager

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
            app_config = self.catalog_manager.get_app_config(app_name)
            if not app_config:
                raise InstallationError("App not found in catalog")

            # Extract source info from v2 config
            source_config = app_config.get("source", {})
            owner = source_config.get("owner", "")
            repo = source_config.get("repo", "")
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
            assert asset is not None

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release=release,
                app_config=app_config,
                source="catalog",
                **options,
            )

        except InstallationError as error:
            logger.error("Failed to install %s: %s", app_name, error)
            # Context-aware error message
            error_msg = str(error)
            if "not found in catalog" in error_msg.lower():
                error_msg = "App not found in catalog"
            elif "no assets found" in error_msg.lower():
                error_msg = (
                    "No assets found in release - may still be building"
                )
            elif "no suitable appimage" in error_msg.lower():
                error_msg = (
                    "AppImage not found in release - may still be building"
                )
            return {
                "success": False,
                "target": app_name,
                "name": app_name,
                "error": error_msg,
                "source": "catalog",
            }
        except Exception as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return {
                "success": False,
                "target": app_name,
                "name": app_name,
                "error": f"Installation failed: {error}",
                "source": "catalog",
            }

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
            assert asset is not None

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
                asset=asset,
                release=release,
                app_config=app_config,
                source="url",
                **options,
            )

        except Exception as error:
            logger.error(
                "Failed to install from URL %s: %s", github_url, error
            )
            return {
                "success": False,
                "target": github_url,
                "name": github_url,
                "error": str(error),
                "source": "url",
            }

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
                    return self._build_install_error_result(
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
    def _get_user_friendly_error(error: InstallationError) -> str:
        """Convert InstallationError to user-friendly message.

        Args:
            error: Installation error to convert

        Returns:
            User-friendly error message

        """
        error_msg = str(error).lower()
        error_mappings = [
            ("not found in catalog", "App not found in catalog"),
            (
                "no assets found",
                "No assets found in release - may still be building",
            ),
            (
                "no suitable appimage",
                "AppImage not found in release - may still be building",
            ),
            ("already installed", "Already installed"),
        ]
        for pattern, message in error_mappings:
            if pattern in error_msg:
                return message
        return str(error)

    def _build_install_error_result(
        self, error: InstallationError, target: str, is_url: bool
    ) -> dict[str, Any]:
        """Build error result dict for failed installation.

        Args:
            error: The installation error
            target: The app name or URL that failed
            is_url: Whether target is a URL

        Returns:
            Error result dictionary

        """
        return {
            "success": False,
            "target": target,
            "name": target,
            "error": self._get_user_friendly_error(error),
            "source": "url" if is_url else "catalog",
        }

    @staticmethod
    def separate_targets_impl(
        catalog_manager: Any, targets: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        This is a helper on the service so CLI code can reuse the
        same logic easily (and tests can target the behavior).

        Args:
            catalog_manager: Catalog manager instance
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

        available_apps = catalog_manager.get_available_apps()

        for target in targets:
            if target.startswith("https://github.com/"):
                url_targets.append(target)
            elif target in available_apps:
                catalog_targets.append(target)
            else:
                unknown_targets.append(target)

        if unknown_targets:
            unknown_list = ", ".join(unknown_targets)
            raise InstallationError(
                f"Unknown applications or invalid URLs: {unknown_list}. Use 'my-unicorn list' to see available apps."
            )

        return url_targets, catalog_targets

    # Backwards compatible instance wrapper
    def separate_targets(
        self, targets: list[str]
    ) -> tuple[list[str], list[str]]:
        """Separate targets into URL and catalog targets.

        Args:
            targets: List of mixed targets (URLs or catalog names)

        Returns:
            (url_targets, catalog_targets)

        """
        return InstallHandler.separate_targets_impl(
            self.catalog_manager, targets
        )

    @staticmethod
    async def check_apps_needing_work_impl(
        catalog_manager: Any,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """Check which apps actually need installation work.

        Args:
            catalog_manager: Catalog manager instance
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
                app_config = catalog_manager.get_app_config(app_name)
                if not app_config:
                    catalog_needing_work.append(app_name)
                    continue

                if not install_options.get("force", False):
                    installed_config = (
                        catalog_manager.get_installed_app_config(app_name)
                    )
                    if installed_config:
                        installed_path = Path(
                            installed_config.get("installed_path", "")
                        )
                        if installed_path.exists():
                            already_installed.append(app_name)
                            continue

                catalog_needing_work.append(app_name)
            except Exception:
                # If we can't determine the status, assume it needs work
                catalog_needing_work.append(app_name)

        return urls_needing_work, catalog_needing_work, already_installed

    # Backwards compatible instance wrapper
    async def check_apps_needing_work(
        self,
        url_targets: list[str],
        catalog_targets: list[str],
        install_options: dict[str, Any],
    ) -> tuple[list[str], list[str], list[str]]:
        """Check which apps actually need installation work.

        Args:
            url_targets: List of URL targets
            catalog_targets: List of catalog targets
            install_options: Installation options

        Returns:
            (urls_needing_work, catalog_needing_work, already_installed)

        """
        return await InstallHandler.check_apps_needing_work_impl(
            self.catalog_manager, url_targets, catalog_targets, install_options
        )

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
                    raise InstallationError(
                        f"Verification failed: {error_msg}"
                    )

            # 3. Move to install directory and rename
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
            config_result = self._create_app_config(
                app_name=app_name,
                app_path=install_path,
                app_config=app_config,
                release=release,
                verify_result=verify_result,
                icon_result=icon_result,
                source=source,
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
                raise InstallationError(f"No release found for {owner}/{repo}")
            return release
        except Exception as error:
            logger.error(
                "Failed to fetch release for %s/%s: %s", owner, repo, error
            )
            raise

    def _create_app_config(
        self,
        app_name: str,
        app_path: Path,
        app_config: dict[str, Any],
        release: Release,
        verify_result: dict[str, Any] | None,
        icon_result: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        """Create app configuration in v2.0.0 format.

        Args:
            app_name: Application name
            app_path: Path to installed AppImage
            app_config: App configuration template
            release: Release information
            verify_result: Verification result
            icon_result: Icon extraction result
            source: Install source ("catalog" or "url")

        Returns:
            Config creation result

        """
        from my_unicorn.constants import APP_CONFIG_VERSION

        # Determine catalog reference and overrides
        catalog_ref = app_name if source == "catalog" else None
        overrides = (
            None
            if source == "catalog"
            else self._build_overrides_from_template(app_config)
        )

        # Build verification state
        verification_state = self._build_verification_state(verify_result)

        # Build state section
        config_data = {
            "config_version": APP_CONFIG_VERSION,
            "source": source,
            "catalog_ref": catalog_ref,
            "state": {
                "version": release.version,
                "installed_date": datetime.now(tz=UTC).isoformat(),
                "installed_path": str(app_path),
                "verification": {
                    "passed": verification_state["passed"],
                    "methods": verification_state["methods"],
                },
                "icon": {
                    "installed": bool(icon_result.get("icon_path")),
                    "method": icon_result.get("source", "none"),
                    "path": icon_result.get("icon_path", ""),
                },
            },
        }

        # Add overrides for URL installs
        if overrides:
            # Update verification method with actual result
            if "verification" in overrides:
                overrides["verification"]["method"] = verification_state[
                    "actual_method"
                ]

            # Update icon filename with actual result
            if icon_result.get("icon_path") and "icon" in overrides:
                icon_path = Path(icon_result["icon_path"])
                overrides["icon"]["filename"] = icon_path.name

            config_data["overrides"] = overrides

        # Save configuration
        try:
            self.config_manager.save_app_config(app_name, config_data)
            return {
                "success": True,
                "config_path": str(
                    self.config_manager.apps_dir / f"{app_name}.json"
                ),
                "config": config_data,
            }
        except Exception as error:
            logger.error("Failed to save config for %s: %s", app_name, error)
            return {
                "success": False,
                "error": str(error),
            }

    @staticmethod
    def _build_method_entry(
        method_type: str, method_result: Any
    ) -> dict[str, Any]:
        """Build verification method entry from result.

        Args:
            method_type: Type of verification (digest, checksum_file)
            method_result: Result data (dict or simple bool)

        Returns:
            Method entry dictionary for config

        """
        method_entry: dict[str, Any] = {"type": method_type}

        if not isinstance(method_result, dict):
            method_entry["status"] = "passed" if method_result else "failed"
            return method_entry

        passed = method_result.get("passed", False)
        hash_type = method_result.get("hash_type", "")
        algorithm = hash_type.upper() if hash_type else "SHA256"

        verification_source = method_result.get("url", "")
        if not verification_source:
            verification_source = (
                "github_api" if method_type == "digest" else ""
            )

        method_entry.update(
            {
                "status": "passed" if passed else "failed",
                "algorithm": algorithm,
                "expected": method_result.get("hash", ""),
                "computed": method_result.get("computed_hash", ""),
                "source": verification_source,
            }
        )
        return method_entry

    def _build_verification_state(
        self, verify_result: dict[str, Any] | None
    ) -> dict[str, Any]:
        """Build verification state from verification result.

        Args:
            verify_result: Verification result dictionary or None

        Returns:
            Dictionary with 'passed', 'methods', and 'actual_method' keys

        """
        if not verify_result:
            return {"passed": False, "methods": [], "actual_method": "skip"}

        methods_data = verify_result.get("methods", {})
        if not methods_data:
            return {"passed": False, "methods": [], "actual_method": "skip"}

        verification_passed = verify_result.get("passed", False)
        actual_method = next(iter(methods_data.keys()), "skip")

        verification_methods = [
            self._build_method_entry(method_type, method_result)
            for method_type, method_result in methods_data.items()
        ]

        return {
            "passed": verification_passed,
            "methods": verification_methods,
            "actual_method": actual_method,
        }

    def _build_overrides_from_template(
        self, app_config: dict[str, Any]
    ) -> dict[str, Any]:
        """Build overrides section from app config template.

        Args:
            app_config: App configuration template (v2 format)

        Returns:
            Overrides dictionary for v2.0.0 config

        """
        # Extract from v2 format
        source_config = app_config.get("source", {})
        owner = source_config.get("owner", "")
        repo = source_config.get("repo", "")
        prerelease = source_config.get("prerelease", False)

        naming_config = app_config.get("appimage", {}).get("naming", {})
        name_template = naming_config.get("template", "")
        target_name = naming_config.get("target_name", "")

        verification_config = app_config.get("verification", {})
        verification_method = verification_config.get("method", "skip")

        icon_config = app_config.get("icon", {})
        icon_method = icon_config.get("method", "extraction")
        icon_filename = icon_config.get("filename", "")

        overrides = {
            "metadata": {
                "name": repo,
                "display_name": repo,
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
                    "template": name_template,
                    "target_name": target_name,
                    "architectures": ["amd64", "x86_64"],
                }
            },
            "verification": {"method": verification_method},
            "icon": {
                "method": icon_method,
                "filename": icon_filename,
            },
        }

        return overrides
