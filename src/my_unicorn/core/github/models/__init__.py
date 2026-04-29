"""GitHub models package."""

from my_unicorn.core.github.models.asset import Asset
from my_unicorn.core.github.models.checksum import ChecksumFileInfo
from my_unicorn.core.github.models.release import Release
from my_unicorn.core.github.models.selector import AssetSelector

__all__ = [
    "Asset",
    "AssetSelector",
    "ChecksumFileInfo",
    "Release",
]
