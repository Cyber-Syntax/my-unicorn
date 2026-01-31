"""Validation modules for my-unicorn test framework.

This package provides focused validators for different aspects of the system:
- AppImage validation (integrity, SHA, executability)
- Desktop entry validation (existence, content)
- Icon validation (extraction, reuse detection)
- Config validation (JSON schema, state consistency)
- Cache validation (consistency, freshness)

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class ValidationCheck:
    """Individual validation check result."""

    name: str
    passed: bool
    expected: Any
    actual: Any
    message: str


@dataclass
class ValidationResult:
    """Result from a validation operation."""

    validator: str
    app_name: str
    operation: str  # install, update, remove
    status: Literal["PASS", "FAIL", "WARN"]
    checks: list[ValidationCheck] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def all_passed(self) -> bool:
        """Check if all checks passed."""
        return self.status == "PASS" and all(
            check.passed for check in self.checks
        )

    def add_check(
        self,
        name: str,
        passed: bool,
        expected: Any,
        actual: Any,
        message: str,
    ) -> None:
        """Add a validation check to the result."""
        check = ValidationCheck(name, passed, expected, actual, message)
        self.checks.append(check)

        if not passed:
            self.errors.append(f"{name}: {message}")
            if self.status == "PASS":
                self.status = "FAIL"

    def add_warning(self, message: str) -> None:
        """Add a warning to the result."""
        self.warnings.append(message)
        if self.status == "PASS":
            self.status = "WARN"

    def add_error(self, message: str) -> None:
        """Add an error to the result."""
        self.errors.append(message)
        self.status = "FAIL"


class BaseValidator:
    """Base class for all validators."""

    def __init__(self, app_name: str):
        """Initialize validator.

        Args:
            app_name: Name of the app to validate
        """
        self.app_name = app_name

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate the app state.

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context for validation

        Returns:
            ValidationResult with check details

        Raises:
            NotImplementedError: Must be implemented by subclasses
        """
        msg = "Subclasses must implement validate()"
        raise NotImplementedError(msg)


class SystemValidator:
    """Coordinates all validators for comprehensive system validation."""

    def __init__(self, app_name: str):
        """Initialize system validator.

        Args:
            app_name: Name of the app to validate
        """
        self.app_name = app_name
        self.validators: list[BaseValidator] = []

    def add_validator(self, validator: BaseValidator) -> None:
        """Add a validator to the system.

        Args:
            validator: Validator instance to add
        """
        self.validators.append(validator)

    def validate_all(
        self, operation: str, **kwargs: Any
    ) -> list[ValidationResult]:
        """Run all validators.

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context passed to all validators

        Returns:
            List of ValidationResult from all validators
        """
        results = []
        for validator in self.validators:
            try:
                result = validator.validate(operation, **kwargs)
                results.append(result)
            except Exception as e:  # noqa: BLE001
                # Create a failed result for validator exception
                result = ValidationResult(
                    validator=validator.__class__.__name__,
                    app_name=self.app_name,
                    operation=operation,
                    status="FAIL",
                )
                result.add_error(f"Validator exception: {e}")
                results.append(result)
        return results


# Import validators after base classes to avoid circular imports
from .appimage import AppImageValidator  # noqa: E402
from .cache import CacheValidator  # noqa: E402
from .config import ConfigValidator  # noqa: E402
from .desktop import DesktopValidator  # noqa: E402
from .icon import IconValidator  # noqa: E402

__all__ = [
    "AppImageValidator",
    "BaseValidator",
    "CacheValidator",
    "ConfigValidator",
    "DesktopValidator",
    "IconValidator",
    "SystemValidator",
    "ValidationCheck",
    "ValidationResult",
]
