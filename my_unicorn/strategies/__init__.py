"""Strategies package for my-unicorn.

This package contains strategy classes that implement different installation
and update approaches following the Strategy design pattern.
"""

from .install_catalog import CatalogInstallStrategy
from .install import InstallStrategy, InstallationError, ValidationError
from .install_url import URLInstallStrategy
from .update import UpdateContext, UpdateResult, UpdateStrategy
from .update_factory import UpdateStrategyFactory
from .update_check_only import CheckOnlyUpdateStrategy
from .update_specific import UpdateSpecificAppsStrategy
from .update_all import UpdateAllAppsStrategy
from .update_result import UpdateResultDisplay

__all__ = [
    # Install strategies
    "InstallStrategy",
    "InstallationError",
    "ValidationError",
    "URLInstallStrategy",
    "CatalogInstallStrategy",
    # Update strategies
    "UpdateStrategy",
    "UpdateContext",
    "UpdateResult",
    "UpdateStrategyFactory",
    "CheckOnlyUpdateStrategy",
    "UpdateSpecificAppsStrategy",
    "UpdateAllAppsStrategy",
    "UpdateResultDisplay",
]
