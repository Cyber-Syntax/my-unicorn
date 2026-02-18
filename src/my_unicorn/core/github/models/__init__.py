"""GitHub models package."""

from my_unicorn.core.github.models.asset import Asset
from my_unicorn.core.github.models.checksum import ChecksumFileInfo
from my_unicorn.core.github.models.constants import UNSTABLE_VERSION_KEYWORDS
from my_unicorn.core.github.models.release import Release
from my_unicorn.core.github.models.selector import AssetSelector

__all__ = [
    "UNSTABLE_VERSION_KEYWORDS",
    "Asset",
    "AssetSelector",
    "ChecksumFileInfo",
    "Release",
]
