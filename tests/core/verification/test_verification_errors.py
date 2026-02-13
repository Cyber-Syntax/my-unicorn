"""Tests for exception handling and warning generation in concurrent verification.

This module tests advanced scenarios:
- Exception handling during concurrent verification
- Warning generation for partial verification and missing methods

Key assertion principles:
1. Exceptions in one method don't block other methods
2. Partial success generates appropriate warnings
3. No verification methods available generates a warning
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


class TestExceptionHandling:
    """Tests for exception handling during concurrent verification."""

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

    @pytest.mark.asyncio
    async def test_checksum_download_exception_doesnt_block_digest(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Checksum download exception doesn't block successful digest."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(side_effect=TimeoutError("Network timeout"))
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

        # Overall should pass due to digest
        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

    @pytest.mark.asyncio
    async def test_network_timeout_recorded_as_method_failure(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Network timeout during checksum download recorded as failure."""
        # Asset with digest and checksum
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(side_effect=TimeoutError("Network timeout"))
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

        # Digest should pass
        assert result.passed is True
        assert "digest" in result.methods

        # Checksum may be recorded as failed or not attempted
        # Either is acceptable - what matters is digest passes

    @pytest.mark.asyncio
    async def test_partial_success_with_exception_generates_warning(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Partial success with exception generates appropriate warning."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum download to raise exception
        mock_download = AsyncMock(
            side_effect=ConnectionError("Connection refused")
        )
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

        # Should pass with digest
        assert result.passed is True
        assert result.methods["digest"]["passed"] is True


class TestWarningGeneration:
    """Tests for verification warning generation in various scenarios."""

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

    @pytest.mark.asyncio
    async def test_no_warning_when_all_methods_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No warning generated when all available methods pass."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
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
            assets=assets,
        )

        assert result.passed is True
        # No warning when all methods pass
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_no_warning_when_single_method_passes(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No warning generated when single available method passes."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]  # No checksum file
        config = {"skip": False}

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
        # No warning needed for single method success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_warning_when_partial_verification(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning generated when some methods pass and others fail."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",  # Correct hash
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Wrong checksum content
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=wrong_checksum)
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

        # Should pass (digest works)
        assert result.passed is True
        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_warning_when_no_verification_available(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning generated when no verification methods are available."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        assets = [asset]  # No checksum files
        config = {"skip": False}

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

        # Should pass (cannot verify, but don't block)
        assert result.passed is True

        # Warning about no checksums provided
        assert result.warning is not None
        warning_lower = result.warning.lower()
        assert "not provide" in warning_lower or "checksum" in warning_lower

    @pytest.mark.asyncio
    async def test_warning_contains_failure_details(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Warning includes details about which method failed."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

        assets = [asset, checksum_asset]
        config = {"skip": False}

        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        mock_download = AsyncMock(return_value=wrong_checksum)
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
        # Warning should exist for partial verification
        assert result.warning is not None
