"""Configuration management - Config, catalog, and path utilities.

This package provides:
- ConfigManager: Unified facade for all configuration operations
- GlobalConfigManager: INI configuration management (from global.py)
- AppConfigManager: Per-app JSON configuration (from app.py)
- CatalogLoader: Bundled catalog access (from catalog.py)
- Paths: Path constants and utilities (from paths.py)
- Parser utilities: INI parser helpers (from parser.py)
"""

# Import from global module (avoiding keyword conflict)
import importlib

from my_unicorn.config.app import AppConfigManager
from my_unicorn.config.catalog import CatalogLoader
from my_unicorn.config.config import ConfigManager, config_manager
from my_unicorn.config.parser import (
    CommentAwareConfigParser,
    ConfigCommentManager,
)
from my_unicorn.config.paths import Paths
from my_unicorn.types import AppStateConfig, GlobalConfig

_global_module = importlib.import_module("my_unicorn.config.global")
GlobalConfigManager = _global_module.GlobalConfigManager

__all__ = [
    "AppConfigManager",
    "AppStateConfig",
    "CatalogLoader",
    "CommentAwareConfigParser",
    "ConfigCommentManager",
    "ConfigManager",
    "GlobalConfig",
    "GlobalConfigManager",
    "Paths",
    "config_manager",
]
