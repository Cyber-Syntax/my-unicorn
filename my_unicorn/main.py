"""Main CLI entry point for my-unicorn AppImage installer.

This module provides the command-line interface for installing, updating,
and managing AppImage applications using the modular architecture.
"""

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import uvloop

from .auth import GitHubAuthManager, auth_manager
from .config import AppConfig, AppImageConfig, ConfigManager, GitHubConfig, IconConfig
from .config import VerificationConfig as VConfig
from .desktop import create_desktop_entry_for_app
from .github_client import GitHubReleaseFetcher
from .install import IconAsset, Installer
from .logger import get_logger
from .parser import is_github_url, parse_github_url
from .update import UpdateManager
from .utils import check_icon_exists
from .verify import Verifier, log_verification_summary

logger = get_logger(__name__)


class CLI:
    """Command-line interface for my-unicorn."""

    def __init__(self) -> None:
        """Initialize CLI with configuration."""
        self.config_manager = ConfigManager()
        self.global_config = self.config_manager.load_global_config()
        self.auth_manager = auth_manager
        self.update_manager = UpdateManager(self.config_manager)

        # Setup file logging
        self._setup_file_logging()

    def parse_cli_args(self) -> argparse.Namespace:
        """Parse command-line arguments."""
        parser = argparse.ArgumentParser(
            description="my-unicorn AppImage Installer",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Install from GitHub URL
  %(prog)s install https://github.com/AppFlowy-IO/AppFlowy

  # Install from catalog (comma-separated)
  %(prog)s install appflowy,joplin,obsidian

  # Update apps
  %(prog)s update appflowy,joplin
  %(prog)s update

  # Other commands
  %(prog)s list
  %(prog)s auth --save-token
            """,
        )

        subparsers = parser.add_subparsers(dest="command", help="Available commands")

        # Install command
        install_parser = subparsers.add_parser(
            "install",
            help="Install AppImages from URLs or catalog",
            epilog="""
Examples:
  # Install from GitHub URL
  %(prog)s install https://github.com/AppFlowy-IO/AppFlowy

  # Install from catalog (comma-separated)
  %(prog)s install appflowy,joplin,obsidian

Note: Cannot mix URLs and catalog names in the same command
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        install_parser.add_argument(
            "targets",
            nargs="+",
            help="GitHub URLs OR catalog app names (comma-separated, cannot mix types)",
        )
        install_parser.add_argument(
            "--concurrency",
            type=int,
            default=self.global_config["max_concurrent_downloads"],
            help="Max parallel installs",
        )
        install_parser.add_argument(
            "--no-icon", action="store_true", help="Skip icon download"
        )
        install_parser.add_argument(
            "--no-verify", action="store_true", help="Skip verification"
        )
        install_parser.add_argument(
            "--no-desktop",
            action="store_true",
            help="Skip desktop entry creation (only affects install, not updates)",
        )
        install_parser.add_argument(
            "--verbose", action="store_true", help="Show detailed logs during installation"
        )

        # Update command
        update_parser = subparsers.add_parser(
            "update",
            help="Update installed AppImages",
            epilog="""
Examples:
  %(prog)s update                    # Update all installed apps
  %(prog)s update appflowy joplin    # Update specific apps
  %(prog)s update appflowy,joplin    # Comma-separated apps
            """,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        update_parser.add_argument(
            "apps",
            nargs="*",
            help="App names to update (comma-separated supported, empty for all)",
        )
        update_parser.add_argument(
            "--check-only", action="store_true", help="Only check for updates"
        )
        update_parser.add_argument(
            "--verbose", action="store_true", help="Show detailed logs during update"
        )

        # List command
        list_parser = subparsers.add_parser("list", help="List installed AppImages")
        list_parser.add_argument(
            "--available", action="store_true", help="Show available apps from catalog"
        )

        # Remove command
        remove_parser = subparsers.add_parser("remove", help="Remove installed AppImages")
        remove_parser.add_argument("apps", nargs="+", help="Apps to remove")
        remove_parser.add_argument(
            "--keep-config", action="store_true", help="Keep configuration files"
        )

        # Auth command
        auth_parser = subparsers.add_parser("auth", help="Manage GitHub authentication")
        auth_group = auth_parser.add_mutually_exclusive_group(required=True)
        auth_group.add_argument("--save-token", action="store_true", help="Save GitHub token")
        auth_group.add_argument(
            "--remove-token", action="store_true", help="Remove GitHub token"
        )
        auth_group.add_argument("--status", action="store_true", help="Show auth status")

        # Config command
        config_parser = subparsers.add_parser("config", help="Manage configuration")
        config_group = config_parser.add_mutually_exclusive_group(required=True)
        config_group.add_argument("--show", action="store_true", help="Show current config")
        config_group.add_argument("--reset", action="store_true", help="Reset to defaults")

        return parser.parse_args()

    def _setup_file_logging(self) -> None:
        """Setup file logging with rotation."""
        try:
            log_file = self.global_config["directory"]["logs"] / "my-unicorn.log"
            log_level = self.global_config.get("log_level", "INFO")
            logger.setup_file_logging(log_file, log_level)
            logger.debug("File logging initialized")
        except Exception as e:
            logger.warning(f"Failed to setup file logging: {e}")

    async def cmd_install(self, args: argparse.Namespace) -> None:
        """Handle install command."""
        # Expand comma-separated inputs
        all_targets = []
        for target in args.targets:
            if "," in target:
                all_targets.extend([t.strip() for t in target.split(",") if t.strip()])
            else:
                all_targets.append(target.strip())

        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in all_targets:
            target_lower = target.lower()
            if target_lower not in seen:
                seen.add(target_lower)
                unique_targets.append(target)

        if not unique_targets:
            print("❌ No targets specified.")
            return

        # Determine if this is URL installation or catalog installation
        first_target = unique_targets[0]
        is_url_install = is_github_url(first_target)

        # Validate all targets are the same type
        mixed_types = False
        for target in unique_targets:
            if is_github_url(target) != is_url_install:
                mixed_types = True
                break

        if mixed_types:
            print("❌ Cannot mix GitHub URLs and catalog app names in the same command.")
            print("   Use separate commands for URLs and catalog apps.")
            return

        # Ensure directories exist
        self.config_manager.ensure_directories_from_config(self.global_config)

        if is_url_install:
            await self._install_from_urls(unique_targets, args)
        else:
            await self._install_from_catalog(unique_targets, args)

    async def _install_from_urls(self, urls: list[str], args: argparse.Namespace) -> None:
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
        semaphore = asyncio.Semaphore(args.concurrency)
        tasks = []

        async with aiohttp.ClientSession() as session:
            for owner, repo, url in valid_repos:
                tasks.append(
                    self._install_single_repo(f"{owner}/{repo}", session, semaphore, args)
                )

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        if len(valid_repos) > 1:
            print("\n📦 Installation Summary:")
            print("-" * 50)
            for (owner, repo, url), result in zip(valid_repos, results, strict=False):
                repo_name = f"{owner}/{repo}"
                if isinstance(result, Exception):
                    print(f"{repo_name:<30} ❌ Failed: {result}")
                else:
                    # Type narrowing - result is now tuple[bool, str, dict]
                    success, message, verification_results = result[0], result[1], result[2]
                    status = "✅" if success else "❌"
                    verification_status = self._get_verification_status(verification_results)
                    print(f"{repo_name:<30} {status} {message:<20} {verification_status}")

    async def _install_from_catalog(
        self, app_names: list[str], args: argparse.Namespace
    ) -> None:
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
        semaphore = asyncio.Semaphore(args.concurrency)
        tasks = []

        async with aiohttp.ClientSession() as session:
            for app in valid_apps:
                tasks.append(self._install_catalog_app(app, session, semaphore, args))

            results = await asyncio.gather(*tasks, return_exceptions=True)

        # Print summary
        if len(valid_apps) > 1:
            print("\n📦 Installation Summary:")
            print("-" * 50)
            for app, result in zip(valid_apps, results, strict=False):
                if isinstance(result, Exception):
                    print(f"{app:<30} ❌ Failed: {result}")
                else:
                    # Type narrowing - result is now tuple[bool, str, dict]
                    success, message, verification_results = result[0], result[1], result[2]
                    status = "✅" if success else "❌"
                    verification_status = self._get_verification_status(verification_results)
                    print(f"{app:<30} {status} {message:<20} {verification_status}")

    async def _install_catalog_app(
        self,
        app_name: str,
        session: aiohttp.ClientSession,
        semaphore: asyncio.Semaphore,
        args: argparse.Namespace,
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
        args: argparse.Namespace,
        catalog_entry: dict | None = None,
    ) -> tuple[bool, str, dict]:
        """Install a single repository."""
        async with semaphore:
            try:
                owner, repo_name = repo.split("/", 1)
                logger.debug(f"Installing {owner}/{repo_name}")

                # Determine the app config key that will be used for saving
                # Need to get the rename value first to ensure consistency
                if catalog_entry:
                    config_key = (
                        catalog_entry.get("appimage", {}).get("rename", repo_name).lower()
                    )
                else:
                    config_key = repo_name.lower()

                # Check if app is already installed and create backup if needed
                existing_app_config = self.config_manager.load_app_config(config_key)
                if existing_app_config:
                    logger.debug(f"Found existing installation of {repo_name}")
                    # Create backup of existing version before installing new one
                    storage_dir = self.global_config["directory"]["storage"]
                    backup_dir = self.global_config["directory"]["backup"]
                    current_appimage_path = (
                        storage_dir / existing_app_config["appimage"]["name"]
                    )

                    logger.debug(f"Looking for existing AppImage at: {current_appimage_path}")
                    if current_appimage_path.exists():
                        logger.debug(f"Creating backup for existing {repo_name}")
                        backup_dir.mkdir(parents=True, exist_ok=True)

                        # Create backup filename
                        stem = current_appimage_path.stem
                        suffix = current_appimage_path.suffix
                        current_version = existing_app_config["appimage"]["version"]
                        version_str = f"-{current_version}" if current_version else ""
                        backup_name = f"{stem}{version_str}.backup{suffix}"
                        backup_path = backup_dir / backup_name

                        # Copy file to backup location
                        import shutil

                        shutil.copy2(current_appimage_path, backup_path)
                        logger.debug(f"💾 Backup created: {backup_path}")
                    else:
                        logger.debug(
                            f"No existing AppImage file found at {current_appimage_path}"
                        )
                else:
                    logger.debug(f"No existing installation found for {repo_name}")

                # Check if app is configured to use GitHub API
                should_use_github = True
                should_use_prerelease = False
                if catalog_entry is None:
                    catalog_entry = self.config_manager.load_catalog_entry(repo_name.lower())

                if catalog_entry:
                    github_config = catalog_entry.get("github", {})
                    should_use_github = github_config.get("repo", True)
                    should_use_prerelease = github_config.get("prerelease", False)

                if not should_use_github:
                    logger.error(f"GitHub API disabled for {repo_name} (github.repo: false)")
                    return False, "GitHub API disabled for this app", {}

                fetcher = GitHubReleaseFetcher(owner, repo_name, session)

                # Track if we fallback to prerelease for config update
                used_prerelease_fallback = False

                # Fetch appropriate release type with fallback for URL installations
                if should_use_prerelease:
                    logger.debug(f"Fetching latest prerelease for {owner}/{repo_name}")
                    release_data = await fetcher.fetch_latest_prerelease()
                else:
                    try:
                        release_data = await fetcher.fetch_latest_release()
                    except aiohttp.ClientResponseError as e:
                        if e.status == 404 and catalog_entry is None:
                            # For URL installations, fallback to prerelease if stable release not found
                            logger.debug(
                                f"Stable release not found for {owner}/{repo_name}, trying prerelease..."
                            )
                            try:
                                release_data = await fetcher.fetch_latest_prerelease()
                                logger.info(f"✅ Found prerelease for {owner}/{repo_name}")
                                used_prerelease_fallback = True
                                should_use_prerelease = True  # Update for config
                            except Exception as prerelease_error:
                                logger.error(
                                    f"❌ No releases found for {owner}/{repo_name}: {prerelease_error}"
                                )
                                raise e  # Re-raise original 404 error
                        else:
                            raise  # Re-raise other errors or catalog-based installations

                # Find AppImage asset
                appimage_asset = fetcher.extract_appimage_asset(release_data)
                if not appimage_asset:
                    logger.warning(f"No AppImage found for {repo}")
                    return False, "No AppImage found", {}

                # Set up installation paths
                download_dir = self.global_config["directory"]["download"]
                install_dir = self.global_config["directory"]["storage"]
                icon_dir = self.global_config["directory"]["icon"]

                # catalog_entry is already loaded above for prerelease check

                icon_asset = None

                # Use catalog for AppImage selection if available
                if catalog_entry:
                    preferred_suffixes = catalog_entry.get("appimage", {}).get(
                        "characteristic_suffix", []
                    )
                    if preferred_suffixes:
                        appimage_asset = fetcher.select_best_appimage(
                            release_data, preferred_suffixes
                        )

                icon_asset = None
                if not args.no_icon:
                    if catalog_entry and catalog_entry.get("icon"):
                        icon_name = catalog_entry["icon"]["name"]
                        icon_url = catalog_entry["icon"]["url"]

                        # Check if icon URL is a path template (doesn't start with http)
                        if not icon_url.startswith("http"):
                            # Build full URL from path template
                            try:
                                default_branch = await fetcher.get_default_branch()
                                icon_url = fetcher.build_icon_url(icon_url, default_branch)
                                logger.debug(f"🎨 Built icon URL from template: {icon_url}")
                            except Exception as e:
                                logger.warning(
                                    f"⚠️  Failed to build icon URL from template: {e}"
                                )
                                icon_url = None

                        if icon_url and check_icon_exists(icon_name, icon_dir):
                            logger.debug(
                                f"Icon already exists for {repo_name}, skipping download"
                            )
                        elif icon_url:
                            icon_asset = IconAsset(
                                icon_filename=icon_name,
                                icon_url=icon_url,
                            )
                    elif "appflowy" in repo.lower():
                        # Fallback for demo purposes
                        icon_name = "appflowy.svg"
                        icon_path = "frontend/resources/flowy_icons/40x/app_logo.svg"
                        if check_icon_exists(icon_name, icon_dir):
                            logger.debug(
                                f"Icon already exists for {repo_name}, skipping download"
                            )
                        else:
                            try:
                                default_branch = await fetcher.get_default_branch()
                                icon_url = fetcher.build_icon_url(icon_path, default_branch)
                                icon_asset = IconAsset(
                                    icon_filename=icon_name,
                                    icon_url=icon_url,
                                )
                                logger.debug(f"🎨 Built AppFlowy icon URL: {icon_url}")
                            except Exception as e:
                                logger.warning(f"⚠️  Failed to build AppFlowy icon URL: {e}")

                # Install
                installer = Installer(
                    asset=appimage_asset,
                    session=session,
                    icon=icon_asset,
                    download_dir=download_dir,
                    install_dir=install_dir,
                )

                # Get clean name for renaming (use catalog rename or repo name)
                rename_to = None
                if catalog_entry:
                    rename_to = catalog_entry.get("appimage", {}).get("rename", repo_name)
                else:
                    rename_to = repo_name

                # Download AppImage first (without renaming)
                with logger.progress_context():
                    appimage_path = await installer.download_appimage(show_progress=True)

                    # Download icon if requested
                    icon_path = None
                    if not args.no_icon and icon_asset is not None:
                        icon_path = await installer.download_icon(icon_dir=icon_dir)

                # Perform verification if requested and not skipped by catalog (BEFORE renaming)
                should_verify = not args.no_verify
                verification_results = {}

                if catalog_entry:
                    verification_config = catalog_entry.get("verification", {})
                    if verification_config.get("skip", False):
                        should_verify = False
                        logger.debug(
                            f"⏭️  Verification skipped for {repo_name} (configured in catalog)"
                        )

                if should_verify:
                    logger.debug(
                        f"🔍 Starting verification for {appimage_path.name} (original filename)"
                    )
                    verifier = Verifier(appimage_path)

                    # Try digest verification first (from GitHub API)
                    if appimage_asset.get("digest"):
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

                    # Try checksum file verification if configured
                    elif catalog_entry and verification_config.get("checksum_file"):
                        checksum_file = verification_config["checksum_file"]
                        hash_type = verification_config.get("checksum_hash_type", "sha256")
                        checksum_url = f"https://github.com/{owner}/{repo_name}/releases/download/{release_data['version']}/{checksum_file}"

                        try:
                            logger.debug(f"🔍 Verifying using checksum file: {checksum_file}")
                            # Use original filename for checksum verification
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

                    # Basic file integrity check
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

                    logger.debug("✅ Verification completed")

                # Now make executable and move to install directory
                installer.make_executable(appimage_path)
                appimage_path = installer.move_to_install_dir(appimage_path)

                # Finally rename to clean name
                if rename_to:
                    clean_name = installer.get_clean_appimage_name(rename_to)
                    appimage_path = installer.rename_appimage(clean_name)

                # Save app config with verification info
                # Use catalog info if available, otherwise use defaults
                if catalog_entry:
                    appimage_config = catalog_entry.get("appimage", {})
                    verification_config = catalog_entry.get("verification", {})
                    icon_config = catalog_entry.get("icon", {})

                    rename = appimage_config.get("rename", repo_name)
                    name_template = appimage_config.get(
                        "name_template", "{rename}-{latest_version}.AppImage"
                    )
                    characteristic_suffix = appimage_config.get("characteristic_suffix", [""])

                    # Auto-detect digest availability and update verification config
                    has_digest = bool(appimage_asset.get("digest"))
                    use_digest = has_digest or verification_config.get("digest", False)

                    verification = VConfig(
                        digest=use_digest,
                        skip=verification_config.get("skip", False),
                        checksum_file=verification_config.get("checksum_file", ""),
                        checksum_hash_type=verification_config.get(
                            "checksum_hash_type", "sha256"
                        ),
                    )

                    # Log digest detection for debugging
                    if has_digest and not verification_config.get("digest", False):
                        logger.debug(
                            f"🔍 Digest detected for {repo_name}, enabling digest verification"
                        )
                        logger.debug(f"   Digest: {appimage_asset.get('digest', '')}")

                    # Log prerelease fallback for debugging
                    if used_prerelease_fallback:
                        logger.debug(
                            f"🔄 Enabling prerelease mode for {repo_name} (fallback from URL installation)"
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

                    if has_digest:
                        logger.debug(
                            f"🔍 Digest detected for {repo_name}, enabling digest verification"
                        )
                        logger.debug(f"   Digest: {appimage_asset.get('digest', '')}")

                    # Log prerelease fallback for debugging
                    if used_prerelease_fallback:
                        logger.debug(
                            f"🔄 Enabling prerelease mode for {repo_name} (fallback from URL installation)"
                        )

                # Store the computed hash from verification or GitHub digest
                stored_hash = ""
                if verification_results.get("digest", {}).get("passed"):
                    stored_hash = verification_results["digest"]["hash"]
                elif verification_results.get("checksum_file", {}).get("passed"):
                    stored_hash = verification_results["checksum_file"]["hash"]
                elif appimage_asset.get("digest"):
                    stored_hash = appimage_asset["digest"]

                app_config = AppConfig(
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
                        catalog_entry, icon_asset, icon_path, icon_dir
                    ),
                )

                self.config_manager.save_app_config(config_key, app_config)

                # Clean up old backups after successful installation (if this was an update)
                if existing_app_config:
                    try:
                        update_manager = UpdateManager(self.config_manager)
                        update_manager.cleanup_old_backups(config_key)
                    except Exception as e:
                        logger.warning(
                            f"⚠️  Failed to cleanup old backups for {rename.lower()}: {e}"
                        )

                # Create or update desktop entry if not disabled
                if not args.no_desktop:
                    try:
                        desktop_path = create_desktop_entry_for_app(
                            app_name=rename_to,
                            appimage_path=appimage_path,
                            icon_path=icon_path,
                            comment=f"{rename_to.title()} AppImage Application",
                            categories=["Utility"],
                            config_manager=self.config_manager,
                        )
                        logger.debug(f"🖥️  Desktop entry ready: {desktop_path.name}")
                    except Exception as e:
                        logger.warning(f"⚠️  Failed to create desktop entry: {e}")

                # Log comprehensive verification summary for debugging
                log_verification_summary(appimage_path, app_config, verification_results)

                # Show completion message after progress bars
                print(f"✅ {repo_name} {release_data['version']} installed successfully")
                if stored_hash:
                    logger.debug(f"🔐 Stored hash: {stored_hash}")

                return True, f"Installed {release_data['version']}", verification_results

            except Exception as e:
                logger.error(f"Failed to install {repo}: {e}")
                return False, str(e), {}

    def _get_verification_status(self, verification_results: dict[str, dict[str, Any]]) -> str:
        """Get verification status emoji and text for summary display.

        Args:
            verification_results: Dictionary containing verification results

        Returns:
            String with verification status for display

        """
        if not verification_results:
            return "⏭️ No verification"

        # Check if verification was skipped
        passed_checks = []
        failed_checks = []

        for check_type, result in verification_results.items():
            if isinstance(result, dict) and "passed" in result:
                if result["passed"]:
                    passed_checks.append(check_type)
                else:
                    failed_checks.append(check_type)

        if not passed_checks and not failed_checks:
            return "⏭️ No verification"
        elif failed_checks:
            if passed_checks:
                return f"⚠️ Partial verification ({len(passed_checks)}/{len(passed_checks) + len(failed_checks)})"
            else:
                return "❌ Verification failed"
        # All checks passed
        elif "digest" in passed_checks:
            return "🔐 Verified (digest)"
        elif "checksum_file" in passed_checks:
            return "🔐 Verified (checksum)"
        else:
            return "Verification skipped but size verified"

    def _format_version_display(self, version: str) -> str:
        """Format version string for display with exactly one 'v' prefix.

        Args:
            version: Version string that may or may not have 'v' prefix

        Returns:
            Version string with exactly one 'v' prefix

        """
        if not version:
            return "v"

        # Strip any existing 'v' prefix and add exactly one
        clean_version = version.lstrip("v")
        return f"v{clean_version}"

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

    async def cmd_list(self, args: argparse.Namespace) -> None:
        """Handle list command."""
        if args.available:
            apps = self.config_manager.list_catalog_apps()
            print("📋 Available AppImages:")
        else:
            apps = self.config_manager.list_installed_apps()
            print("📦 Installed AppImages:")

        if not apps:
            print("  None found")
            return

        for app in sorted(apps):
            if not args.available:
                config = self.config_manager.load_app_config(app)
                if config:
                    version = config["appimage"]["version"]
                    installed_date = config["appimage"].get("installed_date", "Unknown")
                    if installed_date != "Unknown":
                        try:
                            date_obj = datetime.fromisoformat(
                                installed_date.replace("Z", "+00:00")
                            )
                            installed_date = date_obj.strftime("%Y-%m-%d")
                        except ValueError:
                            pass
                    print(
                        f"  {app:<20} {self._format_version_display(version):<16} ({installed_date})"
                    )
                else:
                    print(f"  {app:<20} (config error)")
            else:
                print(f"  {app}")

    async def cmd_update(self, args: argparse.Namespace) -> None:
        """Handle update command."""
        # Parse app names (handle comma-separated)
        if args.apps:
            all_apps = []
            for app_arg in args.apps:
                if "," in app_arg:
                    all_apps.extend([app.strip() for app in app_arg.split(",") if app.strip()])
                else:
                    all_apps.append(app_arg.strip())

            # Remove duplicates while preserving order
            seen = set()
            app_names = []
            for app in all_apps:
                app_lower = app.lower()
                if app_lower not in seen:
                    seen.add(app_lower)
                    app_names.append(app)
        else:
            app_names = None

        # Validate app names are installed
        if app_names:
            installed_apps = self.config_manager.list_installed_apps()
            valid_apps = []
            invalid_apps = []

            for app in app_names:
                if app.lower() in [installed.lower() for installed in installed_apps]:
                    # Find correct case
                    for installed in installed_apps:
                        if installed.lower() == app.lower():
                            valid_apps.append(installed)
                            break
                else:
                    invalid_apps.append(app)

            if invalid_apps:
                print("❌ Apps not installed:")
                for app in invalid_apps:
                    # Suggest similar installed apps
                    suggestions = [
                        inst for inst in installed_apps if app.lower() in inst.lower()
                    ][:2]
                    if suggestions:
                        print(f"   • {app} (did you mean: {', '.join(suggestions)}?)")
                    else:
                        print(f"   • {app}")

                if not valid_apps:
                    print("\nNo valid apps to update.")
                    return

            app_names = valid_apps

        if args.check_only:
            # Just check for updates
            update_infos = await self.update_manager.check_all_updates(app_names)

            if not update_infos:
                print("No installed apps found to check.")
                return

            print("🔍 Update Status:")
            print("-" * 60)

            has_updates = False
            for info in update_infos:
                status = "📦 Update available" if info.has_update else "✅ Up to date"
                version_info = (
                    f"{info.current_version} -> {info.latest_version}"
                    if info.has_update
                    else info.current_version
                )
                print(
                    f"{info.app_name:<20} {status:<20} {self._format_version_display(version_info)}"
                )
                if info.has_update:
                    has_updates = True

            if has_updates:
                print("\nRun 'my-unicorn update' to install updates.")
        else:
            # Perform updates
            if app_names:
                print(f"🔄 Updating {len(app_names)} app(s): {', '.join(app_names)}")

                # First check which apps actually need updates
                print("🔍 Checking for updates...")
                update_infos = await self.update_manager.check_all_updates(app_names)
                apps_to_update = [info for info in update_infos if info.has_update]
                apps_up_to_date = [info for info in update_infos if not info.has_update]

                if apps_up_to_date:
                    print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

                if not apps_to_update:
                    print("All specified apps are up to date!")
                    return

                print(f"📦 Updating {len(apps_to_update)} app(s) that need updates...")

                # Temporarily suppress console logging during downloads
                logger.set_console_level_temporarily("ERROR")

                try:
                    results = await self.update_manager.update_multiple_apps(
                        [info.app_name for info in apps_to_update]
                    )
                finally:
                    # Restore normal logging
                    logger.restore_console_level()

            else:
                installed_apps = self.config_manager.list_installed_apps()
                if not installed_apps:
                    print("No installed apps found to update.")
                    return

                print(f"🔄 Checking all {len(installed_apps)} installed app(s) for updates...")

                # Check which apps need updates
                update_infos = await self.update_manager.check_all_updates(installed_apps)
                apps_to_update = [info for info in update_infos if info.has_update]
                apps_up_to_date = [info for info in update_infos if not info.has_update]

                if apps_up_to_date:
                    print(f"✅ {len(apps_up_to_date)} app(s) already up to date")

                if not apps_to_update:
                    print("All apps are up to date!")
                    return

                print(f"📦 Updating {len(apps_to_update)} app(s) that need updates...")

                # Show which apps will be updated
                for info in apps_to_update:
                    print(
                        f"   • {info.app_name}: {info.current_version} → {info.latest_version}"
                    )

                print()  # Empty line for better spacing

                # Temporarily suppress console logging during downloads
                logger.set_console_level_temporarily("ERROR")

                try:
                    results = await self.update_manager.update_multiple_apps(
                        [info.app_name for info in apps_to_update]
                    )
                finally:
                    # Restore normal logging
                    logger.restore_console_level()

            print("\n📦 Update Summary:")
            print("-" * 50)

            # Show results for apps that were actually updated
            updated_count = 0
            failed_count = 0

            for app_name, success in results.items():
                if success:
                    updated_count += 1
                    # Find the version info for this app
                    app_info = next(
                        (info for info in apps_to_update if info.app_name == app_name), None
                    )
                    if app_info:
                        print(f"{app_name:<25} ✅ Updated to {app_info.latest_version}")
                    else:
                        print(f"{app_name:<25} ✅ Updated")
                else:
                    failed_count += 1
                    print(f"{app_name:<25} ❌ Update failed")

            # Show summary stats
            if updated_count > 0:
                print(f"\n🎉 Successfully updated {updated_count} app(s)")
            if failed_count > 0:
                print(f"❌ {failed_count} app(s) failed to update")

    async def cmd_remove(self, args: argparse.Namespace) -> None:
        """Handle remove command."""
        for app_name in args.apps:
            try:
                app_config = self.config_manager.load_app_config(app_name)
                if not app_config:
                    print(f"❌ App '{app_name}' not found")
                    continue

                # Remove AppImage file (try both original name and clean name)
                storage_dir = self.global_config["directory"]["storage"]
                appimage_path = storage_dir / app_config["appimage"]["name"]

                # Also try clean name format (lowercase .appimage)
                rename_value = app_config["appimage"].get("rename", app_name)
                clean_name = f"{rename_value.lower()}.appimage"
                clean_appimage_path = storage_dir / clean_name

                removed_files = []
                for path in [appimage_path, clean_appimage_path]:
                    if path.exists():
                        path.unlink()
                        removed_files.append(str(path))

                if removed_files:
                    print(f"✅ Removed AppImage(s): {', '.join(removed_files)}")
                else:
                    print(f"⚠️  AppImage not found: {appimage_path}")

                # Remove desktop entry
                try:
                    from .desktop import remove_desktop_entry_for_app

                    if remove_desktop_entry_for_app(app_name, self.config_manager):
                        print(f"✅ Removed desktop entry for {app_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Failed to remove desktop entry: {e}")

                # Remove icon if it exists
                if app_config.get("icon", {}).get("installed"):
                    icon_dir = self.global_config["directory"]["icon"]
                    icon_path = icon_dir / app_config["icon"]["name"]
                    if icon_path.exists():
                        icon_path.unlink()
                        print(f"✅ Removed icon: {icon_path}")

                # Remove config unless keeping it
                if not args.keep_config:
                    self.config_manager.remove_app_config(app_name)
                    print(f"✅ Removed config for {app_name}")
                else:
                    print(f"✅ Kept config for {app_name}")

            except Exception as e:
                logger.error(f"Failed to remove {app_name}: {e}")
                print(f"❌ Failed to remove {app_name}: {e}")

    async def cmd_auth(self, args: argparse.Namespace) -> None:
        """Handle auth command."""
        if args.save_token:
            try:
                GitHubAuthManager.save_token()
            except ValueError as e:
                print(f"❌ {e}")
                sys.exit(1)
        elif args.remove_token:
            GitHubAuthManager.remove_token()
        elif args.status:
            if self.auth_manager.is_authenticated():
                print("✅ GitHub token is configured")

                # Get fresh rate limit information by making a lightweight API call
                import aiohttp

                async def fetch_fresh_rate_limit():
                    try:
                        async with aiohttp.ClientSession() as session:
                            headers = GitHubAuthManager.apply_auth({})
                            # Make a lightweight API call to get rate limit info
                            async with session.get(
                                "https://api.github.com/rate_limit", headers=headers
                            ) as response:
                                response.raise_for_status()
                                self.auth_manager.update_rate_limit_info(
                                    dict(response.headers)
                                )
                                return await response.json()
                    except Exception as e:
                        print(f"   ⚠️  Failed to fetch fresh rate limit info: {e}")
                        return None

                # Fetch fresh rate limit info
                rate_limit_data = await fetch_fresh_rate_limit()

                # Show rate limit information
                rate_limit = self.auth_manager.get_rate_limit_status()
                remaining = rate_limit.get("remaining")
                reset_time = rate_limit.get("reset_time")
                reset_in = rate_limit.get("reset_in_seconds")

                print("\n📊 GitHub API Rate Limit Status:")
                if remaining is not None:
                    print(f"   🔢 Remaining requests: {remaining}")
                    if reset_time:
                        import datetime

                        reset_datetime = datetime.datetime.fromtimestamp(reset_time)
                        print(
                            f"   ⏰ Resets at: {reset_datetime.strftime('%Y-%m-%d %H:%M:%S')}"
                        )
                    if reset_in is not None and reset_in > 0:
                        if reset_in < 60:
                            print(f"   ⏳ Resets in: {reset_in} seconds")
                        elif reset_in < 3600:
                            minutes = reset_in // 60
                            seconds = reset_in % 60
                            print(f"   ⏳ Resets in: {minutes}m {seconds}s")
                        else:
                            hours = reset_in // 3600
                            minutes = (reset_in % 3600) // 60
                            print(f"   ⏳ Resets in: {hours}h {minutes}m")

                    # Rate limit warnings
                    if remaining < 100:
                        if remaining < 10:
                            print("   ⚠️  WARNING: Very low rate limit remaining!")
                        else:
                            print("   ⚠️  Rate limit getting low")

                    # Show additional rate limit details if available
                    if rate_limit_data and "resources" in rate_limit_data:
                        core_info = rate_limit_data["resources"].get("core", {})
                        if core_info:
                            limit = core_info.get("limit", 0)
                            print(f"   📋 Rate limit: {remaining}/{limit} requests")
                else:
                    print("   ℹ️  Unable to fetch rate limit information")
            else:
                print("❌ No GitHub token configured")
                print("Use 'my-unicorn auth --save-token' to configure authentication")

    def cmd_config(self, args: argparse.Namespace) -> None:
        """Handle config command."""
        if args.show:
            print("📋 Current Configuration:")
            print(f"  Config Version: {self.global_config['config_version']}")
            print(f"  Max Downloads: {self.global_config['max_concurrent_downloads']}")
            print(f"  Batch Mode: {self.global_config['batch_mode']}")
            print(f"  Log Level: {self.global_config['log_level']}")
            print(f"  Storage Dir: {self.global_config['directory']['storage']}")
            print(f"  Download Dir: {self.global_config['directory']['download']}")
        elif args.reset:
            # Reset to defaults
            default_config = self.config_manager._get_default_global_config()
            global_config = self.config_manager._convert_to_global_config(default_config)
            self.config_manager.save_global_config(global_config)
            print("✅ Configuration reset to defaults")

    async def run(self) -> None:
        """Run the CLI application."""
        args = self.parse_cli_args()

        if not args.command:
            print("❌ No command specified. Use --help for usage information.")
            sys.exit(1)

        try:
            if args.command == "install":
                await self.cmd_install(args)
            elif args.command == "update":
                await self.cmd_update(args)
            elif args.command == "list":
                await self.cmd_list(args)
            elif args.command == "remove":
                await self.cmd_remove(args)
            elif args.command == "auth":
                await self.cmd_auth(args)
            elif args.command == "config":
                self.cmd_config(args)
            else:
                print(f"❌ Unknown command: {args.command}")
                sys.exit(1)
        except KeyboardInterrupt:
            print("\n❌ Operation cancelled by user")
            sys.exit(1)
        except Exception as e:
            logger.exception("Unexpected error occurred")
            print(f"❌ Unexpected error: {e}")
            sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli = CLI()
    uvloop.run(cli.run())


if __name__ == "__main__":
    main()
