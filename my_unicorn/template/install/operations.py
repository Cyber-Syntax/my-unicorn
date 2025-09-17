"""Install operations for install templates using Command pattern.

This module provides different command implementations for install              
"""

from pathlib import Path
from typing import Any

from ...logger import get_logger
from .selectors import CatalogInstallContext, URLInstallContext

logger = get_logger(__name__)


class InstallOperation:
    """Base class for install operations."""

    def __init__(self, config_manager: Any) -> None:
        """Initialize install operation.

        Args:
            config_manager: Configuration manager for app configs

        """
        self.config_manager = config_manager


class CatalogInstallOperation(InstallOperation):
    """Catalog-specific install operations."""

    async def create_app_config(
        self,
        app_path: Path,
        context: CatalogInstallContext,
        icon_result: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create rich catalog-based configuration.

        Args:
            app_path: Path to installed AppImage
            context: Catalog installation context
            icon_result: Result from icon extraction
            **kwargs: Additional options

        Returns:
            Configuration creation result

        """
        try:
            # Debug logging to understand data structures
            logger.debug("Release data: %s", context.release_data)
            logger.debug("Release data type: %s", type(context.release_data))

            # Check version extraction
            if hasattr(context.release_data, "get"):
                version_val = context.release_data.get("version")
            else:
                version_val = getattr(context.release_data, "version", "no version attr")
            logger.debug("Release data version: %s", version_val)

            logger.debug("Verification result: %s", kwargs.get("verification_result"))
            logger.debug(
                "Verification result type: %s", type(kwargs.get("verification_result"))
            )

            # Get current timestamp for installed_date
            from datetime import datetime

            install_time = kwargs.get("install_time") or datetime.now().isoformat()

            # Get verification result for digest
            verification_result = kwargs.get("verification_result", {})
            logger.debug("Verification result content: %s", verification_result)

            digest = None
            if verification_result and verification_result.get("passed"):
                # Extract digest from verification methods if available
                methods = verification_result.get("methods", {})
                logger.debug("Verification methods: %s", methods)
                # Look for digest or sha256 in methods
                if "digest" in methods:
                    digest = methods["digest"]
                    logger.debug("Found digest in methods: %s", digest)
                elif "sha256" in methods:
                    digest = f"sha256:{methods['sha256']}"
                    logger.debug("Found sha256 in methods: %s", digest)

            # Fallback: extract digest from release_data assets if not found in verification
            if not digest and hasattr(context.release_data, "get"):
                assets = context.release_data.get("assets", [])

                # Try to get original asset name from context.appimage_asset
                original_asset_name = None
                if hasattr(context, "appimage_asset") and context.appimage_asset:
                    # Try different attribute names for the asset name
                    original_asset_name = (
                        getattr(context.appimage_asset, "name", None)
                        or getattr(context.appimage_asset, "filename", None)
                        or getattr(context.appimage_asset, "asset_name", None)
                    )

                app_filename = app_path.name
                logger.debug("Looking for digest in assets for file: %s", app_filename)
                logger.debug("Original asset name: %s", original_asset_name)
                logger.debug("Available assets: %s", [asset.get("name") for asset in assets])

                # Find matching asset by filename
                for asset in assets:
                    asset_name = asset.get("name", "")
                    matched = False

                    # Strategy 1: Match by original asset name (most reliable)
                    if original_asset_name and asset_name == original_asset_name:
                        matched = True
                        logger.debug("Matched by original asset name: %s", asset_name)

                    # Strategy 2: Match by current filename
                    elif asset_name == app_filename or asset_name.endswith(app_filename):
                        matched = True
                        logger.debug("Matched by current filename: %s", asset_name)

                    # Strategy 3: Match AppImage files containing app name
                    elif (
                        asset_name.endswith(".AppImage")
                        and app_filename.lower() in asset_name.lower()
                    ):
                        matched = True
                        logger.debug("Matched by AppImage pattern: %s", asset_name)

                    if matched:
                        asset_digest = asset.get("digest")
                        if asset_digest:
                            digest = asset_digest
                            logger.debug("Found digest in assets: %s", digest)
                            break

            logger.debug("Final digest value: %s", digest)

            # Create app configuration using catalog metadata (matching expected format)
            config_data = {
                "config_version": "1.0.0",
                "source": "catalog",
                "owner": context.app_config.get("owner", ""),
                "repo": context.app_config.get("repo", ""),
                "appimage": {
                    "rename": context.app_config.get("appimage", {}).get(
                        "rename", context.app_name
                    ),
                    "name_template": context.app_config.get("appimage", {}).get(
                        "name_template", ""
                    ),
                    "characteristic_suffix": context.app_config.get("appimage", {}).get(
                        "characteristic_suffix", []
                    ),
                    "version": context.release_data.get("version", "unknown"),
                    "name": app_path.name,
                    "installed_date": install_time,
                    "digest": digest,
                },
                "github": context.app_config.get("github", {}),
                "verification": context.app_config.get("verification", {}),
                "icon": {
                    "extraction": context.app_config.get("icon", {}).get("extraction", True),
                    "url": context.app_config.get("icon", {}).get("url") or None,
                    "name": context.app_config.get("icon", {}).get(
                        "name", f"{context.app_name}.png"
                    ),
                    "source": icon_result.get("source", "none"),
                    "installed": bool(icon_result.get("icon_path")),
                    "path": icon_result.get("icon_path"),
                },
            }

            # Save configuration
            config_path = self.config_manager.save_app_config(context.app_name, config_data)

            logger.info(
                "📝 Created catalog config for %s at %s", context.app_name, config_path
            )

            return {
                "success": True,
                "config_path": str(config_path),
                "config_data": config_data,
            }

        except Exception as error:
            logger.error("Failed to create config for %s: %s", context.app_name, error)
            return {
                "success": False,
                "error": str(error),
                "config_path": None,
            }


class URLInstallOperation(InstallOperation):
    """URL-specific install operations."""

    async def create_app_config(
        self,
        app_path: Path,
        context: URLInstallContext,
        icon_result: dict[str, Any],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create URL-based configuration using the same format as catalog.

        Args:
            app_path: Path to installed AppImage
            context: URL installation context
            icon_result: Result from icon extraction
            **kwargs: Additional options

        Returns:
            Configuration creation result

        """
        try:
            # Debug logging to understand data structures
            logger.debug("Release data: %s", context.release_data)
            logger.debug("Release data type: %s", type(context.release_data))

            # Check version extraction
            if hasattr(context.release_data, "get"):
                version_val = context.release_data.get("version")
            else:
                version_val = getattr(context.release_data, "version", "no version attr")
            logger.debug("Release data version: %s", version_val)

            logger.debug("Verification result: %s", kwargs.get("verification_result"))
            logger.debug(
                "Verification result type: %s", type(kwargs.get("verification_result"))
            )

            # Get current timestamp for installed_date
            from datetime import datetime

            install_time = kwargs.get("install_time") or datetime.now().isoformat()

            # Get verification result for digest
            verification_result = kwargs.get("verification_result", {})
            logger.debug("Verification result content: %s", verification_result)

            digest = None
            if verification_result and verification_result.get("passed"):
                # Extract digest from verification methods if available
                methods = verification_result.get("methods", {})
                logger.debug("Verification methods: %s", methods)
                # Look for digest or sha256 in methods
                if "digest" in methods:
                    digest = methods["digest"]
                    logger.debug("Found digest in methods: %s", digest)
                elif "sha256" in methods:
                    digest = f"sha256:{methods['sha256']}"
                    logger.debug("Found sha256 in methods: %s", digest)

            # Fallback: extract digest from release_data assets if not found in verification
            if not digest and hasattr(context.release_data, "get"):
                assets = context.release_data.get("assets", [])

                # Try to get original asset name from context.appimage_asset
                original_asset_name = None
                if hasattr(context, "appimage_asset") and context.appimage_asset:
                    # Try different attribute names for the asset name
                    original_asset_name = (
                        getattr(context.appimage_asset, "name", None)
                        or getattr(context.appimage_asset, "filename", None)
                        or getattr(context.appimage_asset, "asset_name", None)
                    )

                app_filename = app_path.name
                logger.debug("Looking for digest in assets for file: %s", app_filename)
                logger.debug("Original asset name: %s", original_asset_name)
                logger.debug("Available assets: %s", [asset.get("name") for asset in assets])

                # Find matching asset by filename
                for asset in assets:
                    asset_name = asset.get("name", "")
                    matched = False

                    # Strategy 1: Match by original asset name (most reliable)
                    if original_asset_name and asset_name == original_asset_name:
                        matched = True
                        logger.debug("Matched by original asset name: %s", asset_name)

                    # Strategy 2: Match by current filename
                    elif asset_name == app_filename or asset_name.endswith(app_filename):
                        matched = True
                        logger.debug("Matched by current filename: %s", asset_name)

                    # Strategy 3: Match AppImage files containing app name
                    elif (
                        asset_name.endswith(".AppImage")
                        and app_filename.lower() in asset_name.lower()
                    ):
                        matched = True
                        logger.debug("Matched by AppImage pattern: %s", asset_name)

                    if matched:
                        asset_digest = asset.get("digest")
                        if asset_digest:
                            digest = asset_digest
                            logger.debug("Found digest in assets: %s", digest)
                            break

            logger.debug("Final digest value: %s", digest)

            # Build verification config based on what was actually detected
            verification_config = verification_result.get("updated_config", {}) if verification_result else {}
            logger.debug("Raw verification_result: %s", verification_result)
            logger.debug("Extracted verification_config from updated_config: %s", verification_config)
            
            # If we found a digest in assets, update verification config to reflect that
            if digest:
                verification_config["digest"] = True
                logger.debug("Updated verification config: digest=True (found asset digest)")

            # Provide reasonable defaults if no verification methods were detected
            default_verification = {
                "digest": False,  # Only set True if actually detected
                "skip": False,
                "checksum_file": "",
                "checksum_hash_type": "sha256",
            }
            
            # Merge detected config with defaults (detected config takes precedence)
            final_verification_config = {**default_verification, **verification_config}
            
            logger.debug("URL install verification config: detected=%s, final=%s", 
                        verification_config, final_verification_config)

            # Create app configuration using URL metadata (matching catalog format)
            config_data = {
                "config_version": "1.0.0",
                "source": "url",
                "owner": context.owner,
                "repo": context.repo_name,
                "appimage": {
                    "rename": context.app_name,
                    "name_template": "",  # URL installs don't have templates
                    "characteristic_suffix": [],  # URL installs don't have predefined suffixes
                    "version": context.release_data.get("version", "unknown"),
                    "name": app_path.name,
                    "installed_date": install_time,
                    "digest": digest,
                },
                "github": {
                    "repo": True,
                    "prerelease": getattr(context.release_data, "prerelease", False),
                },
                "verification": final_verification_config,
                "icon": {
                    "extraction": True,  # Default for URL installs
                    "url": "",  # URL installs don't have predefined icon URLs
                    "name": f"{context.app_name}.png",
                    "source": icon_result.get("source", "none"),
                    "installed": bool(icon_result.get("icon_path")),
                    "path": icon_result.get("icon_path"),
                },
                "url_metadata": {
                    "target_url": context.target,
                },
            }

            # Save configuration
            config_path = self.config_manager.save_app_config(context.app_name, config_data)

            logger.info("📝 Created URL config for %s at %s", context.app_name, config_path)

            return {
                "success": True,
                "config_path": str(config_path),
                "config_data": config_data,
            }

        except Exception as error:
            logger.error("Failed to create config for %s: %s", context.app_name, error)
            return {
                "success": False,
                "error": str(error),
                "config_path": None,
            }
