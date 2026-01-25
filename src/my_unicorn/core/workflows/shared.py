"""Shared workflow utilities for install and update operations.

This module provides common utilities used across multiple workflow modules
to eliminate code duplication.
"""

from pathlib import Path
from typing import Any

from my_unicorn.core.github import Asset, AssetSelector, Release
from my_unicorn.core.verification import VerificationService
from my_unicorn.exceptions import InstallationError
from my_unicorn.logger import get_logger

logger = get_logger(__name__)


def select_best_appimage_asset(
    release: Release,
    preferred_suffixes: list[str] | None = None,
    catalog_entry: dict[str, Any] | None = None,
    installation_source: str = "catalog",
    *,
    raise_on_not_found: bool = True,
) -> Asset | None:
    """Select best AppImage asset from release.

    Unified asset selection logic used by both install and update operations.
    Handles extraction of preferred suffixes from catalog entries and provides
    consistent error handling.

    Args:
        release: Release object containing assets to select from
        preferred_suffixes: Explicit list of preferred filename suffixes.
            Takes precedence over catalog_entry if both provided.
        catalog_entry: Optional catalog entry to extract
            preferred_suffixes from. Used when preferred_suffixes is None.
        installation_source: Installation source ("catalog" or "url").
            "url" filters unstable versions (beta, alpha, etc.)
            "catalog" allows all versions but respects preferred_suffixes
        raise_on_not_found: Whether to raise InstallationError if no
            asset found. If False, returns None instead.

    Returns:
        Selected Asset or None if not found and raise_on_not_found=False

    Raises:
        InstallationError: If no assets found in release
            (when raise_on_not_found=True)
        InstallationError: If AppImage not found in release
            (when raise_on_not_found=True)

    Examples:
        # Install operation with explicit suffixes
        >>> asset = select_best_appimage_asset(
        ...     release,
        ...     preferred_suffixes=["x86_64.AppImage"],
        ...     installation_source="catalog",
        ... )

        # Update operation with catalog entry
        >>> asset = select_best_appimage_asset(
        ...     release,
        ...     catalog_entry=catalog_data,
        ...     installation_source="url",
        ...     raise_on_not_found=False,
        ... )

    """
    # Validate release has assets
    if not release or not release.assets:
        if raise_on_not_found:
            msg = "No assets found in release"
            raise InstallationError(msg)
        return None

    # Extract preferred suffixes from catalog if not explicitly provided
    suffixes = preferred_suffixes
    if suffixes is None and catalog_entry:
        appimage_config = catalog_entry.get("appimage")
        if isinstance(appimage_config, dict):
            suffixes = appimage_config.get("preferred_suffixes")

    # Select best AppImage using AssetSelector
    asset = AssetSelector.select_appimage_for_platform(
        release,
        preferred_suffixes=suffixes,
        installation_source=installation_source,
    )

    # Handle not found case
    if not asset and raise_on_not_found:
        msg = "AppImage not found in release - may still be building"
        raise InstallationError(msg)

    return asset


async def verify_appimage_download(  # noqa: PLR0913
    *,
    file_path: Path,
    asset: Asset,
    release: Release,
    app_name: str,
    verification_service: VerificationService,
    verification_config: dict[str, Any] | None = None,
    catalog_entry: dict[str, Any] | None = None,
    owner: str = "",
    repo: str = "",
    progress_task_id: str | None = None,
) -> dict[str, Any]:
    """Verify downloaded AppImage file.

    Unified verification logic for both install and update operations.
    Handles catalog-based and config-based verification settings.

    Args:
        file_path: Path to downloaded file to verify
        asset: GitHub asset information
        release: Release data containing tag and assets
        app_name: Application name for logging
        verification_service: Pre-initialized verification service
        verification_config: Verification configuration from app config
        catalog_entry: Catalog entry with verification settings
        owner: Repository owner (required if not in catalog_entry)
        repo: Repository name (required if not in catalog_entry)
        progress_task_id: Progress task ID for tracking (optional)

    Returns:
        Verification result dictionary with keys:
            - passed (bool): Whether verification passed
            - methods (dict): Verification method results
            - updated_config (dict): Updated verification configuration
            - warning (str): Warning message if applicable
            - error (str): Error message if verification failed

    """
    # Load verification config from catalog or app config
    config: dict[str, Any] = {}
    if catalog_entry and catalog_entry.get("verification"):
        config = dict(catalog_entry["verification"])
        logger.debug(
            "📋 Using catalog verification config for %s: %s",
            app_name,
            config,
        )
    elif verification_config:
        config = dict(verification_config)
        logger.debug(
            "📋 Using app config verification config for %s: %s",
            app_name,
            config,
        )

    # Extract owner/repo from catalog if not provided
    if not owner and catalog_entry:
        owner = catalog_entry.get("source", {}).get("owner", "")
    if not repo and catalog_entry:
        repo = catalog_entry.get("source", {}).get("repo", "")

    # Get tag name and assets from release data
    tag_name = release.original_tag_name or "unknown"
    assets = release.assets

    logger.debug("Performing verification: app=%s", app_name)
    logger.debug("   📋 Config: %s", config)
    logger.debug("   📦 Asset digest: %s", asset.digest or "None")
    logger.debug("   📦 Assets list: %d items", len(assets))

    try:
        # Perform verification using verification service
        result = await verification_service.verify_file(
            file_path=file_path,
            asset=asset,
            config=config,
            owner=owner,
            repo=repo,
            tag_name=tag_name,
            app_name=app_name,
            assets=assets,
            progress_task_id=progress_task_id,
        )
    except Exception:
        logger.exception("Verification failed for %s", app_name)
        return {
            "passed": False,
            "error": "Verification error",
            "methods": {},
            "updated_config": {},
        }

    logger.debug("✅ Verification completed successfully")

    # Handle both dict and object returns from mocked verification service
    if isinstance(result, dict):
        logger.debug("   - passed: %s", result.get("passed"))
        logger.debug(
            "   - methods: %s", list(result.get("methods", {}).keys())
        )
        return result
    logger.debug("   - passed: %s", result.passed)
    logger.debug("   - methods: %s", list(result.methods.keys()))
    return {
        "passed": result.passed,
        "methods": result.methods,
        "updated_config": result.updated_config,
        "warning": result.warning,
    }
