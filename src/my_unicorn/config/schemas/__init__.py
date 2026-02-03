"""JSON Schema validation package for My Unicorn.

This package provides JSON Schema validation for:
- App state configuration files (apps/*.json)
- Release cache entries (cache/releases/*.json)
- Global configuration files (settings.conf)

Note: Catalog validation has been removed as catalogs are bundled and trusted.
Developers ensure catalog correctness before release.

Usage:
    from my_unicorn.config.schemas import (
        validate_app_state,
        validate_cache_release,
        SchemaValidationError,
    )

    try:
        validate_app_state(app_config, "obsidian")
        validate_cache_release(cache_entry, "obsidianmd_obsidian-releases")
    except SchemaValidationError as e:
        print(f"Validation failed: {e}")

    # Or with explicit validator instance for dependency injection:
    validator = ConfigValidator()
    validate_app_state(app_config, "obsidian", validator=validator)
"""

from my_unicorn.config.schemas.validator import (
    ConfigValidator,
    SchemaValidationError,
    validate_app_state,
    validate_cache_release,
    validate_global_config,
)

__all__ = [
    "ConfigValidator",
    "SchemaValidationError",
    "validate_app_state",
    "validate_cache_release",
    "validate_global_config",
]
