"""Asset selection utilities for install and update workflows.

This module provides unified asset selection logic extracted from install.py
and update.py to eliminate code duplication. The core functionality wraps
AssetSelector.select_appimage_for_platform() with consistent error handling
and parameter extraction.

Functions:
    select_best_appimage_asset: Select best AppImage from release

"""

from typing import Any

from my_unicorn.exceptions import InstallationError
from my_unicorn.github_client import Asset, AssetSelector, Release


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
