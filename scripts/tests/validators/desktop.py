#!/usr/bin/env python3
"""Desktop entry validation module for test framework.

Validates desktop entry file existence, content, and correctness.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from typing import Any

from utils import (
    file_exists,
    get_desktop_entry_path,
    get_file_mtime,
    read_file_text,
)

from . import BaseValidator, ValidationResult


class DesktopValidator(BaseValidator):
    """Validates desktop entry files."""

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate desktop entry state.

        For install/update: Verifies desktop entry exists with correct content
        For remove: Verifies desktop entry is deleted

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context (config, etc.)

        Returns:
            ValidationResult with desktop entry validation checks
        """
        result = ValidationResult(
            validator="DesktopValidator",
            app_name=self.app_name,
            operation=operation,
            status="PASS",
        )

        if operation == "remove":
            return self._validate_remove(result)
        return self._validate_install_update(result, **kwargs)

    def _validate_install_update(
        self,
        result: ValidationResult,
        **kwargs: Any,  # noqa: ANN401
    ) -> ValidationResult:
        """Validate desktop entry after install or update operation."""
        config = kwargs.get("config")
        if not config:
            result.add_error("No config provided for validation")
            return result

        desktop_path = get_desktop_entry_path(self.app_name)

        # Check 1: Desktop entry exists
        exists = file_exists(desktop_path)
        result.add_check(
            name="desktop_entry_exists",
            passed=exists,
            expected=True,
            actual=exists,
            message=f"Desktop entry: {desktop_path}",
        )

        if not exists:
            result.add_error(f"Desktop entry not found: {desktop_path}")
            return result

        # Check 2: Validate desktop entry content
        try:
            content = read_file_text(desktop_path)
            parsed_fields = self._validate_content(result, content)

            result.metadata["desktop_path"] = str(desktop_path)
            result.metadata["desktop_mtime"] = get_file_mtime(desktop_path)

            # Now validate the content with config info
            self._validate_exec_and_icon(result, parsed_fields, config)

        except Exception as e:  # noqa: BLE001
            result.add_error(f"Failed to read desktop entry: {e}")

        return result

    def _validate_content(
        self,
        result: ValidationResult,
        content: str,
    ) -> dict[str, str]:
        """Validate desktop entry file content and return parsed fields."""
        # Parse desktop entry into dictionary
        parsed_fields = self._parse_desktop_entry(content)

        # Check required fields
        required_fields = {
            "[Desktop Entry]": "[Desktop Entry]" in content,
            "Exec": "Exec" in parsed_fields,
            "Icon": "Icon" in parsed_fields,
            "Name": "Name" in parsed_fields,
            "Type": "Type" in parsed_fields,
        }

        all_present = all(required_fields.values())

        result.add_check(
            name="desktop_entry_valid",
            passed=all_present,
            expected={"has_required_fields": True},
            actual=required_fields,
            message="Desktop entry has required fields",
        )

        if not all_present:
            missing = [
                field
                for field, present in required_fields.items()
                if not present
            ]
            result.add_error(f"Missing required fields: {', '.join(missing)}")

        # Validate Type field value
        if "Type" in parsed_fields:
            type_value = parsed_fields["Type"]
            valid_types = ["Application", "Link", "Directory"]
            result.add_check(
                name="desktop_type_valid",
                passed=type_value in valid_types,
                expected=f"One of {valid_types}",
                actual=type_value,
                message="Desktop entry Type field should be valid",
            )

        # Store parsed fields in metadata
        result.metadata["desktop_fields"] = parsed_fields
        return parsed_fields

    def _parse_desktop_entry(self, content: str) -> dict[str, str]:
        """Parse desktop entry content into key-value pairs.

        Args:
            content: Desktop entry file content

        Returns:
            Dictionary of field names to values
        """
        fields = {}
        for line in content.splitlines():
            stripped = line.strip()
            if (
                "=" in stripped
                and not stripped.startswith("#")
                and not stripped.startswith("[")
            ):
                key, _, value = stripped.partition("=")
                fields[key.strip()] = value.strip()
        return fields

    def _validate_exec_and_icon(
        self,
        result: ValidationResult,
        parsed_fields: dict[str, str],
        config: dict[str, Any],
    ) -> None:
        """Validate Exec and Icon paths match config."""
        # Validate Exec path matches config
        installed_path = config.get("state", {}).get("installed_path")
        if installed_path and "Exec" in parsed_fields:
            exec_line = parsed_fields["Exec"]
            if installed_path not in exec_line:
                result.add_warning(
                    f"Desktop Exec path doesn't match installed_path. "
                    f"Expected {installed_path} in: {exec_line}"
                )
            else:
                result.add_check(
                    name="desktop_exec_path_correct",
                    passed=True,
                    expected=installed_path,
                    actual=exec_line,
                    message="Desktop Exec path matches config",
                )

        # Validate Icon path matches config (if icon method is extraction)
        icon_method = config.get("icon", {}).get("method")
        if icon_method == "extraction" and "Icon" in parsed_fields:
            icon_path = config.get("icon", {}).get("path")
            if icon_path:
                icon_line = parsed_fields["Icon"]
                icon_matches = icon_line == icon_path

                result.add_check(
                    name="desktop_icon_path_correct",
                    passed=icon_matches,
                    expected=icon_path,
                    actual=icon_line,
                    message="Desktop Icon path matches config",
                )

                if not icon_matches:
                    result.add_warning(
                        f"Desktop Icon path doesn't match config. "
                        f"Expected: {icon_path}, Got: {icon_line}"
                    )

    def _validate_remove(self, result: ValidationResult) -> ValidationResult:
        """Validate desktop entry after remove operation."""
        desktop_path = get_desktop_entry_path(self.app_name)
        exists = file_exists(desktop_path)

        result.add_check(
            name="desktop_entry_deleted",
            passed=not exists,
            expected=False,
            actual=exists,
            message=f"Desktop entry should be deleted: {desktop_path}",
        )

        if exists:
            result.add_error(f"Desktop entry still exists: {desktop_path}")

        return result


def validate_desktop_entry(
    app_name: str, config: dict[str, Any], operation: str = "install"
) -> ValidationResult:
    """Convenience function to validate desktop entry.

    Args:
        app_name: Name of the app
        config: App configuration dictionary
        operation: Operation type (install, update, remove)

    Returns:
        ValidationResult with desktop entry validation checks
    """
    validator = DesktopValidator(app_name)
    return validator.validate(operation, config=config)
