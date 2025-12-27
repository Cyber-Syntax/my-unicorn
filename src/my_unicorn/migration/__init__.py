"""Configuration migration package.

This package provides migration functionality for:
- App state configs (apps/*.json) - v1 → v2
- Catalog configs (catalog/*.json) - v1 → v2
- Global settings (settings.conf) - handled separately

Architecture:
- base: Common utilities (version checking, backups, JSON operations)
- app_config: App state migration logic
- catalog_config: Catalog definition migration logic
- global_config: Global settings migration logic
"""

from my_unicorn.migration.app_config import AppConfigMigrator
from my_unicorn.migration.catalog_config import CatalogMigrator
from my_unicorn.migration.global_config import ConfigMigration

__all__ = ["AppConfigMigrator", "CatalogMigrator", "ConfigMigration"]
