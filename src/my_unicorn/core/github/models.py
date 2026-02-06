"""GitHub models - backward compatibility module.

This module provides backward compatibility imports. All model classes have
been moved to the models package for better organization.
"""

# Re-export from the models package for backward compatibility
from my_unicorn.core.github.models import (
    UNSTABLE_VERSION_KEYWORDS,
    Asset,
    AssetSelector,
    ChecksumFileInfo,
    Release,
)

__all__ = [
    "UNSTABLE_VERSION_KEYWORDS",
    "Asset",
    "AssetSelector",
    "ChecksumFileInfo",
    "Release",
]
