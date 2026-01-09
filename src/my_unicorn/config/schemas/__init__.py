"""JSON Schema validation package for My Unicorn.

This package provides JSON Schema validation for:
- App state configuration files (apps/*.json)
- Release cache entries (cache/releases/*.json)

Note: Catalog validation has been removed as catalogs are bundled and trusted.
Developers ensure catalog correctness before release.

Usage:
    from my_unicorn.config.schemas import validate_app_state, validate_cache_release, SchemaValidationError

    try:
        validate_app_state(app_config, "obsidian")
        validate_cache_release(cache_entry, "obsidianmd_obsidian-releases")
    except SchemaValidationError as e:
        print(f"Validation failed: {e}")
"""

from my_unicorn.config.schemas.validator import (
    ConfigValidator,
    SchemaValidationError,
    get_validator,
    validate_app_state,
    validate_cache_release,
)

__all__ = [
    "ConfigValidator",
    "SchemaValidationError",
    "get_validator",
    "validate_app_state",
    "validate_cache_release",
]
