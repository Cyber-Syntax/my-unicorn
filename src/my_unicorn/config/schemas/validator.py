"""JSON Schema validation for My Unicorn configuration files.

This module provides validation utilities for catalog and app state
configuration files using JSON Schema.
"""

from pathlib import Path
from typing import Any

import orjson
from jsonschema import Draft7Validator, ValidationError
from jsonschema.exceptions import best_match

from my_unicorn.logger import get_logger

logger = get_logger(__name__)

# Schema file paths
SCHEMA_DIR = Path(__file__).parent
CATALOG_V1_SCHEMA_PATH = SCHEMA_DIR / "catalog_v1.schema.json"
CATALOG_V2_SCHEMA_PATH = SCHEMA_DIR / "catalog_v2.schema.json"
APP_STATE_V1_SCHEMA_PATH = SCHEMA_DIR / "app_state_v1.schema.json"
APP_STATE_V2_SCHEMA_PATH = SCHEMA_DIR / "app_state_v2.schema.json"
CACHE_RELEASE_SCHEMA_PATH = SCHEMA_DIR / "cache_release.schema.json"
GLOBAL_CONFIG_V1_SCHEMA_PATH = SCHEMA_DIR / "global_config_v1.schema.json"


class SchemaValidationError(Exception):
    """Raised when JSON schema validation fails."""

    def __init__(
        self,
        message: str,
        path: str | None = None,
        schema_type: str | None = None,
    ) -> None:
        """Initialize schema validation error.

        Args:
            message: Error message
            path: JSON path where error occurred
            schema_type: Type of schema being validated

        """
        self.path = path
        self.schema_type = schema_type
        super().__init__(message)

    def __str__(self) -> str:
        """Format error message with path information."""
        parts = []
        if self.schema_type:
            parts.append(f"[{self.schema_type}]")
        if self.path:
            parts.append(f"at '{self.path}'")
        if parts:
            return f"{' '.join(parts)}: {super().__str__()}"
        return super().__str__()


