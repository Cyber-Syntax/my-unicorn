"""Asset selection and filtering logic.

Pure business logic for selecting appropriate assets from GitHub releases
based on platform, architecture, and file type.
"""

from my_unicorn.domain.types import Asset, Platform


def select_asset_for_platform(
    assets: list[Asset], platform: Platform | None = None
) -> Asset | None:
    """Select appropriate AppImage asset for the given platform.

    Args:
        assets: List of release assets
        platform: Target platform (defaults to current platform)

    Returns:
        Selected asset or None if no suitable asset found
    """
    if platform is None:
        platform = Platform.current()

    # Filter for AppImage files
    appimage_assets = [asset for asset in assets if asset.is_appimage]

    if not appimage_assets:
        return None

    # Try platform-specific selection first
    platform_asset = _select_for_specific_platform(appimage_assets, platform)
    if platform_asset:
        return platform_asset

    # Fallback: return first AppImage asset (assumed universal)
    return appimage_assets[0]


def _select_for_specific_platform(
    appimage_assets: list[Asset], platform: Platform
) -> Asset | None:
    """Select asset for a specific platform.

    Args:
        appimage_assets: List of AppImage assets
        platform: Target platform

    Returns:
        Platform-specific asset or None
    """
    platform_keywords = {
        Platform.LINUX_X86_64: ["x86_64", "amd64"],
        Platform.LINUX_ARM64: ["arm64", "aarch64"],
        Platform.LINUX_ARMV7: ["armv7", "armhf"],
    }

    keywords = platform_keywords.get(platform, [])
    if not keywords:
        return None

    for asset in appimage_assets:
        name_lower = asset.name.lower()
        if any(keyword in name_lower for keyword in keywords):
            return asset

    return None


def find_checksum_asset(assets: list[Asset]) -> Asset | None:
    """Find checksum file in release assets.

    Args:
        assets: List of release assets

    Returns:
        Checksum asset or None if not found
    """
    for asset in assets:
        if asset.is_checksum_file:
            return asset
    return None


def filter_appimage_assets(assets: list[Asset]) -> list[Asset]:
    """Filter list to only AppImage assets.

    Args:
        assets: List of all assets

    Returns:
        List of AppImage assets only
    """
    return [asset for asset in assets if asset.is_appimage]


def is_platform_compatible(asset: Asset, platform: Platform) -> bool:
    """Check if an asset is compatible with the given platform.

    Args:
        asset: Asset to check
        platform: Target platform

    Returns:
        True if compatible, False otherwise
    """
    if not asset.is_appimage:
        return False

    name_lower = asset.name.lower()

    # Platform-specific checks
    if platform == Platform.LINUX_X86_64:
        return "x86_64" in name_lower or "amd64" in name_lower

    if platform == Platform.LINUX_ARM64:
        return "arm64" in name_lower or "aarch64" in name_lower

    if platform == Platform.LINUX_ARMV7:
        return "armv7" in name_lower or "armhf" in name_lower

    # Unknown platform - assume incompatible
    return False
