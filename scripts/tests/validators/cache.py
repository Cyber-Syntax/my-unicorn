#!/usr/bin/env python3
"""Cache validation module for test framework.

Validates GitHub release cache state, consistency, and asset filtering.

Author: Cyber-Syntax
License: Same as my-unicorn project
"""

from typing import Any

from utils import file_exists, get_cache_file_path, is_valid_json, load_json

from . import BaseValidator, ValidationResult


class CacheValidator(BaseValidator):
    """Validates GitHub release cache state and consistency."""

    def validate(self, operation: str, **kwargs: Any) -> ValidationResult:
        """Validate cache state and consistency.

        Args:
            operation: Operation type (install, update, remove)
            **kwargs: Additional context (config, repo)

        Returns:
            ValidationResult with cache validation checks
        """
        result = ValidationResult(
            validator="CacheValidator",
            app_name=self.app_name,
            operation=operation,
            status="PASS",
        )

        config = kwargs.get("config")
        if not config:
            result.add_error("No config provided for validation")
            return result

        repo = config.get("repo")
        if not repo:
            result.add_error("No repo in config")
            return result

        cache_path = get_cache_file_path(repo)

        # Check cache file exists
        cache_exists = file_exists(cache_path)
        result.add_check(
            name="cache_exists",
            passed=cache_exists,
            expected="Cache file exists",
            actual=str(cache_path) if cache_exists else "Not found",
            message="Cache file should exist for installed app",
        )

        if not cache_exists:
            return result

        # Check valid JSON
        is_json_valid = is_valid_json(cache_path)
        result.add_check(
            name="cache_valid_json",
            passed=is_json_valid,
            expected="Valid JSON",
            actual="Valid" if is_json_valid else "Invalid",
            message="Cache file should be valid JSON",
        )

        if not is_json_valid:
            return result

        # Load and validate cache structure
        try:
            cache = load_json(cache_path)
        except Exception as e:
            result.add_error(f"Failed to load cache: {e}")
            return result

        self._validate_structure(result, cache)
        self._validate_asset_filtering(result, cache)
        self._validate_version_consistency(result, config, cache)

        return result

    def _validate_structure(
        self, result: ValidationResult, cache: dict[str, Any]
    ) -> None:
        """Validate cache has expected structure."""
        required_top_level = ["release_data", "cached_at"]
        missing_top_level = [
            field for field in required_top_level if field not in cache
        ]

        if missing_top_level:
            result.add_error(
                f"Missing top-level fields: {', '.join(missing_top_level)}"
            )
            return

        release_data = cache.get("release_data")
        if not isinstance(release_data, dict):
            result.add_error("release_data is not a dictionary")
            return

        required_release_fields = ["tag_name", "published_at", "assets"]
        missing_release_fields = [
            field
            for field in required_release_fields
            if field not in release_data
        ]

        if missing_release_fields:
            result.add_error(
                f"release_data missing fields: {', '.join(missing_release_fields)}"
            )

    def _validate_asset_filtering(
        self, result: ValidationResult, cache: dict[str, Any]
    ) -> None:
        """Validate cache contains only AppImage and checksum assets."""
        release_data = cache.get("release_data", {})
        assets = release_data.get("assets", [])

        if not isinstance(assets, list):
            result.add_error("assets is not a list")
            return

        appimage_extensions = (".AppImage", ".appimage")
        checksum_patterns = (
            "SHA256SUMS",
            "SHA512SUMS",
            "checksums.txt",
            "SHASUMS256.txt",
        )

        invalid_assets = []
        for asset in assets:
            if not isinstance(asset, dict):
                continue

            name = asset.get("name", "")
            is_appimage = name.endswith(appimage_extensions)
            is_checksum = any(pattern in name for pattern in checksum_patterns)

            if not (is_appimage or is_checksum):
                invalid_assets.append(name)

        if invalid_assets:
            result.add_warning(
                f"Non-AppImage/checksum assets found: {', '.join(invalid_assets[:3])}"
            )

        result.metadata["asset_count"] = len(assets)
        result.metadata["filtered_assets"] = len(invalid_assets)

    def _validate_version_consistency(
        self,
        result: ValidationResult,
        config: dict[str, Any],
        cache: dict[str, Any],
    ) -> None:
        """Check version consistency between cache and config."""
        installed_version = config.get("installed_version", "")
        cached_version = cache.get("release_data", {}).get("tag_name", "")

        if installed_version != cached_version:
            result.add_warning(
                f"Cache version ({cached_version}) differs from installed ({installed_version})"
            )

        result.metadata["installed_version"] = installed_version
        result.metadata["cached_version"] = cached_version
