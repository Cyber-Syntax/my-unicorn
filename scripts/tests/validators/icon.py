#!/usr/bin/env python3
"""Icon validation module for test framework.

Validates icon extraction, reuse detection, and management.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from pathlib import Path
from typing import Any

from utils import file_exists, get_file_mtime, get_file_size

from . import BaseValidator, ValidationResult


class IconValidator(BaseValidator):
    """Validates icon file state and management."""

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate icon extraction and management state.

        For install/update: Verifies icon exists, has content, detects reuse
        For remove: Verifies icon is deleted

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context (config, etc.)

        Returns:
            ValidationResult with icon validation checks
        """
        result = ValidationResult(
            validator="IconValidator",
            app_name=self.app_name,
            operation=operation,
            status="PASS",
        )

        config = kwargs.get("config")
        if not config:
            result.add_error("No config provided for validation")
            return result

        # Support v2.0.0 config structure (state.icon.path)
        state = config.get("state", {})
        icon_state = state.get("icon", {})
        icon_path_str = icon_state.get("path") or config.get("icon_path")

        if not icon_path_str:
            msg = (
                "No icon_path in config "
                "(checked state.icon.path and icon_path)"
            )
            result.add_error(msg)
            return result

        icon_path = Path(icon_path_str)

        if operation == "remove":
            return self._validate_remove(result, icon_path)

        return self._validate_install_update(
            result, icon_path, config, operation
        )

    def _validate_remove(
        self, result: ValidationResult, icon_path: Path
    ) -> ValidationResult:
        """Validate icon is properly removed."""
        result.add_check(
            name="icon_removed",
            passed=not file_exists(icon_path),
            expected="Icon file deleted",
            actual="Exists" if file_exists(icon_path) else "Deleted",
            message="Icon file should be deleted after remove",
        )
        return result

    def _validate_install_update(
        self,
        result: ValidationResult,
        icon_path: Path,
        config: dict[str, Any],
        operation: str,
    ) -> ValidationResult:
        """Validate icon exists and has correct properties."""
        # Check existence
        icon_exists = file_exists(icon_path)
        result.add_check(
            name="icon_exists",
            passed=icon_exists,
            expected="Icon file exists",
            actual=str(icon_path) if icon_exists else "Not found",
            message="Icon file should exist after install/update",
        )

        if not icon_exists:
            return result

        # Check file size (should not be empty)
        icon_size = get_file_size(icon_path)
        result.add_check(
            name="icon_size",
            passed=icon_size > 0,
            expected="Icon size > 0 bytes",
            actual=f"{icon_size} bytes",
            message="Icon file should not be empty",
        )

        # Validate icon format
        format_info = self._validate_icon_format(icon_path)
        result.metadata.update(format_info)

        if format_info.get("format_valid"):
            result.add_check(
                name="icon_format_valid",
                passed=True,
                expected="PNG or SVG",
                actual=format_info.get("format", "Unknown"),
                message="Icon format is valid",
            )
        else:
            msg = (
                "Icon format unrecognized: "
                f"{format_info.get('format', 'Unknown')}"
            )
            result.add_warning(msg)

        # Detect icon reuse vs extraction
        reuse_info = self._detect_icon_reuse(icon_path, config)
        result.metadata.update(reuse_info)

        # For updates, log whether icon was reused or re-extracted
        if operation == "update" and reuse_info.get("icon_reused"):
            result.add_warning("Icon reused (not re-extracted)")

        return result

    def _validate_icon_format(self, icon_path: Path) -> dict[str, Any]:
        """Validate icon file format (PNG or SVG).

        Args:
            icon_path: Path to icon file

        Returns:
            Dictionary with format validation info
        """
        try:
            # Read first few bytes for magic number detection
            with icon_path.open("rb") as f:
                header = f.read(16)

            # PNG magic number: 89 50 4E 47 0D 0A 1A 0A
            if header[:8] == b"\x89PNG\r\n\x1a\n":
                return {"format": "PNG", "format_valid": True}

            # SVG detection (XML-based, starts with < or <?xml)
            if header[:5] == b"<?xml" or header[:4] == b"<svg":
                return {"format": "SVG", "format_valid": True}

            # Check file extension as fallback
            suffix = icon_path.suffix.lower()
            if suffix in {".png", ".svg"}:
                return {
                    "format": suffix[1:].upper(),
                    "format_valid": True,
                    "detected_by": "extension",
                }

            return {
                "format": "Unknown",
                "format_valid": False,
                "header_hex": header.hex(),
            }

        except Exception as e:  # noqa: BLE001
            return {
                "format": "Error",
                "format_valid": False,
                "error": str(e),
            }

    def _detect_icon_reuse(
        self, icon_path: Path, config: dict[str, Any]
    ) -> dict[str, Any]:
        """Detect if icon was reused or newly extracted."""
        current_mtime = get_file_mtime(icon_path)
        # v2.0.0 configs don't store icon_mtime, v1 did
        stored_mtime = config.get("icon_mtime") or config.get("state", {}).get(
            "icon", {}
        ).get("mtime")

        if stored_mtime is None:
            return {
                "icon_extracted": True,
                "icon_reused": False,
                "icon_status": "First install, icon newly extracted",
            }

        mtime_diff = abs(current_mtime - stored_mtime)

        if mtime_diff < 1.0:
            return {
                "icon_extracted": False,
                "icon_reused": True,
                "icon_status": "Icon reused (mtime unchanged)",
                "current_mtime": current_mtime,
                "stored_mtime": stored_mtime,
            }

        return {
            "icon_extracted": True,
            "icon_reused": False,
            "icon_status": "Icon re-extracted (mtime changed)",
            "current_mtime": current_mtime,
            "stored_mtime": stored_mtime,
            "mtime_diff": mtime_diff,
        }
