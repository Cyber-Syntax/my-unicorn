"""Strategies package for my-unicorn.

This package contains strategy classes that implement different installation
and update approaches following the Strategy design pattern.
"""

from .catalog_install_strategy import CatalogInstallStrategy
from .install_strategy import InstallStrategy, InstallationError, ValidationError
from .url_install_strategy import URLInstallStrategy
from .update_strategy import UpdateContext, UpdateResult, UpdateStrategy
from .update_strategy_factory import UpdateStrategyFactory
from .check_only_update_strategy import CheckOnlyUpdateStrategy
from .update_specific_apps_strategy import UpdateSpecificAppsStrategy
from .update_all_apps_strategy import UpdateAllAppsStrategy
from .update_result_display import UpdateResultDisplay

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
