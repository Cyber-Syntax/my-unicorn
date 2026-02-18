"""Tests for advanced concurrent verification scenarios.

This module tests edge cases and advanced scenarios in concurrent verification:
- Multiple checksum files (priority selection and de-duplication)
- Exception handling during concurrent verification
- Warning generation for partial verification and missing methods

Key assertion principles:
1. Only the best-priority checksum file is used (no duplication)
2. Exceptions in one method don't block other methods
3. Partial success generates appropriate warnings
4. No verification methods available generates a warning
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.service import VerificationService

# Test data constants - SHA256 hash of b"test content"
TEST_HASH = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
TEST_HASH_SHA512_BASE64 = (
    "DL9MrvOAR7upok5iGpYUhOXSqSF2qFnn6yffND3TTrmNU4psX02hzjAuwlC4IcwA"
    "HkbMl6cEmIKXGFpN9+mWAg=="
)
TEST_CONTENT = b"test content"
WRONG_HASH = "0000000000000000000000000000000000000000000000000000000000000000"

# GitHub test URLs
GITHUB_BASE = "https://github.com/test/repo/releases/download/v1.0"


class TestMultipleChecksumFiles:
    """Tests for scenarios with multiple checksum files available."""

    @pytest.fixture
    def mock_download_service(self) -> MagicMock:
        """Create a mock download service."""
        return MagicMock()

    @pytest.fixture
    def verification_service(
        self, mock_download_service: MagicMock
    ) -> VerificationService:
        """Create a VerificationService instance with mock dependencies."""
        return VerificationService(mock_download_service)

    @pytest.fixture
    def test_file_path(self, tmp_path: Path) -> Path:
        """Create a temporary test file with known content."""
        file_path = tmp_path / "test.AppImage"
        file_path.write_bytes(TEST_CONTENT)
        return file_path

    @pytest.fixture
    def assets_with_multiple_checksums(self) -> list[Asset]:
        """Assets with digest and multiple checksum files."""
        return [
            Asset(
                name="test.AppImage",
                browser_download_url=f"{GITHUB_BASE}/test.AppImage",
                size=len(TEST_CONTENT),
                digest=f"sha256:{TEST_HASH}",
            ),
            Asset(
                name="latest-linux.yml",
                browser_download_url=f"{GITHUB_BASE}/latest-linux.yml",
                size=500,
                digest="",
            ),
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
                size=200,
                digest="",
            ),
            Asset(
                name="SHA512SUMS.txt",
                browser_download_url=f"{GITHUB_BASE}/SHA512SUMS.txt",
                size=300,
                digest="",
            ),
        ]

    @pytest.mark.asyncio
    async def test_multiple_checksum_files_with_digest(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """All methods attempted concurrently.

        When digest and checksums exist, all methods should be attempted.
        """
        asset = assets_with_multiple_checksums[0]
        config = {"skip": False}

        checksum_content = f"{TEST_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=checksum_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_checksum_files_use_unique_keys(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """Only the best checksum file is used, producing single method key."""
        # Use asset without digest to force checksum verification
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        config = {"skip": False}

        # YAML format is selected (highest priority), mock YAML content
        yaml_content = f"""
version: 1.0
path: test.AppImage
sha512: {TEST_HASH_SHA512_BASE64}
"""
        mock_download = AsyncMock(return_value=yaml_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True
        # Exactly one checksum method should be present (best match only)
        checksum_keys = [k for k in result.methods if "checksum" in k]
        assert len(checksum_keys) == 1
        assert "checksum_file" in result.methods

    @pytest.mark.asyncio
    async def test_first_successful_checksum_used_as_primary(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """Best-priority checksum file is used when no digest is present."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        config = {"skip": False}

        # YAML format is selected (highest priority), mock YAML content
        yaml_content = f"""
version: 1.0
path: test.AppImage
sha512: {TEST_HASH_SHA512_BASE64}
"""
        mock_download = AsyncMock(return_value=yaml_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True

        # Only one checksum file (best priority) should be attempted
        checksum_methods = [
            k for k in result.methods if k.startswith("checksum")
        ]
        assert len(checksum_methods) == 1
        assert "checksum_file" in result.methods

    @pytest.mark.asyncio
    async def test_selects_highest_priority_checksum_file(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
    ) -> None:
        """Verification selects best-match checksum file per priority rules.

        Priority order:
        1. Exact .DIGEST match (e.g., test.AppImage.DIGEST)
        2. Platform-specific hash (e.g., test.AppImage.sha256)
        3. YAML files (most comprehensive)
        4. Generic checksum files (SHA256SUMS.txt)
        """
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest - forces checksum verification
        )

        # Multiple checksum files with different priorities
        assets = [
            asset,
            # Priority 5 - generic
            Asset(
                name="SHA256SUMS.txt",
                browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
                size=100,
                digest="",
            ),
            # Priority 3 - YAML
            Asset(
                name="latest-linux.yml",
                browser_download_url=f"{GITHUB_BASE}/latest-linux.yml",
                size=200,
                digest="",
            ),
        ]

        config = {"skip": False}

        # YAML checksum format
        yaml_content = f"""
version: 1.0
path: test.AppImage
sha512: {TEST_HASH_SHA512_BASE64}
"""
        mock_download = AsyncMock(return_value=yaml_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        assert result.passed is True
        # Only ONE checksum_file method should exist
        checksum_keys = [k for k in result.methods if "checksum" in k]
        assert len(checksum_keys) == 1
        assert "checksum_file" in result.methods
        # YAML file should be selected (higher priority than SHA256SUMS)
        assert result.updated_config.get("checksum_file") == "latest-linux.yml"

    @pytest.mark.asyncio
    async def test_no_indexed_checksum_method_keys(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        assets_with_multiple_checksums: list[Asset],
    ) -> None:
        """Verify no checksum_file_0, checksum_file_1 keys are generated."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        config = {"skip": False}

        # YAML format is selected (highest priority), mock YAML content
        yaml_content = f"""
version: 1.0
path: test.AppImage
sha512: {TEST_HASH_SHA512_BASE64}
"""
        mock_download = AsyncMock(return_value=yaml_content)
        verification_service.download_service.download_checksum_file = (
            mock_download
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets_with_multiple_checksums,
        )

        assert result.passed is True
        # No indexed keys should exist
        indexed_keys = [
            k for k in result.methods if k.startswith("checksum_file_")
        ]
        assert len(indexed_keys) == 0, (
            f"Found indexed checksum keys: {indexed_keys}"
        )
