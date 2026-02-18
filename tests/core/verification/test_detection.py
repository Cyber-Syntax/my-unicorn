"""Tests for core detection functions in verification module.

This module provides comprehensive tests for detection-related functions:
- detect_available_methods()
- check_digest_availability()
- resolve_checksum_files()
- auto_detect_checksum_files()
- should_skip_verification()

For prioritize_checksum_files tests, see test_detection_priority.py
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.detection import (
    auto_detect_checksum_files,
    check_digest_availability,
    detect_available_methods,
    resolve_checksum_files,
    should_skip_verification,
)


class TestDetectAvailableMethods:
    """Test detect_available_methods function."""

    def test_detect_available_methods_no_digest_no_assets(self) -> None:
        """Test detection with no digest and no assets."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            digest="",
        )
        config: dict[str, Any] = {}

        has_digest, checksum_files = detect_available_methods(asset, config)

        assert has_digest is False
        assert checksum_files == []

    def test_detect_available_methods_with_digest(self) -> None:
        """Test detection with digest available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            digest="sha256:abc123def456",
        )
        config: dict[str, Any] = {}

        has_digest, checksum_files = detect_available_methods(asset, config)

        assert has_digest is True
        assert checksum_files == []

    def test_detect_available_methods_with_assets_yaml(
        self, sample_assets
    ) -> None:
        """Test detection with assets containing YAML checksum file."""
        asset = Asset(
            name="Legcord-1.1.5-linux-x86_64.AppImage",
            size=124457255,
            browser_download_url="https://github.com/Legcord/Legcord/releases/download/v1.1.5/Legcord-1.1.5-linux-x86_64.AppImage",
            digest="",
        )
        config: dict[str, Any] = {"checksum_file": ""}

        has_digest, checksum_files = detect_available_methods(
            asset, config, sample_assets, "Legcord", "Legcord", "v1.1.5"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "latest-linux.yml"
        assert checksum_files[0].format_type == "yaml"

    def test_detect_available_methods_with_digest_and_assets(
        self, sample_assets_with_both
    ) -> None:
        """Test detection with both digest and checksum files available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://github.com/test/test/releases/download/v1.0.0/app.AppImage",
            digest="sha256:abc123",
        )
        config = {"checksum_file": ""}

        has_digest, checksum_files = detect_available_methods(
            asset,
            config,
            sample_assets_with_both,
            "test",
            "test",
            "v1.0.0",
        )

        assert has_digest is True
        assert len(checksum_files) == 2

    def test_detect_available_methods_manual_checksum_file(self) -> None:
        """Test detection with manually configured checksum file."""
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest="",
        )
        config = {"checksum_file": "manual-checksums.txt"}

        has_digest, checksum_files = detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "manual-checksums.txt"
        assert checksum_files[0].format_type == "traditional"

    def test_detect_available_methods_v2_checksum_file_dict(self) -> None:
        """Test detection with v2 format dict checksum_file configuration.

        This is a regression test for the bug where v2 catalog format
        uses a dict for checksum_file with 'filename' and 'algorithm' keys,
        but the code was treating it as a string and calling .strip() on it.
        """
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest="",
        )
        config: dict[str, Any] = {
            "checksum_file": {
                "filename": "latest-linux.yml",
                "algorithm": "sha512",
            }
        }

        has_digest, checksum_files = detect_available_methods(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert has_digest is False
        assert len(checksum_files) == 1
        assert checksum_files[0].filename == "latest-linux.yml"

    def test_detect_available_methods_backward_compatibility(self) -> None:
        """Test backward compatibility without assets parameter."""
        asset = Asset(
            name="test.AppImage",
            size=124457255,
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/test.AppImage",
            digest="sha256:abc123",
        )
        config = {"checksum_file": "checksums.txt"}

        has_digest, checksum_files = detect_available_methods(asset, config)

        assert has_digest is True
        assert len(checksum_files) == 0


class TestCheckDigestAvailability:
    """Test check_digest_availability function."""

    def test_check_digest_availability_with_digest(self) -> None:
        """Test when digest is available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="sha256:abc123def456",
        )
        config: dict[str, Any] = {}

        result = check_digest_availability(asset, config)

        assert result is True

    def test_check_digest_availability_no_digest(self) -> None:
        """Test when digest is not available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config: dict[str, Any] = {}

        result = check_digest_availability(asset, config)

        assert result is False

    def test_check_digest_availability_empty_string(self) -> None:
        """Test when digest is an empty string."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config: dict[str, Any] = {}

        result = check_digest_availability(asset, config)

        assert result is False

    def test_check_digest_availability_whitespace_only(self) -> None:
        """Test when digest is only whitespace."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="   ",
        )
        config: dict[str, Any] = {}

        result = check_digest_availability(asset, config)

        assert result is False

    def test_check_digest_availability_requested_but_missing(self) -> None:
        """Test when digest is requested but not available."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config = {"digest": True}

        result = check_digest_availability(asset, config)

        assert result is False


class TestResolveChecksumFiles:
    """Test resolve_checksum_files function."""

    def test_resolve_checksum_files_no_config(self) -> None:
        """Test when no checksum file is configured."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config: dict[str, Any] = {}

        result = resolve_checksum_files(asset, config, None, None, None, None)

        assert result == []

    def test_resolve_checksum_files_manual_string(self) -> None:
        """Test with manually configured string checksum file."""
        asset = Asset(
            name="test.AppImage",
            size=12345,
            browser_download_url="https://example.com/test.AppImage",
            digest="",
        )
        config = {"checksum_file": "SHA256SUMS.txt"}

        result = resolve_checksum_files(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert len(result) == 1
        assert result[0].filename == "SHA256SUMS.txt"
        assert result[0].format_type == "traditional"

    def test_resolve_checksum_files_manual_dict(self) -> None:
        """Test with manually configured dict checksum file (v2 format)."""
        asset = Asset(
            name="test.AppImage",
            size=12345,
            browser_download_url="https://example.com/test.AppImage",
            digest="",
        )
        config = {
            "checksum_file": {
                "filename": "latest-linux.yml",
                "algorithm": "sha512",
            }
        }

        result = resolve_checksum_files(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert len(result) == 1
        assert result[0].filename == "latest-linux.yml"

    def test_resolve_checksum_files_manual_dict_empty(self) -> None:
        """Test manually configured dict checksum file with empty filename."""
        asset = Asset(
            name="test.AppImage",
            size=12345,
            browser_download_url="https://example.com/test.AppImage",
            digest="",
        )
        config = {"checksum_file": {"filename": "", "algorithm": "sha512"}}

        result = resolve_checksum_files(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert result == []

    def test_resolve_checksum_files_manual_empty_string(self) -> None:
        """Test with empty string checksum file."""
        asset = Asset(
            name="test.AppImage",
            size=12345,
            browser_download_url="https://example.com/test.AppImage",
            digest="",
        )
        config = {"checksum_file": ""}

        result = resolve_checksum_files(
            asset, config, None, "owner", "repo", "v1.0.0"
        )

        assert result == []

    def test_resolve_checksum_files_auto_detect(self, sample_assets) -> None:
        """Test auto-detection of checksum files."""
        asset = Asset(
            name="Legcord-1.1.5-linux-x86_64.AppImage",
            size=124457255,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config: dict[str, Any] = {}

        result = resolve_checksum_files(
            asset,
            config,
            sample_assets,
            "Legcord",
            "Legcord",
            "v1.1.5",
        )

        assert len(result) >= 1
        assert result[0].filename == "latest-linux.yml"

    def test_resolve_checksum_files_priority_digest_over_detection(
        self, sample_assets
    ) -> None:
        """Test that digest config prevents auto-detection."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config = {"digest": True}

        result = resolve_checksum_files(
            asset,
            config,
            sample_assets,
            "owner",
            "repo",
            "v1.0.0",
        )

        assert result == []

    def test_resolve_checksum_files_manual_overrides_auto(
        self, sample_assets
    ) -> None:
        """Test that manual checksum file overrides auto-detection."""
        asset = Asset(
            name="app.AppImage",
            size=12345,
            browser_download_url="https://example.com/app.AppImage",
            digest="",
        )
        config = {"checksum_file": "custom.txt"}

        result = resolve_checksum_files(
            asset,
            config,
            sample_assets,
            "owner",
            "repo",
            "v1.0.0",
        )

        assert len(result) == 1
        assert result[0].filename == "custom.txt"


class TestAutoDetectChecksumFiles:
    """Test auto_detect_checksum_files function."""

    def test_auto_detect_checksum_files_found(self, sample_assets) -> None:
        """Test when checksum files are found."""
        result = auto_detect_checksum_files(sample_assets, "v1.1.5")

        assert len(result) >= 1
        assert result[0].filename == "latest-linux.yml"
        assert result[0].format_type == "yaml"

    def test_auto_detect_checksum_files_not_found(self) -> None:
        """Test when no checksum files are found."""
        assets = [
            Asset(
                name="app.AppImage",
                size=12345,
                browser_download_url="https://example.com/app.AppImage",
                digest="",
            )
        ]

        result = auto_detect_checksum_files(assets, "v1.0.0")

        assert result == []

    def test_auto_detect_checksum_files_empty_list(self) -> None:
        """Test with empty assets list."""
        result = auto_detect_checksum_files([], "v1.0.0")

        assert result == []

    def test_auto_detect_checksum_files_multiple(
        self, sample_assets_with_both
    ) -> None:
        """Test when multiple checksum files are detected."""
        result = auto_detect_checksum_files(sample_assets_with_both, "v1.0.0")

        assert len(result) >= 1

    def test_auto_detect_checksum_files_exception_handling(self) -> None:
        """Test that exceptions are caught and empty list is returned."""
        assets = [MagicMock()]
        assets[0].name = "app.AppImage"

        result = auto_detect_checksum_files(assets, "v1.0.0")

        assert result == []


class TestShouldSkipVerification:
    """Test should_skip_verification function."""

    def test_should_skip_verification_skip_true_no_methods(self) -> None:
        """Test skip when configured and no verification methods available."""
        config = {"skip": True}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert should_skip is True
        assert updated_config["skip"] is True

    def test_should_skip_verification_skip_true_with_digest(self) -> None:
        """Test skip override when digest is available."""
        config = {"skip": True}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=True, has_checksum_files=False
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_skip_true_with_checksum_files(
        self,
    ) -> None:
        """Test skip override when checksum files are available."""
        config = {"skip": True}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=True
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_skip_true_with_both(self) -> None:
        """Test skip override when both verification methods available."""
        config = {"skip": True}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=True, has_checksum_files=True
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_skip_false_no_methods(self) -> None:
        """Test no skip when configured false."""
        config = {"skip": False}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_skip_false_with_methods(self) -> None:
        """Test no skip when verification methods available."""
        config = {"skip": False}
        should_skip, updated_config = should_skip_verification(
            config, has_digest=True, has_checksum_files=True
        )

        assert should_skip is False
        assert updated_config["skip"] is False

    def test_should_skip_verification_empty_config(self) -> None:
        """Test with empty config (skip defaults to False)."""
        config: dict[str, Any] = {}
        should_skip, _updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert should_skip is False

    def test_should_skip_verification_preserves_other_config(self) -> None:
        """Test that other config values are preserved."""
        config = {"skip": True, "digest": True, "other": "value"}
        _should_skip, updated_config = should_skip_verification(
            config, has_digest=True, has_checksum_files=False
        )

        assert updated_config["digest"] is True
        assert updated_config["other"] == "value"

    def test_should_skip_verification_skip_not_modified_when_not_overridden(
        self,
    ) -> None:
        """Test that skip is not modified when not overridden."""
        config = {"skip": False}
        _should_skip, updated_config = should_skip_verification(
            config, has_digest=False, has_checksum_files=False
        )

        assert updated_config["skip"] is False
