"""Command handlers for my-unicorn CLI.

This module contains all command handler implementations that provide
the core functionality for each CLI command.
"""

from .auth import AuthHandler
from .base import BaseCommandHandler
from .catalog import CatalogHandler
from .config import ConfigHandler
from .install import InstallCommandHandler
from .remove import RemoveHandler
from .update import UpdateHandler
from .upgrade import UpgradeHandler

__all__ = [
    "AuthHandler",
    "BaseCommandHandler",
    "CatalogHandler",
    "ConfigHandler",
    "InstallCommandHandler",
    "RemoveHandler",
    "UpdateHandler",
    "UpgradeHandler",
]
