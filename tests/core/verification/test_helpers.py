"""Tests for verification helper functions.

This module provides comprehensive test coverage for the verification helpers:
- build_checksum_url(): Building URLs for checksum file downloads
- resolve_manual_checksum_file(): Resolving manually configured checksum files
  with template support ({version}, {asset_name}, {tag})
"""

from __future__ import annotations

import pytest

from my_unicorn.core.github import Asset, ChecksumFileInfo
from my_unicorn.core.verification.helpers import (
    build_checksum_url,
    resolve_manual_checksum_file,
)

# =============================================================================
# Task 1: build_checksum_url() Tests
# =============================================================================


class TestBuildChecksumUrl:
    """Tests for build_checksum_url function."""

    def test_basic_url_building(self) -> None:
        """Test basic URL building with standard parameters."""
        url = build_checksum_url("owner", "repo", "v1.0.0", "checksums.txt")
        assert (
            url
            == "https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt"
        )

    def test_url_with_special_characters_in_tag(self) -> None:
        """Test URL building with special characters in tag name."""
        url = build_checksum_url(
            "owner", "repo", "v1.0.0-beta.1", "checksums.txt"
        )
        assert (
            url
            == "https://github.com/owner/repo/releases/download/v1.0.0-beta.1/checksums.txt"
        )

    def test_url_with_uppercase_filename(self) -> None:
        """Test URL building with uppercase checksum filename."""
        url = build_checksum_url("owner", "repo", "v1.0.0", "SHA256SUMS.txt")
        assert (
            url
            == "https://github.com/owner/repo/releases/download/v1.0.0/SHA256SUMS.txt"
        )

    def test_url_with_yaml_filename(self) -> None:
        """Test URL building with YAML checksum filename."""
        url = build_checksum_url("owner", "repo", "v1.0.0", "latest-linux.yml")
        assert (
            url
            == "https://github.com/owner/repo/releases/download/v1.0.0/latest-linux.yml"
        )

    def test_url_with_complex_repo_name(self) -> None:
        """Test URL building with complex repository names."""
        url = build_checksum_url(
            "complex-owner",
            "complex-repo-name",
            "v1.0.0",
            "checksums.txt",
        )
        assert (
            url
            == "https://github.com/complex-owner/complex-repo-name/releases/download/v1.0.0/checksums.txt"
        )

    def test_url_with_numeric_tag(self) -> None:
        """Test URL building with purely numeric tag."""
        url = build_checksum_url("owner", "repo", "1.0.0", "checksums.txt")
        assert (
            url
            == "https://github.com/owner/repo/releases/download/1.0.0/checksums.txt"
        )

    def test_url_with_slash_in_tag(self) -> None:
        """Test URL building with slash in tag name (some repos use this)."""
        url = build_checksum_url(
            "owner", "repo", "release/v1.0.0", "checksums.txt"
        )
        assert (
            url
            == "https://github.com/owner/repo/releases/download/release/v1.0.0/checksums.txt"
        )


# =============================================================================
# Task 2: resolve_manual_checksum_file() Tests
# =============================================================================


