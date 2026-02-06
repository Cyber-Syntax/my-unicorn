"""Update context preparation functions.

This module contains functions for preparing update contexts including
resolving update info, loading configurations, and selecting assets.
"""

from __future__ import annotations

from typing import Any

import aiohttp

from my_unicorn.constants import ERROR_CATALOG_MISSING
from my_unicorn.core.github import Asset, get_github_config
from my_unicorn.core.update.info import UpdateInfo
from my_unicorn.exceptions import ConfigurationError, UpdateError
from my_unicorn.logger import get_logger
from my_unicorn.utils.appimage_utils import select_best_appimage_asset

logger = get_logger(__name__)


async def resolve_update_info(
    app_name: str,
    session: aiohttp.ClientSession,
    force: bool,
    update_info: UpdateInfo | None,
    check_single_update_func: callable,
) -> tuple[UpdateInfo | None, str | None]:
    """Resolve update info by using cached or checking for updates.

    Args:
        app_name: Name of the app
        session: aiohttp session
        force: Force update even if no new version
        update_info: Optional pre-fetched update info
        check_single_update_func: Function to check single update

    Returns:
        Tuple of (UpdateInfo, error message). UpdateInfo is None on error.

    """
    # Use cached update info if provided, otherwise check for updates
    if not update_info:
        update_info = await check_single_update_func(app_name, session)

    # Check if update info indicates an error
    if not update_info.is_success:
        logger.error(
            "Failed to check updates for %s: %s",
            app_name,
            update_info.error_reason,
        )
        return None, update_info.error_reason or "Failed to check updates"

    # Check if update is needed (skip if up to date and not forced)
    if not update_info.has_update and not force:
        logger.info("%s is already up to date", app_name)
        return update_info, None  # Return info for skip handling

    return update_info, None


def load_update_config(
    app_name: str, update_info: UpdateInfo, load_app_config_func: callable
) -> tuple[dict[str, Any] | None, str | None]:
    """Load app config from UpdateInfo cache or filesystem.

    Args:
        app_name: Name of the app
        update_info: UpdateInfo with cached config
        load_app_config_func: Function to load app config

    Returns:
        Tuple of (app_config dict, error message). Config is None on error.

    """
    # Get app config from cached UpdateInfo or load if not available
    if update_info.app_config:
        return update_info.app_config, None

    # Fallback: load if update_info didn't cache it
    try:
        app_config = load_app_config_func(app_name, "prepare_update")
        return app_config, None
    except ConfigurationError as e:
        logger.exception("Config error")
        return None, str(e)


async def load_catalog_for_update(
    app_name: str,
    app_config: dict[str, Any],
    load_catalog_cached_func: callable,
) -> dict[str, Any] | None:
    """Load catalog entry if referenced in app config.

    Args:
        app_name: Name of the app
        app_config: App configuration dictionary
        load_catalog_cached_func: Function to load cached catalog

    Returns:
        Catalog entry dict or None if not referenced

    Raises:
        UpdateError: If catalog is referenced but not found

    """
    catalog_ref = app_config.get("catalog_ref")
    if not catalog_ref:
        return None

    try:
        return await load_catalog_cached_func(catalog_ref)
    except (FileNotFoundError, ValueError) as e:
        msg = ERROR_CATALOG_MISSING.format(
            app_name=app_name, catalog_ref=catalog_ref
        )
        raise UpdateError(
            message=msg,
            context={"app_name": app_name, "catalog_ref": catalog_ref},
            cause=e,
        ) from e


def select_asset_for_update(
    app_name: str,
    update_info: UpdateInfo,
    catalog_entry: dict[str, Any] | None,
) -> tuple[Asset | None, str | None]:
    """Select AppImage asset from release data.

    Args:
        app_name: Name of the app
        update_info: UpdateInfo with release data
        catalog_entry: Optional catalog entry for asset selection

    Returns:
        Tuple of (Asset, error message). Asset is None on error.

    """
    if not update_info.release_data:
        logger.error("No release data available for %s", app_name)
        return None, "No release data available"

    # Convert catalog_entry to dict if needed
    catalog_dict = dict(catalog_entry) if catalog_entry else None
    appimage_asset = select_best_appimage_asset(
        update_info.release_data,
        catalog_entry=catalog_dict,
        installation_source="url",
        raise_on_not_found=False,
    )

    if not appimage_asset:
        logger.error("No AppImage found for %s", app_name)
        return (
            None,
            "AppImage not found in release - may still be building",
        )

    return appimage_asset, None


async def prepare_update_context(
    app_name: str,
    session: aiohttp.ClientSession,
    force: bool,
    update_info: UpdateInfo | None,
    check_single_update_func: callable,
    load_app_config_func: callable,
    load_catalog_cached_func: callable,
) -> tuple[dict[str, Any] | None, str | None]:
    """Prepare context for update operation.

    Args:
        app_name: Name of the app to update
        session: aiohttp session
        force: Force update even if no new version
        update_info: Optional pre-fetched update info
        check_single_update_func: Function to check single update
        load_app_config_func: Function to load app config
        load_catalog_cached_func: Function to load cached catalog

    Returns:
        Tuple of (context dict, error message). Context is None on error.

    """
    # Resolve update info (cached or fresh check)
    update_info, error = await resolve_update_info(
        app_name, session, force, update_info, check_single_update_func
    )
    if error:
        return None, error
    if not update_info:
        return None, "Failed to resolve update info"

    # Handle skip case (already up to date and not forced)
    if not update_info.has_update and not force:
        return {"skip": True, "success": True}, None

    # Load app configuration
    app_config, error = load_update_config(
        app_name, update_info, load_app_config_func
    )
    if error:
        return None, error
    if not app_config:
        return None, "Failed to load app config"

    # Extract GitHub configuration
    github_config = get_github_config(app_config)
    owner = github_config.owner
    repo = github_config.repo

    # Load catalog entry if referenced
    catalog_entry = await load_catalog_for_update(
        app_name, app_config, load_catalog_cached_func
    )

    # Select AppImage asset
    appimage_asset, error = select_asset_for_update(
        app_name, update_info, catalog_entry
    )
    if error:
        return None, error

    return {
        "app_config": app_config,
        "update_info": update_info,
        "owner": owner,
        "repo": repo,
        "catalog_entry": catalog_entry,
        "appimage_asset": appimage_asset,
    }, None
