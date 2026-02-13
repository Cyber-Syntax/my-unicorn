"""Tests for multi-method concurrent verification.

This module tests the concurrent execution of multiple verification methods
(digest and checksum file verification) using asyncio.gather().

Key behaviors tested:
1. Both methods pass → overall passed, no warning
2. Digest passes, checksum fails → overall passed (partial success), warning
3. Digest fails, checksum passes → overall passed (partial success), warning
4. Both methods fail → exception raised, installation blocked
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from my_unicorn.core.github import Asset
from my_unicorn.core.verification.service import VerificationService
from my_unicorn.exceptions import VerificationError

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


class TestConcurrentVerification:
    """Tests for concurrent multi-method verification."""

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
    def asset_with_correct_digest(self) -> Asset:
        """Asset with correct SHA256 digest matching TEST_CONTENT."""
        return Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )

    @pytest.fixture
    def asset_with_wrong_digest(self) -> Asset:
        """Asset with incorrect SHA256 digest."""
        return Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{WRONG_HASH}",
        )

    @pytest.fixture
    def checksum_asset(self) -> Asset:
        """Checksum file asset."""
        return Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )

    @pytest.mark.asyncio
    async def test_concurrent_both_methods_pass(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_correct_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Both methods pass: overall passed, digest is primary, no warning."""
        assets = [asset_with_correct_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum file download to return matching hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_correct_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Assert overall success
        assert result.passed is True

        # Digest method should be recorded and passed
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # No warning for complete success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_concurrent_digest_pass_checksum_fail(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_correct_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Digest passes, checksum fails: passed with partial warning."""
        assets = [asset_with_correct_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum file to return wrong hash
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=wrong_checksum)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_correct_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Overall should pass (at least one method passed)
        assert result.passed is True

        # Digest should pass and be recorded
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # Checksum should be recorded as failed
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is False

        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_concurrent_digest_fail_checksum_pass(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_wrong_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Digest fails, checksum passes: passed with partial warning."""
        assets = [asset_with_wrong_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum to return correct hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
        )

        result = await verification_service.verify_file(
            file_path=test_file_path,
            asset=asset_with_wrong_digest,
            config=config,
            owner="test",
            repo="repo",
            tag_name="v1.0",
            app_name="test.AppImage",
            assets=assets,
        )

        # Overall should pass (checksum passed)
        assert result.passed is True

        # Checksum should be recorded and passed
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

        # Digest should be recorded as failed
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is False

        # Warning about partial verification
        assert result.warning is not None
        assert "Partial" in result.warning

    @pytest.mark.asyncio
    async def test_concurrent_both_methods_fail(
        self,
        verification_service: VerificationService,
        test_file_path: Path,
        asset_with_wrong_digest: Asset,
        checksum_asset: Asset,
    ) -> None:
        """Both methods fail: exception raised, installation blocked."""
        assets = [asset_with_wrong_digest, checksum_asset]
        config = {"skip": False}

        # Mock checksum to return wrong hash too
        wrong_checksum = f"{WRONG_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=wrong_checksum)
        )

        # Should raise VerificationError when all methods fail
        with pytest.raises(VerificationError, match=r"verification|failed"):
            await verification_service.verify_file(
                file_path=test_file_path,
                asset=asset_with_wrong_digest,
                config=config,
                owner="test",
                repo="repo",
                tag_name="v1.0",
                app_name="test.AppImage",
                assets=assets,
            )


class TestConcurrentVerificationEdgeCases:
    """Edge case tests for concurrent verification."""

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
    async def test_digest_only_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Only digest available and passes: overall passed, no warning."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        # No checksum file in assets
        assets = [asset]
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

        # Should pass with digest verification
        assert result.passed is True
        assert "digest" in result.methods
        assert result.methods["digest"]["passed"] is True

        # No warning needed when single method passes
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_checksum_only_pass(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Only checksum available and passes: overall passed, no warning."""
        # Asset without digest
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
        )
        checksum_asset = Asset(
            name="SHA256SUMS.txt",
            browser_download_url=f"{GITHUB_BASE}/SHA256SUMS.txt",
            size=100,
            digest="",
        )
        assets = [asset, checksum_asset]
        config = {"skip": False}

        # Mock checksum file to return correct hash
        checksum_content = f"{TEST_HASH}  test.AppImage"
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
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

        # Should pass with checksum verification
        assert result.passed is True
        assert "checksum_file" in result.methods
        assert result.methods["checksum_file"]["passed"] is True

        # No warning for complete success
        assert result.warning is None

    @pytest.mark.asyncio
    async def test_no_verification_methods_available(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """No verification methods: passes with warning about no checksums."""
        # Asset without digest and no checksum files
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
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

        # Should pass (cannot verify, but don't block)
        assert result.passed is True

        # Warning about no checksums provided
        assert result.warning is not None
        warning_lower = result.warning.lower()
        assert "not provide" in warning_lower or "checksum" in warning_lower

    @pytest.mark.asyncio
    async def test_verification_skipped_when_no_methods(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Verification skipped when no methods available: passes with empty.

        Note: skip=True is ignored when strong verification methods are
        available. This test verifies the skip behavior when NO methods exist.
        """
        # Asset without digest and no checksum files
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",  # No digest
        )
        assets = [asset]  # No checksum file
        config = {"skip": True}

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

        # Should pass (verification skipped)
        assert result.passed is True

        # No methods recorded when skipped (no methods available)
        assert result.methods == {}


class TestMethodResultRecording:
    """Tests for correct method result recording."""

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
    async def test_method_result_contains_hash_details(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Method results contain hash and details information."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]
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

        # Verify method result structure
        assert "digest" in result.methods
        digest_result = result.methods["digest"]

        # Required fields
        assert "passed" in digest_result
        assert "hash" in digest_result
        assert "details" in digest_result

        # Verify hash is recorded
        assert digest_result["hash"] != ""

    @pytest.mark.asyncio
    async def test_updated_config_includes_verification_info(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Updated config includes digest verification flag when successful."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest=f"sha256:{TEST_HASH}",
        )
        assets = [asset]
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

        # Updated config should have digest flag set
        assert result.updated_config.get("digest") is True

    @pytest.mark.asyncio
    async def test_updated_config_includes_checksum_file(
        self, verification_service: VerificationService, test_file_path: Path
    ) -> None:
        """Updated config includes checksum_file when successful."""
        asset = Asset(
            name="test.AppImage",
            browser_download_url=f"{GITHUB_BASE}/test.AppImage",
            size=len(TEST_CONTENT),
            digest="",
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
        verification_service.download_service.download_checksum_file = (
            AsyncMock(return_value=checksum_content)
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

        # Updated config should have checksum_file set
        assert result.updated_config.get("checksum_file") == "SHA256SUMS.txt"
