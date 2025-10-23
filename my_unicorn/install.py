"""Install handler for AppImage installations.

This handler consolidates all installation logic, replacing the complex
template method pattern with a simpler, more maintainable approach.
"""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any

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
from my_unicorn.icon import IconHandler
from my_unicorn.logger import get_logger
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
            # Get app configuration
            app_config = self.catalog_manager.get_app_config(app_name)
            if not app_config:
                raise InstallationError(
                    f"App '{app_name}' not found in catalog"
                )

            # Fetch latest release
            owner = app_config["owner"]
            repo = app_config["repo"]
            release_data = await self._fetch_release_for_catalog(owner, repo)

            # Select best AppImage asset
            characteristic_suffix = app_config.get("appimage", {}).get(
                "characteristic_suffix", []
            )
            asset = self._select_best_asset(
                release_data,
                characteristic_suffix,
                owner,
                repo,
                installation_source="catalog",
            )

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release_data=release_data,
                app_config=app_config,
                source="catalog",
                **options,
            )

        except Exception as error:
            logger.error("Failed to install %s: %s", app_name, error)
            return {
                "success": False,
                "target": app_name,
                "name": app_name,
                "error": str(error),
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

            # Fetch latest release
            release_data = await self._fetch_release_for_url(owner, repo)

            # Select best AppImage asset (URL: filters unstable versions)
            asset = self._select_best_asset(
                release_data, [], owner, repo, installation_source="url"
            )

            # Create minimal app config for URL installs
            # Note: digest=False enables auto-detection of checksum files
            # Verification service will use digest if available from API
            app_config = {
                "owner": owner,
                "repo": repo,
                "appimage": {
                    "rename": app_name,
                    "name_template": "",
                    "characteristic_suffix": [],
                },
                "github": {},
                "verification": {
                    "digest": False,
                    "skip": False,
                    "checksum_file": "",
                    "checksum_hash_type": "sha256",
                },
                "icon": {"extraction": True, "url": None},
            }

            # Install workflow
            return await self._install_workflow(
                app_name=app_name,
                asset=asset,
                release_data=release_data,
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
                    else:
                        return await self.install_from_catalog(
                            app_or_url, **options
                        )
                except Exception as error:
                    logger.error(
                        "Unexpected error installing %s: %s", app_or_url, error
                    )
                    return {
                        "success": False,
                        "target": app_or_url,
                        "name": app_or_url,
                        "error": str(error),
                        "source": "url" if is_url else "catalog",
                    }

        # Create tasks
        tasks = []
        for app in catalog_apps:
            tasks.append(install_one(app, is_url=False))
        for url in url_apps:
            tasks.append(install_one(url, is_url=True))

        return await asyncio.gather(*tasks)

    async def _install_workflow(
        self,
        app_name: str,
        asset: Asset,
        release_data: dict[str, Any],
        app_config: dict[str, Any],
        source: str,
        **options: Any,
    ) -> dict[str, Any]:
        """Core install workflow shared by catalog and URL installs.

        Args:
            app_name: Name of the application
            asset: GitHub asset to download
            release_data: Release information
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

        # Create progress task
        task_id = None
        progress_service = getattr(
            self.download_service, "progress_service", None
        )
        if show_progress and progress_service:
            task_id = await progress_service.create_post_processing_task(
                app_name
            )

        try:
            # 1. Download
            download_path = download_dir / asset.name
            logger.info("📥 Downloading %s", app_name)
            downloaded_path = await self.download_service.download_appimage(
                asset, download_path, show_progress=show_progress
            )

            # 2. Verify
            verify_result = None
            if verify:
                logger.info("🔍 Verifying %s", app_name)
                verify_result = await self._verify_appimage(
                    downloaded_path,
                    asset,
                    app_config,
                    release_data,
                    app_name,
                    task_id,
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
                install_path, app_name, app_config, task_id
            )

            # 5. Create configuration
            logger.info("📝 Creating config for %s", app_name)
            config_result = self._create_app_config(
                app_name=app_name,
                app_path=install_path,
                app_config=app_config,
                release_data=release_data,
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

            return {
                "success": True,
                "target": app_name,
                "name": app_name,
                "path": str(install_path),
                "source": source,
                "verification": verify_result,
                "icon": icon_result,
                "config": config_result,
                "desktop": desktop_result,
            }

        except Exception as error:
            logger.error(
                "Installation workflow failed for %s: %s", app_name, error
            )
            raise

        finally:
            # Cleanup progress
            if task_id and progress_service:
                await progress_service.finish_task(task_id, success=True)

    async def _fetch_release_for_catalog(
        self, owner: str, repo: str
    ) -> dict[str, Any]:
        """Fetch release data from GitHub for catalog app.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release data dictionary

        """
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

    async def _fetch_release_for_url(
        self, owner: str, repo: str
    ) -> dict[str, Any]:
        """Fetch release data from GitHub for URL install.

        Args:
            owner: Repository owner
            repo: Repository name

        Returns:
            Release data dictionary

        """
        # Same as catalog for now
        return await self._fetch_release_for_catalog(owner, repo)

    def _select_best_asset(
        self,
        release_data: dict[str, Any],
        characteristic_suffix: list[str],
        owner: str,
        repo: str,
        installation_source: str = "catalog",
    ) -> Asset:
        """Select best AppImage asset from release.

        Args:
            release_data: Release information
            characteristic_suffix: List of characteristic suffixes
            owner: Repository owner
            repo: Repository name
            installation_source: Installation source ("catalog" or "url")

        Returns:
            Selected Asset

        """
        assets = release_data.get("assets", [])
        if not assets:
            raise InstallationError("No assets found in release")

        # Convert dict assets to Asset objects
        asset_objects = []
        for asset_dict in assets:
            asset = Asset.from_api_response(asset_dict)
            if asset:
                asset_objects.append(asset)

        # Create minimal Release object for selection
        release = Release(
            owner=owner,
            repo=repo,
            version=release_data.get("tag_name", ""),
            prerelease=release_data.get("prerelease", False),
            assets=asset_objects,
            original_tag_name=release_data.get("original_tag_name", ""),
        )

        # Use AssetSelector to find best AppImage
        asset = AssetSelector.select_appimage_for_platform(
            release,
            preferred_suffixes=characteristic_suffix,
            installation_source=installation_source,
        )
        if not asset:
            raise InstallationError(
                f"No suitable AppImage found in release for {owner}/{repo} "
                f"(source: {installation_source}, "
                f"suffixes: {characteristic_suffix})"
            )

        return asset

    async def _verify_appimage(
        self,
        file_path: Path,
        asset: Asset,
        app_config: dict[str, Any],
        release_data: dict[str, Any],
        app_name: str,
        task_id: str | None,
    ) -> dict[str, Any]:
        """Verify downloaded AppImage.

        Args:
            file_path: Path to downloaded file
            asset: GitHub asset information
            app_config: App configuration
            release_data: Release data
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
            tag_name = release_data.get("original_tag_name", "unknown")
            assets = release_data.get("assets", [])

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

        # Ensure .appimage extension
        if not rename.lower().endswith(".appimage"):
            rename = f"{rename}.appimage"

        # Move to install directory
        install_path = self.storage_service.move_to_install_dir(
            temp_path, rename
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
            from my_unicorn.icon import IconConfig

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
            from my_unicorn.config import ConfigManager

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
        release_data: dict[str, Any],
        verify_result: dict[str, Any] | None,
        icon_result: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        """Create app configuration - works for both catalog and URL.

        Args:
            app_name: Application name
            app_path: Path to installed AppImage
            app_config: App configuration template
            release_data: Release information
            verify_result: Verification result
            icon_result: Icon extraction result
            source: Install source

        Returns:
            Config creation result

        """
        # Extract digest hash string from verification result
        digest = None
        if verify_result and verify_result.get("passed"):
            methods = verify_result.get("methods", {})
            if "digest" in methods:
                # Extract just the hash string from digest verification result
                digest_result = methods["digest"]
                if isinstance(digest_result, dict):
                    digest = digest_result.get("hash")
                else:
                    digest = digest_result
            elif "sha256" in methods:
                digest = f"sha256:{methods['sha256']}"

        # Get updated verification config from verification result
        updated_verification_config = app_config.get("verification", {})
        if verify_result and "updated_config" in verify_result:
            updated_verification_config.update(verify_result["updated_config"])

        # Get owner/repo
        owner = app_config.get("owner", "unknown")
        repo = app_config.get("repo", "unknown")

        # Build config data
        config_data = {
            "config_version": "1.0.0",
            "source": source,
            "owner": owner,
            "repo": repo,
            "installed_path": str(app_path),
            "appimage": {
                "version": release_data.get("tag_name", "unknown"),
                "name": app_path.name,
                "rename": app_config.get("appimage", {}).get(
                    "rename", app_name
                ),
                "name_template": app_config.get("appimage", {}).get(
                    "name_template", ""
                ),
                "characteristic_suffix": app_config.get("appimage", {}).get(
                    "characteristic_suffix", []
                ),
                "installed_date": datetime.now().isoformat(),
                "digest": digest,
            },
            "github": app_config.get("github", {}),
            "verification": updated_verification_config,
            "icon": {
                "extraction": app_config.get("icon", {}).get(
                    "extraction", True
                ),
                "url": app_config.get("icon", {}).get("url") or None,
                "name": f"{app_name}.png",
                "source": icon_result.get("source", "none"),
                "installed": bool(icon_result.get("icon_path")),
                "path": icon_result.get("icon_path"),
            },
        }

        # Save configuration
        try:
            config_path = self.config_manager.save_app_config(
                app_name, config_data
            )
            return {
                "success": True,
                "config_path": str(config_path),
                "config": config_data,
            }
        except Exception as error:
            logger.error("Failed to save config for %s: %s", app_name, error)
            return {
                "success": False,
                "error": str(error),
            }

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
            if len(parts) < 2:
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
