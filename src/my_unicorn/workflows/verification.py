"""Verification workflow utilities for install and update operations.

This module provides unified verification orchestration logic extracted from
install.py and update.py to eliminate code duplication.
"""

from pathlib import Path
from typing import Any

from my_unicorn.github_client import Asset, Release
from my_unicorn.logger import get_logger
from my_unicorn.verification import VerificationService

logger = get_logger(__name__)


async def verify_appimage_download(
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
    else:
        logger.debug("✅ Verification completed successfully")
        logger.debug("   - passed: %s", result.passed)
        logger.debug("   - methods: %s", list(result.methods.keys()))

        return {
            "passed": result.passed,
            "methods": result.methods,
            "updated_config": result.updated_config,
            "warning": result.warning,
        }