class TestResolveManualChecksumFile:
    """Tests for resolve_manual_checksum_file function."""

    @pytest.fixture
    def sample_asset(self) -> Asset:
        """Create a sample asset for testing."""
        return Asset(
            name="app-1.0.0-x86_64.AppImage",
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/app-1.0.0-x86_64.AppImage",
            size=100000,
            digest="",
        )

    @pytest.fixture
    def yaml_asset(self) -> Asset:
        """Create a YAML checksum asset."""
        return Asset(
            name="latest-linux.yml",
            browser_download_url="https://github.com/owner/repo/releases/download/v1.0.0/latest-linux.yml",
            size=1000,
            digest="",
        )

    # =========================================================================
    # Traditional Format Tests (string filename)
    # =========================================================================

    def test_simple_filename_without_templates(
        self, sample_asset: Asset
    ) -> None:
        """Test with simple filename without any templates."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "checksums.txt"
        assert (
            result[0].url
            == "https://github.com/owner/repo/releases/download/v1.0.0/checksums.txt"
        )
        assert result[0].format_type == "traditional"

    def test_sha256_sums_filename(self, sample_asset: Asset) -> None:
        """Test with SHA256SUMS.txt filename."""
        result = resolve_manual_checksum_file(
            "SHA256SUMS.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "SHA256SUMS.txt"
        assert result[0].format_type == "traditional"

    def test_sha512_sums_filename(self, sample_asset: Asset) -> None:
        """Test with SHA512SUMS filename."""
        result = resolve_manual_checksum_file(
            "SHA512SUMS",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "SHA512SUMS"
        assert result[0].format_type == "traditional"

    # =========================================================================
    # YAML Format Tests
    # =========================================================================

    def test_yaml_extension_yml(self, sample_asset: Asset) -> None:
        """Test YAML format detection with .yml extension."""
        result = resolve_manual_checksum_file(
            "latest-linux.yml",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "latest-linux.yml"
        assert result[0].format_type == "yaml"

    def test_yaml_extension_yaml(self, sample_asset: Asset) -> None:
        """Test YAML format detection with .yaml extension."""
        result = resolve_manual_checksum_file(
            "checksums.yaml",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "checksums.yaml"
        assert result[0].format_type == "yaml"

    # =========================================================================
    # Template Support Tests ({version}, {tag}, {asset_name})
    # =========================================================================

    def test_version_template_substitution(self, sample_asset: Asset) -> None:
        """Test {version} template substitution."""
        result = resolve_manual_checksum_file(
            "checksums-{version}.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "checksums-v1.0.0.txt"
        assert (
            result[0].url
            == "https://github.com/owner/repo/releases/download/v1.0.0/checksums-v1.0.0.txt"
        )

    def test_tag_template_substitution(self, sample_asset: Asset) -> None:
        """Test {tag} template substitution (alias for {version})."""
        result = resolve_manual_checksum_file(
            "checksums-{tag}.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "checksums-v1.0.0.txt"

    def test_asset_name_template_substitution(
        self, sample_asset: Asset
    ) -> None:
        """Test {asset_name} template substitution."""
        result = resolve_manual_checksum_file(
            "checksums/{asset_name}.sha256",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert (
            result[0].filename == "checksums/app-1.0.0-x86_64.AppImage.sha256"
        )

    def test_multiple_templates_substitution(
        self, sample_asset: Asset
    ) -> None:
        """Test multiple template substitutions in one filename."""
        result = resolve_manual_checksum_file(
            "{version}/{asset_name}.sha256",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "v1.0.0/app-1.0.0-x86_64.AppImage.sha256"

    def test_version_and_tag_templates_both_present(
        self, sample_asset: Asset
    ) -> None:
        """Test when both {version} and {tag} templates are present."""
        result = resolve_manual_checksum_file(
            "checksums-{version}-{tag}.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        # Both should be replaced with the same value
        assert result[0].filename == "checksums-v1.0.0-v1.0.0.txt"

    # =========================================================================
    # Edge Cases: Missing or Empty Parameters
    # =========================================================================

    @pytest.mark.parametrize(
        ("owner", "repo", "tag"),
        [
            (None, "repo", "v1.0.0"),
            ("owner", None, "v1.0.0"),
            ("owner", "repo", None),
            ("", "repo", "v1.0.0"),
            ("owner", "", "v1.0.0"),
            ("owner", "repo", ""),
            (None, None, None),
        ],
    )
    def test_missing_or_empty_required_params(
        self,
        sample_asset: Asset,
        owner: str | None,
        repo: str | None,
        tag: str | None,
    ) -> None:
        """Test with missing or empty required parameters returns empty."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            owner,
            repo,
            tag,
        )
        assert result == []

    def test_templates_with_missing_tag_returns_empty(
        self, sample_asset: Asset
    ) -> None:
        """Test templates with missing tag_name returns empty list."""
        result = resolve_manual_checksum_file(
            "checksums-{version}.txt",
            sample_asset,
            "owner",
            "repo",
            None,
        )
        assert result == []

    def test_asset_name_template_with_none_asset_attribute(self) -> None:
        """Test {asset_name} template when asset lacks name attribute."""
        # Create a mock object without name attribute
        asset_without_name = object()
        # Type: ignore because we're testing edge case behavior
        result = resolve_manual_checksum_file(
            "checksums/{asset_name}.txt",
            asset_without_name,  # type: ignore[arg-type]
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        # Should keep {asset_name} if asset has no name attribute
        assert result[0].filename == "checksums/{asset_name}.txt"

    def test_asset_without_name_attribute(self) -> None:
        """Test with asset object that has no name attribute."""
        asset_no_name = Asset(
            name="test.AppImage",
            browser_download_url="https://example.com/test.AppImage",
            size=1000,
            digest="",
        )
        # Asset has name, so this should work normally
        result = resolve_manual_checksum_file(
            "checksums/{asset_name}.txt",
            asset_no_name,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert result[0].filename == "checksums/test.AppImage.txt"

    # =========================================================================
    # Edge Cases: Special Characters and Complex Paths
    # =========================================================================

    @pytest.mark.parametrize(
        "filename",
        [
            "checksums.txt",
            "SHA256SUMS-v1.0.0-beta.1-rc.2.txt",
            "checksums/SHA256SUMS.txt",
            "app-{version}-checksums.txt",
            "{version}-checksums-{asset_name}",
        ],
    )
    def test_various_filename_patterns(
        self, sample_asset: Asset, filename: str
    ) -> None:
        """Test various filename patterns and special characters."""
        result = resolve_manual_checksum_file(
            filename,
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].url is not None

    # =========================================================================
    # Return Value Structure Tests
    # =========================================================================

    def test_return_is_list(self, sample_asset: Asset) -> None:
        """Test that return value is a list."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert isinstance(result, list)

    def test_return_list_has_single_element(self, sample_asset: Asset) -> None:
        """Test return list has exactly one successful element."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1

    def test_return_element_is_checksum_file_info(
        self, sample_asset: Asset
    ) -> None:
        """Test returned element is ChecksumFileInfo."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert isinstance(result[0], ChecksumFileInfo)

    def test_checksum_file_info_has_all_fields(
        self, sample_asset: Asset
    ) -> None:
        """Test ChecksumFileInfo has all required fields."""
        result = resolve_manual_checksum_file(
            "checksums.txt",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        info = result[0]
        assert hasattr(info, "filename")
        assert hasattr(info, "url")
        assert hasattr(info, "format_type")
        assert info.filename is not None
        assert info.url is not None
        assert info.format_type is not None

    # =========================================================================
    # Integration Tests: Complex Scenarios
    # =========================================================================

    def test_integration_yaml_with_version_template(
        self, sample_asset: Asset
    ) -> None:
        """Integration test: YAML file with version template."""
        result = resolve_manual_checksum_file(
            "latest-{version}.yml",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert result[0].filename == "latest-v1.0.0.yml"
        assert result[0].format_type == "yaml"
        assert (
            result[0].url
            == "https://github.com/owner/repo/releases/download/v1.0.0/latest-v1.0.0.yml"
        )

    def test_integration_complex_asset_name_template(
        self, sample_asset: Asset
    ) -> None:
        """Test complex asset name template with subdirs."""
        result = resolve_manual_checksum_file(
            "checksums/{version}/{asset_name}.sha256",
            sample_asset,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert (
            result[0].filename
            == "checksums/v1.0.0/app-1.0.0-x86_64.AppImage.sha256"
        )

    def test_integration_all_template_types(self, sample_asset: Asset) -> None:
        """Integration test: Using all template types together."""
        result = resolve_manual_checksum_file(
            "{version}/{asset_name}-{tag}.sha256",
            sample_asset,
            "owner",
            "repo",
            "v1.5.2",
        )
        assert len(result) == 1
        expected = "v1.5.2/app-1.0.0-x86_64.AppImage-v1.5.2.sha256"
        assert result[0].filename == expected

    def test_integration_various_repo_names(self, sample_asset: Asset) -> None:
        """Integration test: Various repository naming conventions."""
        test_cases = [
            ("simple", "repo", "v1.0.0"),
            ("owner-with-dashes", "repo-name", "v1.0.0"),
            ("CamelCase", "MyRepo", "v1.0.0"),
            ("underscore_owner", "under_score_repo", "v1.0.0"),
        ]

        for owner, repo, tag in test_cases:
            result = resolve_manual_checksum_file(
                "checksums.txt",
                sample_asset,
                owner,
                repo,
                tag,
            )
            assert len(result) == 1
            expected_url = (
                f"https://github.com/{owner}/{repo}/"
                f"releases/download/{tag}/checksums.txt"
            )
            assert expected_url in result[0].url

    def test_integration_unicode_in_asset_name(self) -> None:
        """Integration test: Unicode characters in asset name."""
        asset_with_unicode = Asset(
            name="app-café-1.0.0.AppImage",
            browser_download_url="https://example.com/app.AppImage",
            size=1000,
            digest="",
        )
        result = resolve_manual_checksum_file(
            "checksums/{asset_name}.sha256",
            asset_with_unicode,
            "owner",
            "repo",
            "v1.0.0",
        )
        assert len(result) == 1
        assert "app-café-1.0.0.AppImage" in result[0].filename
