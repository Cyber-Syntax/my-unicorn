"""Install handler for AppImage installations.

This handler consolidates all installation logic, replacing the complex
template method pattern with a simpler, more maintainable approach.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

from my_unicorn.config import ConfigManager
from my_unicorn.desktop_entry import DesktopEntry
from my_unicorn.download import DownloadService
from my_unicorn.exceptions import InstallationError
from my_unicorn.file_ops import FileOperations
from my_unicorn.github_client import (
    Asset,
    AssetSelector,
    GitHubClient,
    Release,
)
from my_unicorn.icon import IconConfig, IconHandler
from my_unicorn.logger import get_logger
from my_unicorn.verification import VerificationService

# Minimum number of path parts expected for a GitHub owner/repo
MIN_GITHUB_PARTS = 2

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
        icon_service: IconHandler | None = None,
    ) -> None:
        """Initialize install handler.

        Args:
            download_service: Service for downloading files
            storage_service: Service for storage operations
            config_manager: Configuration manager
            github_client: GitHub API client
            catalog_manager: Catalog manager for app configs
            icon_service: Service for icon operations

        """
        self.download_service = download_service
        self.storage_service = storage_service
        self.config_manager = config_manager
        self.github_client = github_client
        self.catalog_manager = catalog_manager
        self.icon_service = icon_service or IconHandler(
            download_service=download_service,
        )

    async def install_from_catalog(
        self,
        app_name: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Install app from catalog.

        Args:
            app_name: Name of app in catalog
            **options: Install options (verify_downloads, show_progress, etc.)

        Returns:
            Installation result dictionary

        """
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
            asset = self._select_best_asset(
                release,
                characteristic_suffix,
                owner,
                repo,
                installation_source="catalog",
            )

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
        try:
            # Parse GitHub URL
            url_info = self._parse_github_url(github_url)
            owner = url_info["owner"]
            repo = url_info["repo"]
            app_name = url_info.get("app_name") or repo
            prerelease = url_info.get("prerelease", False)

            # Fetch latest release (already filtered for x86_64 Linux)
            release = await self._fetch_release(owner, repo)

            # Select best AppImage (filters unstable versions for URLs)
            asset = self._select_best_asset(
                release, [], owner, repo, installation_source="url"
            )

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
                    # Context-aware error message
                    error_msg = str(error)
                    if "not found in catalog" in error_msg.lower():
                        error_msg = "App not found in catalog"
                    elif "no assets found" in error_msg.lower():
                        error_msg = "No assets found in release - may still be building"
                    elif "no suitable appimage" in error_msg.lower():
                        error_msg = "AppImage not found in release - may still be building"
                    elif "already installed" in error_msg.lower():
                        error_msg = "Already installed"
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": error_msg,
                        "source": "url" if is_url else "catalog",
                    }
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
        show_progress = options.get("show_progress", True)
        download_dir = options.get("download_dir", Path.cwd())

        # Ensure task ids are always defined even if an early exception is
        # raised (such as during download). This prevents UnboundLocalError
        # in the exception handler that attempts to finish progress tasks.
        verification_task_id = None
        installation_task_id = None
        try:
            # 1. Download
            download_path = download_dir / asset.name
            logger.info("📥 Downloading %s", app_name)
            downloaded_path = await self.download_service.download_appimage(
                asset, download_path, show_progress=show_progress
            )
            progress_service = getattr(
                self.download_service, "progress_service", None
            )
            if show_progress and progress_service:
                (
                    verification_task_id,
                    installation_task_id,
                ) = await progress_service.create_installation_workflow(
                    app_name, with_verification=verify
                )

            # 2. Verify
            verify_result = None
            if verify:
                logger.info("🔍 Verifying %s", app_name)
                verify_result = await self._verify_appimage(
                    downloaded_path,
                    asset,
                    app_config,
                    release,
                    app_name,
                    verification_task_id,
                )
                if not verify_result["passed"]:
                    error_msg = verify_result.get("error", "Unknown error")
                    raise InstallationError(
                        f"Verification failed: {error_msg}"
                    )

            # 3. Move to install directory
            logger.info("📁 Installing %s", app_name)
            install_path = self._install_and_rename(
                downloaded_path, app_name, app_config
            )

            # 4. Extract icon
            logger.info("🎨 Extracting icon for %s", app_name)
            icon_result = await self._extract_icon_for_app(
                install_path, app_name, app_config, installation_task_id
            )

            # 5. Create configuration
            logger.info("📝 Creating config for %s", app_name)
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
            logger.info("🖥️  Creating desktop entry for %s", app_name)
            desktop_result = self._create_desktop_entry_for_app(
                install_path, app_name, app_config, icon_result
            )

            # Success!
            logger.info("✅ Successfully installed %s", app_name)

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

    def _select_best_asset(
        self,
        release: Release,
        characteristic_suffix: list[str],
        owner: str,
        repo: str,
        installation_source: str = "catalog",
    ) -> Asset:
        """Select best AppImage asset from release.

        Args:
            release: Release object
            characteristic_suffix: List of characteristic suffixes
            owner: Repository owner
            repo: Repository name
            installation_source: Installation source ("catalog" or "url")

        Returns:
            Selected Asset

        """
        if not release.assets:
            raise InstallationError("No assets found in release")

        # Use AssetSelector to find best AppImage
        asset = AssetSelector.select_appimage_for_platform(
            release,
            preferred_suffixes=characteristic_suffix,
            installation_source=installation_source,
        )
        if not asset:
            raise InstallationError(
                "AppImage not found in release - may still be building"
            )
        return asset

    async def _verify_appimage(
        self,
        file_path: Path,
        asset: Asset,
        app_config: dict[str, Any],
        release: Release,
        app_name: str,
        task_id: str | None,
    ) -> dict[str, Any]:
        """Verify downloaded AppImage.

        Args:
            file_path: Path to downloaded file
            asset: GitHub asset information
            app_config: App configuration
            release: Release data
            app_name: Application name
            task_id: Progress task ID

        Returns:
            Verification result

        """
        try:
            # Create verification service
            verification_service = VerificationService(
                download_service=self.download_service,
                progress_service=getattr(
                    self.download_service, "progress_service", None
                ),
            )

            # Get verification config
            verification_config = app_config.get("verification", {})

            # Get tag name from release data
            tag_name = release.original_tag_name or "unknown"
            assets = release.assets

            # Perform verification
            result = await verification_service.verify_file(
                file_path=file_path,
                asset=asset,
                config=verification_config,
                owner=app_config.get("owner", ""),
                repo=app_config.get("repo", ""),
                tag_name=tag_name,
                app_name=app_name,
                assets=assets,
                progress_task_id=task_id,
            )

            return {
                "passed": result.passed,
                "methods": result.methods,
                "updated_config": result.updated_config,
                "warning": result.warning,  # Include warning
            }

        except Exception as error:
            logger.error("Verification failed for %s: %s", app_name, error)
            return {
                "passed": False,
                "error": str(error),
                "methods": {},
            }

    def _install_and_rename(
        self,
        temp_path: Path,
        app_name: str,
        app_config: dict[str, Any],
    ) -> Path:
        """Move file to install directory with proper naming.

        Args:
            temp_path: Temporary download path
            app_name: Application name
            app_config: App configuration

        Returns:
            Final install path

        """
        # Get rename preference
        rename = app_config.get("appimage", {}).get("rename", app_name)

        # Clean base name (remove any provided extension) and delegate
        # extension/casing handling to the storage service to keep behavior
        # consistent with update logic.
        clean_name = self.storage_service.get_clean_appimage_name(rename)

        # Move the downloaded file into the install directory first
        moved_path = self.storage_service.move_to_install_dir(temp_path)

        # Then perform AppImage-specific rename (this will add ".AppImage"
        # with the correct casing if needed)
        install_path = self.storage_service.rename_appimage(
            moved_path, clean_name
        )

        return install_path

    async def _extract_icon_for_app(
        self,
        app_path: Path,
        app_name: str,
        app_config: dict[str, Any],
        task_id: str | None,
    ) -> dict[str, Any]:
        """Extract icon from AppImage or download.

        Args:
            app_path: Path to installed AppImage
            app_name: Application name
            app_config: App configuration
            task_id: Progress task ID

        Returns:
            Icon extraction result

        """
        try:
            icon_cfg = app_config.get("icon", {})
            extraction_enabled = icon_cfg.get("extraction", True)
            icon_url = icon_cfg.get("url")

            if not extraction_enabled:
                return {
                    "success": False,
                    "source": "none",
                    "icon_path": None,
                }

            # Get icon directory from config
            config_mgr = ConfigManager()
            global_config = config_mgr.load_global_config()
            icon_dir = Path(global_config["directory"]["icon"])

            # Create icon config
            icon_config = IconConfig(
                extraction_enabled=extraction_enabled,
                icon_url=icon_url,
                icon_filename=f"{app_name}.png",
            )

            # Use icon service to acquire icon
            result = await self.icon_service.acquire_icon(
                icon_config=icon_config,
                app_name=app_name,
                icon_dir=icon_dir,
                appimage_path=app_path,
                current_config=icon_cfg,
                catalog_entry=app_config,
                progress_task_id=task_id,
            )

            if result.icon_path:
                return {
                    "success": True,
                    "source": result.source,
                    "icon_path": str(result.icon_path),
                }

            return {
                "success": False,
                "source": result.source,
                "icon_path": None,
            }

        except Exception as error:
            logger.warning(
                "Icon extraction failed for %s: %s", app_name, error
            )
            return {
                "success": False,
                "source": "none",
                "icon_path": None,
                "error": str(error),
            }

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

        # Determine catalog reference
        catalog_ref = None
        overrides = None

        if source == "catalog":
            # Use repo name as catalog reference (v2 format)
            catalog_ref = app_config.get("source", {}).get("repo", "").lower()
        else:
            # URL install - need full overrides section
            overrides = self._build_overrides_from_template(app_config)

        # Build verification methods list
        verification_methods = []
        verification_passed = False
        actual_verification_method = "skip"  # Default

        if verify_result:
            methods_data = verify_result.get("methods", {})

            # Determine if verification actually passed
            # If methods dict is empty, no verification happened
            if methods_data:
                verification_passed = verify_result.get("passed", False)
                # Get actual method used from first method in results
                actual_verification_method = (
                    next(iter(methods_data.keys())) if methods_data else "skip"
                )
            else:
                # No methods available - verification did not happen
                verification_passed = False
                actual_verification_method = "skip"

            for method_type, method_result in methods_data.items():
                method_entry = {"type": method_type}

                if isinstance(method_result, dict):
                    # Map verification result fields to config structure
                    # MethodResult.to_dict() provides: passed, hash, details,
                    # computed_hash, url, hash_type
                    passed = method_result.get("passed", False)
                    hash_type = method_result.get("hash_type", "")

                    # Determine algorithm from hash_type or default to SHA256
                    algorithm = hash_type.upper() if hash_type else "SHA256"

                    # Determine verification source (where hash came from)
                    verification_source = method_result.get("url", "")
                    if not verification_source:
                        if method_type == "digest":
                            verification_source = "GitHub API"
                        else:
                            verification_source = ""

                    method_entry.update(
                        {
                            "status": "passed" if passed else "failed",
                            "algorithm": algorithm,
                            "expected": method_result.get("hash", ""),
                            "computed": method_result.get("computed_hash", ""),
                            "source": verification_source,
                        }
                    )
                else:
                    # Simple result
                    method_entry["status"] = (
                        "passed" if method_result else "failed"
                    )

                verification_methods.append(method_entry)

        # Build icon info
        icon_method = "extraction"
        if app_config.get("icon", {}).get("url"):
            icon_method = "download"

        # Build state section
        config_data = {
            "config_version": APP_CONFIG_VERSION,
            "source": source,
            "catalog_ref": catalog_ref,
            "state": {
                "version": release.version,
                "installed_date": datetime.now().isoformat(),
                "installed_path": str(app_path),
                "verification": {
                    "passed": verification_passed,
                    "methods": verification_methods,
                },
                "icon": {
                    "installed": bool(icon_result.get("icon_path")),
                    "method": icon_method,
                    "path": icon_result.get("icon_path", ""),
                },
            },
        }

        # Add overrides for URL installs
        if overrides:
            # Update verification method with actual result
            if "verification" in overrides:
                overrides["verification"]["method"] = (
                    actual_verification_method
                )

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
        icon_url = icon_config.get("download_url", "")
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

        # Add download URL if present
        if icon_url:
            overrides["icon"]["download_url"] = icon_url

        return overrides

    def _create_desktop_entry_for_app(
        self,
        app_path: Path,
        app_name: str,
        app_config: dict[str, Any],
        icon_result: dict[str, Any],
    ) -> dict[str, Any]:
        """Create desktop entry for application.

        Args:
            app_path: Path to installed AppImage
            app_name: Application name
            app_config: App configuration
            icon_result: Icon extraction result

        Returns:
            Desktop entry creation result

        """
        try:
            # Get icon path
            icon_path = None
            if icon_result.get("icon_path"):
                icon_path = Path(icon_result["icon_path"])

            # Create desktop entry
            desktop = DesktopEntry(
                app_name=app_name,
                appimage_path=app_path,
                icon_path=icon_path,
                config_manager=self.config_manager,
            )

            desktop_path = desktop.create_desktop_file()

            return {
                "success": True,
                "desktop_path": str(desktop_path),
            }

        except Exception as error:
            logger.error(
                "Failed to create desktop entry for %s: %s", app_name, error
            )
            return {
                "success": False,
                "error": str(error),
            }

    def _parse_github_url(self, url: str) -> dict[str, str]:
        """Parse GitHub URL to extract owner and repo.

        Args:
            url: GitHub repository URL

        Returns:
            Dictionary with owner, repo, and app_name

        """
        try:
            # Parse owner/repo from URL
            parts = url.replace("https://github.com/", "").split("/")
            if len(parts) < MIN_GITHUB_PARTS:
                raise InstallationError(f"Invalid GitHub URL format: {url}")

            owner, repo = parts[0], parts[1]
            app_name = repo.lower()

            return {
                "owner": owner,
                "repo": repo,
                "app_name": app_name,
            }
        except Exception as error:
            logger.error("Failed to parse GitHub URL %s: %s", url, error)
            raise InstallationError(f"Invalid GitHub URL: {url}") from error
