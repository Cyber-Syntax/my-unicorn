"""JSON Schema validation package for My Unicorn.

This package provides JSON Schema validation for:
- Catalog configuration files (catalog/*.json)
- App state configuration files (apps/*.json)
- Release cache entries (cache/releases/*.json)

Usage:
    from my_unicorn.schemas import validate_catalog, validate_app_state, validate_cache_release, SchemaValidationError

    try:
        validate_catalog(catalog_config, "obsidian")
        validate_app_state(app_config, "obsidian")
        validate_cache_release(cache_entry, "obsidianmd_obsidian-releases")
    except SchemaValidationError as e:
        print(f"Validation failed: {e}")
"""

from my_unicorn.schemas.validator import (
    ConfigValidator,
    SchemaValidationError,
    get_validator,
    validate_app_state,
    validate_cache_release,
    validate_catalog,
)

__all__ = [
    "ConfigValidator",
    "SchemaValidationError",
    "get_validator",
    "validate_app_state",
    "validate_cache_release",
    "validate_catalog",
]
