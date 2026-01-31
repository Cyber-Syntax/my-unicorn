#!/usr/bin/env python3
"""Configuration validation module for test framework.

Validates app configuration files, schema compliance, and state consistency.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from utils import file_exists, get_app_config_path, is_valid_json, load_json

from . import BaseValidator, ValidationResult


class ConfigValidator(BaseValidator):
    """Validates app configuration state and consistency."""

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate app configuration file and state.

        For install/update: Verifies config exists, is valid, matches filesystem
        For remove: Verifies config is deleted

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context

        Returns:
            ValidationResult with config validation checks
        """
        result = ValidationResult(
            validator="ConfigValidator",
            app_name=self.app_name,
            operation=operation,
            status="PASS",
        )

        if operation == "remove":
            return self._validate_remove(result)

        return self._validate_install_update(result, **kwargs)

    def _validate_remove(self, result: ValidationResult) -> ValidationResult:
        """Validate config is properly removed."""
        config_path = get_app_config_path(self.app_name)

        result.add_check(
            name="config_removed",
            passed=not file_exists(config_path),
            expected="Config file deleted",
            actual="Exists" if file_exists(config_path) else "Deleted",
            message="Config file should be deleted after remove",
        )
        return result

    def _validate_install_update(
        self, result: ValidationResult
    ) -> ValidationResult:
        """Validate config exists and is valid."""
        config_path = get_app_config_path(self.app_name)

        # Check file exists
        config_exists = file_exists(config_path)
        result.add_check(
            name="config_exists",
            passed=config_exists,
            expected="Config file exists",
            actual=str(config_path) if config_exists else "Not found",
            message="Config file should exist after install/update",
        )

        if not config_exists:
            return result

        # Check valid JSON
        is_json_valid = is_valid_json(config_path)
        result.add_check(
            name="config_valid_json",
            passed=is_json_valid,
            expected="Valid JSON",
            actual="Valid" if is_json_valid else "Invalid",
            message="Config file should be valid JSON",
        )

        if not is_json_valid:
            return result

        # Load and validate schema
        try:
            config = load_json(config_path)
        except Exception as e:
            result.add_error(f"Failed to load config: {e}")
            return result

        self._validate_schema(result, config)
        self._validate_filesystem_match(result, config)

        return result

    def _validate_schema(
        self, result: ValidationResult, config: dict[str, Any]
    ) -> None:
        """Validate config schema (supports both v1 and v2.0.0)."""
        config_version = config.get("config_version", "1.0.0")

        # V2.0.0 validation
        if config_version == "2.0.0":
            self._validate_v2_schema(result, config)
        else:
            # V1 validation (legacy)
            self._validate_v1_schema(result, config)

    def _validate_v2_schema(
        self, result: ValidationResult, config: dict[str, Any]
    ) -> None:
        """Validate v2.0.0 config schema."""
        # Check top-level required fields
        required_top = ["config_version", "source", "state"]
        missing_top = [field for field in required_top if field not in config]

        if missing_top:
            result.add_error(
                f"Missing top-level fields: {', '.join(missing_top)}"
            )
            return

        # Check state section
        state = config.get("state", {})
        required_state = [
            "version",
            "installed_date",
            "installed_path",
            "verification",
            "icon",
        ]
        missing_state = [
            field for field in required_state if field not in state
        ]

        if missing_state:
            result.add_error(
                f"Missing state fields: {', '.join(missing_state)}"
            )
            return

        # Validate config version
        expected_version = "2.0.0"
        actual_version = config.get("config_version")

        result.add_check(
            name="config_version",
            passed=actual_version == expected_version,
            expected=expected_version,
            actual=actual_version,
            message="Config version should match expected version",
        )

    def _validate_v1_schema(
        self, result: ValidationResult, config: dict[str, Any]
    ) -> None:
        """Validate v1.0.0 config schema (legacy)."""
        required_fields = [
            "version",
            "app_name",
            "repo",
            "appimage_path",
            "icon_path",
            "installed_version",
            "last_updated",
        ]

        missing_fields = [
            field for field in required_fields if field not in config
        ]

        if missing_fields:
            result.add_error(
                f"Missing required fields: {', '.join(missing_fields)}"
            )
            return

        # Check version
        expected_version = "1.0.0"
        actual_version = config.get("version", "1.0.0")

        result.add_check(
            name="config_version",
            passed=actual_version == expected_version,
            expected=expected_version,
            actual=actual_version,
            message="Config version should match expected version",
        )

    def _validate_filesystem_match(
        self, result: ValidationResult, config: dict[str, Any]
    ) -> None:
        """Cross-validate config against actual filesystem state."""
        # Support both v1 and v2 config structures
        config_version = config.get("config_version", "1.0.0")
        state = config.get("state", {})

        # Check AppImage exists
        if config_version == "2.0.0":
            appimage_path_str = state.get("installed_path")
        else:
            appimage_path_str = config.get("appimage_path")

        if appimage_path_str:
            appimage_path = Path(appimage_path_str)
            result.add_check(
                name="appimage_exists",
                passed=file_exists(appimage_path),
                expected="AppImage file exists",
                actual=str(appimage_path),
                message=(
                    "AppImage path in config should point to existing file"
                ),
            )

        # Check icon exists
        if config_version == "2.0.0":
            icon_state = state.get("icon", {})
            icon_path_str = icon_state.get("path")
        else:
            icon_path_str = config.get("icon_path")

        if icon_path_str:
            icon_path = Path(icon_path_str)
            result.add_check(
                name="icon_exists",
                passed=file_exists(icon_path),
                expected="Icon file exists",
                actual=str(icon_path),
                message="Icon path in config should point to existing file",
            )

        # Check desktop entry exists (if present in config)
        desktop_path_str = config.get("desktop_path")
        if desktop_path_str:
            desktop_path = Path(desktop_path_str)
            desktop_exists = file_exists(desktop_path)
            if not desktop_exists:
                result.add_warning(f"Desktop entry not found: {desktop_path}")

        # Enhanced state consistency checks
        self._validate_state_consistency(result, config)

    def _validate_state_consistency(
        self, result: ValidationResult, config: dict[str, Any]
    ) -> None:
        """Validate internal config state consistency.

        Checks for logical consistency between config fields like:
        - installed_version matches last_updated timestamp
        - State fields are mutually consistent
        - Required state fields are present
        """
        config_version = config.get("config_version", "1.0.0")
        state = config.get("state", {})

        # V2.0.0 validation
        if config_version == "2.0.0":
            # Check version is not empty
            version = state.get("version")
            if not version:
                result.add_warning("state.version is empty")
            else:
                result.add_check(
                    name="installed_version_present",
                    passed=True,
                    expected="Non-empty version",
                    actual=version,
                    message="Installed version is recorded",
                )

            # Check installed_date is present (ISO format string in v2)
            installed_date = state.get("installed_date")
            if installed_date:
                result.add_check(
                    name="installed_date_present",
                    passed=True,
                    expected="ISO format date",
                    actual=installed_date,
                    message="Installation date is recorded",
                )
            else:
                result.add_warning("state.installed_date is empty")

            # V2 state validation - these are the actual required fields
            state_required = [
                "version",
                "installed_date",
                "installed_path",
                "verification",
                "icon",
            ]
            state_missing = [
                field for field in state_required if field not in state
            ]

            if state_missing:
                result.add_warning(
                    f"State section missing fields: {', '.join(state_missing)}"
                )
            else:
                result.add_check(
                    name="state_fields_complete",
                    passed=True,
                    expected="All required state fields",
                    actual=list(state.keys()),
                    message="State section has required fields",
                )
        else:
            # V1 validation (legacy)
            installed_version = config.get("installed_version")
            if not installed_version:
                result.add_warning("installed_version is empty")
            else:
                result.add_check(
                    name="installed_version_present",
                    passed=True,
                    expected="Non-empty version",
                    actual=installed_version,
                    message="Installed version is recorded",
                )

            # Check last_updated is a valid timestamp
            last_updated = config.get("last_updated")
            if last_updated:
                try:
                    # Validate it's a reasonable timestamp
                    # (not too far in future)
                    now = datetime.now(UTC).timestamp()
                    # Allow 1 day grace period
                    is_reasonable = 0 < last_updated <= now + 86400

                    result.add_check(
                        name="last_updated_reasonable",
                        passed=is_reasonable,
                        expected="Valid timestamp",
                        actual=f"{last_updated}",
                        message="Last updated timestamp is reasonable",
                    )
                except Exception as e:  # noqa: BLE001
                    result.add_warning(f"Failed to validate last_updated: {e}")