class ConfigValidator:
    """Validates configuration files against JSON schemas."""

    def __init__(self) -> None:
        """Initialize validator with loaded schemas."""
        # Load app state, cache, and global config schemas
        self._app_state_v1_schema = self._load_schema(APP_STATE_V1_SCHEMA_PATH)
        self._app_state_v2_schema = self._load_schema(APP_STATE_V2_SCHEMA_PATH)
        self._cache_release_schema = self._load_schema(
            CACHE_RELEASE_SCHEMA_PATH
        )
        self._global_config_v1_schema = self._load_schema(
            GLOBAL_CONFIG_V1_SCHEMA_PATH
        )

        # Create validators
        self._app_state_v1_validator = Draft7Validator(
            self._app_state_v1_schema
        )
        self._app_state_v2_validator = Draft7Validator(
            self._app_state_v2_schema
        )
        self._cache_release_validator = Draft7Validator(
            self._cache_release_schema
        )
        self._global_config_v1_validator = Draft7Validator(
            self._global_config_v1_schema
        )

    @staticmethod
    def _load_schema(schema_path: Path) -> dict[str, Any]:
        """Load JSON schema from file.

        Args:
            schema_path: Path to schema file

        Returns:
            Loaded schema dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If schema JSON is invalid

        """
        if not schema_path.exists():
            msg = f"Schema file not found: {schema_path}"
            raise FileNotFoundError(msg)

        try:
            with schema_path.open("rb") as f:
                return orjson.loads(f.read())  # type: ignore[no-any-return]
        except orjson.JSONDecodeError as e:
            msg = f"Invalid JSON in schema file {schema_path}: {e}"
            raise ValueError(msg) from e

    @staticmethod
    def _format_validation_error(
        error: ValidationError, schema_type: str
    ) -> str:
        """Format validation error into user-friendly message.

        Args:
            error: Validation error from jsonschema
            schema_type: Type of schema being validated

        Returns:
            Formatted error message

        """
        # Build JSON path from error location
        path = (
            ".".join(str(p) for p in error.absolute_path)
            if error.absolute_path
            else "root"
        )

        # Extract relevant error message
        message = error.message

        # Add context for common error types
        if error.validator == "required":
            missing = (
                error.message.split("'")[1]
                if "'" in error.message
                else "unknown"
            )
            message = f"Missing required field: '{missing}'"
        elif error.validator == "enum":
            message = f"Invalid value. {error.message}"
        elif error.validator == "const":
            expected = error.validator_value
            message = (
                f"Expected constant value '{expected}', got '{error.instance}'"
            )
        elif error.validator == "type":
            expected_type = error.validator_value
            actual = type(error.instance).__name__
            message = f"Expected type '{expected_type}', got '{actual}'"

        return f"{message} (at '{path}')"

    @staticmethod
    def _detect_app_state_version(config: dict[str, Any]) -> str:
        """Detect app state configuration version.

        Args:
            config: App state configuration dictionary

        Returns:
            Version string ("1.0.0" or "2.0.0")

        """
        config_version = config.get("config_version", "")
        return (
            config_version if config_version in ("1.0.0", "2.0.0") else "1.0.0"
        )

    def validate_app_state(
        self, config: dict[str, Any], app_name: str | None = None
    ) -> None:
        """Validate app state configuration against schema.

        Args:
            config: App state configuration dictionary
            app_name: Optional app name for better error messages

        Raises:
            SchemaValidationError: If validation fails

        """
        # Detect version and select appropriate validator
        version = self._detect_app_state_version(config)
        validator = (
            self._app_state_v1_validator
            if version == "1.0.0"
            else self._app_state_v2_validator
        )

        errors = list(validator.iter_errors(config))
        if errors:
            # Get the most relevant error
            best_error = best_match(errors)
            error_msg = self._format_validation_error(best_error, "app_state")

            # Add app name to error if provided
            if app_name:
                error_msg = f"Invalid app state for '{app_name}': {error_msg}"

            # Add migration hint for v1 configs
            if version == "1.0.0":
                error_msg += (
                    "\nThis is a v1 app state format. "
                    "Run 'my-unicorn migrate' to upgrade to version 2.0.0."
                )

            path = (
                ".".join(str(p) for p in best_error.absolute_path)
                if best_error.absolute_path
                else None
            )
            raise SchemaValidationError(
                error_msg, path=path, schema_type="app_state"
            )

        logger.debug(
            "App state validation passed (v%s): %s",
            version,
            app_name or "unknown",
        )

    def validate_cache_release(
        self, config: dict[str, Any], cache_name: str | None = None
    ) -> None:
        """Validate release cache entry against schema.

        Args:
            config: Cache entry dictionary
            cache_name: Optional cache name for better error messages

        Raises:
            SchemaValidationError: If validation fails

        """
        errors = list(self._cache_release_validator.iter_errors(config))
        if errors:
            # Get the most relevant error
            best_error = best_match(errors)
            error_msg = self._format_validation_error(best_error, "cache")

            # Add cache name to error if provided
            if cache_name:
                error_msg = f"Invalid cache entry '{cache_name}': {error_msg}"

            path = (
                ".".join(str(p) for p in best_error.absolute_path)
                if best_error.absolute_path
                else None
            )
            raise SchemaValidationError(
                error_msg, path=path, schema_type="cache"
            )

        logger.debug("Cache validation passed: %s", cache_name or "unknown")

    def validate_global_config(self, config: dict[str, Any]) -> None:
        """Validate global configuration against schema.

        Args:
            config: Global configuration dictionary

        Raises:
            SchemaValidationError: If validation fails

        """
        errors = list(self._global_config_v1_validator.iter_errors(config))
        if errors:
            # Get the most relevant error
            best_error = best_match(errors)
            error_msg = self._format_validation_error(
                best_error, "global_config"
            )

            path = (
                ".".join(str(p) for p in best_error.absolute_path)
                if best_error.absolute_path
                else None
            )
            raise SchemaValidationError(
                error_msg, path=path, schema_type="global_config"
            )

        logger.debug("Global config validation passed")


# Global validator instance
_validator: ConfigValidator | None = None


def get_validator() -> ConfigValidator:
    """Get or create global validator instance.

    Returns:
        ConfigValidator instance

    """
    global _validator
    if _validator is None:
        _validator = ConfigValidator()
    return _validator


def validate_app_state(
    config: dict[str, Any], app_name: str | None = None
) -> None:
    """Validate app state configuration (convenience function).

    Args:
        config: App state configuration dictionary
        app_name: Optional app name for better error messages

    Raises:
        SchemaValidationError: If validation fails

    """
    get_validator().validate_app_state(config, app_name)


def validate_cache_release(
    config: dict[str, Any], cache_name: str | None = None
) -> None:
    """Validate release cache entry (convenience function).

    Args:
        config: Cache entry dictionary
        cache_name: Optional cache name for better error messages

    Raises:
        SchemaValidationError: If validation fails

    """
    get_validator().validate_cache_release(config, cache_name)


def validate_global_config(config: dict[str, Any]) -> None:
    """Validate global configuration (convenience function).

    Args:
        config: Global configuration dictionary

    Raises:
        SchemaValidationError: If validation fails

    """
    get_validator().validate_global_config(config)
