"""Strategies package for my-unicorn.

This package contains strategy classes that implement different installation
approaches following the Strategy design pattern.
"""

from .catalog_install_strategy import CatalogInstallStrategy
from .install_strategy import InstallStrategy, InstallationError, ValidationError
from .url_install_strategy import URLInstallStrategy

__all__ = [
    "InstallStrategy",
    "InstallationError",
    "ValidationError",
    "URLInstallStrategy",
    "CatalogInstallStrategy",
]
