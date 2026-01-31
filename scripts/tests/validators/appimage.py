#!/usr/bin/env python3
"""AppImage validation module for test framework.

Validates AppImage file integrity, SHA hashes, and executability.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from pathlib import Path
from typing import Any

from utils import (
    calculate_sha256,
    calculate_sha512,
    file_exists,
    get_file_size,
    is_executable,
)

from . import BaseValidator, ValidationResult


class AppImageValidator(BaseValidator):
    """Validates AppImage file integrity and properties."""

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate AppImage file state.

        For install/update: Verifies file exists, is executable, and SHA matches
        For remove: Verifies file is deleted

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context (config, expected_sha, etc.)

        Returns:
            ValidationResult with AppImage validation checks
        """
        result = ValidationResult(
            validator="AppImageValidator",
            app_name=self.app_name,
            operation=operation,
            status="PASS",
        )

        if operation == "remove":
            return self._validate_remove(result, **kwargs)
        return self._validate_install_update(result, **kwargs)

    def _validate_install_update(
        self,
        result: ValidationResult,
        **kwargs: Any,  # noqa: ANN401
    ) -> ValidationResult:
        """Validate AppImage after install or update operation."""
        config = kwargs.get("config")
        if not config:
            result.add_error("No config provided for validation")
            return result

        # Get AppImage path from config
        installed_path = config.get("state", {}).get("installed_path")
        if not installed_path:
            result.add_error("No installed_path found in config")
            return result

        appimage_path = Path(installed_path)

        # Check 1: File exists and is valid
        exists = file_exists(appimage_path)
        is_file = appimage_path.is_file() if exists else False
        size = get_file_size(appimage_path)

        result.add_check(
            name="appimage_exists",
            passed=exists and is_file and size > 0,
            expected={"exists": True, "is_file": True, "size_gt_0": True},
            actual={"exists": exists, "is_file": is_file, "size": size},
            message=f"AppImage at {appimage_path}",
        )

        if not exists:
            result.add_error(f"AppImage not found: {appimage_path}")
            return result

        # Check 2: File is executable
        executable = is_executable(appimage_path)
        result.add_check(
            name="appimage_executable",
            passed=executable,
            expected=True,
            actual=executable,
            message=f"AppImage executable permission: {appimage_path}",
        )

        if not executable:
            result.add_warning(f"AppImage not executable: {appimage_path}")

        # Check 3: Minimum size (1MB = sanity check)
        min_size = 1024 * 1024  # 1MB
        result.add_check(
            name="appimage_min_size",
            passed=size >= min_size,
            expected=f">= {min_size} bytes",
            actual=f"{size} bytes",
            message="AppImage size validation",
        )

        # Check 4: SHA verification (if available in config)
        self._validate_sha(result, appimage_path, config)

        result.metadata["appimage_path"] = str(appimage_path)
        result.metadata["appimage_size"] = size
        result.metadata["appimage_executable"] = executable

        return result

    def _validate_sha(
        self,
        result: ValidationResult,
        appimage_path: Path,
        config: dict[str, Any],
    ) -> None:
        """Validate SHA hash if available in config."""
        # Check for SHA256
        expected_sha256 = config.get("state", {}).get("sha256")
        if expected_sha256:
            try:
                actual_sha256 = calculate_sha256(appimage_path)
                sha_matches = actual_sha256.lower() == expected_sha256.lower()

                result.add_check(
                    name="sha256_verification",
                    passed=sha_matches,
                    expected=expected_sha256,
                    actual=actual_sha256,
                    message="SHA256 hash verification",
                )

                if not sha_matches:
                    result.add_error(
                        f"SHA256 mismatch: expected {expected_sha256}, "
                        f"got {actual_sha256}"
                    )

                result.metadata["sha256"] = actual_sha256
            except Exception as e:  # noqa: BLE001
                result.add_warning(f"SHA256 calculation failed: {e}")

        # Check for SHA512
        expected_sha512 = config.get("state", {}).get("sha512")
        if expected_sha512:
            try:
                actual_sha512 = calculate_sha512(appimage_path)
                sha_matches = actual_sha512.lower() == expected_sha512.lower()

                result.add_check(
                    name="sha512_verification",
                    passed=sha_matches,
                    expected=expected_sha512,
                    actual=actual_sha512,
                    message="SHA512 hash verification",
                )

                if not sha_matches:
                    result.add_error(
                        f"SHA512 mismatch: expected {expected_sha512}, "
                        f"got {actual_sha512}"
                    )

                result.metadata["sha512"] = actual_sha512
            except Exception as e:  # noqa: BLE001
                result.add_warning(f"SHA512 calculation failed: {e}")

    def verify_manual_sha(
        self,
        appimage_path: Path,
        expected_hash: str,
        algorithm: str = "sha256",
    ) -> ValidationResult:
        """Manually verify SHA hash independent of config.

        Useful for one-off verification or debugging hash mismatches.

        Args:
            appimage_path: Path to AppImage file
            expected_hash: Expected hash value
            algorithm: Hash algorithm (sha256 or sha512)

        Returns:
            ValidationResult with manual verification check
        """
        result = ValidationResult(
            validator="AppImageValidator",
            app_name=self.app_name,
            operation="manual_sha_verify",
            status="PASS",
        )

        if not file_exists(appimage_path):
            result.add_error(f"AppImage not found: {appimage_path}")
            return result

        try:
            if algorithm == "sha256":
                actual_hash = calculate_sha256(appimage_path)
            elif algorithm == "sha512":
                actual_hash = calculate_sha512(appimage_path)
            else:

                def _raise_unsupported() -> None:
                    msg = f"Unsupported algorithm: {algorithm}"
                    raise ValueError(msg)

                _raise_unsupported()
                return result  # Should never reach here

            hash_matches = actual_hash.lower() == expected_hash.lower()

            result.add_check(
                name=f"manual_{algorithm}_verification",
                passed=hash_matches,
                expected=expected_hash,
                actual=actual_hash,
                message=f"Manual {algorithm.upper()} hash verification",
            )

            if not hash_matches:
                result.add_error(
                    f"{algorithm.upper()} mismatch: expected {expected_hash}, "
                    f"got {actual_hash}"
                )

            result.metadata[f"manual_{algorithm}"] = actual_hash
            result.metadata["algorithm"] = algorithm

        except Exception as e:  # noqa: BLE001
            result.add_error(
                f"Manual {algorithm.upper()} verification failed: {e}"
            )

        return result

    def _validate_remove(
        self,
        result: ValidationResult,
        **kwargs: Any,  # noqa: ANN401
    ) -> ValidationResult:
        """Validate AppImage after remove operation."""
        config = kwargs.get("config")
        if not config:
            # For remove, we might not have config if it was already deleted
            result.add_warning("No config available for remove validation")
            return result

        installed_path = config.get("state", {}).get("installed_path")
        if not installed_path:
            result.add_warning("No installed_path found in config")
            return result

        appimage_path = Path(installed_path)
        exists = file_exists(appimage_path)

        result.add_check(
            name="appimage_deleted",
            passed=not exists,
            expected=False,
            actual=exists,
            message=f"AppImage should be deleted: {appimage_path}",
        )

        if exists:
            result.add_error(
                f"AppImage still exists after remove: {appimage_path}"
            )

        return result


def validate_appimage_integrity(
    app_name: str, config: dict[str, Any], operation: str = "install"
) -> ValidationResult:
    """Convenience function to validate AppImage integrity.

    Args:
        app_name: Name of the app
        config: App configuration dictionary
        operation: Operation type (install, update, remove)

    Returns:
        ValidationResult with AppImage validation checks
    """
    validator = AppImageValidator(app_name)
    return validator.validate(operation, config=config)
