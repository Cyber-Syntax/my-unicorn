"""Install command handler for my-unicorn CLI.

This module handles the installation of AppImages from GitHub URLs or catalog entries,
providing comprehensive verification, backup management, and configuration handling.
"""

import asyncio
import shutil
from argparse import Namespace
from datetime import datetime
from pathlib import Path

import aiohttp

from ..config import AppConfig, AppImageConfig, GitHubConfig, IconConfig
from ..config import VerificationConfig as VConfig
from ..desktop import create_desktop_entry_for_app
from ..github_client import GitHubReleaseFetcher
from ..install import IconAsset, Installer
from ..logger import get_logger
from ..parser import is_github_url, parse_github_url
from ..update import UpdateManager
from ..utils import check_icon_exists
from ..verify import Verifier, log_verification_summary
from .base import BaseCommandHandler

logger = get_logger(__name__)


class InstallHandler(BaseCommandHandler):
    """Handler for install command operations."""

    async def execute(self, args: Namespace) -> None:
        """Execute the install command."""
        # Expand and validate targets
        unique_targets = self._expand_comma_separated_targets(args.targets)

        if not unique_targets:
            print("❌ No targets specified.")
            return

        # Validate target types (URLs vs catalog names)
        if not self._validate_target_types(unique_targets):
            return

        # Ensure directories exist
        self._ensure_directories()

        # Route to appropriate installation method
        first_target = unique_targets[0]
        if is_github_url(first_target):
            await self._install_from_urls(unique_targets, args)
        else:
            await self._install_from_catalog(unique_targets, args)

    def _validate_target_types(self, targets: list[str]) -> bool:
        """Validate that all targets are the same type (URLs or catalog names).

        Args:
            targets: List of installation targets

        Returns:
            True if all targets are the same type, False otherwise

        """
        if not targets:
            return False

        first_target = targets[0]
        is_url_install = is_github_url(first_target)

        # Check for mixed types
        for target in targets:
            if is_github_url(target) != is_url_install:
                print("❌ Cannot mix GitHub URLs and catalog app names in the same command.")
                print("   Use separate commands for URLs and catalog apps.")
                return False

        return True

    async def _install_from_urls(self, urls: list[str], args: Namespace) -> None:
        """Install from GitHub URLs."""
        valid_repos = []
        invalid_inputs = []

        # Parse and validate URLs
        for url in urls:
            try:
                owner, repo = parse_github_url(url)
                valid_repos.append((owner, repo, url))
            except ValueError as e:
                invalid_inputs.append((url, f"Invalid GitHub URL: {e}"))

        # Report invalid URLs
        if invalid_inputs:
            print("❌ Invalid URLs:")
            for invalid_input, error_msg in invalid_inputs:
                print(f"   • {invalid_input}: {error_msg}")

        if not valid_repos:
            print("\nNo valid URLs to install.")
            return

        # Print what will be installed
        print("✅ Will install from URLs:")
        for owner, repo, url in valid_repos:
            print(f"   📡 {owner}/{repo}")

        # Install concurrently
        await self._install_repos_concurrently(valid_repos, args)

    async def _install_from_catalog(self, app_names: list[str], args: Namespace) -> None:
        """Install from catalog app names."""
        catalog_names = self.config_manager.list_catalog_apps()
        valid_apps = []
        invalid_inputs = []

        # Validate catalog app names
        for app_name in app_names:
            if app_name.lower() in [app.lower() for app in catalog_names]:
                # Find correct case
                for app in catalog_names:
                    if app.lower() == app_name.lower():
                        valid_apps.append(app)
                        break
            else:
                # Suggest similar apps
                suggestions = [
                    app for app in catalog_names if app_name.lower() in app.lower()
                ][:2]
                if suggestions:
                    error_msg = f"Unknown app. Did you mean: {', '.join(suggestions)}?"
                else:
                    error_msg = "Unknown catalog app name"
                invalid_inputs.append((app_name, error_msg))

        # Report invalid app names
        if invalid_inputs:
            print("❌ Invalid catalog apps:")
            for invalid_input, error_msg in invalid_inputs:
                print(f"   • {invalid_input}: {error_msg}")

        if not valid_apps:
            print("\nNo valid catalog apps to install.")
            return

        # Install concurrently
        await self._install_catalog_apps_concurrently(valid_apps, args)

    async def _install_repos_concurrently(
        self, repos: list[tuple[str, str, str]], args: Namespace
    ) -> None:
        """Install multiple repositories concurrently."""
        semaphore = asyncio.Semaphore(args.concurrency)
        tasks = []

        async with aiohttp.ClientSession() as session:
            for owner, repo, url in repos:
                tasks.append(
                    self._install_single_repo(f"{owner}/{repo}", session, semaphore, args)
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        if len(repos) > 1:
            self._print_installation_summary(repos, results)

    async def _install_catalog_apps_concurrently(
        self, apps: list[str], args: Namespace
    ) -> None:
        """Install multiple catalog apps concurrently."""
        semaphore = asyncio.Semaphore(args.concurrency)
        tasks = []

        async with aiohttp.ClientSession() as session:
            for app in apps:
                tasks.append(self._install_catalog_app(app, session, semaphore, args))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        if len(apps) > 1:
            self._print_catalog_installation_summary(apps, results)

    async def _install_catalog_app(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        args: Namespace,
    ) -> tuple[bool, str, dict]:
        """Install an app from catalog."""
        async with semaphore:
            try:
                catalog_entry = self.config_manager.load_catalog_entry(app_name)
                if not catalog_entry:
                    return False, "Catalog entry not found", {}

                owner = catalog_entry["owner"]
                repo = catalog_entry["repo"]

                return await self._install_single_repo(
                    f"{owner}/{repo}", session, asyncio.Semaphore(1), args, catalog_entry
                )
            except Exception as e:
                logger.error(f"Failed to install catalog app {app_name}: {e}")
                return False, str(e), {}

    async def _install_single_repo(
        self,
        repo: str,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        args: Namespace,
        catalog_entry: dict | None = None,
    ) -> tuple[bool, str, dict]:
        """Install a single repository."""
        async with semaphore:
            try:
                owner, repo_name = repo.split("/", 1)
                logger.debug(f"Installing {owner}/{repo_name}")

                # Determine the app config key
                config_key = self._get_config_key(repo_name, catalog_entry)

                # Handle existing installation
                await self._handle_existing_installation(config_key)

                # Get release configuration
                should_use_github, should_use_prerelease = self._get_release_config(
                    repo_name, catalog_entry
                )

                if not should_use_github:
                    logger.error(f"GitHub API disabled for {repo_name} (github.repo: false)")
                    return False, "GitHub API disabled for this app", {}

                # Fetch release data
                fetcher = GitHubReleaseFetcher(owner, repo_name, session)
                release_data, used_prerelease_fallback = await self._fetch_release_data(
                    fetcher, should_use_prerelease, catalog_entry is None, owner, repo_name
                )

                # Find AppImage asset
                appimage_asset = self._get_appimage_asset(fetcher, release_data, catalog_entry)
                if not appimage_asset:
                    logger.warning(f"No AppImage found for {repo}")
                    return False, "No AppImage found", {}

                # Setup installation paths
                download_dir = self.global_config["directory"]["download"]
                install_dir = self.global_config["directory"]["storage"]
                icon_dir = self.global_config["directory"]["icon"]

                # Handle icon setup
                icon_asset = await self._setup_icon_asset(
                    fetcher, catalog_entry, repo, repo_name, icon_dir, args.no_icon
                )

                # Perform installation
                installer = Installer(
                    asset=appimage_asset,
                    session=session,
                    icon=icon_asset,
                    download_dir=download_dir,
                    install_dir=install_dir,
                )

                # Download and install
                appimage_path, icon_path = await self._download_and_install(
                    installer, catalog_entry, repo_name, icon_dir, args.no_icon
                )

                # Perform verification
                verification_results = await self._perform_verification(
                    appimage_path,
                    appimage_asset,
                    catalog_entry,
                    release_data,
                    owner,
                    repo_name,
                    session,
                    args.no_verify,
                )

                # Finalize installation
                await self._finalize_installation(
                    appimage_path,
                    icon_path,
                    catalog_entry,
                    repo_name,
                    owner,
                    release_data,
                    appimage_asset,
                    verification_results,
                    should_use_github,
                    should_use_prerelease or used_prerelease_fallback,
                    config_key,
                    args.no_desktop,
                    icon_dir,
                )

                print(f"✅ {repo_name} {release_data['version']} installed successfully")
                return True, f"Installed {release_data['version']}", verification_results

            except Exception as e:
                logger.error(f"Failed to install {repo}: {e}")
                return False, str(e), {}

    def _get_config_key(self, repo_name: str, catalog_entry: dict | None) -> str:
        """Get the configuration key for the app."""
        if catalog_entry:
            return catalog_entry.get("appimage", {}).get("rename", repo_name).lower()
        return repo_name.lower()

    async def _handle_existing_installation(self, config_key: str) -> None:
        """Handle backup of existing installation if present."""
        existing_app_config = self.config_manager.load_app_config(config_key)
        if not existing_app_config:
            return

        logger.debug(f"Found existing installation for {config_key}")
        storage_dir = self.global_config["directory"]["storage"]
        backup_dir = self.global_config["directory"]["backup"]
        current_appimage_path = storage_dir / existing_app_config["appimage"]["name"]

        if not current_appimage_path.exists():
            logger.debug(f"No existing AppImage file found at {current_appimage_path}")
            return

        logger.debug(f"Creating backup for existing {config_key}")
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Create backup filename
        stem = current_appimage_path.stem
        suffix = current_appimage_path.suffix
        current_version = existing_app_config["appimage"]["version"]
        version_str = f"-{current_version}" if current_version else ""
        backup_name = f"{stem}{version_str}.backup{suffix}"
        backup_path = backup_dir / backup_name

        # Copy file to backup location
        shutil.copy2(current_appimage_path, backup_path)
        logger.debug(f"💾 Backup created: {backup_path}")

    def _get_release_config(
        self, repo_name: str, catalog_entry: dict | None
    ) -> tuple[bool, bool]:
        """Get release configuration (GitHub API usage and prerelease preference)."""
        should_use_github = True
        should_use_prerelease = False

        if catalog_entry is None:
            catalog_entry = self.config_manager.load_catalog_entry(repo_name.lower())

        if catalog_entry:
            github_config = catalog_entry.get("github", {})
            should_use_github = github_config.get("repo", True)
            should_use_prerelease = github_config.get("prerelease", False)

        return should_use_github, should_use_prerelease

    async def _fetch_release_data(
        self,
        fetcher: GitHubReleaseFetcher,
        should_use_prerelease: bool,
        is_url_install: bool,
        owner: str,
        repo_name: str,
    ) -> tuple[dict, bool]:
        """Fetch release data with fallback logic."""
        used_prerelease_fallback = False

        if should_use_prerelease:
            logger.debug(f"Fetching latest prerelease for {owner}/{repo_name}")
            release_data = await fetcher.fetch_latest_prerelease()
        else:
            try:
                release_data = await fetcher.fetch_latest_release()
            except aiohttp.ClientResponseError as e:
                if e.status == 404 and is_url_install:
                    # For URL installations, fallback to prerelease if stable release not found
                    logger.debug(
                        f"Stable release not found for {owner}/{repo_name}, trying prerelease..."
                    )
                    try:
                        release_data = await fetcher.fetch_latest_prerelease()
                        logger.info(f"✅ Found prerelease for {owner}/{repo_name}")
                        used_prerelease_fallback = True
                    except Exception as prerelease_error:
                        logger.error(
                            f"❌ No releases found for {owner}/{repo_name}: {prerelease_error}"
                        )
                        raise e  # Re-raise original 404 error
                else:
                    raise  # Re-raise other errors or catalog-based installations

        return release_data, used_prerelease_fallback

    def _get_appimage_asset(
        self,
        fetcher: GitHubReleaseFetcher,
        release_data: dict,
        catalog_entry: dict | None,
    ) -> dict | None:
        """Get the AppImage asset from release data."""
        appimage_asset = fetcher.extract_appimage_asset(release_data)

        # Use catalog for AppImage selection if available
        if catalog_entry and appimage_asset:
            preferred_suffixes = catalog_entry.get("appimage", {}).get(
                "characteristic_suffix", []
            )
            if preferred_suffixes:
                appimage_asset = fetcher.select_best_appimage(release_data, preferred_suffixes)

        return appimage_asset

    async def _setup_icon_asset(
        self,
        fetcher: GitHubReleaseFetcher,
        catalog_entry: dict | None,
        repo: str,
        repo_name: str,
        icon_dir: Path,
        no_icon: bool,
    ) -> IconAsset | None:
        """Setup icon asset for download."""
        if no_icon:
            return None

        # Use catalog icon configuration
        if catalog_entry and catalog_entry.get("icon"):
            return await self._setup_catalog_icon(fetcher, catalog_entry, icon_dir)

        # Fallback for specific repos (demo purposes)
        if "appflowy" in repo.lower():
            return await self._setup_appflowy_icon(fetcher, repo_name, icon_dir)

        return None

    async def _setup_catalog_icon(
        self,
        fetcher: GitHubReleaseFetcher,
        catalog_entry: dict,
        icon_dir: Path,
    ) -> IconAsset | None:
        """Setup icon from catalog configuration."""
        icon_config = catalog_entry["icon"]
        icon_name = icon_config["name"]
        icon_url = icon_config["url"]

        # Check if icon already exists
        if check_icon_exists(icon_name, icon_dir):
            logger.debug("Icon already exists, skipping download")
            return None

        # Handle icon URL templates
        if not icon_url.startswith("http"):
            try:
                default_branch = await fetcher.get_default_branch()
                icon_url = fetcher.build_icon_url(icon_url, default_branch)
                logger.debug(f"🎨 Built icon URL from template: {icon_url}")
            except Exception as e:
                logger.warning(f"⚠️  Failed to build icon URL from template: {e}")
                return None

        return IconAsset(icon_filename=icon_name, icon_url=icon_url)

    async def _setup_appflowy_icon(
        self,
        fetcher: GitHubReleaseFetcher,
        repo_name: str,
        icon_dir: Path,
    ) -> IconAsset | None:
        """Setup AppFlowy-specific icon (fallback demo)."""
        icon_name = "appflowy.svg"

        if check_icon_exists(icon_name, icon_dir):
            logger.debug(f"Icon already exists for {repo_name}, skipping download")
            return None

        try:
            icon_path = "frontend/resources/flowy_icons/40x/app_logo.svg"
            default_branch = await fetcher.get_default_branch()
            icon_url = fetcher.build_icon_url(icon_path, default_branch)
            logger.debug(f"🎨 Built AppFlowy icon URL: {icon_url}")
            return IconAsset(icon_filename=icon_name, icon_url=icon_url)
        except Exception as e:
            logger.warning(f"⚠️  Failed to build AppFlowy icon URL: {e}")
            return None

    async def _download_and_install(
        self,
        installer: Installer,
        catalog_entry: dict | None,
        repo_name: str,
        icon_dir: Path,
        no_icon: bool,
    ) -> tuple[Path, Path | None]:
        """Download and install AppImage and icon."""
        # Download AppImage
        with logger.progress_context():
            appimage_path = await installer.download_appimage(show_progress=True)

            # Download icon if requested
            icon_path = None
            if not no_icon and installer.icon is not None:
                icon_path = await installer.download_icon(icon_dir=icon_dir)

        # Make executable and move to install directory
        installer.make_executable(appimage_path)
        appimage_path = installer.move_to_install_dir(appimage_path)

        # Rename to clean name
        rename_to = self._get_rename_target(catalog_entry, repo_name)
        if rename_to:
            clean_name = installer.get_clean_appimage_name(rename_to)
            appimage_path = installer.rename_appimage(clean_name)

        return appimage_path, icon_path

    def _get_rename_target(self, catalog_entry: dict | None, repo_name: str) -> str:
        """Get the target name for renaming the AppImage."""
        if catalog_entry:
            return catalog_entry.get("appimage", {}).get("rename", repo_name)
        return repo_name

    async def _perform_verification(
        self,
        appimage_path: Path,
        appimage_asset: dict,
        catalog_entry: dict | None,
        release_data: dict,
        owner: str,
        repo_name: str,
        session: aiohttp.ClientSession,
        no_verify: bool,
    ) -> dict:
        """Perform verification of the downloaded AppImage."""
        should_verify = not no_verify
        verification_results = {}

        # Check if verification is disabled in catalog
        if catalog_entry:
            verification_config = catalog_entry.get("verification", {})
            if verification_config.get("skip", False):
                should_verify = False
                logger.debug(
                    f"⏭️  Verification skipped for {repo_name} (configured in catalog)"
                )

        if not should_verify:
            return verification_results

        logger.debug(f"🔍 Starting verification for {appimage_path.name}")
        verifier = Verifier(appimage_path)

        # Try different verification methods
        await self._verify_with_digest(verifier, appimage_asset, verification_results)

        if not verification_results.get("digest", {}).get("passed"):
            await self._verify_with_checksum_file(
                verifier,
                catalog_entry,
                release_data,
                owner,
                repo_name,
                session,
                appimage_path,
                verification_results,
            )

        # Basic file integrity check
        self._verify_file_size(verifier, appimage_asset, verification_results)

        logger.debug("✅ Verification completed")
        return verification_results

    async def _verify_with_digest(
        self,
        verifier: Verifier,
        appimage_asset: dict,
        verification_results: dict,
    ) -> None:
        """Verify using GitHub API digest."""
        if not appimage_asset.get("digest"):
            return

        try:
            verifier.verify_digest(appimage_asset["digest"])
            verification_results["digest"] = {
                "passed": True,
                "hash": appimage_asset["digest"],
                "details": "GitHub API digest verification",
            }
        except Exception as e:
            logger.error(f"❌ Digest verification failed: {e}")
            verification_results["digest"] = {
                "passed": False,
                "hash": appimage_asset.get("digest", ""),
                "details": str(e),
            }

    async def _verify_with_checksum_file(
        self,
        verifier: Verifier,
        catalog_entry: dict | None,
        release_data: dict,
        owner: str,
        repo_name: str,
        session: aiohttp.ClientSession,
        appimage_path: Path,
        verification_results: dict,
    ) -> None:
        """Verify using checksum file if configured."""
        if not catalog_entry:
            return

        verification_config = catalog_entry.get("verification", {})
        checksum_file = verification_config.get("checksum_file")

        if not checksum_file:
            return

        hash_type = verification_config.get("checksum_hash_type", "sha256")
        checksum_url = f"https://github.com/{owner}/{repo_name}/releases/download/{release_data['version']}/{checksum_file}"

        try:
            logger.debug(f"🔍 Verifying using checksum file: {checksum_file}")
            await verifier.verify_from_checksum_file(
                checksum_url, hash_type, session, appimage_path.name
            )
            computed_hash = verifier.compute_hash(hash_type)
            verification_results["checksum_file"] = {
                "passed": True,
                "hash": f"{hash_type}:{computed_hash}",
                "details": f"Verified against {checksum_file}",
            }
        except Exception as e:
            logger.error(f"❌ Checksum file verification failed: {e}")
            verification_results["checksum_file"] = {
                "passed": False,
                "hash": "",
                "details": str(e),
            }

    def _verify_file_size(
        self,
        verifier: Verifier,
        appimage_asset: dict,
        verification_results: dict,
    ) -> None:
        """Verify file size integrity."""
        try:
            file_size = verifier.get_file_size()
            expected_size = appimage_asset.get("size", 0)
            if expected_size > 0:
                verifier.verify_size(expected_size)
            verification_results["size"] = {
                "passed": True,
                "details": f"File size: {file_size:,} bytes",
            }
        except Exception as e:
            logger.warning(f"⚠️  Size verification failed: {e}")
            verification_results["size"] = {"passed": False, "details": str(e)}

    async def _finalize_installation(
        self,
        appimage_path: Path,
        icon_path: Path | None,
        catalog_entry: dict | None,
        repo_name: str,
        owner: str,
        release_data: dict,
        appimage_asset: dict,
        verification_results: dict,
        should_use_github: bool,
        should_use_prerelease: bool,
        config_key: str,
        no_desktop: bool,
        icon_dir: Path,
    ) -> None:
        """Finalize the installation with configuration and desktop entry."""
        # Create app configuration
        app_config = self._create_app_config(
            catalog_entry,
            repo_name,
            owner,
            release_data,
            appimage_asset,
            verification_results,
            should_use_github,
            should_use_prerelease,
            appimage_path,
        )

        # Save configuration
        self.config_manager.save_app_config(config_key, app_config)

        # Cleanup old backups
        try:
            update_manager = UpdateManager(self.config_manager)
            update_manager.cleanup_old_backups(config_key)
        except Exception as e:
            logger.warning(f"⚠️  Failed to cleanup old backups for {config_key}: {e}")

        # Create desktop entry
        if not no_desktop:
            self._create_desktop_entry(appimage_path, icon_path, repo_name)

        # Log verification summary
        log_verification_summary(appimage_path, app_config, verification_results)

    def _create_app_config(
        self,
        catalog_entry: dict | None,
        repo_name: str,
        owner: str,
        release_data: dict,
        appimage_asset: dict,
        verification_results: dict,
        should_use_github: bool,
        should_use_prerelease: bool,
        appimage_path: Path,
    ) -> AppConfig:
        """Create application configuration."""
        # Get stored hash from verification or asset
        stored_hash = self._get_stored_hash(verification_results, appimage_asset)

        if catalog_entry:
            appimage_config = catalog_entry.get("appimage", {})
            verification_config = catalog_entry.get("verification", {})

            rename = appimage_config.get("rename", repo_name)
            name_template = appimage_config.get(
                "name_template", "{rename}-{latest_version}.AppImage"
            )
            characteristic_suffix = appimage_config.get("characteristic_suffix", [""])

            # Auto-detect digest availability
            has_digest = bool(appimage_asset.get("digest"))
            use_digest = has_digest or verification_config.get("digest", False)

            verification = VConfig(
                digest=use_digest,
                skip=verification_config.get("skip", False),
                checksum_file=verification_config.get("checksum_file", ""),
                checksum_hash_type=verification_config.get("checksum_hash_type", "sha256"),
            )
        else:
            rename = repo_name
            name_template = "{rename}-{latest_version}.AppImage"
            characteristic_suffix = [""]

            # Auto-detect digest for URL installations
            has_digest = bool(appimage_asset.get("digest"))
            verification = VConfig(
                digest=has_digest,
                skip=False,
                checksum_file="",
                checksum_hash_type="sha256",
            )

        return AppConfig(
            config_version=self.config_manager.DEFAULT_CONFIG_VERSION,
            appimage=AppImageConfig(
                version=release_data["version"],
                name=appimage_path.name,
                rename=rename,
                name_template=name_template,
                characteristic_suffix=characteristic_suffix,
                installed_date=datetime.now().isoformat(),
                digest=stored_hash,
            ),
            owner=owner,
            repo=repo_name,
            github=GitHubConfig(
                repo=should_use_github,
                prerelease=should_use_prerelease,
            ),
            verification=verification,
            icon=self._create_icon_config(
                catalog_entry, None, icon_path, self.global_config["directory"]["icon"]
            ),
        )

    def _get_stored_hash(self, verification_results: dict, appimage_asset: dict) -> str:
        """Get the hash to store in configuration."""
        if verification_results.get("digest", {}).get("passed"):
            return verification_results["digest"]["hash"]
        elif verification_results.get("checksum_file", {}).get("passed"):
            return verification_results["checksum_file"]["hash"]
        elif appimage_asset.get("digest"):
            return appimage_asset["digest"]
        return ""

    def _create_icon_config(
        self,
        catalog_entry: dict | None,
        icon_asset: IconAsset | None,
        icon_path: Path | None,
        icon_dir: Path,
    ) -> IconConfig:
        """Create icon configuration based on available information."""
        if icon_asset:
            # Icon was downloaded - save the original template path if available
            original_url = icon_asset["icon_url"]
            if catalog_entry and catalog_entry.get("icon"):
                # Check if we used a template path
                catalog_url = catalog_entry["icon"]["url"]
                if not catalog_url.startswith("http"):
                    # This was a template path, save it for future updates
                    original_url = catalog_url

            return IconConfig(
                url=original_url,
                name=icon_asset["icon_filename"],
                installed=icon_path is not None,
            )
        elif catalog_entry and catalog_entry.get("icon"):
            # Icon configured in catalog but not downloaded
            return IconConfig(
                url=catalog_entry["icon"]["url"],
                name=catalog_entry["icon"]["name"],
                installed=False,
            )
        else:
            # No icon configuration
            return IconConfig(url="", name="", installed=False)

    def _create_desktop_entry(
        self, appimage_path: Path, icon_path: Path | None, repo_name: str
    ) -> None:
        """Create desktop entry for the installed application."""
        try:
            desktop_path = create_desktop_entry_for_app(
                app_name=repo_name,
                appimage_path=appimage_path,
                icon_path=icon_path,
                comment=f"{repo_name.title()} AppImage Application",
                categories=["Utility"],
                config_manager=self.config_manager,
            )
            logger.debug(f"🖥️  Desktop entry ready: {desktop_path.name}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to create desktop entry: {e}")

    def _print_installation_summary(
        self, repos: list[tuple[str, str, str]], results: list
    ) -> None:
        """Print installation summary for multiple repos."""
        print("\n📦 Installation Summary:")
        print("-" * 50)
        for (owner, repo, url), result in zip(repos, results, strict=False):
            repo_name = f"{owner}/{repo}"
            if isinstance(result, Exception):
                print(f"{repo_name:<30} ❌ Failed: {result}")
            else:
                success, message, verification_results = result[0], result[1], result[2]
                status = "✅" if success else "❌"
                verification_status = self._get_verification_status(verification_results)
                print(f"{repo_name:<30} {status} {message:<20} {verification_status}")

    def _print_catalog_installation_summary(self, apps: list[str], results: list) -> None:
        """Print installation summary for multiple catalog apps."""
        print("\n📦 Installation Summary:")
        print("-" * 50)
        for app, result in zip(apps, results, strict=False):
            if isinstance(result, Exception):
                print(f"{app:<30} ❌ Failed: {result}")
            else:
                success, message, verification_results = result[0], result[1], result[2]
                status = "✅" if success else "❌"
                verification_status = self._get_verification_status(verification_results)
                print(f"{app:<30} {status} {message:<20} {verification_status}")

    def _get_verification_status(self, verification_results: dict) -> str:
        """Get verification status string for display."""
        if not verification_results:
            return "No verification"

        passed_checks = sum(
            1 for result in verification_results.values() if result.get("passed")
        )
        total_checks = len(verification_results)

        if passed_checks == total_checks:
            return f"✅ Verified ({passed_checks}/{total_checks})"
        elif passed_checks > 0:
            return f"⚠️  Partial ({passed_checks}/{total_checks})"
        else:
            return f"❌ Failed ({passed_checks}/{total_checks})"
